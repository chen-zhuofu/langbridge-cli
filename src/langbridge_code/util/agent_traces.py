"""Per-subagent raw JSONL traces and full compaction audit records."""
from __future__ import annotations

import itertools
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from langbridge_code.context.common.budget import estimate_tokens
from langbridge_code.llm.model_context import model_context_window
from langbridge_code.settings import TRACES_RESUME_MAX_FRACTION
from langbridge_code.util.artifacts import slug_first_message, traces_dir

_INLINE_COMPACTION_CHARS = 4_000
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_COMPACTION_SEQUENCE = itertools.count()


def _lock_for(path: Path) -> threading.Lock:
    key = str(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _role_slug(role: str) -> str:
    return slug_first_message(role or "agent").lower()


def _task_slug(task_name: str) -> str:
    return slug_first_message(task_name or "untitled")


def reserve_agent_trace(run_log_path, role: str, task_name: str) -> tuple[Path | None, int | None]:
    """Reserve ``traces/{role}-{task_name}-{id}.jsonl``; ids start at zero per task."""
    directory = traces_dir(run_log_path)
    if directory is None or not (task_name or "").strip():
        return None, None
    directory.mkdir(parents=True, exist_ok=True)
    prefix = f"{_role_slug(role)}-{_task_slug(task_name)}-"
    lock = _lock_for(directory / f".{prefix}counter")
    with lock:
        instance_id = 0
        while (directory / f"{prefix}{instance_id}.jsonl").exists():
            instance_id += 1
        path = directory / f"{prefix}{instance_id}.jsonl"
        metadata = {
            "type": "agent_trace_start",
            "role": role,
            "task_name": task_name,
            "instance_id": instance_id,
            "timestamp": _timestamp(),
        }
        path.write_text(
            json.dumps(metadata, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
    return path, instance_id


def append_agent_raw_round(
    path: Path | None,
    *,
    role: str,
    task_name: str,
    instance_id: int | None,
    round_index: int,
    messages: list[dict],
) -> None:
    """Append one uncompressed, non-system message round to an agent JSONL trace."""
    if path is None or not messages:
        return
    filtered = [
        item for item in messages if isinstance(item, dict) and item.get("role") != "system"
    ]
    if not filtered:
        return
    record = {
        "type": "round",
        "role": role,
        "task_name": task_name,
        "instance_id": instance_id,
        "round": round_index,
        "timestamp": _timestamp(),
        "messages": filtered,
    }
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with _lock_for(path):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _trace_instance_id(path: Path) -> int:
    try:
        return int(path.stem.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return -1


def agent_trace_paths(
    run_log_path,
    role: str,
    task_name: str,
    *,
    exclude: Path | None = None,
) -> list[Path]:
    """Existing traces for one role/task, oldest dispatch first."""
    directory = traces_dir(run_log_path)
    if directory is None or not directory.exists() or not (task_name or "").strip():
        return []
    prefix = f"{_role_slug(role)}-{_task_slug(task_name)}-"
    excluded = Path(exclude).resolve() if exclude is not None else None
    paths = []
    for path in directory.glob(f"{prefix}*.jsonl"):
        if excluded is not None and path.resolve() == excluded:
            continue
        paths.append(path)
    return sorted(paths, key=_trace_instance_id)


def _read_agent_rounds(paths: list[Path]) -> list[list[dict]]:
    rounds: list[list[dict]] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            messages = record.get("messages")
            if record.get("type") == "round" and isinstance(messages, list):
                rounds.append(messages)
    return rounds


def _render_resume_rounds(rounds: list[list[dict]], role: str) -> str:
    payload = json.dumps(rounds, ensure_ascii=False, indent=2, default=str)
    return f"## Raw {role} traces from earlier dispatches\n\n```json\n{payload}\n```"


def build_agent_resume_background(
    run_log_path,
    *,
    role: str,
    task_name: str,
    model: str,
    progress: str = "",
    exclude_trace: Path | None = None,
) -> str:
    """Resume one subagent task from progress plus its prior raw trace tail.

    This mirrors the main-agent cold-start policy: use raw traces directly when
    they fit; otherwise use the durable progress note plus the newest complete
    raw rounds that fit the remaining resume budget.
    """
    progress = (progress or "").strip()
    rounds = _read_agent_rounds(
        agent_trace_paths(
            run_log_path,
            role,
            task_name,
            exclude=exclude_trace,
        )
    )
    if not rounds:
        return progress

    budget = max(1, int(model_context_window(model) * TRACES_RESUME_MAX_FRACTION))
    full = _render_resume_rounds(rounds, role)
    if estimate_tokens(full) <= budget:
        return full

    remaining = max(0, budget - estimate_tokens(progress))
    kept: list[list[dict]] = []
    for round_messages in reversed(rounds):
        candidate = [round_messages, *kept]
        if estimate_tokens(_render_resume_rounds(candidate, role)) <= remaining:
            kept = candidate
            continue
        break
    if not kept:
        return progress
    tail = _render_resume_rounds(kept, role)
    return f"{progress}\n\n{tail}".strip()


def append_compaction_event(run_log_path, event: dict) -> Path | None:
    """Append a compaction index record; oversized full events become attachments."""
    directory = traces_dir(run_log_path)
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "compactions.jsonl"
    payload = dict(event)
    payload.setdefault("timestamp", _timestamp())
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if len(rendered) > _INLINE_COMPACTION_CHARS:
        attachments = directory / "attachments"
        attachments.mkdir(parents=True, exist_ok=True)
        sequence = next(_COMPACTION_SEQUENCE)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")
        attachment = attachments / f"compaction-{stamp}-{sequence:03d}.json"
        attachment.write_text(rendered + "\n", encoding="utf-8")
        record = {
            "type": payload.get("type", "compaction"),
            "timestamp": payload["timestamp"],
            "role": payload.get("role"),
            "task_name": payload.get("task_name"),
            "instance_id": payload.get("instance_id"),
            "before": payload.get("before"),
            "after": payload.get("after"),
            "full_event_attachment": str(attachment.relative_to(directory)),
        }
    else:
        record = payload
    with _lock_for(path):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return path


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
