"""Four-arm run for multi-step jobs. Makes provider calls.

Every job of every shape is served by four arms in a seeded random order:

  A  one direct call: the baseline model carries out the whole plan;
  R  the whole-plan prompt raced across the roster, first usable answer wins;
  B  the step pipeline with every step on the model race (no code);
  C  the step pipeline over the fast path, starting from an empty store.

Answer time is wall-clock time until the job's value is returned. Background
learning is drained, untimed, before the next job of the same shape.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import random
import tempfile
import threading
import time

from dotenv import load_dotenv

import fast_path
import pipeline
import remote
from run_fast_path_timing_v1 import BASELINE_MODEL, ProviderMonitor, parse_override, sha256_file
import sandbox


ROOT = Path(__file__).resolve().parent
ARMS = ("A", "R", "B", "C")
ARM_ORDER_SEED = 20261118
HASHED_FILES = (
    "config_fast_path.json", "fast_path.py", "pipeline.py", "sandbox.py", "remote.py",
    "run_fast_path_timing_v1.py", "run_fast_path_jobs_v1.py", "analyze_fast_path_jobs_v1.py",
)


def load_bench(path):
    spec = importlib.util.spec_from_file_location("jobs_bench", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def same(a, b):
    return sandbox.canonical(a) == sandbox.canonical(b)


def direct(prompt, remote_config, settings, remote_fn, api_key):
    config = {**remote_config, "model": BASELINE_MODEL, "max_tokens": settings["answer_max_tokens"]}
    try:
        result = remote_fn(prompt, config, api_key)
    except Exception as exc:
        return False, None, type(exc).__name__
    if not result.success:
        return False, None, result.error
    answered, value = fast_path.parse_answer(result.text)
    return answered, value, None if answered else "UNPARSEABLE_ANSWER"


def run_shape(shape, instances, golds, remote_config, settings, remote_fn, api_key,
              workdir, should_stop=lambda: False):
    routers, orchestrators = {}, {}
    for arm, learning in (("B", False), ("C", True)):
        base = Path(workdir) / shape["name"] / arm
        arm_settings = {**settings, "synthesis_enabled": learning}
        if not learning:
            arm_settings["probe_enabled"] = False
        routers[arm] = fast_path.FastPathRouter(
            {"remote": remote_config, "fast_path": arm_settings},
            base / "store", base / "runs.jsonl", remote_fn=remote_fn, api_key=api_key,
        )
        orchestrators[arm] = pipeline.Orchestrator(routers[arm], base / "jobs.jsonl")
    order_rng = random.Random(f"{ARM_ORDER_SEED}:{shape['name']}")
    kinds = {s["id"]: s["kind"] for s in shape["steps"]}
    rows = []
    for index, ((inputs, _), gold) in enumerate(zip(instances, golds)):
        if should_stop():
            break
        document = bench_job(shape, inputs)
        prompt = pipeline.build_job_prompt(document)
        expected = gold[shape["output"]]
        order = list(ARMS)
        order_rng.shuffle(order)
        for position, arm in enumerate(order):
            started = time.perf_counter()
            steps, error, model = None, None, None
            if arm == "A":
                answered, value, error = direct(prompt, remote_config, settings, remote_fn, api_key)
                model = BASELINE_MODEL
            elif arm == "R":
                model, value = routers["B"].race_prompt(prompt)
                answered = model is not None
            else:
                result = orchestrators[arm].run(document)
                answered = result["reason"] == pipeline.JOB_COMPLETED
                value = result["value"]
                steps = [
                    {"id": s["id"], "kind": s["kind"], "route": s["route"], "ms": s["ms"],
                     "started_ms": s["started_ms"],
                     "correct": s["route"] != "none" and same(s["value"], gold[s["id"]])}
                    for s in result["steps"]
                ]
            answer_ms = (time.perf_counter() - started) * 1000
            background_ms = 0.0
            if arm in routers:
                started = time.perf_counter()
                routers[arm].drain()
                background_ms = (time.perf_counter() - started) * 1000
            rows.append({
                "record_type": "job", "shape": shape["name"], "index": index, "arm": arm,
                "position": position, "answer_ms": answer_ms, "background_ms": background_ms,
                "answered": answered, "error": error, "model": model,
                "correct": answered and same(value, expected),
                "value": value if answered else None, "steps": steps,
            })
    for orchestrator in orchestrators.values():
        orchestrator.close()
    for router in routers.values():
        router.close()
    summary = shape_summary(shape, instances, golds, routers["C"], kinds)
    summary["jobs_completed"] = len(rows) // len(ARMS)
    return rows, summary


def bench_job(shape, inputs):
    return {
        "schema_version": pipeline.SCHEMA_VERSION,
        "inputs": inputs,
        "steps": [
            {"id": s["id"], "kind": s["kind"],
             "task": {"spec": s["spec"], "signature": s["signature"]}, "args": s["args"]}
            for s in shape["steps"]
        ],
        "output": shape["output"],
    }


def shape_summary(shape, instances, golds, router, kinds):
    """What arm C learned for each function step, checked against gold."""
    steps = []
    for step in shape["steps"]:
        if step["kind"] != "function":
            continue
        record = router.store.get(fast_path.shape_key(step["spec"], step["signature"]))
        entry = {"id": step["id"], "promoted": False, "function_gold_correct": None,
                 "examples": 0, "wrong_examples": 0, "probes": None,
                 "synthesis_attempts": [], "demotions": []}
        if record is not None:
            calls = [args for args, _ in step["tests"]] + [
                [g[a["ref"]] if "ref" in a else a["value"] for a in step["args"]] for g in golds
            ]
            wanted = [expected for _, expected in step["tests"]] + [g[step["id"]] for g in golds]
            function = record["function"]
            if function is not None:
                run = sandbox.run_function(function["source"], calls, timeout_seconds=10.0)
                entry["function_gold_correct"] = run.ok and all(
                    r["ok"] and same(r["value"], w) for r, w in zip(run.results, wanted)
                )
                entry["function_source"] = function["source"]
            wrong, wrong_list = 0, []
            if record["examples"]:
                check = sandbox.run_function(
                    step["reference"], [e["args"] for e in record["examples"]], timeout_seconds=10.0
                )
                for example, result in zip(record["examples"], check.results if check.ok else []):
                    if result["ok"] and not same(result["value"], example["expected"]):
                        wrong += 1
                        wrong_list.append({**example, "reference": result["value"]})
            entry.update({
                "promoted": function is not None, "examples": len(record["examples"]),
                "wrong_examples": wrong, "wrong_example_detail": wrong_list,
                "probes": record.get("probes"),
                "synthesis_attempts": record["synthesis_attempts"], "demotions": record["demotions"],
            })
        steps.append(entry)
    judgement_shapes_stored = sum(
        router.store.get(fast_path.shape_key(s["spec"], s["signature"])) is not None
        for s in shape["steps"] if s["kind"] == "judgement"
    )
    return {"record_type": "shape", "shape": shape["name"], "function_steps": steps,
            "judgement_shapes_stored": judgement_shapes_stored}


def execute(shapes, bench, remote_config, settings, remote_fn, api_key, workers, write,
            monitor=None):
    should_stop = monitor.tripped if monitor is not None else (lambda: False)

    def job(shape):
        instances = bench.stream(shape)
        return run_shape(shape, instances, bench.gold(shape, instances), remote_config,
                         settings, remote_fn, api_key, workdir, should_stop)

    with tempfile.TemporaryDirectory() as workdir, ThreadPoolExecutor(workers) as pool:
        for rows, summary in pool.map(job, shapes):
            for row in rows + [summary]:
                write(row)
    return "PROVIDER_FAILURE_STOP" if should_stop() else "COMPLETED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", default=str(ROOT / "fast_path_jobs_bench_v1.py"))
    parser.add_argument("--output", required=True, help="observations JSONL (must not exist)")
    parser.add_argument("--label", default="primary")
    parser.add_argument("--set", dest="override", metavar="NAME=VALUE")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    output = Path(args.output)
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        parser.error("output or its .partial already exists; evidence is never overwritten")
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        parser.error("OPENROUTER_API_KEY is not set")
    remote_config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["remote"]
    settings = json.loads((ROOT / "config_fast_path.json").read_text(encoding="utf-8"))["fast_path"]
    override = None
    if args.override:
        name, value = parse_override(args.override)
        if name not in settings:
            parser.error(f"unknown fast_path setting: {name}")
        override = {"name": name, "from": settings[name], "to": value}
        settings[name] = value
    bench = load_bench(args.bench)

    lock = threading.Lock()
    with partial.open("x", encoding="utf-8") as handle:
        def write(row):
            with lock:
                handle.write(json.dumps(row) + "\n")
                handle.flush()

        write({
            "record_type": "header", "label": args.label, "override": override,
            "baseline_model": BASELINE_MODEL, "settings": settings,
            "bench": {"name": Path(args.bench).name, "sha256": sha256_file(args.bench)},
            "shapes": len(bench.SHAPES), "stream_seed": bench.STREAM_SEED,
            "stream_length": bench.STREAM_LENGTH, "arm_order_seed": ARM_ORDER_SEED,
            "workers": args.workers,
            "files": {name: sha256_file(ROOT / name) for name in HASHED_FILES},
        })
        monitor = ProviderMonitor(remote.generate)
        status = execute(bench.SHAPES, bench, remote_config, settings, monitor, api_key,
                         args.workers, write, monitor)
        write({"record_type": "footer", "status": status, "provider": monitor.report()})
    if status == "COMPLETED":
        partial.rename(output)
    print(status, output if status == "COMPLETED" else partial)


if __name__ == "__main__":
    main()
