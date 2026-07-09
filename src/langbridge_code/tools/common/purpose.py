"""Purpose field on tool calls — for trace/UI only, stripped before execution."""

TOOL_PURPOSE = "purpose"

PURPOSE_PARAMETER = {
    "type": "string",
    "description": "One short user-visible sentence explaining why this tool call is needed now.",
}


def without_purpose(arguments):
    if not isinstance(arguments, dict):
        return arguments
    return {name: value for name, value in arguments.items() if name != TOOL_PURPOSE}
