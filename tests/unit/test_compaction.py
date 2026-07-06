import json

import pytest

from langbridge_cli.persistence import context as context_module


def _tool_round(messages, name, arguments, output, *, call_id="c1"):
    messages.extend(
        [
            {
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": json.dumps(arguments),
            },
            {"type": "function_call_output", "call_id": call_id, "output": output},
        ]
    )


def test_recent_file_store_keeps_last_n():
    store = context_module.RecentFileStore(max_files=2)
    store.record_read("a.py", "aaa")
    store.record_read("b.py", "bbb")
    store.record_read("c.py", "ccc")
    assert list(store._files.keys()) == ["b.py", "c.py"]


def test_clear_old_tool_outputs_keeps_recent_rounds():
    messages = [{"role": "system", "content": "sys"}]
    _tool_round(messages, "read_file", {"path": "old.py"}, "OLD CONTENT", call_id="c1")
    _tool_round(messages, "read_file", {"path": "mid.py"}, "MID CONTENT", call_id="c2")
    _tool_round(messages, "read_file", {"path": "new.py"}, "NEW CONTENT", call_id="c3")

    cleared = context_module.clear_old_tool_outputs(messages, keep_recent_steps=1)
    assert cleared == 2
    assert context_module.is_cleared_output(messages[2]["output"])
    assert context_module.is_cleared_output(messages[4]["output"])
    assert messages[6]["output"] == "NEW CONTENT"


def test_sync_compaction_context_injects_recent_files():
    messages = [{"role": "system", "content": "sys"}]
    store = context_module.RecentFileStore(max_files=5)
    store.record_read("src/foo.py", "def foo(): pass")

    context_module.sync_compaction_context(messages, store)

    assert len(messages) == 2
    assert messages[1]["content"].startswith(context_module.COMPACTION_CONTEXT_PREFIX)
    assert "src/foo.py" in messages[1]["content"]
    assert "def foo(): pass" in messages[1]["content"]


def test_maybe_compact_messages_triggers_over_threshold(monkeypatch):
    monkeypatch.setattr(context_module, "COMPACT_LOOP_FRACTION", 0.01)
    messages = [{"role": "system", "content": "x" * 5000}]
    _tool_round(messages, "read_file", {"path": "a.py"}, "A" * 8000, call_id="c1")
    _tool_round(messages, "read_file", {"path": "b.py"}, "B" * 8000, call_id="c2")

    store = context_module.RecentFileStore()
    store.record_read("a.py", "A" * 8000)
    store.record_read("b.py", "B" * 8000)

    result = context_module.maybe_compact_messages(
        messages,
        max_context_tokens=10000,
        file_store=store,
        keep_recent_steps=1,
    )

    assert result["compacted"] is True
    assert result["cleared"] == 1
    assert any(
        m.get("role") == "assistant" and context_module.COMPACTION_CONTEXT_PREFIX in m.get("content", "")
        for m in messages
    )


def test_cleared_tool_summary_read_file():
    summary = context_module.cleared_tool_summary("read_file", {"path": "x.py"}, "line1\nline2\n")
    assert summary.startswith(context_module.CLEARED_PREFIX)
    assert "x.py" in summary


def test_summarize_history_with_llm(monkeypatch):
    import sys
    import types

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Add widget API"},
        {"role": "assistant", "content": "I'll implement the widget handler."},
    ]

    def fake_response(api_key, model, agent_input, **kwargs):
        assert kwargs.get("label") == "test compaction"
        return {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "- Task: widget API\n- Decision: use handler pattern"}],
                }
            ]
        }

    fake_client = types.ModuleType("langbridge_cli.llm.client")
    fake_client.create_model_response = fake_response
    monkeypatch.setitem(sys.modules, "langbridge_cli.llm.client", fake_client)

    summary = context_module.summarize_history_with_llm("key", "model", messages, label="test compaction")
    assert "widget API" in summary
    assert "handler" in summary


def test_sync_history_summary_skips_without_llm():
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]
    context_module.sync_history_summary(messages)
    assert len(messages) == 2


def test_sync_history_summary_uses_llm_when_configured(monkeypatch):
    monkeypatch.setattr(context_module, "COMPACT_USE_LLM", True)
    monkeypatch.setattr(
        context_module,
        "summarize_history_with_llm",
        lambda api_key, model, messages, label="compaction": "LLM summary bullets",
    )
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]
    context_module.sync_history_summary(messages, api_key="k", model="m")
    assert messages[2]["content"] == context_module.HISTORY_SUMMARY_PREFIX + "LLM summary bullets"
