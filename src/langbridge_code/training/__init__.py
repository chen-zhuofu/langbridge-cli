"""Training subsystem: trainer for the coder/reviewer workflow.

Eval lives in langbridge_code.eval (bench, metrics, runners). Training imports
eval callables for the self-play loop but does not own them.

Pieces:
  checkpoint.py     — snapshot/restore tools, skills, system_prompt + change summaries
  signals.py        — trajectory signals + batch pattern mining used by the trainer
  gate.py           — applies trainer file edits + acceptance gate
  trainer.py        — outer self-play loop
  optimizer_trace.py — append-only coder↔reviewer trace (also used at runtime)
"""
from langbridge_code.training import checkpoint, gate, signals, trainer

__all__ = ["checkpoint", "gate", "signals", "trainer"]
