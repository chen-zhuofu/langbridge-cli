from langbridge_code.context.prompt._note_builder_shared import (
    BLOCKERS_NEXT_BUCKETS,
    JSON_TOOL_RESPONSE_BUCKET,
    NOTEBUILDER_PREAMBLE,
)

NOTEBUILDER_SYSTEM_PROMPT = NOTEBUILDER_PREAMBLE + """

## Planner sections (evidence-based planning)

Do NOT record edits or test runs. You write plans, not implementations.

## Planning goal
Omit if unchanged: user request + task_type (coding | slide).

## Key discoveries
- finding → evidence path:line (required for coding), step

## Out of scope
Bullets only.

## Plan state
plan_written, todo counts, integration/parallel flags, one-line plan shape summary.

## Open questions
Only what code cannot answer.

## Changes required index
File targets known — not full snippets:
- todo title → files path:line

## Looking for files
Repo research while planning:
- query → found path:line, step
""" + JSON_TOOL_RESPONSE_BUCKET + BLOCKERS_NEXT_BUCKETS
