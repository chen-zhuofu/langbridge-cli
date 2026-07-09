# Eval: benchmark grading and agent evaluation

Eval is independent from `langbridge_code.training` (the trainer). Training imports
eval callables for its self-play loop but does not own this stack.

## Pieces

- `bench.py` — test-based ground-truth judge (F2P/P2P over hidden tests)
- `metrics.py` — `compute_metrics` + `record_result` + leaderboard
- `langbridge_bench.py` — langbridge-bench dataset adapter
- `jury.py` — offline jury when hidden tests are unavailable
- `reviewer_cases.py` — gold / no-fix reviewer cases from task specs
- `runner.py` — pure eval orchestration over injected callables
- `agents_adapter.py` + `_run_layer.py` — drive real agents in a git worktree

## How to run

```bash
export GITHUB_TOKEN=...                             # optional
export LANGBRIDGE_MODEL=...                         # agent model

uv run python -m langbridge_code.eval.cli eval --role coder --limit 5
uv run python -m langbridge_code.eval.cli eval --role reviewer --limit 5
uv run python -m langbridge_code.eval.cli eval --role loop --limit 5
uv run python -m langbridge_code.eval.cli eval --role workflow --limit 5

python -m langbridge_code.training.cli restore --label step0_baseline \
  uv run python -m langbridge_code.eval.cli eval --role reviewer
```

Default task source: on-disk specs in `evals/langbridge-bench/specs/`
(`--source langbridge-bench`; `swebench` is a backward-compat alias). Use
`--source local` + `LANGBRIDGE_TARGET_REPO` for a git repo with cached specs.

Local git repo + specs cache:

```bash
export LANGBRIDGE_TARGET_REPO=./arrow
export LANGBRIDGE_SPECS_DIR=training/specs

uv run python -m langbridge_code.eval.cli specs --issues training/issues.json
uv run python -m langbridge_code.eval.cli eval --role coder --limit 5 --source local
```

`issues.json` is a list of `{task_id, fix_commit, title, body_summary, hard?}`.

For the trainer (self-play training), use `langbridge_code.training.cli` instead.
