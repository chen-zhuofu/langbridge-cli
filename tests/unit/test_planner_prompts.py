from langbridge_code.workflow.planner import initial_plan_prompt, refine_plan_prompt


def test_initial_plan_prompt_coding_uses_plain_checkboxes():
    prompt = initial_plan_prompt("Build auth system", task_type="coding")
    assert "task type: coding" in prompt.lower()
    assert "- [ ] <description>" in prompt
    assert "[coding]" not in prompt


def test_initial_plan_prompt_presentation_uses_plain_checkboxes():
    prompt = initial_plan_prompt("Quarterly review deck", task_type="presentation")
    assert "task type: presentation" in prompt.lower()
    assert "- [ ] <description>" in prompt
    assert "[presentation]" not in prompt


def test_refine_plan_prompt_mentions_session_task_type():
    prompt = refine_plan_prompt(
        "Add OAuth",
        "tests failed",
        "- [ ] Add OAuth",
        task_type="coding",
    )
    assert "coding session" in prompt.lower()
    assert "failed task: add oauth" in prompt.lower()
