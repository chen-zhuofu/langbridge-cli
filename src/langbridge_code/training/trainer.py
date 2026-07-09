"""trainer.py — outer self-play loop that improves agents via direct file edits.

Each batch:
  1. run inner loop under current artifacts,
  2. grade traces,
  3. mine signals,
  4. trainer LLM proposes file_edits to tools/skills/system_prompt,
  5. apply edits (reviewer paths gated without anchor),
  6. acceptance gate re-runs batch — rollback on failure,
  7. checkpoint on schedule (step0 baseline, then every batch/epoch).
"""
import json

from langbridge_code.settings import (
    TRAIN_DEFAULT_BATCH_SIZE,
    TRAIN_DEFAULT_CHECKPOINT_EVERY,
    TRAIN_DEFAULT_EPOCHS,
)
from langbridge_code.training import checkpoint, gate, signals


TRAINER_SYSTEM = """You improve LangBridge Code agents by editing source files directly.

Editable trees (paths relative to the langbridge_code package):
  - tools/           — tool implementations and subagent loops
  - skills/          — SKILL.md playbooks per role
  - agents/system_prompt/ — system prompts for main/planner/worker/reviewer/explorer

You receive batch traces and recurring failure patterns. Propose GENERAL fixes to
base behaviour — not one-off task hacks.

Rules:
- Never reference signals agents cannot see at runtime (hidden tests, ground truth,
  jury verdicts, pass/fail labels). Edits must be actionable from normal runtime.
- Prefer small, surgical edits over rewriting whole files unless necessary.
- Only change reviewer prompts/skills when evidence shows a calibration error.
- Paths must stay under tools/, skills/, or agents/system_prompt/.

Reply with ONLY a JSON object:
{
  "diagnosis": "one sentence on the systemic issue",
  "file_edits": [
    {"path": "agents/system_prompt/worker.py", "content": "<full file content>"},
    {"path": "skills/worker_coder/karpathy_surgical-changes/SKILL.md", "content": "..."}
  ],
  "file_deletes": ["skills/old_skill/SKILL.md"]
}
"""


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _passed_signal(trace):
    passed, _src = signals.trace_oracle(trace)
    return passed


def _finalize(spec, loop_fn, grade, jury_fn=None):
    trace = loop_fn(spec)
    diff = trace.get("final_diff", "")
    g = grade(spec["task_id"], diff)
    approved = bool(trace.get("approved"))
    if g.get("status") == "graded":
        gt = bool(g.get("resolved"))
        trace["labels"] = {
            "gt_pass": gt,
            "reward_hack": approved and not gt,
            "false_block": (not approved) and gt,
            "source": "tests",
        }
    elif jury_fn is not None:
        verdict = jury_fn(spec, trace)
        trace["jury_convened"] = True
        trace["jury_pass"] = verdict.get("jury_pass")
        trace["jury_verified"] = verdict.get("verified", False)
    return trace


def _gate_row(trace):
    return {"approved": bool(trace.get("approved")), "passed": bool(_passed_signal(trace))}


def _batch_evidence(traces, judge=None):
    blocks = []
    for t in traces:
        passed, src = signals.trace_oracle(t)
        resp = signals.responsiveness(t)["score"]
        algn = signals.alignment(t, judge)["score"]
        blocks.append({
            "task": t.get("task", "")[:200],
            "worker": t.get("worker"),
            "rounds": len(t.get("rounds", [])),
            "approved": bool(t.get("approved")),
            "correct": passed,
            "correct_source": src,
            "calibration": signals.calibration(t),
            "responsiveness": resp,
            "alignment": algn,
            "last_comments": (t.get("rounds", [{}])[-1].get("comments", "") or "")[:300],
        })
    return blocks


def build_trainer_prompt(traces, judge=None):
    evidence = _batch_evidence(traces, judge)
    patterns = signals.batch_patterns(traces, judge)
    payload = {
        "batch": evidence,
        "recurring_patterns": patterns,
        "editable_paths": checkpoint.editable_paths_summary()[:200],
    }
    return json.dumps(payload, indent=2)


