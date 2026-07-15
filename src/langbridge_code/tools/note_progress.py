"""note_progress tool: fork a note-writer on the live context to update progress.md."""

from langbridge_code.tools.common.purpose import PURPOSE_PARAMETER

NOTE_PROGRESS_TOOL_SCHEMA = {
    "type": "function",
    "name": "note_progress",
    "description": (
        "Record session progress right now (main agent only). This forks a "
        "note-writer on your live context: it summarizes the work since the "
        "last progress note and appends it to progress.md — you do not write "
        "the note yourself. You MUST call it once after every subagent result "
        "(planner, explorer, or worker), including failures and partial results; "
        "identify that result in purpose. Also call it whenever something else "
        "meaningful just completed or was decided: a plan committed, a key "
        "discovery, or a user decision. Do not wait for the turn to end. "
        "progress.md survives compaction — it is "
        "re-read into your <progress> block, so anything noted here is never "
        "lost when older rounds are compressed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "purpose": PURPOSE_PARAMETER,
        },
        "required": ["purpose"],
        "additionalProperties": False,
    },
}

TASK_NOTE_PROGRESS_TOOL_SCHEMA = {
    "type": "function",
    "name": "note_progress",
    "description": (
        "Record progress on your assigned task right now. This forks a "
        "note-writer on your live context: it summarizes the work since the "
        "last note and appends it to this task's progress file — you do not "
        "write the note yourself. Call it whenever something meaningful just "
        "completed or was decided: a step finished and verified, a key "
        "discovery, a dead end ruled out. The file survives your context "
        "compaction and is shown (as <progress>) to the next agent dispatched "
        "on this same task, so anything noted here is never lost."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "purpose": PURPOSE_PARAMETER,
        },
        "required": ["purpose"],
        "additionalProperties": False,
    },
}

TASK_NOTE_FORK_INSTRUCTION = """You are a forked progress note-writer for this task.
Write a structure note covering the work since the last progress note (see the
<progress> block and any earlier notes above — do not repeat them).

Output markdown only — no preamble, no code fences. Use these #### sections and
omit any section with nothing new in this batch:

#### Work done
- Steps completed, files created/edited, commands run, with outcomes.

#### Key discoveries
- Facts learned, with path:line pointers when known.

#### Blockers / dead ends
- Hard facts blocking progress and approaches ruled out — never drop these.

#### Next
- What remains for this task.

Be concrete and past-tense. Keep path:line pointers and exact verify commands."""

NOTE_FORK_INSTRUCTION = """You are a forked progress note-writer for this session.
Write a structure note covering the work since the last progress note (see the
<progress> block and any earlier notes above — do not repeat them).

Output markdown only — no preamble, no code fences. Use these #### sections and
omit any section with nothing new in this batch:

#### Delegation
- Subagent and key tool outcomes: kind (planner | worker | explorer | direct),
  what was dispatched, result.

#### Plan progress
- task_type, todos completed / still unchecked, user decisions.

#### Key discoveries
- Facts learned, with path:line pointers when known.

#### Blockers
- Hard facts blocking progress — never drop or weaken these.

#### Next
- Suggested follow-ups (not mandatory).

Be concrete and past-tense. Keep path:line pointers and exact verify commands."""
