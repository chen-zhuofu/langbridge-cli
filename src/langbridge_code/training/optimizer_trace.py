"""Append-only trace of coder↔reviewer handoffs for offline optimizer."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from langbridge_code.util.artifacts import traces_dir


def trace_path(run_log_path) -> Path | None:
    base = traces_dir(run_log_path)
    if base is None or not base.is_dir():
        return None
    logs = sorted(base.glob("*.log"), key=lambda path: path.stat().st_mtime)
    if not logs:
        return None
    return logs[-1]


def append_event(run_log_path, event: dict) -> None:
    path = trace_path(run_log_path)
    if path is None:
        return
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    centis = datetime.now(timezone.utc).microsecond // 10_000
    line = f"{stamp}.{centis:02d} · optimizer · {event.get('event', 'event')}"
    if event.get("report"):
        detail = str(event["report"]).replace("\n", " ")
        if len(detail) > 80:
            detail = detail[:77] + "..."
        line += f": {detail}"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=False) + "\n")


def read_events(run_log_path=None) -> list[dict]:
    path = trace_path(run_log_path)
    if path is None or not path.is_file():
        return []
    events = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def trace_to_loop_rounds(run_log_path, final_diff: str) -> dict:
    """Reconstruct coarse training rounds from unified trace JSONL lines."""
    rounds = []
    for event in read_events(run_log_path):
        if event.get("event") != "reviewer_turn":
            continue
        report = event.get("report", "")
        approved = "REVIEW_VERDICT: PASS" in report
        rounds.append(
            {
                "round": len(rounds) + 1,
                "diff": final_diff,
                "approved": approved,
                "verdict": "pass" if approved else "needs_work",
                "comments": str(report)[:4000],
                "pushed_back": False,
            }
        )
    return {"rounds": rounds, "pushed_back": False, "jury_convened": False}


def trace_to_loop_rounds_from_path(trace_file: str, final_diff: str) -> dict:
    """Parse a trace file path (used by eval subprocess parent)."""
    if not trace_file or not Path(trace_file).is_file():
        return {"rounds": [], "pushed_back": False, "jury_convened": False}
    events = []
    with open(trace_file, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    rounds = []
    for event in events:
        if event.get("event") != "reviewer_turn":
            continue
        report = event.get("report", "")
        approved = "REVIEW_VERDICT: PASS" in report
        rounds.append(
            {
                "round": len(rounds) + 1,
                "diff": final_diff,
                "approved": approved,
                "verdict": "pass" if approved else "needs_work",
                "comments": str(report)[:4000],
                "pushed_back": False,
            }
        )
    return {"rounds": rounds, "pushed_back": False, "jury_convened": False}