def process_batch(
    specs,
    *,
    loop_fn,
    grade,
    trainer_fn,
    jury_fn=None,
    judge=None,
    do_gate=True,
    log=None,
    step: int,
    parent_label: str | None,
):
    traces = [_finalize(s, loop_fn, grade, jury_fn) for s in specs]
    old_rows = [_gate_row(t) for t in traces]

    anchor = any(
        (t.get("labels") and t["labels"].get("gt_pass") is not None)
        or (t.get("jury_convened") and t.get("jury_pass") is not None)
        for t in traces
    )

    prompt = build_trainer_prompt(traces, judge)
    proposal = trainer_fn(prompt) or {}

    snapshot = checkpoint.capture_artifacts()
    changes = gate.apply_proposal(proposal, allow_reviewer=anchor)

    result = {
        "step": step,
        "changes": changes,
        "anchor": anchor,
        "accepted": True,
        "old_total": gate.gate_total(old_rows),
        "new_total": gate.gate_total(old_rows),
    }

    if do_gate and checkpoint.has_file_changes(changes):
        new_traces = [_finalize(s, loop_fn, grade, jury_fn) for s in specs]
        new_rows = [_gate_row(t) for t in new_traces]
        accepted, old_total, new_total = gate.accept_change(old_rows, new_rows)
        result.update(accepted=accepted, old_total=old_total, new_total=new_total)
        if not accepted:
            checkpoint.restore_artifacts(snapshot)

    if log is not None:
        log(result)
    return result


def run(
    specs,
    *,
    loop_fn,
    grade,
    trainer_fn,
    jury_fn=None,
    judge=None,
    epochs=TRAIN_DEFAULT_EPOCHS,
    batch_size=TRAIN_DEFAULT_BATCH_SIZE,
    do_gate=True,
    checkpoint_every=TRAIN_DEFAULT_CHECKPOINT_EVERY,
    log=None,
):
    checkpoint.checkpoints_dir().mkdir(parents=True, exist_ok=True)
    parent_label = "step0_baseline"
    checkpoint.save_checkpoint(
        parent_label,
        step=0,
        parent_label=None,
        diagnosis="Training baseline before trainer edits.",
        metrics={"kind": "baseline"},
    )

    results = []
    step = 0
    for epoch in range(1, epochs + 1):
        for bi, batch in enumerate(_chunks(specs, batch_size)):
            step += 1
            res = process_batch(
                batch,
                loop_fn=loop_fn,
                grade=grade,
                trainer_fn=trainer_fn,
                jury_fn=jury_fn,
                judge=judge,
                do_gate=do_gate,
                log=log,
                step=step,
                parent_label=parent_label,
            )
            res["epoch"] = epoch
            res["batch_index"] = bi
            results.append(res)

            if checkpoint_every == "batch" and (res["accepted"] or not do_gate):
                ids = "-".join(str(s["task_id"]) for s in batch)[:40]
                label = f"step{step}_e{epoch}_b{bi}_{ids}"
                checkpoint.save_checkpoint(
                    label,
                    step=step,
                    parent_label=parent_label,
                    diagnosis=(res.get("changes") or {}).get("diagnosis", ""),
                    proposal_changes=res.get("changes"),
                    metrics={
                        "accepted": res["accepted"],
                        "old_total": res["old_total"],
                        "new_total": res["new_total"],
                    },
                )
                parent_label = label

        if checkpoint_every == "epoch":
            label = f"step{step}_epoch{epoch}"
            checkpoint.save_checkpoint(
                label,
                step=step,
                parent_label=parent_label,
                metrics={"epoch": epoch, "batches": len(results)},
            )
            parent_label = label
    return results


def make_trainer_fn(api_key, model):
    from langbridge_code.llm.client import create_model_response

    def trainer_fn(prompt):
        data = create_model_response(
            api_key,
            model,
            [
                {"role": "system", "content": TRAINER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            label="trainer",
        )
        text = _extract_text(data)
        return _parse_json(text)

    return trainer_fn


def _extract_text(data):
    parts = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    parts.append(c.get("text", ""))
    return "".join(parts)


def _parse_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
