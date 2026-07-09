import json

from langbridge_code.tools.agent_planner import PLANNER_TOOL_SCHEMAS, PlannerSession
from langbridge_code.tools.ask_user import (
    format_ask_user_choices,
    normalize_options,
    resolve_ask_user,
    resolve_ask_user_answer,
)


def _bare_session(callback):
    session = PlannerSession.__new__(PlannerSession)
    session.question_callback = callback
    return session


def test_normalize_options_requires_three_assumptions():
    assert normalize_options(["a", "b", "c"]) == ["a", "b", "c"]
    try:
        normalize_options(["only one"])
    except ValueError as error:
        assert "exactly 3" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_format_ask_user_choices_shows_three_plus_other():
    text = format_ask_user_choices("Which tool?", ["CLI", "Web app", "Library"])
    assert "1. CLI" in text
    assert "2. Web app" in text
    assert "3. Library" in text
    assert "4. Other" in text


def test_resolve_ask_user_answer_maps_numbers_to_options():
    options = ["CLI", "Web app", "Library"]
    assert resolve_ask_user_answer("2", options) == "Web app"
    assert resolve_ask_user_answer("custom thing", options) == "custom thing"


def test_ask_user_schema_requires_options():
    schema = next(item for item in PLANNER_TOOL_SCHEMAS if item["name"] == "ask_user")
    assert "options" in schema["parameters"]["properties"]
    assert "question" in schema["parameters"]["required"]
    assert "options" in schema["parameters"]["required"]


def test_ask_user_returns_the_answer():
    out = resolve_ask_user(
        {
            "question": "Which stack?",
            "options": ["React", "Vue", "Vanilla JS"],
        },
        lambda q, opts: "use vanilla JS, single file",
    )
    assert "use vanilla JS, single file" in out


def test_ask_user_rejects_bad_options():
    out = resolve_ask_user(
        {"question": "Which stack?", "options": ["only one"]},
        lambda q, opts: "x",
    )
    assert "tool error" in out.lower()


def test_run_tool_routes_ask_user_to_callback():
    captured = {}

    def callback(question, options):
        captured["question"] = question
        captured["options"] = options
        return "answer-42"

    session = _bare_session(callback)
    call = {
        "name": "ask_user",
        "call_id": "c1",
        "arguments": json.dumps(
            {
                "question": "Which stack?",
                "options": ["React", "Vue", "Vanilla JS"],
            }
        ),
    }
    out = session._run_tool(call)
    assert out["call_id"] == "c1"
    assert "answer-42" in out["output"]
    assert captured["options"] == ["React", "Vue", "Vanilla JS"]
