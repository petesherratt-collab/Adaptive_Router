"""Measure boundary probing against items with a known buggy variant.

For each item the probe model proposes boundary inputs from the specification
alone, every race model answers them, and unanimous answers become probe
examples, exactly as in the router. The script then records whether those
probe examples alone would reject the buggy variant (wanted) and whether they
would reject the reference (a false reject). Makes provider calls.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

import evaluate_fast_path_gate as gate_eval
import fast_path
import remote
import sandbox


ROOT = Path(__file__).resolve().parent


def passes(source, examples):
    """Per-example pass vector for ``source``; all False if it cannot run."""
    if not examples:
        return []
    run = sandbox.run_function(source, [e["args"] for e in examples], timeout_seconds=10.0)
    if not run.ok:
        return [False] * len(examples)
    return [
        result["ok"]
        and sandbox.canonical(result["value"]) == sandbox.canonical(example["expected"])
        for result, example in zip(run.results, examples)
    ]


def evaluate_item(router, item, bank):
    arity = len(item["tests"][0][0])
    probes, error = router.propose_probes(item["spec"], item["signature"], arity)
    agreed, disagreed = router.answer_probes(item["spec"], item["signature"], probes)
    reference = passes(item["reference"], agreed)
    buggy = passes(item["buggy"], agreed)
    return {
        "record_type": "item",
        "bank": bank,
        "item": item["name"],
        "probe_error": error,
        "proposed": len(probes),
        "agreed": len(agreed),
        "disagreed": disagreed,
        "examples": agreed,
        "reference_passed": reference,
        "buggy_passed": buggy,
        "reference_rejected": not all(reference),
        "buggy_rejected": not all(buggy),
    }


def summarise(rows):
    items = [r for r in rows if r["record_type"] == "item"]
    return {
        "items": len(items),
        "items_with_probe_examples": sum(r["agreed"] > 0 for r in items),
        "probes_proposed": sum(r["proposed"] for r in items),
        "probes_agreed": sum(r["agreed"] for r in items),
        "probes_disagreed": sum(r["disagreed"] for r in items),
        "buggy_rejected": sum(r["buggy_rejected"] for r in items),
        "buggy_accepted": sum(not r["buggy_rejected"] for r in items),
        "reference_rejected": sum(r["reference_rejected"] for r in items),
        "reference_rejected_items": [r["item"] for r in items if r["reference_rejected"]],
        "buggy_accepted_items": [r["item"] for r in items if not r["buggy_rejected"]],
    }


def load_bank(path):
    """Items from a gold bank, or one item from a JSON file of extra cases."""
    if str(path).endswith(".json"):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return gate_eval.load_items(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", action="append", required=True)
    parser.add_argument("--output", required=True, help="observations JSONL (must not exist)")
    args = parser.parse_args()
    if Path(args.output).exists():
        parser.error("output already exists; evidence is never overwritten")
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        parser.error("OPENROUTER_API_KEY is not set")
    config = {
        "remote": json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["remote"],
        "fast_path": json.loads(
            (ROOT / "config_fast_path.json").read_text(encoding="utf-8")
        )["fast_path"],
    }
    rows = []
    with tempfile.TemporaryDirectory() as work, open(args.output, "x", encoding="utf-8") as out:
        router = fast_path.FastPathRouter(
            config, Path(work) / "store", Path(work) / "runs.jsonl",
            remote_fn=remote.generate, api_key=api_key,
        )
        out.write(json.dumps({
            "record_type": "header",
            "banks": {Path(b).name: gate_eval.sha256_file(b) for b in args.bank},
            "probe_model": config["fast_path"]["probe_model"],
            "max_probes": config["fast_path"]["max_probes"],
            "race_models": config["fast_path"]["race_models"],
        }) + "\n")
        for bank in args.bank:
            for item in load_bank(bank):
                row = evaluate_item(router, item, Path(bank).name)
                out.write(json.dumps(row) + "\n")
                out.flush()
                rows.append(row)
        router.close()
    print(json.dumps(summarise(rows), indent=1))


if __name__ == "__main__":
    main()
