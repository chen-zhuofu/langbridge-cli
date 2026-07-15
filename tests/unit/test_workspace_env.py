import os

from langbridge_code.agents.common.workspace import workspace_scope
from langbridge_code.tools.common.env import workspace_env, workspace_python


def test_workspace_env_strips_foreign_host_venv(tmp_path, monkeypatch):
    host_venv = tmp_path / "host-venv"
    (host_venv / "bin").mkdir(parents=True)
    workspace = tmp_path / "project"
    workspace.mkdir()

    monkeypatch.setenv("VIRTUAL_ENV", str(host_venv))
    monkeypatch.setenv("PATH", f"{host_venv}/bin{os.pathsep}/usr/bin")

    with workspace_scope(workspace):
        env = workspace_env()

    assert "VIRTUAL_ENV" not in env
    assert str(host_venv / "bin") not in env["PATH"].split(os.pathsep)
    assert "/usr/bin" in env["PATH"].split(os.pathsep)


def test_workspace_env_activates_workspace_venv(tmp_path, monkeypatch):
    workspace = tmp_path / "project"
    ws_bin = workspace / ".venv" / "bin"
    ws_bin.mkdir(parents=True)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    with workspace_scope(workspace):
        env = workspace_env()

    assert env["VIRTUAL_ENV"] == str(workspace / ".venv")
    assert env["PATH"].split(os.pathsep)[0] == str(ws_bin)


def test_workspace_env_keeps_venv_inside_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "project"
    ws_venv = workspace / ".venv"
    (ws_venv / "bin").mkdir(parents=True)
    monkeypatch.setenv("VIRTUAL_ENV", str(ws_venv))
    monkeypatch.setenv("PATH", f"{ws_venv}/bin{os.pathsep}/usr/bin")

    with workspace_scope(workspace):
        env = workspace_env()

    assert env["VIRTUAL_ENV"] == str(ws_venv)


def test_workspace_python_prefers_workspace_venv(tmp_path):
    workspace = tmp_path / "project"
    ws_bin = workspace / ".venv" / "bin"
    ws_bin.mkdir(parents=True)
    python = ws_bin / "python"
    python.touch()

    with workspace_scope(workspace):
        assert workspace_python() == str(python)
