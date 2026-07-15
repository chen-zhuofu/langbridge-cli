"""Stop-aware subprocess runner: user stop kills the child immediately."""
import os
import time

import pytest

from langbridge_code.agents.common import control
from langbridge_code.tools.common.proc import run_command


def test_run_command_returns_output_and_exit_code(tmp_path):
    output, exit_code, timed_out = run_command(
        ["bash", "-c", "echo hi; exit 3"], cwd=tmp_path, env=os.environ.copy(), timeout=10
    )
    assert output.strip() == "hi"
    assert exit_code == 3
    assert timed_out is False


def test_run_command_times_out(tmp_path):
    start = time.monotonic()
    output, exit_code, timed_out = run_command(
        ["bash", "-c", "sleep 30"], cwd=tmp_path, env=os.environ.copy(), timeout=1
    )
    assert timed_out is True
    assert exit_code is None
    assert time.monotonic() - start < 5


def test_run_command_aborts_on_stop(tmp_path):
    control.clear_stop()
    try:
        start = time.monotonic()
        control.request_stop()
        with pytest.raises(control.StopRequested):
            run_command(
                ["bash", "-c", "sleep 30"], cwd=tmp_path, env=os.environ.copy(), timeout=60
            )
        assert time.monotonic() - start < 5
    finally:
        control.clear_stop()
