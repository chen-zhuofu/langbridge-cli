from langbridge_code.context.message import recent_chat_turns


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
