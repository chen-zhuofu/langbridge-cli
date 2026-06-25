"""Shared L4<->L3 worklog: the durable record of one review negotiation.

Each turn of the L4<->L3 loop appends an entry that ends with a status token.
The token is what the loop routes on, so the worklog is the loop's memory rather
than a side note. When there is no active run (run_log_path is None, e.g. in unit
tests) the writer is a no-op so it never litters the workspace.
"""


def worklog_path(run_log_path):
    if run_log_path is None:
        return None
    return run_log_path.with_name(f"{run_log_path.stem}.worklog.md")


def start_worklog(run_log_path, task):
    path = worklog_path(run_log_path)
    if path is None:
        return
    _append(path, [f"## L4<->L3 negotiation: {task}", ""])


def append_worklog_entry(run_log_path, role, text, token):
    path = worklog_path(run_log_path)
    if path is None:
        return
    _append(path, [f"### {role}", "", text.strip(), "", f"WORKLOG_TOKEN: {token}", ""])


def _append(path, lines):
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
