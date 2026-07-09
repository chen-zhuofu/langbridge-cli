import json

import pytest

from langbridge_code.agents.common.workspace import set_workspace_root
from langbridge_code.tools import TOOL_SCHEMAS, TOOLS
from langbridge_code.tools.filesystem import delete_file, glob, grep, read_file


@pytest.fixture
def isolated_workspace(tmp_path):
    set_workspace_root(tmp_path)
    yield tmp_path
    set_workspace_root(None)


def test_grep_and_glob_are_registered():
    assert "glob" in TOOLS
    assert "grep" in TOOLS
    names = {schema["name"] for schema in TOOL_SCHEMAS}
    assert {"glob", "grep"}.issubset(names)


@pytest.mark.skipif(__import__("shutil").which("rg") is None, reason="ripgrep not installed")
def test_glob_finds_files(isolated_workspace):
    (isolated_workspace / "alpha.py").write_text("x = 1\n", encoding="utf-8")
    (isolated_workspace / "beta.txt").write_text("y = 2\n", encoding="utf-8")

    payload = json.loads(glob("*.py", path="."))

    assert payload["matches"] == ["alpha.py"]


@pytest.mark.skipif(__import__("shutil").which("rg") is None, reason="ripgrep not installed")
def test_grep_finds_content(isolated_workspace):
    (isolated_workspace / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    payload = json.loads(grep("hello", path=".", output_mode="content"))

    assert payload["matches"][0]["path"] == "sample.py"
    assert payload["matches"][0]["line"] == 1
    assert "def hello" in payload["matches"][0]["text"]


def test_delete_file_is_registered():
    assert "delete_file" in TOOLS
    assert any(schema["name"] == "delete_file" for schema in TOOL_SCHEMAS)


def test_delete_file_removes_file(isolated_workspace):
    target = isolated_workspace / "stale.txt"
    target.write_text("remove me", encoding="utf-8")

    result = delete_file("stale.txt")

    assert result == "Deleted stale.txt."
    assert not target.exists()


def test_delete_file_rejects_directories(isolated_workspace):
    (isolated_workspace / "folder").mkdir()

    with pytest.raises(IsADirectoryError, match="Not a file"):
        delete_file("folder")


def test_read_file_line_range(isolated_workspace):
    (isolated_workspace / "sample.py").write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    output = read_file("sample.py", start_line=2, end_line=3)

    assert "# sample.py lines 2-3 (4 lines total)" in output
    assert "2| line2" in output
    assert "3| line3" in output
    assert "line4" not in output


def test_read_file_by_function_name(isolated_workspace):
    (isolated_workspace / "sample.py").write_text(
        "def helper():\n    return 1\n\ndef target():\n    x = 2\n    return x\n",
        encoding="utf-8",
    )

    output = read_file("sample.py", function_name="target")

    assert "function `target`" in output
    assert "def target():" in output
    assert "return x" in output
    assert "def helper" not in output


def test_read_file_rejects_function_and_line_range(isolated_workspace):
    (isolated_workspace / "sample.py").write_text("def target():\n    pass\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not both"):
        read_file("sample.py", function_name="target", start_line=1)
