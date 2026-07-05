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
