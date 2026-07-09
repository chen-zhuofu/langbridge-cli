"""gate.py — apply trainer file edits and the acceptance gate."""
import re

from langbridge_code.training import checkpoint

_ORACLE_LEAK = re.compile(
    r"\b(ground[\s_-]?truth|gt_pass|fail_to_pass|pass_to_pass|hidden tests?|"
    r"oracle|the jury|reward[\s_-]?hack|f2p|p2p)\b",
    re.IGNORECASE,
)


def _strip_leaks(text: str) -> tuple[str, bool]:
    if _ORACLE_LEAK.search(text or ""):
        return "", True
    return text, False


def apply_proposal(proposal, allow_reviewer=True):
    """Apply a trainer proposal (direct file edits) and return a change record."""
    cleaned = dict(proposal or {})
    edits = []
    dropped = []
    for edit in cleaned.get("file_edits") or []:
        if not isinstance(edit, dict):
            continue
        content, leaked = _strip_leaks(edit.get("content") or "")
        if leaked:
            dropped.append(edit.get("path", ""))
            continue
        edits.append({**edit, "content": content})
    cleaned["file_edits"] = edits
    if dropped:
        cleaned["_dropped_leaks"] = dropped
    changes = checkpoint.apply_file_edits(cleaned, allow_reviewer=allow_reviewer)
    if dropped:
        changes["dropped_leaks"] = dropped
    return changes


def sample_score(approved, passed):
    """Penalty for one graded loop outcome (higher = better; max 0)."""
    if approved and passed:
        return 0
    if approved and not passed:
        return -3
    if not approved and passed:
        return -1
    return -2


def gate_blame(approved, passed):
    if approved and not passed:
        return "coder+reviewer"
    if not approved and passed:
        return "reviewer"
    if not approved and not passed:
        return "coder"
    return ""


def gate_total(rows):
    """Sum the penalty over rows of {approved, passed}."""
    return sum(sample_score(bool(r.get("approved")), bool(r.get("passed"))) for r in rows)


def accept_change(old_rows, new_rows):
    """Accept the new artifacts iff total penalty strictly improves."""
    old_total = gate_total(old_rows)
    new_total = gate_total(new_rows)
    return new_total > old_total, old_total, new_total
