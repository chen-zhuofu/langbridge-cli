"""cli.py — run the trainer (self-play training loop).

Examples (see training/README.md):

  python -m langbridge_code.training.cli train --epochs 1 --batch-size 2
  python -m langbridge_code.training.cli restore --label step0_baseline
  python -m langbridge_code.training.cli list-checkpoints
"""
import argparse
import os

from langbridge_code.eval import jury
from langbridge_code.eval.cli import _build, _limit
from langbridge_code import settings
from langbridge_code.settings import (
    TRAIN_DEFAULT_BATCH_SIZE,
    TRAIN_DEFAULT_CHECKPOINT_EVERY,
    TRAIN_DEFAULT_EPOCHS,
    load_api_key,
)
from langbridge_code.training import checkpoint, trainer


def cmd_train(args):
    api_key = load_api_key()
    model = args.model or os.environ.get("LANGBRIDGE_MODEL") or settings.DEFAULT_MODEL
    trainer_model = args.trainer_model or model
    specs_for, grade, calls = _build(args, model)
    trainer_fn = trainer.make_trainer_fn(api_key, trainer_model)
    jury_fn = None
    if not args.no_jury:
        jury_fn = jury.make_jury_fn(api_key, model)
    specs = _limit(specs_for(), args)
    results = trainer.run(
        specs,
        loop_fn=calls["loop_fn"],
        grade=grade,
        trainer_fn=trainer_fn,
        jury_fn=jury_fn,
        epochs=args.epochs,
        batch_size=args.batch_size,
        do_gate=not args.no_gate,
        checkpoint_every=args.checkpoint_every,
    )
    accepted = sum(1 for r in results if r["accepted"])
    latest = checkpoint.latest_checkpoint_label()
    print(f"batches: {len(results)}  accepted: {accepted}  latest_checkpoint: {latest}")


def cmd_restore(args):
    meta = checkpoint.restore_checkpoint(args.label)
    lines = meta.get("changes", {}).get("summary_lines") or []
    print(f"Restored checkpoint: {args.label} (step {meta.get('step')})")
    if lines:
        print("Changes in that checkpoint vs its parent:")
        for line in lines[:30]:
            print(f"  {line}")


def cmd_list_checkpoints(_args):
    rows = checkpoint.list_checkpoints()
    if not rows:
        print("No checkpoints found.")
        return
    for meta in rows:
        label = meta.get("label")
        step = meta.get("step")
        saved = meta.get("saved_at")
        n_changed = len(meta.get("changes", {}).get("summary_lines") or [])
        print(f"{label}\tstep={step}\tsaved={saved}\tfiles_changed={n_changed}")


def main():
    ap = argparse.ArgumentParser(prog="langbridge-train")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("train", help="run the trainer (self-play)")
    pt.add_argument(
        "--source",
        default="langbridge-bench",
        choices=["langbridge-bench", "swebench", "local"],
        help="langbridge-bench (default), swebench (alias), or local git specs",
    )
    pt.add_argument("--model", default=None, help="agent model")
    pt.add_argument("--trainer-model", default=None, help="model for the trainer itself")
    pt.add_argument("--epochs", type=int, default=TRAIN_DEFAULT_EPOCHS)
    pt.add_argument("--batch-size", type=int, default=TRAIN_DEFAULT_BATCH_SIZE)
    pt.add_argument("--no-gate", action="store_true", help="skip the acceptance gate")
    pt.add_argument("--no-jury", action="store_true", help="skip offline jury when tests are unavailable")
    pt.add_argument("--checkpoint-every", default=TRAIN_DEFAULT_CHECKPOINT_EVERY, choices=["batch", "epoch"])
    pt.add_argument("--limit", type=int, default=0)
    pt.set_defaults(func=cmd_train)

    pr = sub.add_parser("restore", help="restore tools/skills/system_prompt from a checkpoint")
    pr.add_argument("--label", required=True, help="checkpoint label, e.g. step0_baseline")
    pr.set_defaults(func=cmd_restore)

    pl = sub.add_parser("list-checkpoints", help="list saved training checkpoints")
    pl.set_defaults(func=cmd_list_checkpoints)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
