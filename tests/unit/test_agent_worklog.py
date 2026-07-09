import langbridge_code.util.agent_worklog as agent_worklog
from langbridge_code.util.artifacts import create_artifact_session, traces_dir
from langbridge_code.util.trace_log import begin_trace, end_trace


def test_worklog_writes_nothing_without_an_active_run():
    agent_worklog.write_worklog_finish(None, "Worker", 1, 1, "done")
    assert agent_worklog.worklog_path(None, "Worker") is None
    assert agent_worklog.new_worklog_id(None, "Worker") is None


def test_worklog_writes_to_unified_trace(tmp_path, monkeypatch):
    monkeypatch.setattr("langbridge_code.util.artifacts.ARTIFACTS_DIR", tmp_path)
    run_log = create_artifact_session("Fix login bug")
    trace_id = "2026-07-09T120000.00"
    begin_trace(run_log, trace_id)

    output = [
        {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Inspect repo."}]},
        {
            "type": "function_call",
            "name": "read_file",
            "call_id": "c1",
            "arguments": '{"purpose":"look at the file","path":"README.md"}',
        },
    ]
    instance_id = agent_worklog.new_worklog_id(run_log, "Worker")
    agent_worklog.write_worklog_received(run_log, "Worker", instance_id, 2, "Build auth")
    agent_worklog.write_worklog_step(run_log, "Worker", instance_id, 2, 0, output)
    agent_worklog.write_worklog_observation(
        run_log, "Worker", instance_id, 2, 0, {"call_id": "c1", "output": "file contents here"}
    )
    agent_worklog.write_worklog_finish(run_log, "Worker", instance_id, 2, "WORKER_STATUS: READY_FOR_REVIEW")
    end_trace()

    text = (traces_dir(run_log) / f"{trace_id}.log").read_text(encoding="utf-8")
    assert "Worker" in text
    assert "Inspect repo." in text
    assert "read_file" in text
    assert "READY_FOR_REVIEW" in text


def test_distinct_instances_get_distinct_ids(tmp_path):
    run_log = create_artifact_session("Review task")
    first = agent_worklog.new_worklog_id(run_log, "Reviewer")
    second = agent_worklog.new_worklog_id(run_log, "Reviewer")
    assert first != second
