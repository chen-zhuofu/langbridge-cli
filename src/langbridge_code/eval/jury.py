"""Offline dispute jury for the trainer when hidden tests are unavailable.

Runtime coder/reviewer loops are a simple back-and-forth (worktrial style).
During training, grade() may return no ground truth — then jury_fn acts as the
correctness anchor via two independent reviewers.
"""
from concurrent.futures import ThreadPoolExecutor

from langbridge_code.tools.agent_worker_reviewer import reviewer_review_passed, run_reviewer

JUROR_COUNT = 2


def juror_context(context, worker_report, worker_label="Worker"):
    parts = []
    if context:
        parts.append(context)
    parts.append(
        f"You are an independent juror. Verify the {worker_label} implementation "
        "on its own merits and vote PASS or FAIL."
    )
    parts.append(f"{worker_label} implementation to verify:\n{worker_report}")
    return "\n\n".join(parts)


def _run_jurors(api_key, model, task, prompt):
    with ThreadPoolExecutor(max_workers=JUROR_COUNT) as pool:
        futures = [
            pool.submit(run_reviewer, api_key, model, task, prompt)
            for _ in range(JUROR_COUNT)
        ]
        return [future.result() for future in futures]


def make_jury_fn(api_key, model):
    """Return jury_fn(spec, trace) -> {jury_pass, verified} for the trainer."""

    def jury_fn(spec, trace):
        task = spec.get("problem_statement") or trace.get("task") or ""
        context = spec.get("context", "")
        report = trace.get("final_report") or trace.get("final_diff") or ""
        if not report.strip():
            rounds = trace.get("rounds") or []
            if rounds:
                report = rounds[-1].get("worker_report") or report
        if not report.strip():
            return {"jury_pass": None, "verified": False}

        prompt = juror_context(context, report, "Worker")
        reports = _run_jurors(api_key, model, task, prompt)
        jury_pass = all(reviewer_review_passed(report) for report in reports)
        return {"jury_pass": jury_pass, "verified": True}

    return jury_fn
