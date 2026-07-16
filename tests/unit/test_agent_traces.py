import json
from types import SimpleNamespace

from langbridge_code.context.agent_context import AgentContextManager, finish_step
from langbridge_code.tools.agent_worker_reviewer import new_reviewer_session
from langbridge_code.util.agent_traces import (
    append_agent_raw_round,
    append_compaction_event,
    build_agent_resume_background,
    reserve_agent_trace,
)


def _jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_trace_instance_ids_start_at_zero_and_increment_per_role_task(tmp_path):
    first, first_id = reserve_agent_trace(tmp_path, "Worker", "task-3-api")
    second, second_id = reserve_agent_trace(tmp_path, "Worker", "task-3-api")
    other, other_id = reserve_agent_trace(tmp_path, "Worker", "task-4-ui")

    assert first_id == 0
    assert second_id == 1
    assert other_id == 0
    assert first.name == "worker-task-3-api-0.jsonl"
    assert second.name == "worker-task-3-api-1.jsonl"
    assert other.name == "worker-task-4-ui-0.jsonl"


def test_agent_trace_keeps_full_raw_round(tmp_path):
    path, instance_id = reserve_agent_trace(tmp_path, "Explore", "find-auth-flow")
    messages = [
        {"role": "user", "content": "inspect auth"},
        {"type": "function_call", "name": "read_file", "arguments": '{"path":"auth.py"}'},
        {"type": "function_call_output", "call_id": "c1", "output": "x" * 10_000},
    ]
    append_agent_raw_round(
        path,
        role="Explore",
        task_name="find-auth-flow",
        instance_id=instance_id,
        round_index=0,
        messages=messages,
    )

    records = _jsonl(path)
    assert records[0]["type"] == "agent_trace_start"
    assert records[1]["type"] == "round"
    assert records[1]["messages"] == messages
    assert len(records[1]["messages"][2]["output"]) == 10_000


def test_resume_background_reads_prior_dispatch_but_not_current_trace(tmp_path):
    prior, prior_id = reserve_agent_trace(tmp_path, "Worker", "task-3-api")
    append_agent_raw_round(
        prior,
        role="Worker",
        task_name="task-3-api",
        instance_id=prior_id,
        round_index=0,
        messages=[
            {"role": "user", "content": "implement applications API"},
            {"role": "assistant", "content": "PUT still needs review"},
        ],
    )
    current, _ = reserve_agent_trace(tmp_path, "Worker", "task-3-api")

    background = build_agent_resume_background(
        tmp_path,
        role="Worker",
        task_name="task-3-api",
        model="kimi-k2.7-code",
        progress="older progress",
        exclude_trace=current,
    )

    assert "implement applications API" in background
    assert "PUT still needs review" in background


def test_reviewer_session_keeps_task_name_for_trace_resume(tmp_path):
    session = new_reviewer_session(
        "key",
        "kimi-k2.7-code",
        run_log_path=tmp_path,
        task_name="task-3-api",
    )

    assert session.context.task_name == "task-3-api"
    assert session.context.agent_trace_path.name == "reviewer-task-3-api-0.jsonl"


def test_full_compaction_event_moves_to_attachment(tmp_path):
    path = append_compaction_event(
        tmp_path,
        {
            "type": "active_context_compaction",
            "role": "Worker",
            "task_name": "task-3-api",
            "instance_id": 0,
            "before": {"tokens": 10_000, "raw_round_count": 20},
            "input": {"rounds": [[{"role": "user", "content": "x" * 8_000}]]},
            "output": {"compact_prose": "full compact result"},
            "after": {"tokens": 2_000, "raw_round_count": 11},
        },
    )

    record = _jsonl(path)[0]
    assert record["before"]["tokens"] == 10_000
    assert record["after"]["tokens"] == 2_000
    attachment = path.parent / record["full_event_attachment"]
    full = json.loads(attachment.read_text(encoding="utf-8"))
    assert len(full["input"]["rounds"][0][0]["content"]) == 8_000
    assert full["output"]["compact_prose"] == "full compact result"


def test_context_manager_logs_compaction_input_and_output(tmp_path):
    manager = AgentContextManager(
        system_content="system",
        run_log_path=tmp_path,
        label="Worker",
        task_name="task-3-api",
    )
    messages = []
    manager.attach(messages)
    manager.stack.raw_keep = 1
    manager.stack.compact_fraction = 0.000001
    manager.stack._prose_compactor = lambda *args, **kwargs: "COMPRESSED RESULT"

    manager.begin_turn("first prompt")
    manager.after_tool_step(
        [{"role": "assistant", "content": "first result"}],
        api_key="key",
        model="kimi-k2.7-code",
        budget_tokens=None,
    )
    manager.begin_turn("second prompt")
    manager.after_tool_step(
        [{"role": "assistant", "content": "second result"}],
        api_key="key",
        model="kimi-k2.7-code",
        budget_tokens=None,
    )

    index = tmp_path / "traces" / "compactions.jsonl"
    record = _jsonl(index)[0]
    if "full_event_attachment" in record:
        event = json.loads(
            (index.parent / record["full_event_attachment"]).read_text(encoding="utf-8")
        )
    else:
        event = record
    assert event["role"] == "Worker"
    assert event["task_name"] == "task-3-api"
    assert event["input"]["rounds"][0][0]["content"] == "first prompt"
    assert event["output"]["compact_prose"] == "COMPRESSED RESULT"
    assert event["before"]["raw_round_count"] == 2
    assert event["after"]["raw_round_count"] == 1


def test_finish_step_persists_subagent_round(tmp_path):
    manager = AgentContextManager(
        system_content="system",
        run_log_path=tmp_path,
        label="Planner",
        task_name="plan-interview-tool",
    )
    messages = []
    manager.attach(messages)
    manager.begin_turn("make a plan")
    session = SimpleNamespace(
        api_key=None,
        model="kimi-k2.7-code",
        run_log_path=tmp_path,
        label="Planner",
        turn_id=1,
    )
    finish_step(
        manager,
        [{"role": "assistant", "content": "the complete plan"}],
        session,
        budget=100_000,
    )

    trace = tmp_path / "traces" / "planner-plan-interview-tool-0.jsonl"
    records = _jsonl(trace)
    assert records[1]["round"] == 0
    assert records[1]["messages"] == [
        {"role": "user", "content": "make a plan"},
        {"role": "assistant", "content": "the complete plan"},
    ]
