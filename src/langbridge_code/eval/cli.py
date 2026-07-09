"""cli.py — run evals against workflow roles.

Examples (after setting the target repo + specs, see eval/README.md):

  # Evaluate one role on the spec set under the current policy:
  LANGBRIDGE_TARGET_REPO=./arrow LANGBRIDGE_SPECS_DIR=evals/langbridge-bench/specs \\
    python -m langbridge_code.eval.cli eval --role coder --limit 5

  # Evaluate against a frozen artifact checkpoint (restore first, or set LANGBRIDGE_ARTIFACT_ROOT):
  python -m langbridge_code.training.cli restore --label step0_baseline \\
    python -m langbridge_code.eval.cli eval --role reviewer
"""
import argparse
import os

from langbridge_code.training import checkpoint
from langbridge_code.eval import agents_adapter, bench, langbridge_bench, metrics, reviewer_cases, runner
from langbridge_code.settings import DEFAULT_MODEL


def _build(args, model):
    """Return (specs_for(hard), grade, calls) for the chosen task source."""
    source = getattr(args, "source", "langbridge-bench")
    if source == "swebench":
        source = "langbridge-bench"
    if source == "local":
        grade = bench.make_git_grader()
        calls = agents_adapter.make_callables(model=model)

        def specs_for(hard=None):
            return bench.list_specs(hard=hard)
        return specs_for, grade, calls

    ws = langbridge_bench.Workspaces()
    grade = langbridge_bench.make_grader(ws)
    calls = langbridge_bench.make_callables(ws, model=model)

    def specs_for(hard=None):
        return langbridge_bench.specs(hard=hard)
    return specs_for, grade, calls


def _limit(specs, args):
    if not specs:
        raise SystemExit("No specs found. Check the dataset / --source.")
    return specs[: args.limit] if args.limit else specs


def cmd_eval(args):
    model = args.model or os.environ.get("LANGBRIDGE_MODEL", DEFAULT_MODEL)
    specs_for, grade, calls = _build(args, model)
    step = checkpoint.current_step()

    if args.role == "coder":
        rows = runner.eval_coder(_limit(specs_for(), args), coder_fn=calls["coder_fn"], grade=grade)
    elif args.role == "reviewer":
        specs = _limit(specs_for(), args)
        cases = reviewer_cases.reviewer_cases_from_specs(specs, grade)
        print(f"Reviewer: {len(cases)} cases ({len(specs)} tasks × gold + no_fix)")
        rows = runner.eval_reviewer(cases, review_fn=calls["review_fn"])
    elif args.role == "loop":
        rows, _traces = runner.eval_loop(_limit(specs_for(), args), loop_fn=calls["loop_fn"], grade=grade)
    elif args.role == "workflow":
        rows = runner.eval_workflow(_limit(specs_for(), args), workflow_fn=calls["workflow_fn"], grade=grade)
    else:
        raise SystemExit(f"unknown role {args.role}")

    path = metrics.record_result(
        args.role,
        rows,
        model=model,
        dataset=os.environ.get("LANGBRIDGE_TARGET_REPO", ""),
        policy_version=step,
    )
    metrics.write_leaderboard()
    print(f"metrics: {metrics.compute_metrics(args.role, rows)}")
    print(f"recorded: {path}")


def cmd_specs(args):
    import json

    with open(args.issues) as f:
        issues = json.load(f)
    ok, statuses = bench.build_specs(issues)
    print(f"built {ok} ok specs out of {len(issues)} issues")
    for tid, st in statuses.items():
        if st != "ok":
            print(f"  {tid}: {st}")


def main():
    ap = argparse.ArgumentParser(prog="langbridge-eval")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("specs", help="build F2P/P2P specs from a repo's fix commits")
    ps.add_argument("--issues", required=True,
                    help="JSON list of {task_id, fix_commit, title, body_summary, hard?}")
    ps.set_defaults(func=cmd_specs)

    pe = sub.add_parser("eval", help="evaluate one role")
    pe.add_argument("--role", required=True, choices=["coder", "reviewer", "loop", "workflow"])
    pe.add_argument("--source", default="langbridge-bench",
                    choices=["langbridge-bench", "swebench", "local"],
                    help="langbridge-bench (default), swebench (alias), or local git specs")
    pe.add_argument("--model", default=None)
    pe.add_argument("--limit", type=int, default=0)
    pe.set_defaults(func=cmd_eval)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
