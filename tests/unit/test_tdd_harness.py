from pathlib import Path

import pytest

from langbridge_cli.agents import tdd_harness


def test_is_test_path():
    assert tdd_harness.is_test_path("tests/test_foo.py")
    assert tdd_harness.is_test_path("src/foo_test.py")
    assert tdd_harness.is_test_path("test_integration.py")
    assert not tdd_harness.is_test_path("src/foo.py")


def test_lock_and_verify_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(tdd_harness, "WORKSPACE_ROOT", tmp_path)
    test_file = tmp_path / "tests" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x():\n    assert False\n", encoding="utf-8")

    locked = tdd_harness.lock_hashes(["tests/test_x.py"])
    ok, _ = tdd_harness.verify_locked_unchanged(locked)
    assert ok

    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    ok, msg = tdd_harness.verify_locked_unchanged(locked)
    assert not ok
    assert "hash mismatch" in msg


def test_test_phase_guard_blocks_production_edit():
    err = tdd_harness.test_phase_guard("edit_file", {"path": "src/main.py"})
    assert err is not None
    assert tdd_harness.test_phase_guard("edit_file", {"path": "tests/test_a.py"}) is None


def test_implement_phase_guard_blocks_test_edit():
    locked = {"tests/test_a.py": "abc123"}
    err = tdd_harness.implement_phase_guard(locked, "edit_file", {"path": "tests/test_a.py"})
    assert err is not None
    assert "locked" in err
    assert tdd_harness.implement_phase_guard(locked, "edit_file", {"path": "src/main.py"}) is None


def test_verify_green_gate(monkeypatch):
    monkeypatch.setattr(
        "langbridge_cli.tools.testing.run_tests",
        lambda path=".": '{"exit_code": 0, "output": "ok"}',
    )
    acceptance = {"paths": ["tests/test_a.py"], "locked_hashes": {"tests/test_a.py": "abc"}}
    ok, msg = tdd_harness.verify_green_gate(acceptance)
    assert ok
    assert "pass" in msg

    monkeypatch.setattr(
        "langbridge_cli.tools.testing.run_tests",
        lambda path=".": '{"exit_code": 1, "output": "FAILED"}',
    )
    ok, msg = tdd_harness.verify_green_gate(acceptance)
    assert not ok
    assert "test.json" in msg


def test_write_and_read_test_json(tmp_path, monkeypatch):
    monkeypatch.setattr(tdd_harness, "WORKSPACE_ROOT", tmp_path)
    locked = {"tests/test_x.py": "deadbeef" * 8}
    spec = tdd_harness.write_test_json("Add widget API", locked)

    assert spec["status"] == "frozen"
    assert spec["paths"] == ["tests/test_x.py"]
    assert spec["locked_hashes"] == locked
    assert spec["test_json_path"].endswith("/test.json")

    path = tmp_path / spec["test_json_path"]
    assert path.is_file()

    loaded = tdd_harness.read_test_json("Add widget API")
    assert loaded == spec


def test_acceptance_context_block():
    acceptance = {
        "test_json_path": "agent-state/acceptance/add-widget/test.json",
        "runner": "pytest",
        "paths": ["tests/test_widget.py"],
        "locked_hashes": {"tests/test_widget.py": "a" * 64},
    }
    block = tdd_harness.acceptance_context_block(acceptance)
    assert "test.json" in block
    assert "tests/test_widget.py" in block
    assert tdd_harness.acceptance_context_block({}) == ""


def test_verify_acceptance_combines_lock_and_green(tmp_path, monkeypatch):
    monkeypatch.setattr(tdd_harness, "WORKSPACE_ROOT", tmp_path)
    test_file = tmp_path / "tests" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")

    locked = tdd_harness.lock_hashes(["tests/test_x.py"])
    acceptance = tdd_harness.build_acceptance_spec("task", locked)

    monkeypatch.setattr(
        "langbridge_cli.tools.testing.run_tests",
        lambda path=".": '{"exit_code": 0, "output": "ok"}',
    )
    ok, _ = tdd_harness.verify_acceptance(acceptance)
    assert ok

    test_file.write_text("def test_x():\n    assert False\n", encoding="utf-8")
    ok, msg = tdd_harness.verify_acceptance(acceptance)
    assert not ok
    assert "hash mismatch" in msg


def test_verify_red_gate_requires_failure(monkeypatch):
    monkeypatch.setattr(
        "langbridge_cli.tools.testing.run_tests",
        lambda path=".": '{"exit_code": 0, "output": "ok"}',
    )
    ok, msg = tdd_harness.verify_red_gate(["tests/test_a.py"])
    assert not ok
    assert "already pass" in msg

    monkeypatch.setattr(
        "langbridge_cli.tools.testing.run_tests",
        lambda path=".": '{"exit_code": 1, "output": "FAILED"}',
    )
    ok, msg = tdd_harness.verify_red_gate(["tests/test_a.py"])
    assert ok
