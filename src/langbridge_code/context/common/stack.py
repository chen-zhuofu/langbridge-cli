"""Layered context: compact prose + structure notes + raw rounds.

Hyperparameters (settings):
  STRUCTURE_MIN_RAW_KEEP   — minimum raw rounds kept in the tail (default 2)
  STRUCTURE_BATCH          — raw rounds per structure note (default 4)
  STRUCTURE_COMPACT_FRACTION — when assembled context reaches this fraction of
                               the model window, merge structure notes to prose

Flow after each worker step:
  1. Append one raw round (user message on first step of a send(), then assistant+tools).
  2. While len(raw_rounds) >= MIN_RAW_KEEP + BATCH: NoteBuild LLM → structure note.
  3. When tokens >= window * FRACTION and structure notes exist: prose compact LLM.
  4. Rebuild flat messages[] for the next model call.
"""
from __future__ import annotations

import copy
from pathlib import Path

from langbridge_code.context.common.budget import estimate_tokens
from langbridge_code.context.debug import format_raws, record_prose_compression, record_structure_compression
from langbridge_code.context.memory import StructureNote
from langbridge_code.context.message import iter_tool_rounds
from langbridge_code.context.prose import COMPACT_PROSE_PREFIX, compact_structure_notes_to_prose
from langbridge_code.context.structure_note import (
    STRUCTURE_NOTE_PREFIX,
    build_structure_note,
    unwrap_structure_note_content,
)
from langbridge_code.llm.model_context import model_context_window
from langbridge_code.settings import (
    STRUCTURE_BATCH,
    STRUCTURE_COMPACT_FRACTION,
    STRUCTURE_MIN_RAW_KEEP,
    STRUCTURE_USE_LLM,
)

ASSIGNED_TASK_PREFIX = "[ASSIGNED_TASK]\n"


