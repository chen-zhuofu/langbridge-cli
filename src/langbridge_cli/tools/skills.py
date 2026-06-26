from langbridge_cli.skills import list_skills, load_skill

_AVAILABLE = list_skills()

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "read_skill",
        "description": (
            "Load a skill: a short playbook of guidelines for a kind of work. "
            "Call it when one of the listed skills fits the current task, then "
            "follow it. Available skills:\n"
            + "\n".join(f"- {name}: {description}" for name, description in _AVAILABLE)
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the skill to load.",
                    "enum": [name for name, _ in _AVAILABLE],
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    }
]

TOOLS = {}


def tool(name):
    def register(function):
        TOOLS[name] = function
        return function

    return register


@tool("read_skill")
def read_skill(name):
    try:
        return load_skill(name)
    except FileNotFoundError:
        available = ", ".join(skill_name for skill_name, _ in list_skills())
        return f"Tool error: unknown skill '{name}'. Available skills: {available}"
