import pytest


@pytest.fixture(autouse=True)
def bypass_tdd_harness(monkeypatch):
    """Functional tests mock single-phase L4/L5; skip the two-phase TDD runtime."""

    def fake(
        api_key,
        model,
        task,
        context,
        feedback,
        new_session_fn,
        run_engineer_fn,
        ready_fn,
        worker_label,
        trace_sink,
        approval_callback,
        run_log_path,
        turn_id,
    ):
        session = new_session_fn(
            api_key,
            model,
            trace_sink=trace_sink,
            approval_callback=approval_callback,
            run_log_path=run_log_path,
            turn_id=turn_id,
        )
        report = run_engineer_fn(api_key, model, task, context, feedback, session=session)
        if not ready_fn(report):
            return report, None, None, None
        return None, session, report, {}

    monkeypatch.setattr("langbridge_cli.agents.agent._run_worker_tdd", fake)
