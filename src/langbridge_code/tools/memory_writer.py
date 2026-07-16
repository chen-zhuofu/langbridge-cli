"""memory_writer tool: fork a tool-using agent on the live main context."""

from langbridge_code.tools.common.purpose import PURPOSE_PARAMETER


MEMORY_WRITER_TOOL_SCHEMA = {
    "type": "function",
    "name": "memory_writer",
    "description": (
        "Fork a Memory Writer agent on the live conversation prefix. Use it as "
        "soon as the user reveals or corrects durable identity, preferences, "
        "working feedback, references, or project context. The fork reads both "
        "Memory indexes and uses ordinary file tools in a restricted Memory "
        "workspace to add, update, or delete entries, then exits."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "purpose": PURPOSE_PARAMETER,
        },
        "required": ["purpose"],
        "additionalProperties": False,
    },
}
