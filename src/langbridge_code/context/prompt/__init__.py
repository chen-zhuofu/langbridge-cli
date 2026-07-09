"""Context-related LLM system prompts."""
from __future__ import annotations

from langbridge_code.context.prompt.note_builder_explorer import NOTEBUILDER_SYSTEM_PROMPT as EXPLORE_NOTEBUILDER
from langbridge_code.context.prompt.note_builder_langbridge import NOTEBUILDER_SYSTEM_PROMPT as LANGBRIDGE_NOTEBUILDER
from langbridge_code.context.prompt.note_builder_planner import NOTEBUILDER_SYSTEM_PROMPT as PLANNER_NOTEBUILDER
from langbridge_code.context.prompt.note_builder_reviewer import NOTEBUILDER_SYSTEM_PROMPT as REVIEWER_NOTEBUILDER
from langbridge_code.context.prompt.note_builder_worker import NOTEBUILDER_SYSTEM_PROMPT as WORKER_NOTEBUILDER

_ROLE_PROMPTS: dict[str, str] = {
    "worker": WORKER_NOTEBUILDER,
    "reviewer": REVIEWER_NOTEBUILDER,
    "explorer": EXPLORE_NOTEBUILDER,
    "planner": PLANNER_NOTEBUILDER,
    "langbridge": LANGBRIDGE_NOTEBUILDER,
}


def normalize_note_builder_role(label: str) -> str:
    """Extract agent role from ContextStack label (e.g. 'Worker structure note')."""
    token = (label or "").strip().lower().split()[0] if label else ""
    aliases = {
        "explore": "explorer",
    }
    if token in aliases:
        return aliases[token]
    if token in _ROLE_PROMPTS:
        return token
    if token.startswith("worker"):
        return "worker"
    if token.startswith("review"):
        return "reviewer"
    if token.startswith("explor"):
        return "explorer"
    if token.startswith("plann"):
        return "planner"
    if token.startswith("langbridge"):
        return "langbridge"
    return "worker"


def note_builder_system_prompt(label: str) -> str:
    role = normalize_note_builder_role(label)
    return _ROLE_PROMPTS[role]
