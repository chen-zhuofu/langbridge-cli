"""Training subsystem: eval + evolver for the coder/reviewer workflow.

Ported (distilled) from the neighbouring coder/reviewer self-play worktrial and
mapped onto this repo's workflow roles:

  neighbour          this repo
  ---------          ---------
  coder              Coder (implements and writes tests)
  reviewer           Reviewer (verifies coder work)
  loop               Coder↔Reviewer inner review loop
  (no analog)        Full workflow (router → planner → todo → specialists)

Pieces:
  metrics.py  — compute_metrics + record/report for eval types
  signals.py  — trajectory signals + batch pattern mining used by the evolver
  bench.py    — pluggable ground-truth grader (F2P/P2P over hidden tests)
  gate.py     — acceptance-gate scoring + applying an evolver proposal to a policy
  evals/      — eval runners that drive the real agents (injectable for tests)
  evolver.py  — the outer self-play loop that improves the agents via the policy
"""
