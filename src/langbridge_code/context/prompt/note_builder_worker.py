from langbridge_code.context.prompt._note_builder_shared import (
    BLOCKERS_NEXT_BUCKETS,
    JSON_TOOL_RESPONSE_BUCKET,
    NOTEBUILDER_PREAMBLE,
)

NOTEBUILDER_SYSTEM_PROMPT = NOTEBUILDER_PREAMBLE + """

## Worker sections (implementation + verify)

The assigned task is in pinned [ASSIGNED_TASK] — do NOT duplicate it here.
read_plan context (if used) belongs in Looking for files / Understanding code flow, not here.

## Looking for files
- query pattern → found paths/lines, step, active/dismissed (+ reason if dismissed)

## Understanding code flow
- flow chain or open question → evidence path:line, status (confirmed | needs_read | stale)

## Edits to files
Latest state per path touched this batch:
- **path** (step N): plain-English change summary

## Test / build output
- verify_command: string
- latest run: step, exit_code, pass/fail counts
- failures (P0 when tests fail): test id, expected, actual, assertion snippet
- history: older runs as one-line results
""" + JSON_TOOL_RESPONSE_BUCKET + BLOCKERS_NEXT_BUCKETS + """

Worker P0: test failures; latest edit per path; blockers.
Worker P1: found paths; code-flow evidence; verify_command.
Worker P2: stale tool summaries; test history beyond latest.
"""
