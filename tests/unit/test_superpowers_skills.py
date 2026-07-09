from langbridge_code.skills import list_skills, load_skill


def test_agent_skills_are_discoverable():
    names = {name for name, _ in list_skills()}
    assert "superpowers_test-driven-development" in names
    assert "superpowers_systematic-debugging" in names
    assert "karpathy_think-before-coding" in names


def test_superpowers_skill_has_body():
    body = load_skill("superpowers_test-driven-development")
    assert "test" in body.lower()
    assert len(body) > 100


def test_karpathy_expertise_skill_has_body():
    body = load_skill("karpathy_surgical-changes")
    assert "surgical" in body.lower() or "touch only" in body.lower()


def test_list_skills_for_role():
    planner_names = {name for name, _ in list_skills("planner")}
    assert "superpowers_brainstorming" in planner_names
    assert "superpowers_test-driven-development" not in planner_names

    langbridge_names = {name for name, _ in list_skills("langbridge")}
    assert langbridge_names == set()

    explorer_names = {name for name, _ in list_skills("explorer")}
    assert "superpowers_systematic-debugging" in explorer_names
    assert "superpowers_test-driven-development" not in explorer_names

    worker_names = {name for name, _ in list_skills("worker_coder")}
    assert "superpowers_test-driven-development" in worker_names
    assert "superpowers_using-git-worktrees" not in worker_names
