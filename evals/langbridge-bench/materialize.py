"""Split validated jsonl into per-instance JSON files and build on-disk specs.

Work-trial style layout:
  instances/<task_id>.json   — raw SWE-bench-schema instance
  specs/<task_id>.json       — eval-ready spec (what training runners consume)

Run after reference_test.py validates a jsonl batch:

  uv run python evals/langbridge-bench/materialize.py \\
    --jsonl evals/langbridge-bench/out/instances_validated.jsonl
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path


BENCH_DIR = Path(__file__).resolve().parent
DEFAULT_INSTANCES = BENCH_DIR / "instances"
DEFAULT_SPECS = BENCH_DIR / "specs"


def _load_reference_test():
    path = BENCH_DIR / "reference_test.py"
    spec = importlib.util.spec_from_file_location("_lb_reference_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def instance_to_spec(inst, ref):
    return {
        "task_id": inst["instance_id"],
        "status": "ok" if inst.get("FAIL_TO_PASS") else "no_f2p",
        "repo": inst["repo"],
        "base_commit": inst["base_commit"],
        "problem_statement": inst.get("problem_statement", ""),
        "test_files": ref.test_files_in_patch(inst.get("test_patch", "")),
        "test_patch": inst.get("test_patch", ""),
        "gold_code_patch": inst.get("patch", ""),
        "fail_to_pass": inst.get("FAIL_TO_PASS", []),
        "pass_to_pass": inst.get("PASS_TO_PASS", []),
        "hard": bool(inst.get("hard")) or len(inst.get("FAIL_TO_PASS", [])) >= 2,
    }


def split_instances(instances, instances_dir):
    instances_dir = Path(instances_dir)
    instances_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for inst in instances:
        task_id = inst["instance_id"]
        path = instances_dir / f"{task_id}.json"
        path.write_text(json.dumps(inst, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def build_specs(instances_dir, specs_dir, ok_only=True):
    ref = _load_reference_test()
    instances_dir = Path(instances_dir)
    specs_dir = Path(specs_dir)
    specs_dir.mkdir(parents=True, exist_ok=True)
    written = []
    skipped = []
    for path in sorted(instances_dir.glob("*.json")):
        inst = json.loads(path.read_text(encoding="utf-8"))
        spec = instance_to_spec(inst, ref)
        if ok_only and spec.get("status") != "ok":
            skipped.append((spec["task_id"], spec["status"]))
            continue
        out = specs_dir / f"{spec['task_id']}.json"
        out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(out)
    return written, skipped


def materialize(jsonl_path, instances_dir=None, specs_dir=None, ok_only=True):
    instances = load_jsonl(jsonl_path)
    instances_dir = instances_dir or DEFAULT_INSTANCES
    specs_dir = specs_dir or DEFAULT_SPECS
    inst_paths = split_instances(instances, instances_dir)
    spec_paths, skipped = build_specs(instances_dir, specs_dir, ok_only=ok_only)
    return {
        "instances": len(inst_paths),
        "specs": len(spec_paths),
        "skipped": skipped,
        "instances_dir": str(instances_dir),
        "specs_dir": str(specs_dir),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jsonl",
        default=str(BENCH_DIR / "out" / "instances_validated.jsonl"),
        help="Validated instances jsonl (from reference_test.py).",
    )
    parser.add_argument("--instances-dir", default=str(DEFAULT_INSTANCES))
    parser.add_argument("--specs-dir", default=str(DEFAULT_SPECS))
    parser.add_argument("--include-non-ok", action="store_true",
                        help="Also write specs with status != ok.")
    args = parser.parse_args()

    if not Path(args.jsonl).exists():
        print(f"jsonl not found: {args.jsonl}", file=sys.stderr)
        return 1

    summary = materialize(
        args.jsonl,
        instances_dir=args.instances_dir,
        specs_dir=args.specs_dir,
        ok_only=not args.include_non_ok,
    )
    print(f"Wrote {summary['instances']} instances -> {summary['instances_dir']}")
    print(f"Wrote {summary['specs']} specs -> {summary['specs_dir']}")
    if summary["skipped"]:
        print(f"Skipped {len(summary['skipped'])} non-ok specs:")
        for task_id, status in summary["skipped"][:10]:
            print(f"  {task_id}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
