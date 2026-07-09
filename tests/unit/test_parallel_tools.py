import threading
import time

import pytest

from langbridge_code.agents.common.parallel_tools import (
    PARALLEL_TOOL_NAMES,
    can_run_tool_calls_in_parallel,
    run_tool_calls,
)


@pytest.fixture(autouse=True)
def parallel_agents_enabled(monkeypatch):
    monkeypatch.setattr("langbridge_code.settings.PARALLEL_AGENTS_ENABLED", True)
    monkeypatch.setattr(
        "langbridge_code.agents.common.parallel_tools.PARALLEL_AGENTS_ENABLED",
        True,
    )


def test_parallel_tool_names_include_subagents():
    assert "agent_explorer" in PARALLEL_TOOL_NAMES
    assert "agent_worker" in PARALLEL_TOOL_NAMES
    assert "agent_planner" not in PARALLEL_TOOL_NAMES
    assert "bash" not in PARALLEL_TOOL_NAMES


def test_can_parallelize_explorers_and_workers():
    explore = {"name": "agent_explorer", "call_id": "1"}
    read = {"name": "read_file", "call_id": "2"}
    worker_a = {"name": "agent_worker", "call_id": "3"}
    worker_b = {"name": "agent_worker", "call_id": "4"}
    planner = {"name": "agent_planner", "call_id": "5"}
    assert can_run_tool_calls_in_parallel([explore, read])
    assert can_run_tool_calls_in_parallel([worker_a, worker_b])
    assert not can_run_tool_calls_in_parallel([explore, planner])
    assert not can_run_tool_calls_in_parallel([worker_a, planner])


def test_run_tool_calls_preserves_order():
    started = []
    lock = threading.Lock()

    def run_fn(call):
        delay = 0.03 if call["call_id"] == "slow" else 0.01
        time.sleep(delay)
        with lock:
            started.append(call["call_id"])
        return {"call_id": call["call_id"], "output": call["call_id"]}

    calls = [
        {"name": "agent_explorer", "call_id": "slow"},
        {"name": "agent_explorer", "call_id": "fast"},
    ]
    outputs = run_tool_calls(run_fn, calls, max_workers=2)
    assert [item["output"] for item in outputs] == ["slow", "fast"]
    assert set(started) == {"slow", "fast"}


def test_run_tool_calls_parallel_workers():
    order = []

    def run_fn(call):
        time.sleep(0.02)
        order.append(call["call_id"])
        return {"call_id": call["call_id"], "output": "ok"}

    calls = [
        {"name": "agent_worker", "call_id": "a"},
        {"name": "agent_worker", "call_id": "b"},
    ]
    outputs = run_tool_calls(run_fn, calls, max_workers=2)
    assert len(outputs) == 2
    assert set(order) == {"a", "b"}


def test_run_tool_calls_serial_when_mixed_with_planner():
    order = []

    def run_fn(call):
        order.append(call["call_id"])
        return {"call_id": call["call_id"], "output": "ok"}

    calls = [
        {"name": "agent_explorer", "call_id": "1"},
        {"name": "agent_planner", "call_id": "2"},
    ]
    run_tool_calls(run_fn, calls, max_workers=4)
    assert order == ["1", "2"]


def test_parallel_agents_disabled_runs_serial(monkeypatch):
    monkeypatch.setattr("langbridge_code.settings.PARALLEL_AGENTS_ENABLED", False)
    monkeypatch.setattr(
        "langbridge_code.agents.common.parallel_tools.PARALLEL_AGENTS_ENABLED",
        False,
    )
    order = []

    def run_fn(call):
        order.append(call["call_id"])
        return {"call_id": call["call_id"], "output": "ok"}

    calls = [
        {"name": "agent_worker", "call_id": "a"},
        {"name": "agent_worker", "call_id": "b"},
    ]
    assert not can_run_tool_calls_in_parallel(calls)
    run_tool_calls(run_fn, calls, max_workers=2)
    assert order == ["a", "b"]
