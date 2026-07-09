"""STRUCT_NOTE formatting and LLM note building."""
from __future__ import annotations

import json
import re

from langbridge_code.context.prompt import note_builder_system_prompt
from langbridge_code.llm.parse import extract_output_text, truncate_text
from langbridge_code.settings import STRUCTURE_NOTE_TARGET_CHARS

STRUCTURE_NOTE_PREFIX = "STRUCTURE_NOTE\n"

_MD_FENCE_RE = re.compile(r"```(?:markdown|md)?\s*([\s\S]*?)```", re.IGNORECASE)
_STRUCTURE_NOTE_FILENAME_RE = re.compile(
    r"structure_(\d+)_r(\d+)-(\d+)\.md$",
    re.IGNORECASE,
)


def unwrap_structure_note_content(content: str) -> str | None:
    if content.startswith(STRUCTURE_NOTE_PREFIX):
        return content[len(STRUCTURE_NOTE_PREFIX) :]
    return None


def parse_structure_note_filename(name: str) -> tuple[int, int, int] | None:
    match = _STRUCTURE_NOTE_FILENAME_RE.match(name)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def normalize_structure_note_text(text: str) -> str:
    """Normalize LLM output to canonical STRUCT_NOTE markdown text."""
    stripped = (text or "").strip()
    if not stripped:
        return ""
    fence = _MD_FENCE_RE.search(stripped)
    if fence:
        stripped = fence.group(1).strip()
    body = stripped
    if len(body) <= STRUCTURE_NOTE_TARGET_CHARS:
        return body
    return body[:STRUCTURE_NOTE_TARGET_CHARS] + "..."


def _serialize_rounds(rounds: list[list[dict]]) -> str:
    payload = [{"round": index + 1, "messages": round_messages} for index, round_messages in enumerate(rounds)]
    return truncate_text(json.dumps(payload, ensure_ascii=False, indent=2), 120_000)


def build_structure_note(
    api_key: str,
    model: str,
    rounds: list[list[dict]],
    *,
    label: str = "structure note",
) -> str:
    """Call LLM to write a STRUCT_NOTE markdown note from raw message rounds."""
    from langbridge_code.llm.client import create_model_response

    if not rounds:
        return ""
    prompt = (
        "Write a STRUCT_NOTE markdown note for these conversation rounds:\n\n"
        f"{_serialize_rounds(rounds)}"
    )
    data = create_model_response(
        api_key,
        model,
        [
            {"role": "system", "content": note_builder_system_prompt(label)},
            {"role": "user", "content": prompt},
        ],
        label=label,
    )
    text = extract_output_text(data.get("output", [])).strip()
    if not text:
        return ""
    return normalize_structure_note_text(text)
