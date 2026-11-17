"""Measure the fast-path promotion gate against CCC-style gold items.

Each item supplies a reference implementation (gold-correct), a single-bug
variant (gold-wrong) and unit tests. The gate sees k of the tests as examples.
For every k and every k-subset of an item's tests, this script records whether
the gate would accept the buggy variant (false accept) or reject the reference
(false reject). No model is called.

The acceptance outcome for a subset follows from the per-test pass vector, so
each candidate is executed once in the sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from itertools import combinations
import json
from pathlib import Path

import sandbox


ROOT = Path(__file__).resolve().parent
DEFAULT_BANK = ROOT / "vendor" / "ccc_code_items.py"
PINS = ROOT / "vendor" / "VENDOR_PINS.json"


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_pin(path):
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    pin = pins.get(Path(path).name)
    return pin is not None and pin["sha256"] == sha256_file(path)


def load_items(path):
    spec = importlib.util.spec_from_file_location("gold_items", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ITEMS


def jsonable(value):
    """Round-trip through JSON so tuples compare as the sandbox returns them."""
    return json.loads(json.dumps(value, allow_nan=False))


def pass_vector(source, tests):
    """Return ``(static_reason, [bool per test])`` for one candidate."""
    accepted, reason = sandbox.check_source(source)
    if not accepted:
        return reason, [False] * len(tests)
    run = sandbox.run_function(source, [jsonable(list(args)) for args, _ in tests])
    if not run.ok:
        return run.error, [False] * len(tests)
    return "OK", [
        result["ok"]
        and sandbox.canonical(result["value"]) == sandbox.canonical(jsonable(expected))
        for result, (_, expected) in zip(run.results, tests)
    ]


def evaluate(items):
    rows, by_k = [], {}
    for item in items:
        tests = item["tests"]
        ref_static, ref = pass_vector(item["reference"], tests)
        bug_static, bug = pass_vector(item["buggy"], tests)
        row = {
            "name": item["name"],
            "tests": len(tests),
            "reference_static": ref_static,
            "reference_passed": sum(ref),
            "buggy_static": bug_static,
            "buggy_passed": sum(bug),
            "by_k": {},
        }
        for k in range(1, len(tests) + 1):
            subsets = list(combinations(range(len(tests)), k))
            false_accepts = sum(all(bug[i] for i in s) for s in subsets)
            false_rejects = sum(not all(ref[i] for i in s) for s in subsets)
            row["by_k"][str(k)] = {
                "subsets": len(subsets),
                "buggy_accepted": false_accepts,
                "reference_rejected": false_rejects,
            }
            total = by_k.setdefault(
                k, {"items": 0, "false_accept_rate_sum": 0.0, "false_reject_rate_sum": 0.0,
                    "items_with_any_false_accept": 0}
            )
            total["items"] += 1
            total["false_accept_rate_sum"] += false_accepts / len(subsets)
            total["false_reject_rate_sum"] += false_rejects / len(subsets)
            total["items_with_any_false_accept"] += false_accepts > 0
        rows.append(row)
    summary = {
        str(k): {
            "items": t["items"],
            "mean_false_accept_rate": t["false_accept_rate_sum"] / t["items"],
            "mean_false_reject_rate": t["false_reject_rate_sum"] / t["items"],
            "items_with_any_false_accept": t["items_with_any_false_accept"],
        }
        for k, t in sorted(by_k.items())
    }
    return {"items": rows, "by_example_count": summary}


def render(result):
    lines = ["examples  items  mean false-accept  items with any  mean false-reject"]
    for k, row in result["by_example_count"].items():
        lines.append(
            f"{k:>8}  {row['items']:>5}  {row['mean_false_accept_rate']:>17.1%}"
            f"  {row['items_with_any_false_accept']:>14}"
            f"  {row['mean_false_reject_rate']:>17.1%}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", default=str(DEFAULT_BANK))
    parser.add_argument("--output")
    args = parser.parse_args()
    if Path(args.bank).resolve() == DEFAULT_BANK and not verify_pin(args.bank):
        parser.error("vendored item bank does not match VENDOR_PINS.json")
    result = evaluate(load_items(args.bank))
    result["bank"] = {"name": Path(args.bank).name, "sha256": sha256_file(args.bank)}
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(render(result))


if __name__ == "__main__":
    main()