class ContextStack:
    def __init__(
        self,
        *,
        system_content: str,
        persist_dir: Path | None = None,
        label: str = "Worker",
        min_raw_keep: int | None = None,
        structure_batch: int | None = None,
        compact_fraction: float | None = None,
        note_builder=None,
        prose_compactor=None,
    ):
        self.system_content = system_content
        self.persist_dir = persist_dir
        self.label = label
        self.min_raw_keep = STRUCTURE_MIN_RAW_KEEP if min_raw_keep is None else min_raw_keep
        self.structure_batch = STRUCTURE_BATCH if structure_batch is None else structure_batch
        self.compact_fraction = (
            STRUCTURE_COMPACT_FRACTION if compact_fraction is None else compact_fraction
        )
        self._note_builder = note_builder or build_structure_note
        self._prose_compactor = prose_compactor or compact_structure_notes_to_prose

        self.compact_prose: str | None = None
        self.pinned_user_content: str | None = None
        self.structure_notes: list[StructureNote] = []
        self.raw_rounds: list[list[dict]] = []

        self._pending_user: str | None = None
        self._next_note_id = 1
        self._next_live_round = 1
        self._covered_through_round = 0

    def load_persisted_layers(self) -> bool:
        """Debug persistence is write-only; runtime stack stays in memory."""
        return False

    def reconcile_after_persisted_load(self) -> None:
        """Drop raw rounds already represented by persisted structure notes."""
        covered = self._covered_through_round
        if covered <= 0:
            return
        if len(self.raw_rounds) > covered:
            self.raw_rounds = self.raw_rounds[covered:]
        else:
            self.raw_rounds = []
        self._next_live_round = covered + len(self.raw_rounds) + 1

    def start_turn(self, user_content: str) -> None:
        self._pending_user = user_content

    def set_pinned_user(self, content: str | None) -> None:
        """Fixed user message prepended on every to_messages(); never compacted."""
        if content and str(content).strip():
            self.pinned_user_content = str(content).strip()
        else:
            self.pinned_user_content = None

    def set_pinned_assigned_task(self, task: str) -> None:
        text = (task or "").strip()
        self.set_pinned_user(f"{ASSIGNED_TASK_PREFIX}{text}" if text else None)

    def bootstrap_from_messages(self, messages: list[dict]) -> None:
        """Import a flat message list (session resume) into layered state."""
        if not messages:
            return
        index = 0
        if messages[0].get("role") == "system":
            self.system_content = str(messages[0].get("content", ""))
            index = 1

        while index < len(messages):
            message = messages[index]
            if message.get("role") != "user" or message.get("type"):
                break
            content = str(message.get("content", ""))
            if content.startswith(ASSIGNED_TASK_PREFIX):
                self.pinned_user_content = content
                index += 1
                continue
            if content.startswith(COMPACT_PROSE_PREFIX):
                self.compact_prose = content[len(COMPACT_PROSE_PREFIX) :]
                index += 1
                continue
            note_text = unwrap_structure_note_content(content)
            if note_text is not None:
                note = StructureNote(
                    id=self._next_note_id,
                    round_start=self._next_live_round,
                    round_end=self._next_live_round,
                    text=note_text,
                )
                self._next_note_id += 1
                self._next_live_round += 1
                self.structure_notes.append(note)
                index += 1
                continue
            break

        pending_user: str | None = None
        index = 0
        while index < len(messages):
            message = messages[index]
            if message.get("role") == "user" and not message.get("type"):
                content = str(message.get("content", ""))
                if content.startswith(ASSIGNED_TASK_PREFIX):
                    index += 1
                    continue
                if content.startswith(COMPACT_PROSE_PREFIX):
                    index += 1
                    continue
                if unwrap_structure_note_content(content) is not None:
                    index += 1
                    continue
                pending_user = content
                index += 1
                continue
            if message.get("role") == "assistant":
                round_items: list[dict] = []
                if pending_user is not None:
                    round_items.append({"role": "user", "content": pending_user})
                    pending_user = None
                round_items.append(copy.deepcopy(message))
                index += 1
                self.raw_rounds.append(round_items)
                self._next_live_round += 1
                continue
            if message.get("type") in {"reasoning", "function_call", "function_call_output"}:
                round_items = []
                if pending_user is not None:
                    round_items.append({"role": "user", "content": pending_user})
                    pending_user = None
                tool_items, index = self._consume_tool_round(messages, index)
                round_items.extend(tool_items)
                if round_items:
                    self.raw_rounds.append(round_items)
                    self._next_live_round += 1
                continue
            index += 1

        if pending_user is not None:
            self._pending_user = pending_user

    def _consume_tool_round(self, messages: list[dict], index: int) -> tuple[list[dict], int]:
        rounds = iter_tool_rounds(messages[index:])
        if not rounds:
            return [], index + 1
        _, indices = rounds[0]
        items = [copy.deepcopy(messages[index + offset]) for offset in indices]
        return items, index + max(indices) + 1

    def complete_step(self, step_items: list[dict]) -> None:
        """Record one agent step (assistant output + tool results)."""
        round_messages: list[dict] = []
        if self._pending_user is not None:
            round_messages.append({"role": "user", "content": self._pending_user})
            self._pending_user = None
        round_messages.extend(copy.deepcopy(step_items))
        self.raw_rounds.append(round_messages)

    def maybe_advance(
        self,
        *,
        api_key: str | None,
        model: str | None,
        budget_tokens: int | None = None,
    ) -> dict:
        """Run structure-note and prose-compact passes. Returns a stats dict."""
        stats = {
            "structure_notes_added": 0,
            "prose_compacted": False,
            "tokens": self.token_count(),
        }
        if not (api_key and model and STRUCTURE_USE_LLM):
            return stats

        while len(self.raw_rounds) >= self.min_raw_keep + self.structure_batch:
            if not self._take_structure_note(api_key, model):
                break
            stats["structure_notes_added"] += 1

        if self._should_prose_compact(model, budget_tokens):
            if self._prose_compact(api_key, model):
                stats["prose_compacted"] = True

        stats["tokens"] = self.token_count()
        return stats

    def to_messages(self) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": self.system_content}]
        if self.pinned_user_content:
            messages.append({"role": "user", "content": self.pinned_user_content})
        if self.compact_prose:
            messages.append(
                {
                    "role": "user",
                    "content": COMPACT_PROSE_PREFIX + self.compact_prose,
                }
            )
        for note in self.structure_notes:
            messages.append(
                {
                    "role": "user",
                    "content": STRUCTURE_NOTE_PREFIX + note.text,
                }
            )
        for round_messages in self.raw_rounds:
            messages.extend(copy.deepcopy(round_messages))
        if self._pending_user is not None:
            messages.append({"role": "user", "content": self._pending_user})
        return messages

    def token_count(self) -> int:
        return estimate_tokens(self.to_messages())

    def layer_snapshot(self) -> dict:
        return {
            "compact_prose": bool(self.compact_prose),
            "pinned_user": bool(self.pinned_user_content),
            "structure_note_count": len(self.structure_notes),
            "raw_round_count": len(self.raw_rounds),
            "pending_user": self._pending_user is not None,
        }

    def _take_structure_note(self, api_key: str, model: str) -> bool:
        batch = self.raw_rounds[: self.structure_batch]
        round_start = self._next_live_round
        round_end = round_start + len(batch) - 1
        text = self._note_builder(
            api_key,
            model,
            batch,
            label=f"{self.label} structure note",
        )
        if not text.strip():
            return False

        note = StructureNote(
            id=self._next_note_id,
            round_start=round_start,
            round_end=round_end,
            text=text,
        )
        self._next_note_id += 1
        self._next_live_round = round_end + 1
        self.structure_notes.append(note)
        self.raw_rounds = self.raw_rounds[self.structure_batch :]
        record_structure_compression(
            round_start=round_start,
            round_end=round_end,
            raw_readable=format_raws(batch),
            output=text,
        )
        return True

    def _should_prose_compact(self, model: str | None, budget_tokens: int | None) -> bool:
        if not self.structure_notes:
            return False
        window = model_context_window(model or "")
        threshold = int(window * self.compact_fraction)
        if budget_tokens is not None:
            threshold = min(threshold, budget_tokens)
        return self.token_count() >= threshold

    def _prose_compact(self, api_key: str, model: str) -> bool:
        prior_prose = self.compact_prose
        note_texts = [note.text for note in self.structure_notes]
        merged = self._prose_compactor(
            api_key,
            model,
            compact_prose=prior_prose,
            structure_notes=note_texts,
            label=f"{self.label} prose compact",
        )
        if not merged.strip():
            return False
        input_parts = []
        if prior_prose:
            input_parts.append(f"## Prior prose\n\n{prior_prose}")
        input_parts.extend(
            f"## Structure note {index + 1}\n\n{text}"
            for index, text in enumerate(note_texts)
        )
        record_prose_compression(
            input_text="\n\n".join(input_parts) if input_parts else merged,
            output=merged,
        )
        self.compact_prose = merged
        self.structure_notes = []
        return True
