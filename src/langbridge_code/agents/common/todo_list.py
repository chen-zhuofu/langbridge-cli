"""Plan file (todo_list.md) helpers.

The plan is a plain markdown file at the workspace root, written and edited
only by the main agent with regular file tools (write / edit_file /
read_file) — including marking todos ``[x]`` after a worker reply. No code
edits the plan automatically.
"""
import re

from langbridge_code.agents.common.workspace import get_workspace_root

PLAN_FILENAME = "todo_list.md"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def plan_path():
    return get_workspace_root() / PLAN_FILENAME


def read_plan_file() -> str:
    path = plan_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def clean_task_text(text: str) -> str:
    stripped = _HTML_COMMENT.sub("", text or "").strip()
    return " ".join(stripped.split())
