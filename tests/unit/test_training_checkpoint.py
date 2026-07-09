"""Unit tests for training checkpoint snapshot/restore."""
import os
import tempfile

from langbridge_code.training import checkpoint, gate


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


def test_checkpoint_baseline_and_restore():
    with tempfile.TemporaryDirectory() as artifacts, tempfile.TemporaryDirectory() as checkpoints:
        _sandbox_env(artifacts, checkpoints)
        try:
            _write_worker_prompt(artifacts, "BASE\n")
            checkpoint.save_checkpoint("step0_baseline", step=0, parent_label=None)
            _write_worker_prompt(artifacts, "CHANGED\n")
            checkpoint.restore_checkpoint("step0_baseline")
            assert _read_worker_prompt(artifacts) == "BASE\n"
        finally:
            os.environ.pop("LANGBRIDGE_ARTIFACT_ROOT", None)
            os.environ.pop("LANGBRIDGE_CHECKPOINT_DIR", None)


def test_summarize_changes_between_checkpoints():
    with tempfile.TemporaryDirectory() as artifacts, tempfile.TemporaryDirectory() as checkpoints:
        _sandbox_env(artifacts, checkpoints)
        try:
            _write_worker_prompt(artifacts, "BASE\n")
            checkpoint.save_checkpoint("step0_baseline", step=0, parent_label=None)
            _write_worker_prompt(artifacts, "Make a surgical fix.\n")
            checkpoint.save_checkpoint("step1", step=1, parent_label="step0_baseline")
            meta = next(m for m in checkpoint.list_checkpoints() if m["label"] == "step1")
            summary = meta["changes"]["summary_lines"]
            assert any("worker.py" in line for line in summary)
        finally:
            os.environ.pop("LANGBRIDGE_ARTIFACT_ROOT", None)
            os.environ.pop("LANGBRIDGE_CHECKPOINT_DIR", None)


def test_gate_apply_file_edits_and_oracle_leak_filter():
    with tempfile.TemporaryDirectory() as artifacts, tempfile.TemporaryDirectory() as checkpoints:
        _sandbox_env(artifacts, checkpoints)
        try:
            _write_worker_prompt(artifacts, "BASE\n")
            proposal = {
                "diagnosis": "fix",
                "file_edits": [
                    {
                        "path": "agents/system_prompt/worker.py",
                        "content": "Make the hidden tests pass.\n",
                    },
                    {
                        "path": "agents/system_prompt/worker.py",
                        "content": "Make a surgical fix.\n",
                    },
                ],
            }
            # second edit wins in loop — test leak strip on single edit instead
            changes = gate.apply_proposal(
                {
                    "file_edits": [
                        {"path": "agents/system_prompt/worker.py", "content": "Keep changes surgical.\n"}
                    ]
                },
                allow_reviewer=True,
            )
            assert "surgical" in _read_worker_prompt(artifacts)
            assert changes["written"] == ["agents/system_prompt/worker.py"]

            leaked = gate.apply_proposal(
                {"file_edits": [{"path": "agents/system_prompt/worker.py", "content": "hidden tests pass\n"}]},
                allow_reviewer=True,
            )
            assert leaked.get("dropped_leaks")
        finally:
            os.environ.pop("LANGBRIDGE_ARTIFACT_ROOT", None)
            os.environ.pop("LANGBRIDGE_CHECKPOINT_DIR", None)


def test_reviewer_edits_need_anchor():
    with tempfile.TemporaryDirectory() as artifacts, tempfile.TemporaryDirectory() as checkpoints:
        _sandbox_env(artifacts, checkpoints)
        try:
            path = os.path.join(artifacts, "agents", "system_prompt", "reviewer.py")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("BASE\n")
            changes = gate.apply_proposal(
                {
                    "file_edits": [
                        {"path": "agents/system_prompt/reviewer.py", "content": "Be stricter.\n"}
                    ]
                },
                allow_reviewer=False,
            )
            assert "skipped" in changes
            assert open(path, encoding="utf-8").read() == "BASE\n"
        finally:
            os.environ.pop("LANGBRIDGE_ARTIFACT_ROOT", None)
            os.environ.pop("LANGBRIDGE_CHECKPOINT_DIR", None)
