from pathlib import Path

import pytest

from langbridge_code.context.common.stack import (
    ASSIGNED_TASK_PREFIX,
    COMPACT_PROSE_PREFIX,
    STRUCTURE_NOTE_PREFIX,
    ContextStack,
)


def _tool_step(call_id: str, name: str, output: str) -> list[dict]:
    return [
        {
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": "{}",
        },
        {"type": "function_call_output", "call_id": call_id, "output": output},
    ]


def _fake_note_builder(api_key, model, rounds, *, label=""):
    round_nums = "+".join(str(index + 1) for index in range(len(rounds)))
    return (
        f"## Meta\n- agent: worker\n- rounds: {round_nums}\n\n"
        f"## Tool summaries\n- grep (step {len(rounds)}, ok): structure note for rounds {round_nums}"
    )


def _fake_prose_compactor(api_key, model, *, compact_prose, structure_notes, label=""):
    parts = []
    if compact_prose:
        parts.append(compact_prose)
    parts.extend(structure_notes)
    return "compact prose: " + " | ".join(parts)


@pytest.fixture
def stack(tmp_path):
    return ContextStack(
        system_content="system prompt",
        persist_dir=tmp_path / "notes",
        min_raw_keep=2,
        structure_batch=4,
        compact_fraction=0.4,
        note_builder=_fake_note_builder,
        prose_compactor=_fake_prose_compactor,
    )


def test_raw_rounds_accumulate_before_structure(stack):
    stack.start_turn("task")
    for index in range(5):
        stack.complete_step(_tool_step(f"c{index}", "grep", f"out-{index}"))
    assert len(stack.raw_rounds) == 5
    assert not stack.structure_notes


def test_structure_note_after_six_rounds(stack):
    stack.start_turn("task")
    for index in range(6):
        stack.complete_step(_tool_step(f"c{index}", "grep", f"out-{index}"))

    stats = stack.maybe_advance(api_key="k", model="test-model", budget_tokens=999_999)

    assert stats["structure_notes_added"] == 1
    assert len(stack.structure_notes) == 1
    assert stack.structure_notes[0].round_start == 1
    assert stack.structure_notes[0].round_end == 4
    assert len(stack.raw_rounds) == 2
    messages = stack.to_messages()
    assert any(STRUCTURE_NOTE_PREFIX in m.get("content", "") for m in messages if m.get("role") == "user")
    assert sum(1 for m in messages if m.get("type") == "function_call_output") == 2


def test_structure_note_persisted_to_debug(stack, tmp_path, monkeypatch):
    monkeypatch.setattr("langbridge_code.context.debug.CONTEXT_DEBUG_PERSIST", True)
    session_dir = tmp_path / "session-test-2026-07-09T120000"
    session_dir.mkdir()
    (session_dir / "traces").mkdir()
    (session_dir / "debug" / "2026-07-09T120000.00").mkdir(parents=True)
    run_log = session_dir / "session.json"
    run_log.write_text("{}\n")
    from langbridge_code.util.agent_debug import set_agent_debug
    from langbridge_code.util.trace_log import begin_trace

    begin_trace(run_log, "2026-07-09T120000.00")
    set_agent_debug("Worker", 1)
    stack.start_turn("task")
    for index in range(6):
        stack.complete_step(_tool_step(f"c{index}", "grep", f"out-{index}"))
    stack.maybe_advance(api_key="k", model="test-model", budget_tokens=999_999)

    debug_dir = session_dir / "debug" / "2026-07-09T120000.00"
    files = list(debug_dir.glob("worker_1_structure_*_output.md"))
    assert len(files) == 1
    assert "structure note for rounds 1+2+3+4" in files[0].read_text(encoding="utf-8")


def test_second_structure_note_appends(stack):
    stack.start_turn("task")
    for index in range(10):
        stack.complete_step(_tool_step(f"c{index}", "grep", f"out-{index}"))
    stack.maybe_advance(api_key="k", model="test-model", budget_tokens=999_999)

    assert len(stack.structure_notes) == 2
    assert stack.structure_notes[0].round_end == 4
    assert stack.structure_notes[1].round_start == 5
    assert stack.structure_notes[1].round_end == 8
    assert len(stack.raw_rounds) == 2


def test_prose_compact_when_over_threshold(stack, monkeypatch):
    monkeypatch.setattr(
        "langbridge_code.context.common.stack.model_context_window",
        lambda _model: 100,
    )
    stack.compact_fraction = 0.4
    stack.start_turn("task")
    for index in range(6):
        stack.complete_step(_tool_step(f"c{index}", "grep", "x" * 200))
    stack.maybe_advance(api_key="k", model="test-model", budget_tokens=40)

    assert stack.compact_prose is not None
    assert COMPACT_PROSE_PREFIX in stack.to_messages()[1]["content"]
    assert not stack.structure_notes
    assert len(stack.raw_rounds) == 2


