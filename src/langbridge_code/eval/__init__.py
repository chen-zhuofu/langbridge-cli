"""Eval subsystem: benchmark grading, metrics, and agent eval runners.

Independent from training (the trainer). Training imports eval callables and
graders but does not own the eval stack.

Pieces:
  bench.py            — ground-truth grader (F2P/P2P over hidden tests)
  metrics.py          — compute_metrics + record/report for eval types
  langbridge_bench.py — langbridge-bench dataset adapter
  jury.py             — offline jury when hidden tests are unavailable
  reviewer_cases.py   — build reviewer eval cases from task specs
  runner.py           — pure eval orchestration (injectable agent callables)
  agents_adapter.py   — real-agent callables for eval/train
  _run_layer.py       — subprocess entry: run one agent layer in a worktree
"""
