from langbridge_code.ui.tui import LangBridgeTui


def test_replay_session_records_shows_interrupted_turn():
    tui = LangBridgeTui.__new__(LangBridgeTui)
    lines = []

    tui.write_user = lambda text: lines.append(("user", text))
    tui.write_assistant = lambda text: lines.append(("assistant", text))
    tui.write_system = lambda text, **kwargs: lines.append(("system", text))

    records = [
        {
            "turn_id": 1,
            "user": "你现在是新版了",
            "assistant": "是的，已更新。",
            "steps": [],
        },
        {
            "turn_id": 2,
            "user": "帮我开发一个网页游戏吧",
            "assistant": "",
            "steps": [],
        },
    ]
    tui._replay_session_records(records)

    assert lines == [
        ("user", "你现在是新版了"),
        ("assistant", "是的，已更新。"),
        ("user", "帮我开发一个网页游戏吧"),
        ("system", "\u25a0 No reply yet (turn interrupted before the agent finished)"),
    ]
