import subprocess

import pytest

from langbridge_code.agents.common import worktree as worktree_mod
from langbridge_code.tools.merge_branch import merge_branch


def _git(repo, *args):
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@test")
    _git(root, "config", "user.name", "test")
    (root / "base.txt").write_text("base\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    monkeypatch.setattr(
        "langbridge_code.tools.merge_branch.get_workspace_root", lambda: root
    )
    monkeypatch.setattr(worktree_mod, "WORKSPACE_ROOT", root)
    monkeypatch.setattr(worktree_mod, "AGENT_STATE_DIR", tmp_path / "agent-state")
    return root


def _make_branch(repo, name, filename, content):
    _git(repo, "checkout", "-b", name)
    (repo / filename).write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"work on {name}")
    _git(repo, "checkout", "main")


def test_merge_branch_success_marks_merged(repo, tmp_path):
    run_log = tmp_path / "run.json"
    branch = "lb/run/t1-auth"
    _make_branch(repo, branch, "auth.txt", "auth\n")
    worktree_mod.record_branch(
        run_log,
        worktree_mod.WorktreeInfo(branch, tmp_path / "missing-wt", "Add auth"),
        "ready",
    )

    reply = merge_branch(branch, run_log_path=run_log)

    assert f"Merged {branch!r}" in reply
    assert "No ready branches left" in reply
    assert (repo / "auth.txt").exists()
    assert worktree_mod.ready_branches(run_log) == []


def test_merge_branch_rejects_unknown_branch(repo, tmp_path):
    run_log = tmp_path / "run.json"
    _make_branch(repo, "lb/run/t1-auth", "auth.txt", "auth\n")
    worktree_mod.record_branch(
        run_log,
        worktree_mod.WorktreeInfo("lb/run/t1-auth", tmp_path / "wt", "Add auth"),
        "ready",
    )

    reply = merge_branch("lb/run/t9-nope", run_log_path=run_log)

    assert reply.startswith("Tool error:")
    assert "is not ready" in reply
    assert worktree_mod.ready_branches(run_log) == ["lb/run/t1-auth"]


def test_merge_branch_rejects_failed_branch_for_in_place_resume(repo, tmp_path):
    run_log = tmp_path / "run.json"
    branch = "lb/run/t1-auth"
    _make_branch(repo, branch, "auth.txt", "half done\n")
    worktree_mod.record_branch(
        run_log,
        worktree_mod.WorktreeInfo(branch, tmp_path / "missing-wt", "Add auth"),
        "failed",
    )

    reply = merge_branch(branch, run_log_path=run_log)

    assert reply.startswith("Tool error:")
    assert "Only reviewer-PASS branches can be merged" in reply
    assert not (repo / "auth.txt").exists()


def test_merge_branch_conflict_leaves_merge_in_progress(repo, tmp_path):
    run_log = tmp_path / "run.json"
    branch = "lb/run/t1-auth"
    _make_branch(repo, branch, "base.txt", "branch version\n")
    (repo / "base.txt").write_text("main version\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "main change")
    worktree_mod.record_branch(
        run_log,
        worktree_mod.WorktreeInfo(branch, tmp_path / "wt", "Add auth"),
        "ready",
    )

    reply = merge_branch(branch, run_log_path=run_log)

    assert "hit conflicts" in reply
    assert "base.txt" in reply
    assert worktree_mod.ready_branches(run_log) == [branch]

    # Resolve the conflict the way the main agent would, then confirm.
    (repo / "base.txt").write_text("resolved\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--no-edit")

    confirm = merge_branch(branch, run_log_path=run_log)
    assert "is merged into HEAD" in confirm
    assert worktree_mod.ready_branches(run_log) == []


def test_successful_merge_cleans_only_requested_worktree(repo, tmp_path):
    run_log = tmp_path / "session-artifacts"
    stale_branch = "lb/run/stale-retry"
    stale_path = worktree_mod.worktrees_dir(run_log) / "t1-stale-retry"
    stale_path.parent.mkdir(parents=True)
    _git(repo, "worktree", "add", "-b", stale_branch, str(stale_path), "HEAD")
    (stale_path / "stale.txt").write_text("included later\n", encoding="utf-8")
    _git(stale_path, "add", "-A")
    _git(stale_path, "commit", "-m", "stale retry work")
    _git(repo, "merge", "--no-edit", stale_branch)
    assert stale_path.exists()

    ready_branch = "lb/run/t2-ready"
    _make_branch(repo, ready_branch, "ready.txt", "ready\n")
    worktree_mod.record_branch(
        run_log,
        worktree_mod.WorktreeInfo(
            ready_branch,
            worktree_mod.worktrees_dir(run_log) / "missing-ready",
            "Ready task",
        ),
        "ready",
    )

    reply = merge_branch(ready_branch, run_log_path=run_log)

    assert f"Merged {ready_branch!r}" in reply
    assert stale_path.exists()
    listing = _git(repo, "worktree", "list", "--porcelain")
    assert stale_branch in listing
