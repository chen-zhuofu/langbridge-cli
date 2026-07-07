# Training: eval + evolver for the workflow agents

The evolver improves **Coder** and **Reviewer** policy from optimizer trace JSONL
files under `agent-state/workflow/optimizer-traces/`.

## What `train` optimizes today

- `train` runs the **coder↔reviewer** loop (`loop_fn`), reconstructs rounds from
  optimizer trace JSONL, grades final diffs with hidden tests, and proposes updates
  to coder/reviewer guidance.
- Full **workflow** trace mining (router/planner/presenter) is still evolving.
  Eval hooks accept `--role` values: `coder`, `reviewer`, `loop`, `workflow`.

Default task source for eval/train: on-disk specs in `evals/langbridge-bench/specs/`
(`--source langbridge-bench`; `swebench` is a backward-compat alias). Use
`--source local` + `LANGBRIDGE_TARGET_REPO` for a git repo with cached specs.


## What is built (and tested)

Pure, unit-tested logic (no API/model needed — see `tests/unit/test_training_*.py`):

- `policy.py` (in the package root) — the mutable policy the evolver writes and the
  roles read. Guidance per role (`router/planner/coder/reviewer/presenter`), skills
  (reuses the existing `read_skill` tool), checkpoints.
- `metrics.py` — `compute_metrics` + `record_result` + leaderboard for eval types
  (`coder`, `reviewer`, `loop`, `workflow`).
- `signals.py` — responsiveness, alignment, calibration, and batch pattern mining.
- `bench.py` — the test-based ground-truth judge (F2P/P2P over hidden tests).
- `gate.py` — applies an evolver proposal to the policy (with the **reviewer anchor
  gate**) and the **acceptance gate**.
- `evals/runner.py` — eval runners as pure orchestration over injected callables.
- `reviewer_cases.py` — expands each task spec into gold / no-fix reviewer cases.
- `evolver.py` — the outer self-play loop.

Integration wiring:

- `evals/agents_adapter.py` + `evals/_run_layer.py` — drive the real agents in a
  subprocess whose cwd is a fresh git worktree at the task's base commit.
- `cli.py` — `specs`, `eval`, and `train` commands.

## How to run

```bash
export GITHUB_TOKEN=...                             # optional
export LANGBRIDGE_MODEL=...                         # agent model

uv run python -m langbridge_code.training.cli eval --role coder --limit 5
uv run python -m langbridge_code.training.cli eval --role reviewer --limit 5
uv run python -m langbridge_code.training.cli eval --role loop --limit 5
uv run python -m langbridge_code.training.cli eval --role workflow --limit 5

uv run python -m langbridge_code.training.cli train --epochs 1 --batch-size 2

LANGBRIDGE_POLICY_DIR=training/policy/checkpoints/epoch1 \
  uv run python -m langbridge_code.training.cli eval --role reviewer
```

Local git repo + specs cache:

```bash
export LANGBRIDGE_TARGET_REPO=./arrow
export LANGBRIDGE_SPECS_DIR=training/specs

uv run python -m langbridge_code.training.cli specs --issues training/issues.json
uv run python -m langbridge_code.training.cli eval --role coder --limit 5 --source local
uv run python -m langbridge_code.training.cli train --epochs 1 --batch-size 2 --source local
```

`issues.json` is a list of `{task_id, fix_commit, title, body_summary, hard?}`.
