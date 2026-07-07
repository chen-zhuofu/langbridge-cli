"""Workflow tests for session context and todo resume."""

from langbridge_code.workflow import todo as todo_mod
from langbridge_code.workflow.run import run_workflow


def _write_todo(run_log_path, lines):
    content = "# Todo\n\n" + "\n".join(lines) + "\n"
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    (run_log_path.parent / f"{run_log_path.stem}.todo_list.md").write_text(content, encoding="utf-8")


def test_workflow_chat_reply_uses_history(tmp_path, monkeypatch):
    run_log = tmp_path / "run.json"
    seen = {}

    monkeypatch.setattr(
        "langbridge_code.workflow.run.route",
        lambda *args, **kwargs: {
            "kind": "chat",
            "reply": "",
            "hard": False,
            "task_type": "coding",
            "task_summary": "",
        },
    )

    def fake_chat_reply(_key, _model, messages, user_message, **kwargs):
        seen["messages"] = messages
        seen["user_message"] = user_message
        return "Continuing our chat."

    monkeypatch.setattr("langbridge_code.workflow.run._chat_reply", fake_chat_reply)

    history = [
        {"role": "system", "content": "You are LangBridge Code."},
        {"role": "user", "content": "你现在是新版了"},
        {"role": "assistant", "content": "是的，已更新。"},
    ]
    reply = run_workflow(
        "key",
        "model",
        "继续吧",
        run_log,
        1,
        print_reply=False,
        messages=history,
    )

    assert reply == "Continuing our chat."
    assert seen["user_message"] == "继续吧"
    assert any(message.get("content") == "你现在是新版了" for message in seen["messages"])


def test_workflow_skips_new_todo_when_open_items_exist(tmp_path, monkeypatch):
    run_log = tmp_path / "run.json"
    _write_todo(run_log, ["- [ ] Build a web game"])

    route_calls = []
    planner_calls = []

    monkeypatch.setattr(
        "langbridge_code.workflow.run.route",
        lambda *args, **kwargs: route_calls.append(kwargs) or {
            "kind": "task",
            "reply": "",
            "hard": True,
            "task_type": "coding",
            "task_summary": "Build a web game",
        },
    )
    monkeypatch.setattr(
        "langbridge_code.workflow.run.run_planner",
        lambda *args, **kwargs: planner_calls.append(True),
    )
    monkeypatch.setattr(
        "langbridge_code.workflow.run.run_coder_reviewer_loop",
        lambda *args, **kwargs: (True, "REVIEW_VERDICT: PASS"),
    )

    reply = run_workflow(
        "key",
        "model",
        "继续吧",
        run_log,
        1,
        print_reply=False,
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "帮我开发一个网页游戏吧"},
        ],
    )

    assert route_calls
    assert route_calls[0]["messages"] is not None
    assert planner_calls == []
    assert todo_mod.unfinished_count(todo_mod.load_tasks(run_log)) == 0
    assert "Workflow complete" in reply
