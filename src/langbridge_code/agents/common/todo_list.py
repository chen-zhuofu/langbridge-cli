"""Shared session todo_list file I/O and parsing (planner + worker)."""
import re
from dataclasses import dataclass

from langbridge_code.settings import TODO_LIST_PATH
from langbridge_code.util.artifacts import todo_list_path as artifact_todo_list_path


_TASK_TYPE_RE = re.compile(
    r"<!--\s*task_type:\s*(?P<type>coding|slide|presentation)\s*-->",
    re.IGNORECASE,
)
_TASK_LINE = re.compile(
    r"^\s*-\s*\[(?P<done>[ xX])\]\s*(?:\[(?:coding|presentation)\]\s*)?(?P<text>.+?)\s*$",
    re.IGNORECASE,
)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass
class TodoTask:
    description: str
    done: bool = False
    note: str = ""

    @property
    def unfinished(self):
        return not self.done


def todo_list_path(run_log_path=None):
    if run_log_path is None:
        return TODO_LIST_PATH
    path = artifact_todo_list_path(run_log_path)
    if path is not None:
        return path
    return run_log_path.with_name("todo_list.md")


def read_todo_list(run_log_path=None):
    path = todo_list_path(run_log_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_todo_list(content, run_log_path=None):
    path = todo_list_path(run_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def parse_todo_list(content: str) -> list[TodoTask]:
    tasks: list[TodoTask] = []
    current: TodoTask | None = None
    for line in (content or "").splitlines():
        match = _TASK_LINE.match(line)
        if match:
            current = TodoTask(
                description=match.group("text").strip(),
                done=match.group("done").strip().lower() == "x",
            )
            tasks.append(current)
            continue
        if current is not None and line.strip().lower().startswith("note:"):
            current.note = line.split(":", 1)[1].strip()
    return tasks


def render_todo_list(tasks: list[TodoTask], title: str = "Todo") -> str:
    lines = [f"# {title}", ""]
    for task in tasks:
        mark = "x" if task.done else " "
        lines.append(f"- [{mark}] {task.description}")
        if task.note:
            lines.append(f"  note: {task.note}")
    return "\n".join(lines).strip() + "\n"


def load_tasks(run_log_path) -> list[TodoTask]:
    return parse_todo_list(read_todo_list(run_log_path))


def read_task_type(run_log_path) -> str | None:
    content = read_todo_list(run_log_path)
    match = _TASK_TYPE_RE.search(content or "")
    if not match:
        return None
    value = match.group("type").lower()
    if value == "presentation":
        return "slide"
    return value


def write_task_type_marker(content: str, task_type: str) -> str:
    lines = [line for line in (content or "").splitlines() if not _TASK_TYPE_RE.match(line.strip())]
    marker = f"<!-- task_type: {task_type} -->"
    body = "\n".join(lines).strip()
    if body:
        return f"{marker}\n{body}\n"
    return f"{marker}\n"


def unfinished_count(tasks: list[TodoTask]) -> int:
    return sum(1 for task in tasks if task.unfinished)


def clean_task_text(text: str) -> str:
    stripped = _HTML_COMMENT.sub("", text or "").strip()
    return " ".join(stripped.split())


def _normalize_match(text: str) -> str:
    return clean_task_text(text).lower()


def find_matching_unfinished_task(tasks: list[TodoTask], subtask: str) -> TodoTask | None:
    needle = _normalize_match(subtask)
    if not needle:
        return None
    unfinished = [task for task in tasks if task.unfinished]
    exact = [task for task in unfinished if _normalize_match(task.description) == needle]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    partial = [
        task
        for task in unfinished
        if needle in _normalize_match(task.description) or _normalize_match(task.description) in needle
    ]
    if len(partial) == 1:
        return partial[0]
    return None


def mark_subtask_done_in_content(content: str, subtask: str) -> tuple[str, TodoTask | None]:
    tasks = parse_todo_list(content)
    target = find_matching_unfinished_task(tasks, subtask)
    if target is None:
        return content, None
    target_key = _normalize_match(target.description)
    lines: list[str] = []
    matched = False
    for line in (content or "").splitlines():
        match = _TASK_LINE.match(line)
        if (
            match
            and match.group("done").strip().lower() != "x"
            and _normalize_match(match.group("text")) == target_key
        ):
            lines.append(re.sub(r"^\s*-\s*\[\s*\]", "- [x]", line, count=1))
            matched = True
            continue
        lines.append(line)
    if not matched:
        return content, None
    body = "\n".join(lines)
    if content.endswith("\n"):
        body += "\n"
    return body, target
