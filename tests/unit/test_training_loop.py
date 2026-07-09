"""Orchestration tests for the eval runners and the trainer, using stub agents."""
import os
import tempfile

import pytest


def _grade_from_diff(task_id, diff):
    return {"resolved": "FIX" in (diff or ""), "status": "graded"}


def _sandbox_env(artifact_root, checkpoint_root):
    os.environ["LANGBRIDGE_ARTIFACT_ROOT"] = artifact_root
    os.environ["LANGBRIDGE_CHECKPOINT_DIR"] = checkpoint_root


def _write_worker_prompt(root, text):
    path = os.path.join(root, "agents", "system_prompt", "worker.py")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _read_worker_prompt(root):
    path = os.path.join(root, "agents", "system_prompt", "worker.py")
    return open(path, encoding="utf-8").read()


def test_eval_runners_with_stubs():
    from langbridge_code.eval import runner

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


def test_trainer_accepts_improving_change():
    from langbridge_code.training import checkpoint, trainer

    with tempfile.TemporaryDirectory() as artifacts, tempfile.TemporaryDirectory() as checkpoints:
        _sandbox_env(artifacts, checkpoints)
        try:
            _write_worker_prompt(artifacts, "BASE\n")

            def loop_fn(spec):
                learned = "surgical fix" in _read_worker_prompt(artifacts).lower()
                diff = "FIX" if learned else "noop"
                return {
                    "task": spec["task_id"], "worker": "coder",
                    "rounds": [{"round": 1, "diff": diff, "approved": True, "comments": ""}],
                    "approved": True, "final_diff": diff,
                }

            def trainer_fn(prompt):
                content = _read_worker_prompt(artifacts).replace(
                    "BASE", "Make a surgical fix to the failing function."
                )
                return {
                    "diagnosis": "implementer flailing",
                    "file_edits": [{"path": "agents/system_prompt/worker.py", "content": content}],
                }

            results = trainer.run(
                [{"task_id": "t1"}, {"task_id": "t2"}],
                loop_fn=loop_fn, grade=_grade_from_diff, trainer_fn=trainer_fn,
                epochs=1, batch_size=2, do_gate=True, checkpoint_every="batch",
            )
            assert len(results) == 1
            res = results[0]
            assert res["accepted"] is True
            assert res["new_total"] > res["old_total"]
            assert "surgical fix" in _read_worker_prompt(artifacts).lower()
            assert checkpoint.list_checkpoints()
        finally:
            os.environ.pop("LANGBRIDGE_ARTIFACT_ROOT", None)
            os.environ.pop("LANGBRIDGE_CHECKPOINT_DIR", None)


def test_trainer_rolls_back_non_improving_change():
    from langbridge_code.training import trainer

    with tempfile.TemporaryDirectory() as artifacts, tempfile.TemporaryDirectory() as checkpoints:
        _sandbox_env(artifacts, checkpoints)
        try:
            _write_worker_prompt(artifacts, "BASE\n")

            def loop_fn(spec):
                return {
                    "task": spec["task_id"], "worker": "coder",
                    "rounds": [{"round": 1, "diff": "noop", "approved": True, "comments": ""}],
                    "approved": True, "final_diff": "noop",
                }

            def trainer_fn(prompt):
                return {
                    "file_edits": [
                        {"path": "agents/system_prompt/worker.py", "content": "Some guidance.\n"}
                    ]
                }

            results = trainer.run(
                [{"task_id": "t1"}, {"task_id": "t2"}],
                loop_fn=loop_fn, grade=_grade_from_diff, trainer_fn=trainer_fn,
                epochs=1, batch_size=2, do_gate=True, checkpoint_every="batch",
            )
            res = results[0]
            assert res["accepted"] is False
            assert _read_worker_prompt(artifacts) == "BASE\n"
        finally:
            os.environ.pop("LANGBRIDGE_ARTIFACT_ROOT", None)
            os.environ.pop("LANGBRIDGE_CHECKPOINT_DIR", None)


def test_reviewer_edits_need_anchor_in_trainer():
    from langbridge_code.training import trainer

    with tempfile.TemporaryDirectory() as artifacts, tempfile.TemporaryDirectory() as checkpoints:
        _sandbox_env(artifacts, checkpoints)
        try:
            reviewer_path = os.path.join(artifacts, "agents", "system_prompt", "reviewer.py")
            os.makedirs(os.path.dirname(reviewer_path), exist_ok=True)
            with open(reviewer_path, "w", encoding="utf-8") as handle:
                handle.write("BASE\n")
            _write_worker_prompt(artifacts, "BASE\n")

            def loop_fn(spec):
                return {"task": spec["task_id"], "worker": "coder",
                        "rounds": [{"round": 1, "diff": "x", "approved": True, "comments": ""}],
                        "approved": True, "final_diff": "x"}

            def grade_unknown(task_id, diff):
                return {"resolved": False, "status": "no_spec"}

            def trainer_fn(prompt):
                return {
                    "file_edits": [
                        {"path": "agents/system_prompt/reviewer.py", "content": "Be much stricter.\n"}
                    ]
                }

            trainer.run([{"task_id": "t1"}], loop_fn=loop_fn, grade=grade_unknown,
                        trainer_fn=trainer_fn, jury_fn=None, epochs=1, batch_size=1,
                        do_gate=False)
            assert open(reviewer_path, encoding="utf-8").read() == "BASE\n"
        finally:
            os.environ.pop("LANGBRIDGE_ARTIFACT_ROOT", None)
            os.environ.pop("LANGBRIDGE_CHECKPOINT_DIR", None)
