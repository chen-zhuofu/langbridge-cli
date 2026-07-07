"""Orchestration tests for the eval runners and the evolver, using stub agents."""
import os
import tempfile

import pytest


def _grade_from_diff(task_id, diff):
    return {"resolved": "FIX" in (diff or ""), "status": "graded"}


def test_eval_runners_with_stubs():
    from langbridge_code.training.evals import runner

    specs = [{"task_id": "t1"}, {"task_id": "t2"}]

    def coder_fn(spec):
        return {"diff": "FIX" if spec["task_id"] == "t1" else "noop\n+x", "turns": 2}

    rows = runner.eval_coder(specs, coder_fn=coder_fn, grade=_grade_from_diff)
    assert [r["gt_pass"] for r in rows] == [True, False]
    assert rows[1]["patch_lines"] == 1

    cases = [
        {"task_id": "t1", "case": "good", "gt_pass": True},
        {"task_id": "t1", "case": "bad", "gt_pass": False},
    ]
    rrows = runner.eval_reviewer(cases, review_fn=lambda c: {"approved": c["gt_pass"]})
    assert all(r["approved"] == r["gt_pass"] for r in rrows)

    def loop_fn(spec):
        return {
            "task": spec["task_id"], "worker": "coder",
            "rounds": [{"round": 1, "diff": "FIX", "approved": True, "comments": ""}],
            "approved": True, "final_diff": "FIX",
        }

    lrows, traces = runner.eval_loop(specs, loop_fn=loop_fn, grade=_grade_from_diff)
    assert all(r["gt_pass"] for r in lrows)
    assert traces[0]["labels"]["gt_pass"] is True


def test_evolver_accepts_improving_change():
    from langbridge_code import policy
    from langbridge_code.training import evolver

    with tempfile.TemporaryDirectory() as d:
        os.environ["LANGBRIDGE_POLICY_DIR"] = d
        try:
            def loop_fn(spec):
                p = policy.load()
                learned = any("surgical fix" in b for b in p["coder"]["guidance"])
                diff = "FIX" if learned else "noop"
                return {
                    "task": spec["task_id"], "worker": "coder",
                    "rounds": [{"round": 1, "diff": diff, "approved": True, "comments": ""}],
                    "approved": True, "final_diff": diff,
                }

            def evolve_fn(prompt):
                return {"diagnosis": "implementer flailing",
                        "coder_guidance_add": ["Make a surgical fix to the failing function."]}

            results = evolver.run(
                [{"task_id": "t1"}, {"task_id": "t2"}],
                loop_fn=loop_fn, grade=_grade_from_diff, evolve_fn=evolve_fn,
                epochs=1, batch_size=2, do_gate=True, checkpoint_every="batch",
            )
            assert len(results) == 1
            res = results[0]
            assert res["accepted"] is True
            assert res["new_total"] > res["old_total"]
            p = policy.load()
            assert any("surgical fix" in b for b in p["coder"]["guidance"])
            assert policy.list_checkpoints()
        finally:
            del os.environ["LANGBRIDGE_POLICY_DIR"]


def test_evolver_rolls_back_non_improving_change():
    from langbridge_code import policy
    from langbridge_code.training import evolver

    with tempfile.TemporaryDirectory() as d:
        os.environ["LANGBRIDGE_POLICY_DIR"] = d
        try:
            def loop_fn(spec):
                return {
                    "task": spec["task_id"], "worker": "coder",
                    "rounds": [{"round": 1, "diff": "noop", "approved": True, "comments": ""}],
                    "approved": True, "final_diff": "noop",
                }

            def evolve_fn(prompt):
                return {"coder_guidance_add": ["Some guidance that does nothing useful."]}

            results = evolver.run(
                [{"task_id": "t1"}, {"task_id": "t2"}],
                loop_fn=loop_fn, grade=_grade_from_diff, evolve_fn=evolve_fn,
                epochs=1, batch_size=2, do_gate=True, checkpoint_every="batch",
            )
            res = results[0]
            assert res["accepted"] is False
            p = policy.load()
            assert p["coder"]["guidance"] == []
        finally:
            del os.environ["LANGBRIDGE_POLICY_DIR"]


def test_reviewer_guidance_needs_anchor_in_evolver():
    from langbridge_code import policy
    from langbridge_code.training import evolver

    with tempfile.TemporaryDirectory() as d:
        os.environ["LANGBRIDGE_POLICY_DIR"] = d
        try:
            def loop_fn(spec):
                return {"task": spec["task_id"], "worker": "coder",
                        "rounds": [{"round": 1, "diff": "x", "approved": True, "comments": ""}],
                        "approved": True, "final_diff": "x"}

            def grade_unknown(task_id, diff):
                return {"resolved": False, "status": "no_spec"}

            def evolve_fn(prompt):
                return {"reviewer_guidance_add": ["Be much stricter."]}

            evolver.run([{"task_id": "t1"}], loop_fn=loop_fn, grade=grade_unknown,
                        evolve_fn=evolve_fn, jury_fn=None, epochs=1, batch_size=1,
                        do_gate=False)
            p = policy.load()
            assert p["reviewer"]["guidance"] == []
        finally:
            del os.environ["LANGBRIDGE_POLICY_DIR"]
