import threading

from langbridge_code.ui.tui import LangBridgeTui


class _Box:
    def __init__(self):
        self.disabled = False

    def focus(self):
        pass


OPTIONS = ["CLI tool", "Web app", "Python library"]


def _bare_tui():
    tui = LangBridgeTui.__new__(LangBridgeTui)
    tui.pending_question = None
    tui.state = "working"
    lines = []
    box = _Box()
    tui.write_user = lambda text: lines.append(("user", text))
    tui.write_system = lambda text, **kwargs: lines.append(("sys", text))
    tui.update_status = lambda: None
    tui._sync_streaming_phase = lambda: None
    tui.query_one = lambda *args, **kwargs: box
    return tui, lines, box


def test_show_question_lists_three_assumptions_and_other():
    tui, lines, box = _bare_tui()
    answer = {"text": ""}
    ready = threading.Event()
    shown = threading.Event()

    tui.show_question("Which tool?", OPTIONS, answer, ready, shown)

    joined = "\n".join(text for kind, text in lines if kind == "sys")
    assert "1. CLI tool" in joined
    assert "2. Web app" in joined
    assert "3. Python library" in joined
    assert "4. Other" in joined
    assert tui.pending_question[2] == OPTIONS


def test_answer_question_maps_number_to_assumption():
    tui, lines, box = _bare_tui()
    answer = {"text": ""}
    ready = threading.Event()
    tui.pending_question = (answer, ready, OPTIONS)

    tui.answer_question("2")

    assert answer["text"] == "Web app"
    assert ready.is_set()
    assert ("user", "2") in lines


def test_answer_question_keeps_custom_other_text():
    tui, lines, box = _bare_tui()
    answer = {"text": ""}
    ready = threading.Event()
    tui.pending_question = (answer, ready, OPTIONS)

    tui.answer_question("browser extension")

    assert answer["text"] == "browser extension"
    assert ("user", "browser extension") in lines
