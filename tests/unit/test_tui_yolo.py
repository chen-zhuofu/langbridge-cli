from langbridge_code.ui.tui import LangBridgeTui


def _bare_tui():
    tui = LangBridgeTui.__new__(LangBridgeTui)
    tui.always_approve = False
    tui.pending_approval = None
    tui.workflow_step = ""
    tui.streaming_phase = "idle"
    tui.state = "ready"
    tui.messages = []
    tui.model = "test-model"
    tui.cwd_display = "~"
    tui.git_branch = ""
    lines = []
    tui.write_system = lambda text, **kwargs: lines.append(text)
    tui.update_status = lambda: None
    tui.resolve_approval = lambda approved: lines.append(f"resolved:{approved}")
    return tui, lines


def test_toggle_yolo_enables_auto_approve():
    tui, lines = _bare_tui()

    tui.action_toggle_yolo()

    assert tui.always_approve is True
    assert any("Yolo mode on" in line for line in lines)


def test_toggle_yolo_approves_pending_request():
    tui, lines = _bare_tui()
    tui.pending_approval = ({"approved": False}, None)

    tui.set_yolo_mode(True)

    assert tui.always_approve is True
    assert "resolved:True" in lines


def test_toggle_yolo_off_disables_auto_approve():
    tui, lines = _bare_tui()
    tui.always_approve = True

    tui.action_toggle_yolo()

    assert tui.always_approve is False
    assert any("Yolo mode off" in line for line in lines)
