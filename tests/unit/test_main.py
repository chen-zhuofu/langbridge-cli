from langbridge_code.agents.roles import CODER_ENGINEER_PROMPT, REVIEWER_ENGINEER_PROMPT, SYSTEM_PROMPT


def test_chat_system_prompt():
    assert "LangBridge Code" in SYSTEM_PROMPT
    assert "Do not reveal" in SYSTEM_PROMPT


def test_engineering_guidelines_live_in_specialist_prompts():
    assert "Think before coding." not in CODER_ENGINEER_PROMPT
    assert "CODER_STATUS: READY_FOR_REVIEW" in CODER_ENGINEER_PROMPT
    assert "REVIEW_VERDICT: PASS" in REVIEWER_ENGINEER_PROMPT
