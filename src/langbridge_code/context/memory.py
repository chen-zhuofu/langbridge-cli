"""Persist and load structure notes and compact prose."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from langbridge_code.context.structure_note import parse_structure_note_filename


@dataclass
class StructureNote:
    id: int
    round_start: int
    round_end: int
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PersistedState:
    compact_prose: str | None
    structure_notes: list[StructureNote]
    next_note_id: int
    covered_through_round: int
    next_live_round: int


def structure_notes_dir(run_log_path, label: str, instance_id=None) -> Path | None:
    """Run-scoped directory for persisted structure notes (shared across turns)."""
    del instance_id
    if run_log_path is None:
        return None
    from langbridge_code.util.agent_worklog import worklog_dir_for_label, worklog_file_prefix

    prefix = worklog_file_prefix(label)
    stem = Path(run_log_path).stem
    return worklog_dir_for_label(label) / stem / prefix / "structure-notes"


def load_persisted_state(persist_dir: Path | None, label: str) -> PersistedState | None:
    """Restore compact prose and structure notes written under persist_dir."""
    del label
    if persist_dir is None or not persist_dir.is_dir():
        return None

    notes_by_id: dict[int, StructureNote] = {}
    prose: str | None = None
    prose_next_round = 0

    prose_path = persist_dir / "prose_compact.json"
    if prose_path.is_file():
        payload = json.loads(prose_path.read_text(encoding="utf-8"))
        prose = payload.get("text") or prose
        prose_next_round = max(prose_next_round, int(payload.get("next_live_round") or 0))

    for path in sorted(persist_dir.glob("structure_*.md")):
        parsed = parse_structure_note_filename(path.name)
        if parsed is None:
            continue
        note_id, round_start, round_end = parsed
        notes_by_id[note_id] = StructureNote(
            id=note_id,
            round_start=round_start,
            round_end=round_end,
            text=path.read_text(encoding="utf-8").strip(),
        )

    if not notes_by_id and not (prose and prose.strip()):
        return None

    structure_notes = [notes_by_id[key] for key in sorted(notes_by_id)]
    next_note_id = max(note.id for note in structure_notes) + 1 if structure_notes else 1
    covered = prose_next_round - 1 if prose_next_round > 0 else 0
    if structure_notes:
        covered = max(covered, max(note.round_end for note in structure_notes))
    next_live_round = covered + 1 if covered > 0 else 1

    return PersistedState(
        compact_prose=prose.strip() if prose and prose.strip() else None,
        structure_notes=structure_notes,
        next_note_id=next_note_id,
        covered_through_round=covered,
        next_live_round=next_live_round,
    )


def persist_note(persist_dir: Path | None, note: StructureNote) -> None:
    if persist_dir is None:
        return
    persist_dir.mkdir(parents=True, exist_ok=True)
    path = persist_dir / f"structure_{note.id:04d}_r{note.round_start}-{note.round_end}.md"
    path.write_text(note.text.strip() + "\n", encoding="utf-8")


def persist_prose_compact(persist_dir: Path | None, prose: str, *, next_live_round: int) -> None:
    if persist_dir is None:
        return
    persist_dir.mkdir(parents=True, exist_ok=True)
    path = persist_dir / "prose_compact.json"
    payload = {
        "text": prose,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "next_live_round": next_live_round,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
