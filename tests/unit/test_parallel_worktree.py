import subprocess
from unittest.mock import patch

from langbridge_code.agents.common.todo_list import TodoTask
from langbridge_code.agents.common import worktree as worktree_mod
from langbridge_code.tools.agent_worker_reviewer import (
    clean_task_description,
    is_parallel_task,
    next_parallel_batch,
    parallel_task_paths,
)
from langbridge_code.agents.common.workspace import get_workspace_root, workspace_scope


def test_is_parallel_task_and_paths():
    task = TodoTask("Add auth <!-- parallel paths:src/auth/** -->")
    assert is_parallel_task(task)
    assert parallel_task_paths(task) == "src/auth/**"
    assert clean_task_description(task) == "Add auth"


def test_next_parallel_batch_requires_two():
    tasks = [
        TodoTask("A <!-- parallel -->"),
        TodoTask("B <!-- parallel -->"),
        TodoTask("C"),
    ]
    assert len(next_parallel_batch(tasks, 4)) == 2
    assert next_parallel_batch([tasks[0]], 4) == []


def test_workspace_scope_switches_root(tmp_path, monkeypatch):
    import langbridge_code.settings as settings

    main = tmp_path / "main"
    other = tmp_path / "other"
    main.mkdir()
    other.mkdir()
    (main / "marker").write_text("main", encoding="utf-8")
    (other / "marker").write_text("other", encoding="utf-8")
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", main)

    assert (get_workspace_root() / "marker").read_text(encoding="utf-8") == "main"
    with workspace_scope(other):
        assert (get_workspace_root() / "marker").read_text(encoding="utf-8") == "other"
    assert (get_workspace_root() / "marker").read_text(encoding="utf-8") == "main"


def test_worktree_registry_records_ready_branch(tmp_path):
    run_log = tmp_path / "run.json"
    info = worktree_mod.WorktreeInfo(
        branch="lb/session/t1-auth",
        path=tmp_path / "wt",
        task_description="Add auth",
    )
    worktree_mod.record_branch(run_log, info, "ready")
    assert worktree_mod.ready_branches(run_log) == ["lb/session/t1-auth"]


def test_create_worktree_in_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    run_log = tmp_path / "run.json"
    with patch.object(worktree_mod, "WORKSPACE_ROOT", repo):
        with patch.object(worktree_mod, "AGENT_STATE_DIR", tmp_path / "agent-state"):
            info = worktree_mod.create_worktree(run_log, 1, "Add auth API")
    assert info.path.exists()
    assert (info.path / "README").exists()
    worktree_mod.remove_worktree(info, force=True)
