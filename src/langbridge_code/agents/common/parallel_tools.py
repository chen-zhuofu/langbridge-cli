"""Parallel tool-call execution for the main agent loop (not an LLM tool)."""

from concurrent.futures import ThreadPoolExecutor

from langbridge_code.settings import MAX_PARALLEL_TOOL_CALLS, PARALLEL_AGENTS_ENABLED

# Subagent tools safe to run concurrently (read-only explorers, or isolated worktree workers).
PARALLEL_TOOL_NAMES = frozenset(
    {
        "agent_explorer",
        "agent_worker",
        "list_dir",
        "glob",
        "read_file",
        "grep",
        "read_webpage",
        "browse_webpage",
        "read_plan",
        "read_skill",
    }
)


def can_run_tool_calls_in_parallel(tool_calls) -> bool:
    if not PARALLEL_AGENTS_ENABLED:
        return False
    if len(tool_calls) < 2:
        return False
    return all(call.get("name") in PARALLEL_TOOL_NAMES for call in tool_calls)


def run_tool_calls(run_fn, tool_calls, *, max_workers: int | None = None):
    """Run tool calls in parallel when every call is in PARALLEL_TOOL_NAMES."""
    if not can_run_tool_calls_in_parallel(tool_calls):
        return [run_fn(call) for call in tool_calls]

    limit = max_workers if max_workers is not None else MAX_PARALLEL_TOOL_CALLS
    workers = max(1, min(len(tool_calls), limit))
    outputs = [None] * len(tool_calls)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_fn, call) for call in tool_calls]
        for index, future in enumerate(futures):
            outputs[index] = future.result()
    return outputs
