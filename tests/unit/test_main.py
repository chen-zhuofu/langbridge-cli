from langbridge_code.agents.system_prompt import LANGBRIDGE_PROMPT, langbridge_system_prompt
from langbridge_code.agents.system_prompt import WORKER_ENGINEER_PROMPT
from langbridge_code.agents.system_prompt.reviewer import REVIEWER_ENGINEER_PROMPT


def test_main_agent_identity_prompt():
    assert "LangBridge Code" in LANGBRIDGE_PROMPT
    assert "Do not reveal" in LANGBRIDGE_PROMPT


def test_langbridge_system_prompt_covers_answer_and_delegate():
    from langbridge_code.agents.main_agent import MAIN_AGENT_TOOL_SCHEMAS

    prompt = langbridge_system_prompt()
    tool_names = {schema["name"] for schema in MAIN_AGENT_TOOL_SCHEMAS}
    assert "LangBridge Code" in prompt
    assert "tool schemas" in prompt
    assert {"agent_planner", "agent_explorer", "agent_worker"} <= tool_names
    assert "继续" in prompt or "continue" in prompt.lower()
    assert "worker-reviewer loop" in prompt.lower() or "one task" in prompt.lower()
    assert "Subagent-driven execution" in prompt
    assert "superpowers_writing-plans" not in prompt
    assert "answer in conversation" in prompt.lower() or "answer directly" in prompt.lower()
    # Tool how-to belongs in schemas; workflow mentions (read_plan, agent_worker) are OK.
    for tool_name in ("ask_user", "grep", "read_file"):
        assert tool_name not in prompt


def test_engineering_guidelines_live_in_specialist_prompts():
    assert "Think before coding." not in WORKER_ENGINEER_PROMPT
    assert "WORKER_STATUS: READY_FOR_REVIEW" in WORKER_ENGINEER_PROMPT
    assert "REVIEW_VERDICT: PASS" in REVIEWER_ENGINEER_PROMPT
