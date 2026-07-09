from langbridge_code.context.structure_note import (
    STRUCTURE_NOTE_PREFIX,
    normalize_structure_note_text,
    parse_structure_note_filename,
    unwrap_structure_note_content,
)


def test_normalize_structure_note_text_keeps_markdown():
    raw = "## Meta\n- agent: worker\n\n## Edits to files\n- **a.py** (step 1): fix"
    normalized = normalize_structure_note_text(raw)
    assert normalized.startswith("## Meta")
    assert "a.py" in normalized


def test_unwrap_structure_note_content():
    body = "## Blockers\n- none"
    wrapped = STRUCTURE_NOTE_PREFIX + body
    assert unwrap_structure_note_content(wrapped) == body


def test_parse_structure_note_filename():
    assert parse_structure_note_filename("structure_0001_r1-4.md") == (1, 1, 4)
    assert parse_structure_note_filename("structure_0002_r5-8.md") == (2, 5, 8)
    assert parse_structure_note_filename("structure_0002_r5-8.json") is None
