"""Thread-local workspace root for parallel worktree workers (not an LLM tool)."""
import threading
from contextlib import contextmanager
from pathlib import Path

_tls = threading.local()


def get_workspace_root() -> Path:
    if hasattr(_tls, "root"):
        return _tls.root
    from langbridge_code.settings import WORKSPACE_ROOT

    return Path(WORKSPACE_ROOT).resolve()


def set_workspace_root(path: Path | None) -> None:
    if path is None:
        if hasattr(_tls, "root"):
            delattr(_tls, "root")
    else:
        _tls.root = path.resolve()


@contextmanager
def workspace_scope(path: Path):
    previous = getattr(_tls, "root", None)
    set_workspace_root(path)
    try:
        yield path.resolve()
    finally:
        if previous is None:
            set_workspace_root(None)
        else:
            set_workspace_root(previous)
