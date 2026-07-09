"""Merge structure notes and compact prose into one handoff block."""
from __future__ import annotations

from langbridge_code.context.prompt.structure_prose import STRUCTURE_PROSE_SYSTEM
from langbridge_code.llm.parse import extract_output_text, truncate_text
from langbridge_code.settings import STRUCTURE_PROSE_TARGET_CHARS

COMPACT_PROSE_PREFIX = "[CONTEXT_COMPACT]\n"


def compact_structure_notes_to_prose(
    api_key: str,
    model: str,
    *,
    compact_prose: str | None,
    structure_notes: list[str],
    label: str = "structure prose compact",
) -> str:
    """Merge existing compact prose and structure notes into one prose block."""
    from langbridge_code.llm.client import create_model_response

    parts: list[str] = []
    if compact_prose and compact_prose.strip():
        parts.append("Existing compact context:\n" + compact_prose.strip())
    for index, note in enumerate(structure_notes, start=1):
        parts.append(f"Structure note {index}:\n{note.strip()}")
    if not parts:
        return compact_prose or ""

    prompt = "Merge the following into one compact handoff note:\n\n" + "\n\n---\n\n".join(parts)
    data = create_model_response(
        api_key,
        model,
        [
            {"role": "system", "content": STRUCTURE_PROSE_SYSTEM},
            {"role": "user", "content": truncate_text(prompt, 120_000)},
        ],
        label=label,
    )
    text = extract_output_text(data.get("output", [])).strip()
    if not text:
        return compact_prose or "\n\n".join(structure_notes)
    return truncate_text(text, STRUCTURE_PROSE_TARGET_CHARS)
