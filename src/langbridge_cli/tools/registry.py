from langbridge_cli.llm.tool_schema import with_tool_purpose
from langbridge_cli.tools.profiles import detect_tool_profile, search_tool_names, search_tool_schemas


def _load_base():
    from langbridge_cli.tools import agents, execution, filesystem, packages, plan, search, skills, testing, web

    tools = (
        filesystem.TOOLS
        | testing.TOOLS
        | packages.TOOLS
        | execution.TOOLS
        | agents.TOOLS
        | plan.TOOLS
        | web.TOOLS
        | skills.TOOLS
        | search.TOOLS
    )
    schemas = (
        filesystem.TOOL_SCHEMAS
        + testing.TOOL_SCHEMAS
        + packages.TOOL_SCHEMAS
        + execution.TOOL_SCHEMAS
        + agents.TOOL_SCHEMAS
        + plan.TOOL_SCHEMAS
        + web.TOOL_SCHEMAS
        + skills.TOOL_SCHEMAS
    )
    return filesystem, testing, execution, skills, search, tools, schemas


_PM_BASE_TOOL_NAMES = {
    "list_dir",
    "read_file",
    "execute_program",
    "read_webpage",
    "ask_l4_engineer",
    "ask_l5_engineer",
    "update_plan",
}
_L3_BASE_TOOL_NAMES = {"list_dir", "read_file", "run_tests"}
_L4_BASE_TOOL_NAMES = {
    "list_dir",
    "read_file",
    "edit_file",
    "create_file",
    "delete_file",
    "run_tests",
    "execute_program",
    "read_skill",
}


def _schema_by_name(schemas):
    return {schema["name"]: schema for schema in schemas}


def _select_schemas(all_schemas, names):
    by_name = _schema_by_name(all_schemas)
    return [by_name[name] for name in names if name in by_name]


def tool_schemas(*, provider=None, model=None, profile=None):
    _, _, _, _, _, _, base_schemas = _load_base()
    profile = profile or detect_tool_profile(provider=provider, model=model)
    return with_tool_purpose(base_schemas + search_tool_schemas(profile=profile))


def all_tools():
    _, _, _, _, _, tools, _ = _load_base()
    return dict(tools)


def main_tool_names(*, provider=None, model=None, profile=None):
    profile = profile or detect_tool_profile(provider=provider, model=model)
    return _PM_BASE_TOOL_NAMES | search_tool_names(profile=profile)


def main_tool_schemas(*, provider=None, model=None, profile=None):
    _, _, _, _, _, _, base_schemas = _load_base()
    profile = profile or detect_tool_profile(provider=provider, model=model)
    search_names = [schema["name"] for schema in search_tool_schemas(profile=profile)]
    glob_name, grep_name = search_names
    names = [
        "list_dir",
        glob_name,
        "read_file",
        grep_name,
        "execute_program",
        "read_webpage",
        "ask_l4_engineer",
        "ask_l5_engineer",
        "update_plan",
    ]
    return with_tool_purpose(_select_schemas(base_schemas + search_tool_schemas(profile=profile), names))


def main_tools(*, provider=None, model=None, profile=None):
    _, _, _, _, _, tools, _ = _load_base()
    profile = profile or detect_tool_profile(provider=provider, model=model)
    names = main_tool_names(profile=profile)
    return {name: tools[name] for name in names}


def l3_tool_names(*, provider=None, model=None, profile=None):
    profile = profile or detect_tool_profile(provider=provider, model=model)
    return _L3_BASE_TOOL_NAMES | search_tool_names(profile=profile)


def l3_tool_schemas(*, provider=None, model=None, profile=None):
    filesystem, testing, _, _, _, _, _ = _load_base()
    profile = profile or detect_tool_profile(provider=provider, model=model)
    names = l3_tool_names(profile=profile)
    selected = filesystem.TOOL_SCHEMAS + testing.TOOL_SCHEMAS + search_tool_schemas(profile=profile)
    return with_tool_purpose(_select_schemas(selected, names))


def l3_tools(*, provider=None, model=None, profile=None):
    filesystem, testing, _, _, search, tools, _ = _load_base()
    profile = profile or detect_tool_profile(provider=provider, model=model)
    names = l3_tool_names(profile=profile)
    available = filesystem.TOOLS | testing.TOOLS | search.TOOLS
    return {name: available[name] for name in names}


def l4_tool_names(*, provider=None, model=None, profile=None):
    profile = profile or detect_tool_profile(provider=provider, model=model)
    return _L4_BASE_TOOL_NAMES | search_tool_names(profile=profile)


def l4_tool_schemas(*, provider=None, model=None, profile=None):
    filesystem, testing, execution, skills, _, _, _ = _load_base()
    profile = profile or detect_tool_profile(provider=provider, model=model)
    names = l4_tool_names(profile=profile)
    selected = (
        filesystem.TOOL_SCHEMAS
        + testing.TOOL_SCHEMAS
        + execution.TOOL_SCHEMAS
        + skills.TOOL_SCHEMAS
        + search_tool_schemas(profile=profile)
    )
    return with_tool_purpose(_select_schemas(selected, names))


def l4_tools(*, provider=None, model=None, profile=None):
    filesystem, testing, execution, skills, search, _, _ = _load_base()
    profile = profile or detect_tool_profile(provider=provider, model=model)
    names = l4_tool_names(profile=profile)
    available = filesystem.TOOLS | testing.TOOLS | execution.TOOLS | skills.TOOLS | search.TOOLS
    return {name: available[name] for name in names}
