"""TDD execution harness for L4/L5 component tasks.

Workflow enforced by the runtime (not prompt-only):

  1. Test phase — engineer may change test files only; production code is off limits.
  2. Red gate — the new tests must fail (exit code != 0) before implementation starts.
  3. Lock — content hashes of every touched test file are recorded and written
     to agent-state/acceptance/<slug>/test.json (frozen acceptance spec).
  4. Implement phase — any write to a test path is blocked; hashes are re-checked
     before L3 review rounds. L4/L3 use test.json paths to judge completion.

Plan-mode L5 requests skip this harness.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

from langbridge_cli.settings import WORKSPACE_ROOT

WRITE_TOOL_NAMES = frozenset({"create_file", "edit_file", "delete_file"})
ACCEPTANCE_DIR_NAME = "acceptance"
TEST_JSON_NAME = "test.json"

_TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|test)(/|$)|(^|/)test_[^/]+\.py$|[^/]+_test\.py$|(^|/)conftest\.py$",
    re.IGNORECASE,
)


def is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip().lstrip("./")
    return bool(_TEST_PATH_RE.search(normalized))


def _resolve_rel(path: str) -> str:
    target = (WORKSPACE_ROOT / path).resolve()
    return str(target.relative_to(WORKSPACE_ROOT)).replace("\\", "/")


def file_content_hash(path: str) -> str | None:
    target = WORKSPACE_ROOT / path
    if not target.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(target.read_bytes())
    return digest.hexdigest()


def lock_hashes(paths: list[str]) -> dict[str, str]:
    locked = {}
    for path in paths:
        rel = _resolve_rel(path)
        digest = file_content_hash(rel)
        if digest is not None:
            locked[rel] = digest
    return locked


def verify_locked_unchanged(locked: dict[str, str]) -> tuple[bool, str]:
    for rel, expected in locked.items():
        current = file_content_hash(rel)
        if current is None:
            return False, f"TDD lock violated: missing locked test file {rel}"
        if current != expected:
            return False, f"TDD lock violated: {rel} was modified during implementation (hash mismatch)."
    return True, ""


def collect_changed_test_paths() -> list[str]:
    """Return test paths added or modified in the working tree (staged or not)."""
    if not (WORKSPACE_ROOT / ".git").exists():
        return _collect_changed_test_paths_no_git()
    result = subprocess.run(
        ["git", "status", "--porcelain", "-u", "--", "."],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        raw = line[3:].strip()
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        if is_test_path(raw):
            paths.append(_resolve_rel(raw))
    return sorted(set(paths))


def _collect_changed_test_paths_no_git() -> list[str]:
    # Without git, treat every test file under tests/ as in scope after test phase.
    paths = []
    for candidate in WORKSPACE_ROOT.rglob("*"):
        if not candidate.is_file():
            continue
        rel = str(candidate.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        if is_test_path(rel):
            paths.append(rel)
    return sorted(set(paths))


def verify_red_gate(test_paths: list[str]) -> tuple[bool, str]:
    return _verify_pytest_gate(test_paths, expect_pass=False)


def verify_green_gate(acceptance: dict) -> tuple[bool, str]:
    """Acceptance tests from test.json must pass before the task is complete."""
    paths = acceptance.get("paths") or []
    if not paths:
        return False, "Acceptance spec has no test paths."
    return _verify_pytest_gate(paths, expect_pass=True)


def _verify_pytest_gate(test_paths: list[str], *, expect_pass: bool) -> tuple[bool, str]:
    if not test_paths:
        label = "green" if expect_pass else "red"
        return False, f"TDD {label} gate: no test paths."

    from langbridge_cli.tools.testing import run_tests

    target = test_paths[0] if len(test_paths) == 1 else _common_test_root(test_paths)
    payload = json.loads(run_tests(target))
    exit_code = payload.get("exit_code")
    if exit_code is None:
        return False, "TDD gate: test command did not finish (timeout or error)."
    if expect_pass:
        if exit_code == 0:
            return True, "Green gate passed: acceptance tests in test.json all pass."
        return False, (
            "Green gate: acceptance tests in test.json still fail. "
            "Implement production code until they pass."
        )
    if exit_code == 0:
        return False, (
            "TDD red gate: tests already pass before implementation. "
            "Write failing tests that encode the missing behavior first."
        )
    return True, "TDD red gate passed: tests fail as expected before implementation."


def test_json_path(task: str) -> Path:
    from langbridge_cli.agents.component_plan import slugify

    return WORKSPACE_ROOT / "agent-state" / ACCEPTANCE_DIR_NAME / slugify(task) / TEST_JSON_NAME


def build_acceptance_spec(task: str, locked: dict[str, str]) -> dict:
    rel_path = str(test_json_path(task).relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    return {
        "version": 1,
        "task": task,
        "status": "frozen",
        "runner": "pytest",
        "paths": sorted(locked.keys()),
        "locked_hashes": locked,
        "test_json_path": rel_path,
    }


def write_test_json(task: str, locked: dict[str, str]) -> dict:
    """Persist frozen acceptance tests so L4/L3 can judge task completion."""
    spec = build_acceptance_spec(task, locked)
    path = test_json_path(task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    return spec


def read_test_json(task: str) -> dict | None:
    path = test_json_path(task)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def acceptance_context_block(acceptance: dict) -> str:
    paths = acceptance.get("paths") or []
    if not paths:
        return ""
    test_json = acceptance.get("test_json_path", TEST_JSON_NAME)
    locked = acceptance.get("locked_hashes") or {}
    lines = [
        f"Acceptance criteria (frozen in {test_json}):",
        f"- Runner: {acceptance.get('runner', 'pytest')}",
        "- Test paths:",
    ]
    for rel in paths:
        digest = locked.get(rel, "")
        suffix = f" (sha256={digest[:12]}…)" if digest else ""
        lines.append(f"  - {rel}{suffix}")
    lines.extend(
        [
            "",
            "Task is complete only when all acceptance tests in test.json pass and "
            "those test files are unchanged. Run exactly the paths listed above.",
        ]
    )
    return "\n".join(lines)


def verify_acceptance(acceptance: dict) -> tuple[bool, str]:
    """Hashes unchanged and acceptance tests pass — runtime completion check."""
    paths = acceptance.get("paths") or []
    if not paths:
        return False, "Acceptance spec has no test paths."
    locked = acceptance.get("locked_hashes") or {}
    ok, msg = verify_locked_unchanged(locked)
    if not ok:
        return False, msg
    return verify_green_gate(acceptance)


def _common_test_root(paths: list[str]) -> str:
    parts = [path.split("/") for path in paths]
    common = []
    for segment in zip(*parts):
        if len(set(segment)) == 1:
            common.append(segment[0])
        else:
            break
    return "/".join(common) if common else paths[0]


def test_phase_guard(tool_name: str, arguments: dict) -> str | None:
    if tool_name not in WRITE_TOOL_NAMES:
        return None
    path = arguments.get("path")
    if not path:
        return None
    if not is_test_path(str(path)):
        return (
            "TDD harness (test phase): change test files only. "
            "Do not edit production code until the implement phase."
        )
    return None


def implement_phase_guard(locked: dict[str, str], tool_name: str, arguments: dict) -> str | None:
    if tool_name not in WRITE_TOOL_NAMES:
        return None
    path = arguments.get("path")
    if not path or not is_test_path(str(path)):
        return None
    rel = _resolve_rel(str(path))
    if rel in locked:
        return (
            f"TDD harness (implement phase): {rel} is locked "
            f"(sha256 {locked[rel][:12]}…). Implement production code only."
        )
    return (
        f"TDD harness (implement phase): cannot add or modify test file {rel} "
        "after the test phase."
    )


def lock_summary(locked: dict[str, str]) -> str:
    if not locked:
        return "No test files locked."
    lines = ["Locked test files (do not edit during implementation):"]
    for rel, digest in sorted(locked.items()):
        lines.append(f"- {rel} sha256={digest}")
    return "\n".join(lines)


def save_lock(task: str, locked: dict[str, str]) -> dict:
    """Write agent-state/acceptance/<slug>/test.json and return the spec."""
    return write_test_json(task, locked)


def test_phase_user_prompt(task: str, context: str, worker_label: str = "L4") -> str:
    parts = [
        f"TDD test phase ({worker_label}). Write ONLY the failing tests for this task.",
        "Do not change production/source code in this phase.",
        "Run the tests and confirm they fail for the right reason, then return READY_FOR_REVIEW.",
        "",
        f"Task:\n{task}",
    ]
    if context:
        parts.extend(["", f"Additional context:\n{context}"])
    return "\n\n".join(parts)


def implement_phase_user_prompt(
    task: str, context: str, acceptance: dict, feedback: str = "", worker_label: str = "L4"
) -> str:
    locked = acceptance.get("locked_hashes") or {}
    test_json = acceptance.get("test_json_path", TEST_JSON_NAME)
    parts = [
        f"TDD implement phase ({worker_label}). Acceptance tests are frozen in {test_json}.",
        "Do not edit those test files; implement production code until they pass.",
        "",
        lock_summary(locked),
        "",
        f"Run pytest on the paths in {test_json} and confirm all pass before READY_FOR_REVIEW.",
        "",
        f"Task:\n{task}",
    ]
    if context:
        parts.extend(["", f"Additional context:\n{context}"])
    if feedback:
        parts.extend(["", f"L3 feedback to address:\n{feedback}"])
    return "\n\n".join(parts)
