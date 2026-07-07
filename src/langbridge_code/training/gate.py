"""gate.py — apply an evolver proposal to a policy, and the acceptance gate.

Two deterministic pieces the evolver leans on:

1. apply_proposal(policy, proposal, allow_reviewer): translate the evolver LLM's
   JSON proposal into concrete policy edits (guidance add/remove/replace per role,
   plus new skills). Reviewer levers are gated by `allow_reviewer` so the
   reviewer is only re-tuned when there is a TRUSTWORTHY correctness signal in the
   batch (real tests or a unanimous jury) — the guard against reviewer collapse.

2. The acceptance gate: every policy change is provisional. After applying it we
   re-run the batch and keep the change only if the total penalty score improves.
   The penalty table makes reward-hacking the worst outcome, so a change that buys
   approvals by passing broken code is rejected.

Both are pure functions of their inputs (no LLM, no I/O beyond policy.add_skill),
so they are fully unit-testable.
"""
import re

from langbridge_code import policy

_ORACLE_LEAK = re.compile(
    r"\b(ground[\s_-]?truth|gt_pass|fail_to_pass|pass_to_pass|hidden tests?|"
    r"oracle|the jury|reward[\s_-]?hack|f2p|p2p)\b",
    re.IGNORECASE,
)

_ROLE_KEYS = {
    "coder": "coder",
    "reviewer": "reviewer",
    "planner": "planner",
    "router": "router",
    "presenter": "presenter",
}
_REVIEWER_ROLES = {"reviewer"}


def _strip_leaks(bullets):
    """Split bullets into (kept, leaked)."""
    kept, leaked = [], []
    for b in bullets or []:
        (leaked if _ORACLE_LEAK.search(b or "") else kept).append(b)
    return kept, leaked


def apply_proposal(p, proposal, allow_reviewer=True):
    """Apply an evolver proposal dict to policy dict `p` in place."""
    changes = {"diagnosis": proposal.get("diagnosis", "")}

    for key, role in _ROLE_KEYS.items():
        is_reviewer = role in _REVIEWER_ROLES
        add = proposal.get(f"{key}_guidance_add") or []
        rem = proposal.get(f"{key}_guidance_remove") or []
        rep = proposal.get(f"{key}_guidance_replace") or []
        if not (add or rem or rep):
            continue
        if is_reviewer and not allow_reviewer:
            changes.setdefault("skipped", []).append(
                f"{key}: no trustworthy correctness anchor (tests or jury) this batch"
            )
            continue
        kept, leaked = _strip_leaks(add)
        added = policy.add_guidance(p, role, kept)
        removed = policy.remove_guidance(p, role, rem)
        replaced = policy.replace_guidance(p, role, rep)
        entry = {}
        if added:
            entry["added"] = added
        if removed:
            entry["removed"] = removed
        if replaced:
            entry["replaced"] = replaced
        if leaked:
            entry["dropped_leaks"] = leaked
        if entry:
            changes.setdefault("guidance", {})[role] = entry

    skills_added = []
    for sk in proposal.get("new_skills") or []:
        if not isinstance(sk, dict) or not sk.get("content"):
            continue
        target = sk.get("target", "all")
        if policy._TARGET_ALIASES.get(target, (target,)) == ("reviewer",) and not allow_reviewer:
            changes.setdefault("skipped", []).append("skill for reviewer: no anchor this batch")
            continue
        sid = policy.add_skill(p, sk.get("name", "skill"), target,
                               sk.get("when", ""), sk["content"])
        skills_added.append(sid)
    if skills_added:
        changes["skills_added"] = skills_added

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
    """Accept the new policy iff its total penalty strictly improves on the old."""
    old_total = gate_total(old_rows)
    new_total = gate_total(new_rows)
    return new_total > old_total, old_total, new_total
