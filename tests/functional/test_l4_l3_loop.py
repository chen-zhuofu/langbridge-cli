from langbridge_cli.agents.agent import run_l4_component

READY = "L4_STATUS: READY_FOR_REVIEW\nSummary: implemented"
PASS = "REVIEW_VERDICT: PASS\nEvidence: tests pass"
NEEDS_WORK = "REVIEW_VERDICT: NEEDS_WORK\nIssues: missing edge case"


def test_loop_passes_on_first_review_without_retrying_l4(monkeypatch):
    l3_calls = []
    l4_calls = {"n": 0}

    def fake_l3(api_key, model, task, context, **kwargs):
        l3_calls.append(task)
        return PASS

    def fake_l4(api_key, model, task, context, feedback="", **kwargs):
        l4_calls["n"] += 1
        if l4_calls["n"] > 1:
            raise AssertionError("L4 should not be re-run when L3 passes first review")
        return READY

    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l3_test_engineer", fake_l3)
    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l4_engineer", fake_l4)

    output = run_l4_component("key", "model", {"task": "build", "context": "repo"})

    assert "PM_REVIEW_STATUS: OK" in output
    assert l3_calls == ["build"]


def test_loop_retries_l4_until_l3_passes(monkeypatch):
    verdicts = iter([NEEDS_WORK, PASS])
    l4_feedback = []
    l4_calls = {"n": 0}

    def fake_l3(api_key, model, task, context, **kwargs):
        return next(verdicts)

    def fake_l4(api_key, model, task, context, feedback="", **kwargs):
        l4_calls["n"] += 1
        if l4_calls["n"] == 1:
            return READY  # initial build
        l4_feedback.append(feedback)
        return "L4_STATUS: READY_FOR_REVIEW\nSummary: fixed the edge case"

    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l3_test_engineer", fake_l3)
    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l4_engineer", fake_l4)

    output = run_l4_component("key", "model", {"task": "build", "context": "repo"})

    assert "PM_REVIEW_STATUS: OK" in output
    assert "fixed the edge case" in output
    assert len(l4_feedback) == 1
    assert "NEEDS_WORK" in l4_feedback[0]


def test_loop_gives_up_after_max_turns(monkeypatch):
    l3_calls = []
    l4_fix_calls = []
    l4_calls = {"n": 0}

    def fake_l3(api_key, model, task, context, **kwargs):
        l3_calls.append(task)
        return NEEDS_WORK

    def fake_l4(api_key, model, task, context, feedback="", **kwargs):
        l4_calls["n"] += 1
        if l4_calls["n"] > 1:
            l4_fix_calls.append(feedback)
        return READY

    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l3_test_engineer", fake_l3)
    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l4_engineer", fake_l4)
    monkeypatch.setattr("langbridge_cli.agents.agent.MAX_L4_L3_TURNS", 2)

    output = run_l4_component("key", "model", {"task": "build", "context": "repo"})

    assert "PM_REVIEW_STATUS: NEEDS_WORK" in output
    assert len(l3_calls) == 2
    assert len(l4_fix_calls) == 2


def test_in_progress_skips_l3_review(monkeypatch):
    l3_calls = []

    def fake_l3(api_key, model, task, context, **kwargs):
        l3_calls.append(task)
        return PASS

    def fake_l4(api_key, model, task, context, feedback="", **kwargs):
        return "L4_STATUS: IN_PROGRESS\nSummary: still working"

    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l3_test_engineer", fake_l3)
    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l4_engineer", fake_l4)

    output = run_l4_component("key", "model", {"task": "build", "context": "repo"})

    assert "IN_PROGRESS" in output
    assert "PM_REVIEW_STATUS" not in output
    assert l3_calls == []


def test_l4_commits_on_l3_pass(monkeypatch):
    commits = []

    def fake_l3(api_key, model, task, context, **kwargs):
        return PASS

    def fake_l4(api_key, model, task, context, feedback="", **kwargs):
        return READY

    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l3_test_engineer", fake_l3)
    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l4_engineer", fake_l4)
    monkeypatch.setattr(
        "langbridge_cli.agents.workspace_git.commit_task",
        lambda label, task: commits.append((label, task)) or "abc123",
    )
    monkeypatch.setattr("langbridge_cli.agents.workspace_git.snapshot_head", lambda: "before")
    monkeypatch.setattr("langbridge_cli.agents.workspace_git.revert_snapshot", lambda commit: False)

    output = run_l4_component("key", "model", {"task": "build feature", "context": "repo"})

    assert "PM_REVIEW_STATUS: OK" in output
    assert commits == [("L4", "build feature")]


def test_l4_reverts_on_review_failure(monkeypatch):
    reverts = []

    def fake_l3(api_key, model, task, context, **kwargs):
        return NEEDS_WORK

    def fake_l4(api_key, model, task, context, feedback="", **kwargs):
        return READY

    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l3_test_engineer", fake_l3)
    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l4_engineer", fake_l4)
    monkeypatch.setattr("langbridge_cli.agents.agent.MAX_L4_L3_TURNS", 1)
    monkeypatch.setattr("langbridge_cli.agents.workspace_git.snapshot_head", lambda: "before")
    monkeypatch.setattr(
        "langbridge_cli.agents.workspace_git.revert_snapshot",
        lambda commit: reverts.append(commit) or True,
    )
    monkeypatch.setattr("langbridge_cli.agents.workspace_git.commit_task", lambda *args: None)

    output = run_l4_component("key", "model", {"task": "build feature", "context": "repo"})

    assert "PM_REVIEW_STATUS: NEEDS_WORK" in output
    assert reverts == ["before"]


def test_worklog_records_negotiation(tmp_path, monkeypatch):
    monkeypatch.setattr("langbridge_cli.settings.L4_WORKLOG_DIR", tmp_path)

    def fake_l3(api_key, model, task, context, **kwargs):
        return PASS

    def fake_l4(api_key, model, task, context, feedback="", **kwargs):
        return READY

    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l3_test_engineer", fake_l3)
    monkeypatch.setattr("langbridge_cli.agents.multi_agent.run_l4_engineer", fake_l4)

    run_log = tmp_path / "run.json"
    output = run_l4_component(
        "key",
        "model",
        {"task": "build", "context": "repo"},
        run_log_path=run_log,
    )

    worklog = tmp_path / "run" / "l34_share_1.md"
    assert worklog.exists()
    text = worklog.read_text(encoding="utf-8")
    assert "L4<->L3 negotiation: build" in text
    assert "WORKLOG_TOKEN: ready" in text
    assert "WORKLOG_TOKEN: pass" in text
    assert "PM_REVIEW_STATUS: OK" in output
