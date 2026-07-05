"""Shared worker<->L3 worklog: the durable record of one review negotiation.

Each turn of the review loop appends an entry that ends with a status token. The
token is what the loop routes on, so this shared ledger is the negotiation's
decision record, not a side note.

Every negotiation gets its OWN file -- the parties of one review do not need to
see an earlier review's ledger, so they are never appended together. start_worklog
opens a new numbered file and append_worklog_entry writes to that current one. The
review loop is serial (one open L4<->L3 negotiation, and separately one L5<->L3,
at a time), so a per-(run, worker) "current negotiation" pointer is enough.

Files are grouped per run under the worker that drives the review:
  L4<->L3 -> L4_WORKLOG_DIR/<run>/l34_share_<n>.md
  L5<->L3 -> L5_WORKLOG_DIR/<run>/l45_share_<n>.md
When there is no active run (run_log_path is None, e.g. in unit tests) the writer
is a no-op so it never litters the workspace.
"""

from langbridge_cli import settings


# (run, worker_label) -> negotiations opened so far / the currently open one.
_negotiation_counts = {}
_current_negotiation = {}


def _key(run_log_path, worker_label):
    return (str(run_log_path), worker_label)


def _worklog_dir(worker_label):
    if worker_label == "L5":
        return settings.L5_WORKLOG_DIR
    return settings.L4_WORKLOG_DIR


def _worklog_filename(worker_label, negotiation_id):
    base = "l45_share" if worker_label == "L5" else "l34_share"
    return f"{base}_{negotiation_id}.md"


def worklog_path(run_log_path, worker_label="L4"):
    if run_log_path is None:
        return None
    negotiation_id = _current_negotiation.get(_key(run_log_path, worker_label))
    if negotiation_id is None:
        return None
    run_dir = _worklog_dir(worker_label) / run_log_path.stem
    return run_dir / _worklog_filename(worker_label, negotiation_id)


def start_worklog(run_log_path, task, worker_label="L4"):
    if run_log_path is None:
        return
    key = _key(run_log_path, worker_label)
    negotiation_id = _negotiation_counts.get(key, 0) + 1
    _negotiation_counts[key] = negotiation_id
    _current_negotiation[key] = negotiation_id
    _append(worklog_path(run_log_path, worker_label), [f"## {worker_label}<->L3 negotiation: {task}", ""])


def append_worklog_entry(run_log_path, role, text, token, worker_label="L4"):
    path = worklog_path(run_log_path, worker_label)
    if path is None:
        return
    _append(path, [f"### {role}", "", text.strip(), "", f"WORKLOG_TOKEN: {token}", ""])


def _append(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
