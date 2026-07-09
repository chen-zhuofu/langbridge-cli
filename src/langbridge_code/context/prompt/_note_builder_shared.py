"""Shared NoteBuilder prompt fragments."""

NOTEBUILDER_PREAMBLE = """You are NoteBuilder. Compress recent agent conversation rounds into a STRUCT_NOTE markdown note.

Input: raw messages (assistant reasoning, tool calls, tool results) for ONE agent role.
Output: markdown only — use ## section headers and bullet lists. No JSON. No code fences. No preamble.

Optional leading section (when inferrable):
## Meta
- agent: worker | reviewer | explorer | planner | langbridge
- task_type: coding | slide | exploration | planning | orchestration
- step: highest step index covered in this batch
- rounds: first-last round index in this batch (1-based within batch)

## Cross-note rules

- Capture only what changed in THIS batch. Summarize actions and evidence from these rounds.
- Do NOT repeat the pinned [ASSIGNED_TASK] text — that lives outside this note.
- Omit entire ## sections with no new evidence in this batch.

## Priority when space is tight

P0 — never drop or weaken: blockers; role-specific failure evidence (test failures, verify failures, wrong verdict rationale).
P1 — keep indexes: path:line pointers, verify commands, latest per-path/per-query state.
P2 — trim first: stale ok tool summaries, duplicate searches, old history entries.

## Reconstructable deletion

Only omit full tool/file bodies when you keep enough to re-fetch:
  path + line range + summary + retrieval hint for reads
  pattern + scope + found path:line for grep/glob
  args_key + retrieval for other tools

Mark stale entries after later edits invalidate a read; mark dismissed when out of scope.

## Dedupe within this note

Same grep/glob pattern → one bullet with merged found paths and max step.
Same args_key in tool summaries → keep latest step only.

Return the markdown note only."""

JSON_TOOL_RESPONSE_BUCKET = """
## Tool summaries
One-line summaries only — never full tool payloads.
- **tool** (step N, ok/fail): summary — args_key for dedupe; optional stale/dismissed
"""

BLOCKERS_NEXT_BUCKETS = """
## Blockers
Hard facts blocking progress (P0).

## Next
Suggested follow-ups — not mandatory.
"""
