import copy
import json

from langbridge_cli.tool_schema import TOOL_PURPOSE_ARGUMENT


DIM = "\033[2m"
RESET = "\033[0m"


def parse_json_string(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def extract_reasoning_items(output):
    return [copy.deepcopy(item) for item in output if item.get("type") == "reasoning"]


def truncate_text(text, max_chars):
    compact = " ".join(str(text).split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars] + "..."


def print_step_trace(output, include_message=False, label="Agent"):
    tool_purposes = [
        purpose
        for item in output
        if item.get("type") == "function_call"
        for purpose in [extract_tool_purpose(item)]
        if purpose
    ]
    thoughts = tool_purposes
    if not thoughts and include_message:
        thoughts = [extract_output_text(output)]
        thoughts = [thought for thought in thoughts if thought]
    if not thoughts:
        thoughts = extract_reasoning_summaries(output)

    for thought in thoughts:
        print(f"\n{dim_text(f'{label}: {thought}')}")

    for item in output:
        if item.get("type") != "function_call":
            continue
        name = item.get("name", "unknown")
        arguments = format_tool_arguments(item)
        print(dim_text(f"{label}: ↳ {name}({arguments})"))


def dim_text(text):
    return f"{DIM}{text}{RESET}"


def extract_tool_purpose(item):
    arguments = parse_json_string(item.get("arguments") or "{}")
    if isinstance(arguments, dict):
        return arguments.get(TOOL_PURPOSE_ARGUMENT, "")
    return ""


def format_tool_arguments(item):
    arguments = parse_json_string(item.get("arguments") or "{}")
    if isinstance(arguments, dict):
        arguments.pop(TOOL_PURPOSE_ARGUMENT, None)
        return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    return item.get("arguments") or "{}"


def extract_reasoning_summaries(output):
    return [
        content["text"]
        for item in output
        if item.get("type") == "reasoning"
        for content in item.get("summary", [])
        if content.get("type") == "summary_text" and content.get("text")
    ]


def extract_turn_user_input(agent_input):
    for message in reversed(agent_input):
        if message.get("role") == "user":
            return message["content"]
    raise ValueError("agent_input has no user message")


def extract_output_text(output):
    return "".join(
        content["text"]
        for item in output
        for content in item.get("content", [])
        if content["type"] == "output_text"
    )
