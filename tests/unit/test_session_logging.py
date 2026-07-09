import json

from langbridge_code.util.logging import read_turn_record, record_user_turn, write_finish_log
from langbridge_code.util.session import read_session_log


def test_record_user_turn_persists_before_assistant_reply(tmp_path):
    run_log = tmp_path / "session.json"
    record_user_turn(run_log, 1, "hello world")

    session = read_session_log(run_log)
    assert session["turns"] == [{"turn_id": 1, "user": "hello world", "assistant": ""}]


def test_record_user_turn_does_not_wipe_assistant_on_merge(tmp_path):
    run_log = tmp_path / "session.json"
    record_user_turn(run_log, 1, "hello")
    write_finish_log(run_log, 1, "hi back")

    record_user_turn(run_log, 1, "hello")

    record = read_turn_record(run_log, 1)
    assert record["user"] == "hello"
    assert record["assistant"] == "hi back"


def test_write_finish_log_preserves_user_when_assistant_arrives(tmp_path):
    run_log = tmp_path / "session.json"
    record_user_turn(run_log, 2, "build feature")
    write_finish_log(run_log, 2, "done")

    data = json.loads(run_log.read_text(encoding="utf-8"))
    assert data["turns"][0] == {
        "turn_id": 2,
        "user": "build feature",
        "assistant": "done",
    }
