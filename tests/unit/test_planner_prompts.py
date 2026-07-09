from langbridge_code.tools.agent_planner import initial_plan_prompt, parse_plan_task_type, refine_plan_prompt


def test_initial_plan_prompt_uses_plain_checkboxes():
    prompt = initial_plan_prompt("Build auth system")
    assert "coding" in prompt.lower()
    assert "slide" in prompt.lower()
    assert "- [ ] <description>" in prompt
    assert "[coding]" not in prompt
    assert "plan_task_type" in prompt.lower()


def test_initial_plan_prompt_requires_evidence_based_plan():
    prompt = initial_plan_prompt("Build a web Tetris game").lower()
    assert "out of scope" in prompt
    assert "key discoveries" in prompt
    assert "path:line" in prompt or "`path:line`" in prompt
    assert "verify:" in prompt
    assert "changes required" in prompt
    assert "snippet" in prompt
    assert "no limit/offset" in prompt
    assert "padding" in prompt or "duplicate" in prompt


def test_refine_plan_prompt_blocks_duplicate_and_doc_steps():
    prompt = refine_plan_prompt(
        "Add OAuth",
        "tests failed",
        "- [ ] Add OAuth",
        task_type="coding",
    ).lower()
    assert "duplicate" in prompt
    assert "design-doc" in prompt or "planning steps" in prompt
    assert "verify:" in prompt
    assert "grep/read_file" in prompt or "read_file/grep" in prompt


def test_refine_plan_prompt_mentions_session_task_type():
    prompt = refine_plan_prompt(
        "Add OAuth",
        "tests failed",
        "- [ ] Add OAuth",
        task_type="coding",
    )
    assert "coding session" in prompt.lower()
    assert "failed task: add oauth" in prompt.lower()


def test_parse_plan_task_type_reads_planner_report():
    assert parse_plan_task_type("PLAN_TASK_TYPE: coding\n\nSix steps.") == "coding"
    assert parse_plan_task_type("PLAN_TASK_TYPE: slide\nDone.") == "slide"
    assert parse_plan_task_type("PLAN_TASK_TYPE: presentation\nDone.") == "slide"
    assert parse_plan_task_type("No type here") is None
