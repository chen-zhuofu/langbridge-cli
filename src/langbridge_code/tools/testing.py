import json
from pathlib import Path

from langbridge_code.settings import (
    DEFAULT_TEST_TIMEOUT_SECONDS,
    MAX_TEST_OUTPUT_CHARS,
    MAX_TEST_TIMEOUT_SECONDS,
)
from langbridge_code.tools.common.env import workspace_env, workspace_python
from langbridge_code.tools.common.proc import run_command
from langbridge_code.tools.common.purpose import PURPOSE_PARAMETER
from langbridge_code.tools.common.runtime import ensure_test_python
from langbridge_code.agents.common.workspace import get_workspace_root

WORKSPACE_ROOT = Path.cwd().resolve()

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "run_tests",
        "description": "Run Python unit tests under the current workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "purpose": PURPOSE_PARAMETER,
                "path": {
                    "type": "string",
                    "description": "Test file or directory path relative to the current workspace.",
                    "default": ".",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum time to wait before stopping tests.",
                    "default": DEFAULT_TEST_TIMEOUT_SECONDS,
                },
            },
            "required": ["purpose"],
            "additionalProperties": False,
        },
    }
]

TOOLS = {}


def tool(name):
    def register(function):
        TOOLS[name] = function
        return function

    return register


def resolve_workspace_path(path):
    target = (get_workspace_root() / path).resolve()
    try:
        target.relative_to(get_workspace_root())
    except ValueError:
        raise ValueError("Path must stay inside the current workspace")
    return target


@tool("run_tests")
def run_tests(path=".", timeout_seconds=DEFAULT_TEST_TIMEOUT_SECONDS):
    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"No such test path: {path}")

    timeout = max(1, min(int(timeout_seconds), MAX_TEST_TIMEOUT_SECONDS))
    env = workspace_env()
    python = ensure_test_python(workspace_python(env))
    command = [python, "-m", "pytest", str(target.relative_to(get_workspace_root()))]

    output, exit_code, timed_out = run_command(
        command,
        cwd=get_workspace_root(),
        env=env,
        timeout=timeout,
    )
    output, truncated = truncate_output(output)
    return json.dumps(
        {
            "command": command,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "truncated": truncated,
            "output": output,
        },
        ensure_ascii=False,
        indent=2,
    )


def truncate_output(output):
    if len(output) <= MAX_TEST_OUTPUT_CHARS:
        return output, False
    return output[:MAX_TEST_OUTPUT_CHARS] + "\n\n[truncated]", True
