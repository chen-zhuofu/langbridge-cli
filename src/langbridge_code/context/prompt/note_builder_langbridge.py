from langbridge_code.context.prompt._note_builder_shared import (
    BLOCKERS_NEXT_BUCKETS,
    JSON_TOOL_RESPONSE_BUCKET,
    NOTEBUILDER_PREAMBLE,
)

NOTEBUILDER_SYSTEM_PROMPT = NOTEBUILDER_PREAMBLE + """

## LangBridge sections (orchestration)

Do NOT record edits or test runs. You coordinate; specialists implement.

## Session goal
Omit if unchanged: user intent + mode (answer | delegate | continue).

## Delegation
Subagent and key tool outcomes this batch:
- kind (planner | worker | explorer | ask_user | direct_tool), description, outcome, step

## Plan progress
From read_plan or tool results: task_type, unchecked todos, last completed, user choice.

## Direct reads
Only when you read/grepped yourself — not subagent summaries:
- query or path → finding, step
""" + JSON_TOOL_RESPONSE_BUCKET + BLOCKERS_NEXT_BUCKETS
