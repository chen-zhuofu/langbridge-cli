"""Per-task progress notes for subagents — same machinery as the main agent.

A task's notes live at {session}/progress-{task-slug}.md, derived from the
explicit task_name the main agent passes when dispatching. The file is pinned
into the subagent's context as the <progress> block, re-read after every
compaction, appended to via the same forked note-writer the main agent uses,
and compacted with the same middle-turn merge strategy. Re-dispatching the
same task_name resumes from the earlier agent's notes: each dispatch is one
"## Turn N" section in the file.
"""
from __future__ import annotations

from langbridge_code.settings import PROGRESS_NOTE_REMINDER_ROUNDS

TASK_NOTE_REMINDER = (
    "[HOOK] More than {rounds} rounds have passed without a progress note. "
    "Call note_progress NOW, before any other tool call: record what you have "
    "done since the last note and the current state of your task. If your "
    "context is compacted or you are stopped, this file is the only record "
    "the next agent on this task gets. Then continue working."
)


class TaskProgress:
    """Binds one subagent session to its task progress file."""

    def __init__(self, api_key, model, run_log_path, task_name, *, label="Subagent"):
        self.api_key = api_key
        self.model = model
        self.run_log_path = run_log_path
        self.task_name = (task_name or "").strip()
        self.label = label
        self.turn_id = 0
        self._stack = None
        self._messages = None
        self._rounds_since_note = 0

    @property
    def enabled(self) -> bool:
        return bool(self.task_name and self.run_log_path)

    def attach(self, stack, messages) -> None:
        """Start one dispatch: pin existing notes and open the next turn section."""
        if not self.enabled:
            return
        from langbridge_code.util.progress import last_progress_turn_id

        self._stack = stack
        self._messages = messages
        self.turn_id = last_progress_turn_id(self.run_log_path, self.task_name) + 1
        self.refresh_block()
        previous = stack.on_compacted

        def on_compacted(compacted_stack):
            if previous is not None:
                try:
                    previous(compacted_stack)
                except Exception:
                    pass
            self.refresh_block()

        stack.on_compacted = on_compacted

    def refresh_block(self) -> None:
        if self._stack is None or not self.enabled:
            return
        from langbridge_code.util.progress import PROGRESS_HEADER, read_progress

        content = read_progress(self.run_log_path, self.task_name).strip()
        if content == PROGRESS_HEADER.strip():
            content = ""
        self._stack.set_progress_block(content)

    def write_note(self, **_ignored) -> str:
        """note_progress tool implementation: fork a note-writer on the live context."""
        if not self.enabled:
            return "No task progress file for this session; note not recorded."
        from langbridge_code.agents.common.fork import fork_one_pass
        from langbridge_code.tools.note_progress import TASK_NOTE_FORK_INSTRUCTION
        from langbridge_code.util.progress import append_progress_note, maybe_compact_progress

        self._rounds_since_note = 0
        try:
            note = fork_one_pass(
                self.api_key,
                self.model,
                list(self._messages or []),
                TASK_NOTE_FORK_INSTRUCTION,
                label=f"{self.label} note fork",
            )
        except Exception as error:
            return f"Progress note fork failed: {error}"
        if not note.strip():
            return "Progress note fork returned nothing; no note recorded."
        result = append_progress_note(self.run_log_path, self.turn_id, note, self.task_name)
        maybe_compact_progress(self.api_key, self.model, self.run_log_path, self.task_name)
        return result

    def maybe_remind(self, context) -> None:
        """Same nudge cadence as the main agent: inject a [HOOK] after silent rounds."""
        if not self.enabled:
            return
        self._rounds_since_note += 1
        if self._rounds_since_note <= PROGRESS_NOTE_REMINDER_ROUNDS:
            return
        self._rounds_since_note = 0
        context.begin_turn(TASK_NOTE_REMINDER.format(rounds=PROGRESS_NOTE_REMINDER_ROUNDS))
