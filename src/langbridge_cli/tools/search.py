"""Ripgrep-backed search tools with Kimi and OpenAI Codex-compatible handlers."""

import json
import shutil
import subprocess
from pathlib import Path

from langbridge_cli.tools.filesystem import WORKSPACE_ROOT, resolve_workspace_path

DEFAULT_GLOB_LIMIT = 100
DEFAULT_GREP_LIMIT = 250
RG_TIMEOUT_SECONDS = 60

TOOLS = {}


def tool(name):
    def register(function):
        TOOLS[name] = function
        return function

    return register


def _rg_binary():
    rg = shutil.which("rg")
    if not rg:
        raise RuntimeError(
            "ripgrep (rg) is required for search tools but was not found on PATH. "
            "Install ripgrep or use execute_program."
        )
    return rg


def _run_rg(args):
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=RG_TIMEOUT_SECONDS,
    )
    if result.returncode not in (0, 1):
        detail = (result.stderr or result.stdout or "rg failed").strip()
        raise RuntimeError(detail)
    return result.stdout


def _relative_workspace_path(path):
    resolved = Path(path).resolve()
    return str(resolved.relative_to(WORKSPACE_ROOT))


def _glob_impl(pattern, path=".", limit=DEFAULT_GLOB_LIMIT, include_ignored=False):
    if not pattern:
        raise ValueError("pattern must not be empty")

    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"No such path: {path}")

    limit = max(1, min(int(limit), 500))
    args = [_rg_binary(), "--files", "--glob", pattern]
    if include_ignored:
        args.append("--no-ignore")
    args.append(str(target))

    stdout = _run_rg(args)
    ranked = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        file_path = Path(line.strip()).resolve()
        try:
            rel = str(file_path.relative_to(WORKSPACE_ROOT))
        except ValueError:
            continue
        ranked.append((file_path.stat().st_mtime, rel))

    ranked.sort(key=lambda item: item[0], reverse=True)
    matches = [rel for _, rel in ranked[:limit]]
    return json.dumps(
        {
            "pattern": pattern,
            "path": path,
            "matches": matches,
            "truncated": len(ranked) > limit,
        },
        ensure_ascii=False,
        indent=2,
    )


def _grep_impl(
    pattern,
    path=".",
    *,
    glob_pattern=None,
    file_type=None,
    output_mode="files_with_matches",
    before_context=None,
    after_context=None,
    context=None,
    line_number=True,
    ignore_case=False,
    head_limit=DEFAULT_GREP_LIMIT,
    offset=0,
    multiline=False,
    include_ignored=False,
):
    if not pattern:
        raise ValueError("pattern must not be empty")
    if output_mode not in {"content", "files_with_matches", "count_matches"}:
        raise ValueError(
            "output_mode must be 'content', 'files_with_matches', or 'count_matches'"
        )

    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"No such path: {path}")

    offset = max(0, int(offset))
    unlimited = int(head_limit) == 0
    head_limit = DEFAULT_GREP_LIMIT if unlimited else max(1, min(int(head_limit), 1000))
    fetch_limit = head_limit + offset if not unlimited else None

    args = [_rg_binary(), "--color=never", "--hidden"]
    if include_ignored:
        args.append("--no-ignore")
    for vcs_dir in (".git", ".svn", ".hg", ".bzr"):
        args.extend(["--glob", f"!{vcs_dir}/"])

    if ignore_case:
        args.append("-i")
    if multiline:
        args.extend(["-U", "--multiline-dotall"])
    if glob_pattern:
        args.extend(["--glob", glob_pattern])
    if file_type:
        args.extend(["--type", file_type])

    if output_mode == "content":
        if before_context is not None:
            args.extend(["-B", str(before_context)])
        if after_context is not None:
            args.extend(["-A", str(after_context)])
        if context is not None:
            args.extend(["-C", str(context)])
        if line_number:
            args.append("-n")
        if fetch_limit is not None:
            args.extend(["--max-count", str(fetch_limit)])
    elif output_mode == "files_with_matches":
        args.append("-l")
    else:
        args.append("-c")

    args.extend(["--", pattern, str(target)])
    stdout = _run_rg(args)
    lines = [line for line in stdout.splitlines() if line.strip()]

    if offset:
        lines = lines[offset:]
    if fetch_limit is not None:
        lines = lines[:head_limit]

    if output_mode == "files_with_matches":
        files = []
        for line in lines:
            try:
                files.append(_relative_workspace_path(line.strip()))
            except ValueError:
                continue
        payload = {"pattern": pattern, "path": path, "files": files}
    elif output_mode == "count_matches":
        counts = []
        for line in lines:
            parts = line.rsplit(":", 1)
            if len(parts) != 2:
                continue
            file_path, count_text = parts
            try:
                rel = _relative_workspace_path(file_path)
                counts.append({"path": rel, "count": int(count_text)})
            except ValueError:
                continue
        payload = {"pattern": pattern, "path": path, "counts": counts}
    else:
        matches = []
        for line in lines:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            file_path, line_no, text = parts
            try:
                rel = _relative_workspace_path(file_path)
            except ValueError:
                continue
            matches.append({"path": rel, "line": int(line_no), "text": text})
        payload = {"pattern": pattern, "path": path, "matches": matches}

    raw_count = len(stdout.splitlines())
    payload["truncated"] = not unlimited and raw_count > (offset + head_limit)
    return json.dumps(payload, ensure_ascii=False, indent=2)


@tool("Grep")
def kimi_grep(
    pattern,
    path=".",
    glob=None,
    type=None,
    output_mode="files_with_matches",
    head_limit=DEFAULT_GREP_LIMIT,
    offset=0,
    multiline=False,
    include_ignored=False,
    **kwargs,
):
    return _grep_impl(
        pattern,
        path,
        glob_pattern=glob,
        file_type=type,
        output_mode=output_mode,
        before_context=kwargs.get("-B"),
        after_context=kwargs.get("-A"),
        context=kwargs.get("-C"),
        line_number=kwargs.get("-n", True),
        ignore_case=kwargs.get("-i", False),
        head_limit=head_limit,
        offset=offset,
        multiline=multiline,
        include_ignored=include_ignored,
    )


@tool("Glob")
def kimi_glob(pattern, path=".", include_ignored=False):
    return _glob_impl(pattern, path=path, include_ignored=include_ignored)


@tool("grep_files")
def openai_grep_files(pattern, path=".", include=None, limit=DEFAULT_GLOB_LIMIT):
    return _grep_impl(
        pattern,
        path,
        glob_pattern=include,
        output_mode="files_with_matches",
        head_limit=limit,
    )


@tool("glob_file_search")
def openai_glob_file_search(pattern, path=".", limit=DEFAULT_GLOB_LIMIT):
    return _glob_impl(pattern, path=path, limit=limit)
