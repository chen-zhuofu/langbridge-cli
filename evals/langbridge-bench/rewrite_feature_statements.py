"""Rewrite problem_statement for feature tasks and restore them to the active set.

Run once after curating excluded feature tasks:

  uv run python evals/langbridge-bench/rewrite_feature_statements.py
"""
from __future__ import annotations

import json
from pathlib import Path

BENCH = Path(__file__).resolve().parent

# Actionable problem statements aligned with hidden tests (not raw GitHub issue text).
REWRITTEN: dict[str, str] = {
    "tqdm__tqdm-1130": """\
Add a `delay` parameter to tqdm progress bars

Implement a new `delay` float parameter on `tqdm` (default `0` for backward compatibility).

When `delay > 0`, the progress bar must not write any output until `delay` seconds have elapsed since the bar was created. After that threshold, updates should render normally.

Expected behavior:
- `tqdm(total=2, delay=3)` with mocked time:
  - At elapsed time 2s, `update(1)` → no output written yet
  - At elapsed time 4s, `update(1)` → output appears
- If the bar is closed before ever being displayed, `close()` should not try to clear the screen.

This is similar to Qt's `QProgressDialog.minimumDuration` — hide the bar for fast operations.""",

    "tqdm__tqdm-1493": """\
Improve tqdm's `envwrap` decorator for typed environment-variable overrides

Refactor `tqdm.utils.envwrap` so environment variables can override function parameters with correct types.

Requirements:
1. Replace the old `literal_eval` and `case_sensitive` kwargs with a `types` dict mapping parameter names to coercion callables (e.g. `int`, `ast.literal_eval`). Use `types[name](value)` when inference fails.
2. When the wrapped function has type annotations, try each annotation type (including `Union` members via `__args__`) to coerce env var strings.
3. When there is no annotation, coerce using the type of the parameter's default value.
4. Ignore env vars that do not match a function parameter name.
5. Update `@envwrap("TQDM_")` on `tqdm.__init__` to pass explicit `types` for `total` (float), `ncols`, `miniters` (float), `position`, and `nrows` (int).

Tests exercise `@envwrap("FUNC_", types=defaultdict(lambda: literal_eval))` and annotation-based coercion.""",

    "networkx__networkx-8630": """\
Make `nx.barycenter` an alias of `nx.centroid`

In `networkx.algorithms.distance_measures`, `centroid` is the primary name for the graph centroid/barycenter function. Keep backward compatibility:

- `nx.barycenter` must be the **same function object** as `nx.centroid` (e.g. `barycenter = centroid`, not a wrapper).
- Update doc cross-references to prefer `centroid` over `barycenter`.""",

    "networkx__networkx-8591": """\
Add butterfly counting to the NetworkX bipartite module

Implement `networkx.algorithms.bipartite.butterflies(G, nodes=None)`.

**Definition**: A butterfly is a complete bipartite subgraph K_{2,2} — four vertices with all cross-edges present.

**Returns**: `dict[node, int]` — per-node participation count.
- Total butterfly count = `sum(result.values()) // 4` (each butterfly touches 4 nodes).
- Example: a single K_{2,2} → `{0: 1, 1: 1, 2: 1, 3: 1}` with total 1.
- K_{3,3} → each node count 6, total 9.
- Graphs with no butterflies → all zeros; isolated nodes → 0.

**`nodes` parameter** (optional): filter returned dict keys only (same convention as `nx.triangles`). Computation always uses the full graph. Nodes not in `G` are silently ignored.

**Errors**: directed graphs must raise `NetworkXNotImplemented`.

**Disconnected bipartite graphs** must work without raising `AmbiguousSolution`.

Export in module `__all__` and add to bipartite reference docs.""",

    "pallets__click-3473": """\
Add `help` parameter to `click.Argument`

Implement optional `help` on positional arguments, similar to options.

Requirements:
1. `--help` shows a **"Positional arguments:"** section before **"Options:"** when any argument has help text.
2. Omit the positional section when no arguments define help.
3. Optional arguments display metavar as `[NAME]`.
4. Deprecated arguments append a deprecation label: `(DEPRECATED)` or `(DEPRECATED: message)`. When help is empty or `None`, show only the label with no leading space.
5. `Argument.to_info_dict()` includes a `help` field (apply `inspect.cleandoc` to multi-line help).
6. `Command.to_info_dict()` exposes argument help in its `params` list.""",

    "pytest-dev__pytest-14568": """\
Add public `pytest.register_fixture()` API for plugins

Plugins sometimes need to register fixtures imperatively during collection (e.g. dynamically created multihost fixtures). Add a public API:

```python
pytest.register_fixture(name="fix", func=..., node=session_or_item, scope="function", ...)
```

Requirements:
- Export `register_fixture` from the top-level `pytest` package.
- Delegate to the fixture manager's registration logic.
- Replace internal `session._fixturemanager._register_fixture(...)` calls in pytest's own codebase with `fixtures.register_fixture(...)`.
- Fixture visibility follows the collection tree: only items under `node` can request the fixture. Use `node=session` for global visibility.
- When multiple fixtures share a name at different scopes, item-level fixtures must take precedence over session-level fixtures with correct chaining order.""",

    "pytest-dev__pytest-14576": """\
Improve assertion reporting for `dict.items()` subset comparisons

When `assert left.items() >= right.items()` or `assert left.items() <= right.items()` fails, pytest should show a readable diff (like set comparisons), not a raw `dict_items(...)` repr.

Requirements:
- For `>=` failures: show **"Extra items in the right set:"** with the missing `(key, value)` pairs from the right side.
- For `<=` failures: show **"Extra items in the left set:"** with items present on the left but not covered by the right side.

Example:
```python
x = {"a": 1, "b": 2}
y = {"a": 1, "b": 2, "c": 3}
assert x.items() >= y.items()
# Expected output includes: Extra items in the right set: ('c', 3)
```

Implement in pytest's assertion rewrite / repr-compare path so `ItemsView` comparisons get set-style reporting.""",
}

FEATURE_IDS = list(REWRITTEN.keys())


def restore_feature(task_id: str, problem_statement: str) -> None:
    for sub in ("specs", "instances"):
        ex = BENCH / sub / "excluded" / f"{task_id}.json"
        active = BENCH / sub / f"{task_id}.json"
        if not ex.exists():
            raise FileNotFoundError(ex)
        data = json.loads(ex.read_text(encoding="utf-8"))
        data["status"] = "ok"
        data.pop("exclude_reason", None)
        data["problem_statement"] = problem_statement
        if sub == "specs":
            data["task_kind"] = "feature"
            data["problem_statement_source"] = "rewritten"
        active.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ex.unlink()


def main() -> int:
    for task_id, stmt in REWRITTEN.items():
        restore_feature(task_id, stmt)
        print(f"restored {task_id}")
    active = len(list((BENCH / "specs").glob("*.json")))
    excluded = len(list((BENCH / "specs" / "excluded").glob("*.json")))
    print(f"active specs: {active}, still excluded: {excluded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
