from langbridge_code.tools import browser, execution, filesystem, skills, testing, todo_list, web

TOOL_SCHEMAS = (
    filesystem.TOOL_SCHEMAS
    + testing.TOOL_SCHEMAS
    + execution.TOOL_SCHEMAS
    + todo_list.TOOL_SCHEMAS
    + web.TOOL_SCHEMAS
    + skills.TOOL_SCHEMAS
)
TOOLS = filesystem.TOOLS | testing.TOOLS | execution.TOOLS | todo_list.TOOLS | web.TOOLS | skills.TOOLS

MAIN_TOOL_SCHEMAS = (
    filesystem.TOOL_SCHEMAS
    + testing.TOOL_SCHEMAS
    + execution.TOOL_SCHEMAS
    + todo_list.TOOL_SCHEMAS
    + web.TOOL_SCHEMAS
    + browser.TOOL_SCHEMAS
    + skills.TOOL_SCHEMAS
)
MAIN_TOOL_NAMES = {schema["name"] for schema in MAIN_TOOL_SCHEMAS}
MAIN_TOOLS = {
    name: tool
    for name, tool in (
        filesystem.TOOLS
        | testing.TOOLS
        | execution.TOOLS
        | todo_list.TOOLS
        | web.TOOLS
        | browser.TOOLS
        | skills.TOOLS
    ).items()
}

GOAL_VERIFICATION_TOOL_NAMES = MAIN_TOOL_NAMES
GOAL_VERIFICATION_TOOL_SCHEMAS = list(MAIN_TOOL_SCHEMAS)
GOAL_VERIFICATION_TOOLS = dict(MAIN_TOOLS)

__all__ = [
    "TOOL_SCHEMAS",
    "TOOLS",
    "MAIN_TOOL_SCHEMAS",
    "MAIN_TOOLS",
    "GOAL_VERIFICATION_TOOL_NAMES",
    "GOAL_VERIFICATION_TOOL_SCHEMAS",
    "GOAL_VERIFICATION_TOOLS",
]
