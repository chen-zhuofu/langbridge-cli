"""Shared JSON schema shape for subagent delegation tools."""

from langbridge_code.tools.common.purpose import PURPOSE_PARAMETER


def agent_tool_schema(name, description, *, include_thoroughness=False):
    properties = {
        "purpose": PURPOSE_PARAMETER,
        "prompt": {
            "type": "string",
            "description": "Full task description for the subagent.",
        },
        "description": {
            "type": "string",
            "description": "Short 3-5 word title for logging.",
        },
    }
    if include_thoroughness:
        properties["thoroughness"] = {
            "type": "string",
            "enum": ["quick", "medium", "thorough"],
            "description": "Search depth (default medium).",
        }
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": ["purpose", "prompt", "description"],
            "additionalProperties": False,
        },
    }
