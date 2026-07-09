from langbridge_code.ui.tui import (
    INPUT_LINES_MAX,
    INPUT_LINES_MIN,
    clamp_input_lines,
    is_chat_log_descendant,
)


def test_clamp_input_lines_respects_bounds():
    assert clamp_input_lines(INPUT_LINES_MIN - 1) == INPUT_LINES_MIN
    assert clamp_input_lines(INPUT_LINES_MAX + 5) == INPUT_LINES_MAX
    assert clamp_input_lines(6) == 6


class _Widget:
    def __init__(self, widget_id=None, parent=None):
        self.id = widget_id
        self.parent = parent


def test_is_chat_log_descendant():
    chat = _Widget("chat_log")
    child = _Widget(parent=chat)
    assert is_chat_log_descendant(child) is True
    assert is_chat_log_descendant(_Widget("input")) is False
    assert is_chat_log_descendant(None) is False
