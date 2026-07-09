# Training: trainer for the workflow agents

Eval lives in `langbridge_code.eval`. Training imports eval callables for grading
and agent wiring but only owns the self-play trainer loop.

## What `train` optimizes

The trainer **directly edits** live agent artifacts:

- `src/langbridge_code/tools/`
- `src/langbridge_code/skills/`
- `src/langbridge_code/agents/system_prompt/`

Before step 0 it saves `step0_baseline`. After each accepted batch (or each epoch,
depending on `--checkpoint-every`), it saves a checkpoint under
`<repo>/training/checkpoints/<label>/` with:

- full copies of the three trees
- `meta.json` — step, diagnosis, and a summary of file changes vs the parent checkpoint

Restore anytime:

```bash
python -m langbridge_code.training.cli restore --label step0_baseline
python -m langbridge_code.training.cli list-checkpoints
```

## What is built (and tested)

Pure, unit-tested logic (see `tests/unit/test_training_*.py`):

- `training/checkpoint.py` — snapshot, restore, diff, apply file edits
- `signals.py` — responsiveness, alignment, calibration, batch pattern mining
- `gate.py` — applies trainer proposals + acceptance gate
- `trainer.py` — outer self-play loop
- `optimizer_trace.py` — append-only coder↔reviewer trace

## How to run

```bash
export GITHUB_TOKEN=...                             # optional
export LANGBRIDGE_MODEL=...                         # agent model

uv run python -m langbridge_code.training.cli train --epochs 1 --batch-size 2

# Eval commands:
uv run python -m langbridge_code.eval.cli eval --role coder --limit 5
```

Local git repo + specs cache:

```bash
export LANGBRIDGE_TARGET_REPO=./arrow
export LANGBRIDGE_SPECS_DIR=training/specs

uv run python -m langbridge_code.eval.cli specs --issues training/issues.json
uv run python -m langbridge_code.training.cli train --epochs 1 --batch-size 2 --source local
```
