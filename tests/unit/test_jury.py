import langbridge_code.eval.jury as jury_module


def test_jury_passes_when_both_jurors_pass(monkeypatch):
    def fake_reviewer(*args, **kwargs):
        return "REVIEW_VERDICT: PASS\nEvidence: ok"

    monkeypatch.setattr(jury_module, "run_reviewer", fake_reviewer)

    jury_fn = jury_module.make_jury_fn("key", "model")
    verdict = jury_fn(
        {"problem_statement": "fix bug"},
        {"final_report": "WORKER_STATUS: READY_FOR_REVIEW\nSummary: done"},
    )
    assert verdict["jury_pass"] is True
    assert verdict["verified"] is True


def test_jury_fails_when_one_juror_fails(monkeypatch):
    calls = {"n": 0}

    def fake_reviewer(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "REVIEW_VERDICT: PASS\nEvidence: ok"
        return "REVIEW_VERDICT: FAIL\nIssues: bad"

    monkeypatch.setattr(jury_module, "run_reviewer", fake_reviewer)

    jury_fn = jury_module.make_jury_fn("key", "model")
    verdict = jury_fn(
        {"problem_statement": "fix bug"},
        {"worker": "coder", "final_report": "WORKER_STATUS: READY_FOR_REVIEW\nSummary: done"},
    )
    assert verdict["jury_pass"] is False
