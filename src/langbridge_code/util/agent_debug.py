"""Thread-local agent label/instance for trace and debug attribution."""
from __future__ import annotations

import threading

_current = threading.local()


def set_agent_debug(label: str, instance_id: int | None) -> None:
    _current.label = label
    _current.instance_id = instance_id


def get_agent_debug() -> tuple[str, int | None]:
    return getattr(_current, "label", "Agent"), getattr(_current, "instance_id", None)
