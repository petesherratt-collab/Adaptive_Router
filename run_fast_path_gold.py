"""Collect model-side fail rates on a gold item bank. Makes provider calls.

For every item this records, without retries or repair:

* each race model's answer to every test (per-model fail rate, and how often
  two models agree on a wrong answer);
* one function written by the synthesis model from the spec alone, graded
  against every test (synthesiser fail rate).

Raw observations go to a JSONL file; ``summarise`` derives the rates from it.
Freeze the item bank, the model list and this file before running.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from itertools import combinations
import json
import os
from pathlib import Path

from dotenv import load_dotenv

import evaluate_fast_path_gate as gate_eval
import fast_path
import remote
import sandbox


ROOT = Path(__file__).resolve().parent


def answer_rows(item, models, remote_config, remote_fn, api_key, pool, max_tokens=None):
    if max_tokens is not None:
        remote_config = {**remote_config, "max_tokens": max_tokens}

    def ask(job):
        index, model = job
        args, expected = item["tests"][index]
        args, expected = gate_eval.jsonable(list(args)), gate_eval.jsonable(expected)
        prompt = fast_path.build_answer_prompt(item["spec"], item["signature"], args)
        result = remote_fn(prompt, {**remote_config, "model": model}, api_key)
        valid, value = (
            fast_path.parse_answer(result.text) if result.success else (False, None)
        )
        return {
            "record_type": "answer",
            "item": item["name"],
            "test": index,
            "model": model,
            "success": result.success,
            "error": result.error,
            "valid": valid,
            "answer": value,
            "correct": valid and sandbox.canonical(value) == sandbox.canonical(expected),
            "total_ms": result.total_ms,
        }

    jobs = [(i, m) for i in range(len(item["tests"])) for m in models]
    return list(pool.map(ask, jobs))


def synthesis_row(item, model, remote_config, max_tokens, remote_fn, api_key):
    prompt = fast_path.build_synthesis_prompt(item["spec"], item["signature"])
    result = remote_fn(
        prompt, {**remote_config, "model": model, "max_tokens": max_tokens}, api_key
    )
    row = {
        "record_type": "synthesis",
        "item": item["name"],
        "model": model,
        "success": result.success,
        "error": result.error,
        "total_ms": result.total_ms,
        "source": None,
        "static": None,
        "passed": [],
    }
    if result.success:
        row["source"] = fast_path._unfence(result.text) + "\n"
        row["static"], row["passed"] = gate_eval.pass_vector(row["source"], item["tests"])
    return row


def summarise(rows):
    answers = [r for r in rows if r["record_type"] == "answer"]
    synth = [r for r in rows if r["record_type"] == "synthesis"]
    models = sorted({r["model"] for r in answers})
    per_model = {}
    for model in models:
        mine = [r for r in answers if r["model"] == model]
        per_model[model] = {
            "observations": len(mine),
            "task_clusters": len({r["item"] for r in mine}),
            "wrong_or_invalid": sum(not r["correct"] for r in mine),
            "invalid": sum(not r["valid"] for r in mine),
        }
    by_case = {}
    for r in answers:
        by_case.setdefault((r["item"], r["test"]), {})[r["model"]] = r
    pairs = {}
    for a, b in combinations(models, 2):
        both = [c for c in by_case.values() if a in c and b in c]
        agreed = [
            c for c in both
            if c[a]["valid"] and c[b]["valid"]
            and sandbox.canonical(c[a]["answer"]) == sandbox.canonical(c[b]["answer"])
        ]
        pairs[f"{a} + {b}"] = {
            "cases": len(both),
            "agreed": len(agreed),
            "agreed_and_wrong": sum(not c[a]["correct"] for c in agreed),
        }
    completed = [r for r in synth if r["success"]]
    return {
        "per_model": per_model,
        "pairwise_agreement": pairs,
        "synthesis": {
            "items": len(synth),
            "provider_failures": len(synth) - len(completed),
            "statically_rejected": sum(r["static"] != "OK" for r in completed),
            "gold_correct": sum(bool(r["passed"]) and all(r["passed"]) for r in completed),
            "gold_wrong": sum(not (r["passed"] and all(r["passed"])) for r in completed),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", default=str(ROOT / "fast_path_gold_items_v1.py"))
    parser.add_argument("--output", required=True, help="observations JSONL (must not exist)")
    args = parser.parse_args()
    if Path(args.output).exists():
        parser.error("output already exists; evidence is never overwritten")

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        parser.error("OPENROUTER_API_KEY is not set")
    remote_config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["remote"]
    settings = json.loads(
        (ROOT / "config_fast_path.json").read_text(encoding="utf-8")
    )["fast_path"]
    items = gate_eval.load_items(args.bank)

    rows = []
    with ThreadPoolExecutor(max_workers=8) as pool, open(
        args.output, "x", encoding="utf-8"
    ) as handle:
        handle.write(json.dumps({
            "record_type": "header",
            "bank_sha256": gate_eval.sha256_file(args.bank),
            "race_models": settings["race_models"],
            "synthesis_model": settings["synthesis_model"],
            "answer_max_tokens": settings["answer_max_tokens"],
            "answer_prompt_sha256": hashlib.sha256(
                fast_path.build_answer_prompt("S", "def solve(a):", ["A"]).encode()
            ).hexdigest(),
        }) + "\n")
        for item in items:
            batch = answer_rows(
                item, settings["race_models"], remote_config, remote.generate, api_key, pool,
                settings["answer_max_tokens"],
            )
            batch.append(synthesis_row(
                item, settings["synthesis_model"], remote_config,
                settings["synthesis_max_tokens"], remote.generate, api_key,
            ))
            for row in batch:
                handle.write(json.dumps(row) + "\n")
            handle.flush()
            rows.extend(batch)
    print(json.dumps(summarise(rows), indent=1))


if __name__ == "__main__":
    main()
