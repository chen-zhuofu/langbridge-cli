"""Per-agent instance ids and trace logging (replaces per-role worklog files)."""
from __future__ import annotations

import threading

from langbridge_code.util.agent_debug import set_agent_debug
from langbridge_code.llm.parse import extract_output_text, extract_reasoning_summaries
from langbridge_code.util.trace_log import log_finish, log_from_step_output, log_received, log_tool_result

# label -> file-name prefix (kept for tests expecting instance ids)
_WORKLOG_FILE_BY_LABEL = {
    "LangBridge": "langbridge",
    "Planner": "planner",
    "Worker": "worker",
    "Coder": "worker",
    "Reviewer": "reviewer",
    "Explore": "explore",
}

_INSTANCE_COUNTERS: dict[tuple[str, str], int] = {}
_INSTANCE_COUNTER_LOCK = threading.Lock()


def new_worklog_id(run_log_path, label):
    if run_log_path is None or label not in _WORKLOG_FILE_BY_LABEL:
        return None
    key = (str(run_log_path), label)
    with _INSTANCE_COUNTER_LOCK:
        next_id = _INSTANCE_COUNTERS.get(key, 0) + 1
        _INSTANCE_COUNTERS[key] = next_id
    set_agent_debug(label, next_id)
    return next_id


def worklog_path(run_log_path, label, instance_id=None):
    del run_log_path, label, instance_id
    return None


def write_worklog_received(run_log_path, label, instance_id, turn_id, text):
    del run_log_path, turn_id
    set_agent_debug(label, instance_id)
    log_received(label, text)


def write_worklog_step(run_log_path, label, instance_id, turn_id, step, output):
    del run_log_path, turn_id, step
    set_agent_debug(label, instance_id)
    log_from_step_output(label, output)


def write_worklog_observation(run_log_path, label, instance_id, turn_id, step, tool_output):
    del run_log_path, turn_id, step
    set_agent_debug(label, instance_id)
    call_id = tool_output.get("call_id", "tool")
    log_tool_result(label, str(call_id), str(tool_output.get("output", "")))


def write_worklog_finish(run_log_path, label, instance_id, turn_id, finished):
    del run_log_path, turn_id
    set_agent_debug(label, instance_id)
    log_finish(label, finished)
