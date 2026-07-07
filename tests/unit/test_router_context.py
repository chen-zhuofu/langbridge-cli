from langbridge_code.persistence.context import recent_chat_turns
from langbridge_code.workflow.router import route


def test_recent_chat_turns_skips_tools_and_empty_assistant():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "build a game"},
        {"role": "assistant", "content": "On it."},
        {"type": "function_call", "name": "read_file"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "continue"},
    ]
    turns = recent_chat_turns(messages)
    assert turns == [
        {"role": "user", "content": "build a game"},
        {"role": "assistant", "content": "On it."},
        {"role": "user", "content": "continue"},
    ]


def test_route_includes_conversation_history(monkeypatch):
    seen = {}

    def fake_create_model_response(_key, _model, messages, **kwargs):
        seen["messages"] = messages
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"kind":"task","hard":false,"task_type":"coding","task_summary":"Build a web game","reply":""}',
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(
        "langbridge_code.workflow.router.create_model_response",
        fake_create_model_response,
    )

    history = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "帮我开发一个网页游戏吧"},
        {"role": "assistant", "content": "好的，开始。"},
    ]
    decision = route("key", "model", "继续吧", messages=history)

    assert decision["kind"] == "task"
    assert decision["task_summary"] == "Build a web game"
    roles = [message["role"] for message in seen["messages"]]
    contents = [message.get("content", "") for message in seen["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert "帮我开发一个网页游戏吧" in contents
    assert seen["messages"][-1]["content"] == "继续吧"
