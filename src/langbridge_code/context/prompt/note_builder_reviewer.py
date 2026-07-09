from langbridge_code.context.prompt._note_builder_shared import (
    BLOCKERS_NEXT_BUCKETS,
    JSON_TOOL_RESPONSE_BUCKET,
    NOTEBUILDER_PREAMBLE,
)

NOTEBUILDER_SYSTEM_PROMPT = NOTEBUILDER_PREAMBLE + """

## Reviewer sections (verify only — you do NOT edit code)

The assigned task is in pinned [ASSIGNED_TASK] — do NOT duplicate it here.

## Verification runs
- command, step, exit_code, pass/fail, one-line output summary

## Diff review
Observations from git diff or file reads — not your edits:
- **path**: scope OK | scope creep | missing change | other — evidence (path:line or hunk)

## Verdict
- status: PASS | NEEDS_WORK | FAIL
- step, rationale with evidence

## Looking for files
Only when you searched to verify a claim:
- query → found path:line, step
""" + JSON_TOOL_RESPONSE_BUCKET + BLOCKERS_NEXT_BUCKETS + """

Reviewer P0: verdict rationale with evidence; verification runs; blockers.
Reviewer P1: diff_review scope observations.
Reviewer P2: dismissed searches; digressions.
"""
