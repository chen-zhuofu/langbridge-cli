"""Tool schema profiles aligned with Kimi Code CLI and OpenAI Codex."""

from langbridge_cli.settings import DEFAULT_MODEL, active_api_provider

from langbridge_cli.tools.profiles import kimi, openai

PROFILES = {
    "kimi": {
        "schemas": kimi.KIMI_SEARCH_SCHEMAS,
        "tool_names": kimi.KIMI_SEARCH_TOOL_NAMES,
    },
    "openai": {
        "schemas": openai.OPENAI_SEARCH_SCHEMAS,
        "tool_names": openai.OPENAI_SEARCH_TOOL_NAMES,
    },
}


def detect_tool_profile(*, provider=None, model=None):
    provider = (provider or active_api_provider() or "openai").lower()
    model_lower = (model or DEFAULT_MODEL or "").lower()

    if provider == "moonshot" or "kimi" in model_lower or "moonshot" in model_lower:
        return "kimi"
    return "openai"


def search_tool_names(*, provider=None, model=None, profile=None):
    profile = profile or detect_tool_profile(provider=provider, model=model)
    return set(PROFILES[profile]["tool_names"])


def search_tool_schemas(*, provider=None, model=None, profile=None):
    profile = profile or detect_tool_profile(provider=provider, model=model)
    return list(PROFILES[profile]["schemas"])
