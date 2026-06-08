import getpass
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.1-codex"
CONFIG_PATH = Path.home() / ".langbridge" / "config.json"
MAX_AGENT_STEPS = 8
MAX_FILE_BYTES = 20_000
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
]

TOOLS = {}


def main():
    api_key = load_api_key()
    model = os.environ.get("LANGBRIDGE_MODEL", DEFAULT_MODEL)

    messages = [
        {
            "role": "system",
            "content": "You are langbridge-cli, a concise coding agent. Help the user implement software step by step.",
        }
    ]

    print(f"langbridge-cli using {model}")
    print("Type /exit to quit.\n")

    while True:
        text = input("langbridge> ")

        if text.strip() == "/exit":
            break

        messages.append({"role": "user", "content": text})
        reply = run_agent(api_key, model, messages)
        messages.append({"role": "assistant", "content": reply})
        print(f"\n{reply}\n")


def load_api_key():
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key

    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())["api_key"]

    api_key = getpass.getpass("Enter Codex API key: ")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"api_key": api_key}, indent=2))
    CONFIG_PATH.chmod(0o600)
    return api_key


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


def run_agent(api_key, model, messages):
    agent_input = list(messages)

    for _ in range(MAX_AGENT_STEPS):
        data = create_response(api_key, model, agent_input)
        output = data.get("output", [])
        tool_calls = [item for item in output if item.get("type") == "function_call"]

        if not tool_calls:
            return extract_output_text(output)

        agent_input.extend(output)
        for call in tool_calls:
            agent_input.append(run_tool_call(call))

    return "Agent stopped because it reached the maximum tool-call steps."


def create_response(api_key, model, agent_input):
    body = json.dumps({"model": model, "input": agent_input, "tools": TOOL_SCHEMAS}).encode()
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as error:
        data = json.loads(error.read())
        raise RuntimeError(data.get("error", {}).get("message", "OpenAI request failed"))

    return data


def run_tool_call(call):
    name = call.get("name")
    call_id = call.get("call_id")

    try:
        arguments = json.loads(call.get("arguments") or "{}")
        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")
        output = TOOLS[name](**arguments)
    except Exception as error:
        output = f"Tool error: {error}"

    return {"type": "function_call_output", "call_id": call_id, "output": output}


def extract_output_text(output):
    return "".join(
        content["text"]
        for item in output
        for content in item.get("content", [])
        if content["type"] == "output_text"
    )


if __name__ == "__main__":
    main()
