"""Append role-scoped skill catalogs to agent system prompts (names only — no tool usage)."""


def append_role_playbooks(base: str, catalog: str, *, task_type: str | None = None) -> str:
    if not catalog.strip():
        return base
    header = f"Task type: {task_type}.\n" if task_type else ""
    return base + f"\n\n{header}Role playbooks:\n{catalog}"
