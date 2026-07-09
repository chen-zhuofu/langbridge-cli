from langbridge_code.context.prompt._note_builder_shared import (
    BLOCKERS_NEXT_BUCKETS,
    JSON_TOOL_RESPONSE_BUCKET,
    NOTEBUILDER_PREAMBLE,
)

NOTEBUILDER_SYSTEM_PROMPT = NOTEBUILDER_PREAMBLE + """

## Explorer sections (read-only investigation)

Do NOT record edits or test runs. You do not implement or fix.

## Investigation goal
Omit if unchanged from parent task: question + thoroughness (quick | medium | thorough).

## Looking for files
Primary bucket — merge duplicate queries:
- query → found paths/lines, step, active/dismissed (+ reason if dismissed)

## Understanding code flow
- flow or open question → evidence path:line, status

## Findings
Actionable discoveries for the parent agent:
- finding → evidence path:line, step

## Open questions
Only what parent or user must decide.

## Edge cases
Gotchas, test gaps, risks — omit if none.
""" + JSON_TOOL_RESPONSE_BUCKET + BLOCKERS_NEXT_BUCKETS
