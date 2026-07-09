"""Checkpoint snapshots of evolvable agent artifacts (tools, skills, system_prompt).

Training edits live files under src/langbridge_code/{tools,skills,agents/system_prompt}.
Each checkpoint stores full copies of those trees plus meta.json (step, changes summary).

Override roots for tests:
  LANGBRIDGE_ARTIFACT_ROOT  — parent of tools/, skills/, agents/system_prompt/
  LANGBRIDGE_CHECKPOINT_DIR — where checkpoints/ are stored (default <repo>/training/checkpoints)
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
from pathlib import Path

ARTIFACT_KEYS = ("tools", "skills", "system_prompt")
_ALLOWED_PREFIXES = ("tools/", "skills/", "agents/system_prompt/")
_REVIEWER_MARKERS = ("agents/system_prompt/reviewer.py", "skills/reviewer_")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def checkpoints_dir() -> Path:
    env = os.environ.get("LANGBRIDGE_CHECKPOINT_DIR")
    if env:
        return Path(env).resolve()
    return _repo_root() / "training" / "checkpoints"


def artifact_roots() -> dict[str, Path]:
    override = os.environ.get("LANGBRIDGE_ARTIFACT_ROOT")
    base = Path(override).resolve() if override else _package_root()
    return {
        "tools": base / "tools",
        "skills": base / "skills",
        "system_prompt": base / "agents" / "system_prompt",
    }


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if "__pycache__" in parts:
        return True
    return path.suffix == ".pyc"


def _rel_path(artifact: str, path: Path, root: Path) -> str:
    inner = path.relative_to(root).as_posix()
    if artifact == "system_prompt":
        return f"agents/system_prompt/{inner}"
    return f"{artifact}/{inner}"


def _resolve_rel_path(rel_path: str) -> Path:
    rel = rel_path.replace("\\", "/").lstrip("/")
    if not any(rel.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        raise ValueError(f"Path not under evolvable artifacts: {rel_path}")
    if ".." in rel.split("/"):
        raise ValueError(f"Invalid path: {rel_path}")
    roots = artifact_roots()
    if rel.startswith("tools/"):
        return roots["tools"] / rel[len("tools/") :]
    if rel.startswith("skills/"):
        return roots["skills"] / rel[len("skills/") :]
    return roots["system_prompt"] / rel[len("agents/system_prompt/") :]


def list_live_files() -> dict[str, str]:
    """Map relative artifact path -> file text."""
    out: dict[str, str] = {}
    for key, root in artifact_roots().items():
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and not _should_skip(path):
                rel = _rel_path(key, path, root)
                out[rel] = path.read_text(encoding="utf-8")
    return out


def capture_artifacts() -> dict[str, str]:
    return dict(list_live_files())


def restore_artifacts(files: dict[str, str]) -> None:
    """Replace live artifact files with an in-memory snapshot."""
    current = list_live_files()
    for rel in sorted(set(current) - set(files)):
        path = _resolve_rel_path(rel)
        if path.exists():
            path.unlink()
    for rel, content in files.items():
        path = _resolve_rel_path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _prune_empty_dirs()


def _prune_empty_dirs() -> None:
    for root in artifact_roots().values():
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def summarize_file_changes(before: dict[str, str], after: dict[str, str]) -> dict:
    before_keys = set(before)
    after_keys = set(after)
    added = sorted(after_keys - before_keys)
    deleted = sorted(before_keys - after_keys)
    modified = sorted(
        rel for rel in before_keys & after_keys if before[rel] != after[rel]
    )
    by_area = {"tools": [], "skills": [], "system_prompt": []}
    for rel in added + modified + deleted:
        if rel.startswith("tools/"):
            area = "tools"
        elif rel.startswith("skills/"):
            area = "skills"
        else:
            area = "system_prompt"
        if rel in added:
            by_area[area].append(f"+ {rel}")
        elif rel in deleted:
            by_area[area].append(f"- {rel}")
        else:
            by_area[area].append(f"~ {rel}")
    return {
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "summary_lines": [line for area in by_area.values() for line in area],
        "by_area": by_area,
    }


def _checkpoint_path(label: str) -> Path:
    safe = label.replace("/", "_")
    return checkpoints_dir() / safe


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    if src.is_dir():
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)


def _load_checkpoint_files(label: str) -> dict[str, str]:
    base = _checkpoint_path(label)
    files: dict[str, str] = {}
    for key in ARTIFACT_KEYS:
        src = base / key
        if not src.is_dir():
            continue
        for path in src.rglob("*"):
            if path.is_file() and not _should_skip(path):
                rel = _rel_path(key, path, src)
                files[rel] = path.read_text(encoding="utf-8")
    return files


def save_checkpoint(
    label: str,
    *,
    step: int,
    parent_label: str | None = None,
    diagnosis: str = "",
    proposal_changes: dict | None = None,
    metrics: dict | None = None,
) -> Path:
    """Write tools/skills/system_prompt trees and meta.json for `label`."""
    dest = _checkpoint_path(label)
    dest.mkdir(parents=True, exist_ok=True)
    roots = artifact_roots()
    for key in ARTIFACT_KEYS:
        _copy_tree(roots[key], dest / key)

    live = list_live_files()
    parent_files = _load_checkpoint_files(parent_label) if parent_label else {}
    changes = summarize_file_changes(parent_files, live) if parent_label else summarize_file_changes({}, live)

    meta = {
        "label": label,
        "step": step,
        "parent": parent_label,
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "diagnosis": diagnosis,
        "changes": changes,
        "proposal": proposal_changes or {},
        "metrics": metrics or {},
        "file_hashes": {rel: _file_hash(text) for rel, text in live.items()},
    }
    with open(dest / "meta.json", "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    state = {"latest": label, "step": step}
    with open(checkpoints_dir() / "state.json", "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    return dest


def restore_checkpoint(label: str) -> dict:
    """Restore live artifacts from a saved checkpoint. Returns meta.json."""
    src = _checkpoint_path(label)
    meta_path = src / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"No checkpoint '{label}' under {checkpoints_dir()}")
    files = _load_checkpoint_files(label)
    restore_artifacts(files)
    with open(meta_path, encoding="utf-8") as handle:
        return json.load(handle)


def list_checkpoints() -> list[dict]:
    root = checkpoints_dir()
    if not root.is_dir():
        return []
    out = []
    for path in root.iterdir():
        meta = path / "meta.json"
        if path.is_dir() and meta.exists():
            with open(meta, encoding="utf-8") as handle:
                out.append(json.load(handle))
    return sorted(out, key=lambda item: item.get("saved_at", ""), reverse=True)


def latest_checkpoint_label() -> str | None:
    state_path = checkpoints_dir() / "state.json"
    if state_path.exists():
        with open(state_path, encoding="utf-8") as handle:
            return json.load(state_path).get("latest")
    checkpoints = list_checkpoints()
    return checkpoints[0]["label"] if checkpoints else None


def current_step() -> int:
    state_path = checkpoints_dir() / "state.json"
    if state_path.exists():
        with open(state_path, encoding="utf-8") as handle:
            return int(json.load(state_path).get("step", 0))
    return 0


def apply_file_edits(proposal: dict, *, allow_reviewer: bool = True) -> dict:
    """Apply trainer file edits to live artifacts. Returns a change record."""
    changes: dict = {"diagnosis": (proposal.get("diagnosis") or "").strip()}
    written: list[str] = []
    deleted: list[str] = []
    skipped: list[str] = []

    for edit in proposal.get("file_edits") or []:
        if not isinstance(edit, dict):
            continue
        rel = (edit.get("path") or "").replace("\\", "/").lstrip("/")
        content = edit.get("content")
        if not rel or content is None:
            continue
        if not allow_reviewer and _is_reviewer_path(rel):
            skipped.append(f"{rel}: reviewer edit blocked (no anchor)")
            continue
        path = _resolve_rel_path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)

    for rel in proposal.get("file_deletes") or []:
        rel = str(rel).replace("\\", "/").lstrip("/")
        if not rel:
            continue
        if not allow_reviewer and _is_reviewer_path(rel):
            skipped.append(f"{rel}: reviewer delete blocked (no anchor)")
            continue
        path = _resolve_rel_path(rel)
        if path.exists():
            path.unlink()
            deleted.append(rel)

    if written:
        changes["written"] = written
    if deleted:
        changes["deleted"] = deleted
    if skipped:
        changes["skipped"] = skipped
    return changes


def _is_reviewer_path(rel_path: str) -> bool:
    return any(marker in rel_path for marker in _REVIEWER_MARKERS)


def editable_paths_summary() -> list[str]:
    return sorted(list_live_files())


def has_file_changes(changes: dict) -> bool:
    return bool(changes.get("written") or changes.get("deleted"))
