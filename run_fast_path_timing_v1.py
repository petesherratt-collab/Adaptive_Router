"""Three-arm timing run for the fast path. Makes provider calls.

Every request of every shape is served by three arms in a seeded random order:

  A  one direct call to the baseline model;
  B  the fast-path router with synthesis disabled (race only);
  C  the fast-path router as configured, starting from an empty store.

Answer time is wall-clock time until a value is returned. Background learning
is drained, untimed, before the next request of the same shape.

``--set name=value`` overrides one ``fast_path`` setting for a sensitivity run;
the override and a label are written to the header.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
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
import remote
import sandbox


ROOT = Path(__file__).resolve().parent
BASELINE_MODEL = "openai/gpt-5.6-luna"
ARM_ORDER_SEED = 20261116
EARLY_STOP_SHAPES = 3
EARLY_STOP_FAILURE_RATE = 0.20
HASHED_FILES = (
    "config_fast_path.json",
    "fast_path.py",
    "sandbox.py",
    "remote.py",
    "run_fast_path_timing_v1.py",
    "analyze_fast_path_timing_v1.py",
)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_bench(path):
    spec = importlib.util.spec_from_file_location("timing_bench", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_override(text):
    name, _, raw = text.partition("=")
    if not name or not _:
        raise ValueError("override must be name=value")
    return name, json.loads(raw)


def direct_answer(shape, args, remote_config, settings, remote_fn, api_key):
    prompt = fast_path.build_answer_prompt(shape["spec"], shape["signature"], args)
    config = {
        **remote_config,
        "model": BASELINE_MODEL,
        "max_tokens": settings["answer_max_tokens"],
    }
    try:
        result = remote_fn(prompt, config, api_key)
    except Exception:
        return False, None
    return fast_path.parse_answer(result.text) if result.success else (False, None)


def run_shape(shape, inputs, golds, remote_config, settings, remote_fn, api_key, workdir):
    """Return (request rows, shape summary) for one shape."""
    request = {
        "schema_version": fast_path.SCHEMA_VERSION,
        "task": {"spec": shape["spec"], "signature": shape["signature"]},
    }
    routers = {}
    for arm, enabled in (("B", False), ("C", True)):
        base = Path(workdir) / shape["name"] / arm
        routers[arm] = fast_path.FastPathRouter(
            {
                "remote": remote_config,
                "fast_path": {**settings, "synthesis_enabled": enabled},
            },
            base / "store",
            base / "runs.jsonl",
            remote_fn=remote_fn,
            api_key=api_key,
        )
    order_rng = random.Random(f"{ARM_ORDER_SEED}:{shape['name']}")
    rows, promoted_at = [], None
    for index, (args, expected) in enumerate(zip(inputs, golds)):
        order = ["A", "B", "C"]
        order_rng.shuffle(order)
        for position, arm in enumerate(order):
            started = time.perf_counter()
            if arm == "A":
                answered, value = direct_answer(
                    shape, args, remote_config, settings, remote_fn, api_key
                )
                route, model = ("model" if answered else "none"), BASELINE_MODEL
            else:
                result = routers[arm].handle({**request, "args": args})
                answered = result["route"] != "none"
                value, route, model = result["value"], result["route"], result["model"]
            answer_ms = (time.perf_counter() - started) * 1000
            background_ms = 0.0
            if arm != "A":
                started = time.perf_counter()
                routers[arm].drain()
                background_ms = (time.perf_counter() - started) * 1000
            rows.append(
                {
                    "record_type": "request",
                    "shape": shape["name"],
                    "index": index,
                    "arm": arm,
                    "position": position,
                    "answer_ms": answer_ms,
                    "background_ms": background_ms,
                    "route": route,
                    "model": model,
                    "answered": answered,
                    "correct": answered
                    and sandbox.canonical(value) == sandbox.canonical(expected),
                    "value": value if answered else None,
                }
            )
        record = routers["C"].store.get(routers["C"].store.shapes()[0]["shape"])
        if promoted_at is None and record["function"] is not None:
            promoted_at = index
    for router in routers.values():
        router.close()
    return rows, shape_summary(shape, inputs, golds, record, promoted_at)


def shape_summary(shape, inputs, golds, record, promoted_at):
    function = record["function"]
    function_correct = None
    if function is not None:
        calls = [args for args, _ in shape["tests"]] + list(inputs)
        wanted = [expected for _, expected in shape["tests"]] + list(golds)
        run = sandbox.run_function(function["source"], calls, timeout_seconds=10.0)
        function_correct = run.ok and all(
            result["ok"]
            and sandbox.canonical(result["value"]) == sandbox.canonical(expected)
            for result, expected in zip(run.results, wanted)
        )
    gold_by_args = {sandbox.canonical(a): sandbox.canonical(g) for a, g in zip(inputs, golds)}
    wrong_examples = sum(
        gold_by_args.get(sandbox.canonical(e["args"])) != sandbox.canonical(e["expected"])
        for e in record["examples"]
    )
    return {
        "record_type": "shape",
        "shape": shape["name"],
        "promoted_at_index": promoted_at,
        "function_present_at_end": function is not None,
        "function_gold_correct": function_correct,
        "function_source": function["source"] if function else None,
        "synthesis_attempts": record["synthesis_attempts"],
        "demotions": record["demotions"],
        "examples": len(record["examples"]),
        "wrong_examples": wrong_examples,
        "disagreements": record["disagreements"],
    }


def failure_rates(rows):
    rates = {}
    for arm in "ABC":
        mine = [row for row in rows if row["arm"] == arm]
        rates[arm] = sum(not row["answered"] for row in mine) / len(mine) if mine else 0.0
    return rates


def execute(shapes, bench, remote_config, settings, remote_fn, api_key, workers, write):
    """Run all shapes. Returns ``"COMPLETED"`` or ``"EARLY_STOP"``."""
    def job(shape):
        inputs = bench.stream(shape)
        return run_shape(
            shape, inputs, bench.gold(shape, inputs), remote_config, settings,
            remote_fn, api_key, workdir,
        )

    def collect(batch, pool):
        collected = []
        for rows, summary in pool.map(job, batch):
            for row in rows + [summary]:
                write(row)
            collected.extend(rows)
        return collected

    with tempfile.TemporaryDirectory() as workdir, ThreadPoolExecutor(workers) as pool:
        first = collect(shapes[:EARLY_STOP_SHAPES], pool)
        rates = failure_rates(first)
        if len(shapes) > EARLY_STOP_SHAPES and max(rates.values()) > EARLY_STOP_FAILURE_RATE:
            write({"record_type": "early_stop", "failure_rates": rates})
            return "EARLY_STOP"
        collect(shapes[EARLY_STOP_SHAPES:], pool)
    return "COMPLETED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", default=str(ROOT / "fast_path_timing_bench_v1.py"))
    parser.add_argument("--output", required=True, help="observations JSONL (must not exist)")
    parser.add_argument("--label", default="primary")
    parser.add_argument("--set", dest="override", metavar="NAME=VALUE")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit-shapes", type=int)
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
    settings = json.loads(
        (ROOT / "config_fast_path.json").read_text(encoding="utf-8")
    )["fast_path"]
    override = None
    if args.override:
        name, value = parse_override(args.override)
        if name not in settings:
            parser.error(f"unknown fast_path setting: {name}")
        override = {"name": name, "from": settings[name], "to": value}
        settings[name] = value
    bench = load_bench(args.bench)
    shapes = bench.SHAPES[: args.limit_shapes] if args.limit_shapes else bench.SHAPES

    lock = threading.Lock()
    with partial.open("x", encoding="utf-8") as handle:
        def write(row):
            with lock:
                handle.write(json.dumps(row) + "\n")
                handle.flush()

        write(
            {
                "record_type": "header",
                "label": args.label,
                "override": override,
                "baseline_model": BASELINE_MODEL,
                "settings": settings,
                "bench": {"name": Path(args.bench).name, "sha256": sha256_file(args.bench)},
                "shapes": len(shapes),
                "stream_seed": bench.STREAM_SEED,
                "stream_length": bench.STREAM_LENGTH,
                "arm_order_seed": ARM_ORDER_SEED,
                "workers": args.workers,
                "files": {name: sha256_file(ROOT / name) for name in HASHED_FILES},
            }
        )
        status = execute(
            shapes, bench, remote_config, settings, remote.generate, api_key,
            args.workers, write,
        )
        write({"record_type": "footer", "status": status})
    if status == "COMPLETED":
        partial.rename(output)
    print(status, output if status == "COMPLETED" else partial)


if __name__ == "__main__":
    main()
