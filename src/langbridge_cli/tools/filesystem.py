import json
from pathlib import Path

from langbridge_cli.settings import MAX_FILE_BYTES

WORKSPACE_ROOT = Path.cwd().resolve()
TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "list_dir",
        "description": "List files and directories under the current workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to the current workspace.",
                    "default": ".",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a text file under the current workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the current workspace.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "edit_file",
        "description": "Edit a text file by replacing one exact, unique string with another string.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the current workspace.",
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact text to replace. It must appear exactly once in the file.",
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement text.",
                },
            },
            "required": ["path", "old_string", "new_string"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "create_file",
        "description": "Create a new UTF-8 text file under the current workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "New file path relative to the current workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write.",
                },
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "delete_file",
        "description": "Delete a file under the current workspace. This does not delete directories.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the current workspace.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
]

TOOLS = {}


def tool(name):
    def register(function):
        TOOLS[name] = function
        return function

    return register


def resolve_workspace_path(path):
    target = (WORKSPACE_ROOT / path).resolve()
    try:
        target.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise ValueError("Path must stay inside the current workspace")
    return target


@tool("list_dir")
def list_dir(path="."):
    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"No such directory: {path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = []
    for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        kind = "directory" if child.is_dir() else "file"
        entries.append({"name": child.name, "type": kind})

    return json.dumps({"path": str(target.relative_to(WORKSPACE_ROOT)), "entries": entries}, indent=2)


@tool("read_file")
def read_file(path):
    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"No such file: {path}")
    if not target.is_file():
        raise IsADirectoryError(f"Not a file: {path}")

    data = target.read_bytes()
    truncated = len(data) > MAX_FILE_BYTES
    data = data[:MAX_FILE_BYTES]

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"File is not valid UTF-8 text: {path}")

    if truncated:
        text += f"\n\n[truncated after {MAX_FILE_BYTES} bytes]"
    return text


@tool("edit_file")
def edit_file(path, old_string, new_string):
    if not old_string:
        raise ValueError("old_string must not be empty")

    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"No such file: {path}")
    if not target.is_file():
        raise IsADirectoryError(f"Not a file: {path}")

    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"File is not valid UTF-8 text: {path}")

    matches = text.count(old_string)
    if matches == 0:
        raise ValueError("old_string was not found")
    if matches > 1:
        raise ValueError(f"old_string matched {matches} times; provide a unique replacement target")

    target.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
    return f"Edited {path}: replaced 1 occurrence."


@tool("create_file")
def create_file(path, content):
    target = resolve_workspace_path(path)
    if target.exists():
        raise FileExistsError(f"File already exists: {path}")
    if not target.parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {target.parent.relative_to(WORKSPACE_ROOT)}")

    target.write_text(content, encoding="utf-8")
    return f"Created {path}."


@tool("delete_file")
def delete_file(path):
    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"No such file: {path}")
    if not target.is_file():
        raise IsADirectoryError(f"Not a file: {path}")

    target.unlink()
    return f"Deleted {path}."