def test_user_message_attached_to_first_step_only(stack):
    stack.start_turn("hello")
    stack.complete_step(_tool_step("c0", "grep", "one"))
    stack.complete_step(_tool_step("c1", "grep", "two"))

    messages = stack.to_messages()
    user_contents = [m["content"] for m in messages if m.get("role") == "user"]
    assert user_contents.count("hello") == 1


def test_bootstrap_from_flat_messages(stack):
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "task"},
        *_tool_step("c0", "grep", "one"),
        *_tool_step("c1", "grep", "two"),
    ]
    stack.bootstrap_from_messages(messages)
    assert len(stack.raw_rounds) == 2
    rebuilt = stack.to_messages()
    assert rebuilt[0]["role"] == "system"
    assert any(m.get("call_id") == "c1" for m in rebuilt if m.get("type") == "function_call")


def test_bootstrap_preserves_trailing_user_message(stack):
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "Session progress\n\nCurrent request:\ncontinue"},
    ]
    stack.bootstrap_from_messages(messages)
    rebuilt = stack.to_messages()
    assert any(
        "Session progress" in m.get("content", "")
        for m in rebuilt
        if m.get("role") == "user"
    )


def test_agent_context_manager_mutates_in_place():
    from langbridge_code.context.agent_context import AgentContextManager

    messages = [{"role": "system", "content": "sys"}]
    holder = messages
    context = AgentContextManager(system_content="sys", run_log_path=None, label="Worker")
    context.attach(messages)
    context.begin_turn("hello")
    assert holder is messages
    assert any(m.get("content") == "hello" for m in messages if m.get("role") == "user")


def test_maybe_advance_noop_without_api_key(stack):
    stack.start_turn("task")
    for index in range(6):
        stack.complete_step(_tool_step(f"c{index}", "grep", f"out-{index}"))
    stats = stack.maybe_advance(api_key=None, model=None)
    assert stats["structure_notes_added"] == 0
    assert len(stack.raw_rounds) == 6


def test_pinned_assigned_task_in_every_to_messages(stack):
    stack.set_pinned_assigned_task("Fix login bug")
    stack.start_turn("implement fix")
    stack.complete_step(_tool_step("c0", "grep", "one"))

    messages = stack.to_messages()
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == f"{ASSIGNED_TASK_PREFIX}Fix login bug"
    assert not any(
        ASSIGNED_TASK_PREFIX in str(m.get("content", ""))
        for round_msgs in stack.raw_rounds
        for m in round_msgs
    )


def test_pinned_survives_structure_note_advance(stack):
    stack.set_pinned_assigned_task("Add retry logic")
    stack.start_turn("step prompt")
    for index in range(6):
        stack.complete_step(_tool_step(f"c{index}", "grep", f"out-{index}"))
    stack.maybe_advance(api_key="k", model="test-model", budget_tokens=999_999)

    messages = stack.to_messages()
    pinned = [m for m in messages if m.get("content", "").startswith(ASSIGNED_TASK_PREFIX)]
    assert len(pinned) == 1
    assert "Add retry logic" in pinned[0]["content"]
    assert len(stack.structure_notes) == 1


def test_bootstrap_restores_pinned_assigned_task(stack):
    pinned = f"{ASSIGNED_TASK_PREFIX}Ship feature X"
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": pinned},
        {"role": "user", "content": "turn prompt"},
        *_tool_step("c0", "grep", "one"),
    ]
    stack.bootstrap_from_messages(messages)
    assert stack.pinned_user_content == pinned
    rebuilt = stack.to_messages()
    assert rebuilt[1]["content"] == pinned


def test_load_persisted_structure_notes_is_memory_only(tmp_path):
    notes_dir = tmp_path / "langbridge" / "structure-notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "structure_0001_r1-4.md").write_text("persisted note\n", encoding="utf-8")

    stack = ContextStack(
        system_content="system prompt",
        persist_dir=notes_dir,
        min_raw_keep=2,
        structure_batch=4,
    )
    stack.bootstrap_from_messages(
        [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "task"},
            *_tool_step("c0", "grep", "one"),
            *_tool_step("c1", "grep", "two"),
            *_tool_step("c2", "grep", "three"),
            *_tool_step("c3", "grep", "four"),
            *_tool_step("c4", "grep", "five"),
            *_tool_step("c5", "grep", "six"),
        ]
    )
    assert stack.load_persisted_layers() is False
    assert not stack.structure_notes


def test_agent_context_manager_does_not_load_disk_notes(tmp_path):
    from langbridge_code.context.agent_context import AgentContextManager

    run_log = tmp_path / "session.json"
    run_log.parent.mkdir(parents=True, exist_ok=True)
    run_log.write_text("{}\n")
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        *_tool_step("c0", "grep", "one"),
    ]
    context = AgentContextManager(
        system_content="sys",
        run_log_path=run_log,
        label="LangBridge",
    )
    context.attach(messages, bootstrap=True)
    assert not any("from disk" in m.get("content", "") for m in messages if m.get("role") == "user")

