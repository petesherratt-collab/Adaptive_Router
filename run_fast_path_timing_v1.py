"""Three-arm timing run for the fast path. Makes provider calls.

Every request of every shape is served by three arms in a seeded random order:

  A  one direct call to the baseline model;
  B  the fast-path router with synthesis disabled (race only);
  C  the fast-path router as configured, starting from an empty store.

Answer time is wall-clock time until a value is returned. Background learning
is drained, untimed, before the next request of the same shape.

``--arrival immediate`` removes that pause: the next request is issued while
learning from earlier ones may still be running, and each row records the gap
since the previous request of the same arm. Background work is drained only
when the shape ends.

``--set name=value`` overrides one ``fast_path`` setting for a sensitivity run;
the override and a label are written to the header.
"""

from __future__ import annotations

import argparse
import collections
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


HARD_PROVIDER_ERRORS = frozenset({"OPENROUTER_HTTP_401", "OPENROUTER_HTTP_402"})


class ProviderMonitor:
    """Wrap the remote call, tally provider errors and trip on sustained failure.

    Trips at once on an account-level error (401, 402), or when more than half
    of the last ``window`` calls failed.
    """

    def __init__(self, remote_fn, window=100, limit=0.5):
        self.remote_fn, self.limit = remote_fn, limit
        self.recent = collections.deque(maxlen=window)
        self.errors = collections.Counter()
        self.calls = 0
        self.tripped_by = None
        self._lock = threading.Lock()

    def __call__(self, prompt, config, api_key):
        result = self.remote_fn(prompt, config, api_key)
        with self._lock:
            self.calls += 1
            self.recent.append(result.success)
            if not result.success:
                self.errors[result.error or "UNKNOWN"] += 1
                if result.error in HARD_PROVIDER_ERRORS:
                    self.tripped_by = self.tripped_by or result.error
            if (
                self.tripped_by is None
                and len(self.recent) == self.recent.maxlen
                and self.recent.count(False) / len(self.recent) > self.limit
            ):
                self.tripped_by = "SUSTAINED_FAILURE_RATE"
        return result

    def tripped(self):
        return self.tripped_by is not None

    def report(self):
        return {
            "calls": self.calls,
            "errors": dict(self.errors),
            "tripped_by": self.tripped_by,
        }


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
    except Exception as exc:
        return False, None, type(exc).__name__
    if not result.success:
        return False, None, result.error
    answered, value = fast_path.parse_answer(result.text)
    return answered, value, None if answered else "UNPARSEABLE_ANSWER"


def run_shape(
    shape, inputs, golds, remote_config, settings, remote_fn, api_key, workdir,
    arrival="drained", should_stop=lambda: False,
):
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
    rows, promoted_at, last_end = [], None, {}
    for index, (args, expected) in enumerate(zip(inputs, golds)):
        if should_stop():
            break
        order = ["A", "B", "C"]
        order_rng.shuffle(order)
        for position, arm in enumerate(order):
            started = time.perf_counter()
            gap_ms = (started - last_end[arm]) * 1000 if arm in last_end else None
            error = None
            if arm == "A":
                answered, value, error = direct_answer(
                    shape, args, remote_config, settings, remote_fn, api_key
                )
                route, model = ("model" if answered else "none"), BASELINE_MODEL
            else:
                result = routers[arm].handle({**request, "args": args})
                answered = result["route"] != "none"
                value, route, model = result["value"], result["route"], result["model"]
            last_end[arm] = time.perf_counter()
            answer_ms = (last_end[arm] - started) * 1000
            background_ms = 0.0
            if arm != "A" and arrival == "drained":
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
                    "gap_ms": gap_ms,
                    "background_ms": background_ms,
                    "route": route,
                    "model": model,
                    "answered": answered,
                    "error": error,
                    "correct": answered
                    and sandbox.canonical(value) == sandbox.canonical(expected),
                    "value": value if answered else None,
                }
            )
        record = routers["C"].store.get(
            fast_path.shape_key(shape["spec"], shape["signature"])
        )
        if promoted_at is None and record["function"] is not None:
            promoted_at = index
    for router in routers.values():
        router.close()
    key = fast_path.shape_key(shape["spec"], shape["signature"])
    record = routers["C"].store.get(key)
    if record is None:  # stopped before this shape's first request
        summary = {"record_type": "shape", "shape": shape["name"],
                   "promoted_at_index": None, "function_gold_correct": None,
                   "demotions": [], "wrong_examples": 0}
    else:
        summary = shape_summary(shape, inputs, golds, record, promoted_at)
    summary["requests_completed"] = len(rows) // 3
    return rows, summary


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
    # Examples may include probe inputs outside the request stream, so gold
    # comes from the reference directly. A probe the reference cannot run is
    # outside the specification and is counted separately.
    wrong_examples = unverifiable_examples = 0
    if record["examples"]:
        check = sandbox.run_function(
            shape["reference"], [e["args"] for e in record["examples"]],
            timeout_seconds=10.0,
        )
        for example, result in zip(record["examples"], check.results if check.ok else []):
            if not result["ok"]:
                unverifiable_examples += 1
            elif sandbox.canonical(result["value"]) != sandbox.canonical(example["expected"]):
                wrong_examples += 1
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
        "unverifiable_examples": unverifiable_examples,
        "probes": record.get("probes"),
        "example_sources": dict(
            collections.Counter(e["source"] for e in record["examples"])
        ),
        "disagreements": record["disagreements"],
    }


def failure_rates(rows):
    rates = {}
    for arm in "ABC":
        mine = [row for row in rows if row["arm"] == arm]
        rates[arm] = sum(not row["answered"] for row in mine) / len(mine) if mine else 0.0
    return rates


def execute(
    shapes, bench, remote_config, settings, remote_fn, api_key, workers, write,
    arrival="drained", monitor=None,
):
    """Run all shapes.

    Returns ``"COMPLETED"``, ``"EARLY_STOP"`` or ``"PROVIDER_FAILURE_STOP"``.
    """
    should_stop = monitor.tripped if monitor is not None else (lambda: False)

    def job(shape):
        inputs = bench.stream(shape)
        return run_shape(
            shape, inputs, bench.gold(shape, inputs), remote_config, settings,
            remote_fn, api_key, workdir, arrival, should_stop,
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
        if not should_stop():
            collect(shapes[EARLY_STOP_SHAPES:], pool)
    return "PROVIDER_FAILURE_STOP" if should_stop() else "COMPLETED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", default=str(ROOT / "fast_path_timing_bench_v1.py"))
    parser.add_argument("--output", required=True, help="observations JSONL (must not exist)")
    parser.add_argument("--label", default="primary")
    parser.add_argument("--set", dest="override", metavar="NAME=VALUE")
    parser.add_argument("--arrival", choices=("drained", "immediate"), default="drained")
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
                "arrival": args.arrival,
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
        monitor = ProviderMonitor(remote.generate)
        status = execute(
            shapes, bench, remote_config, settings, monitor, api_key,
            args.workers, write, args.arrival, monitor,
        )
        write({"record_type": "footer", "status": status, "provider": monitor.report()})
    if status == "COMPLETED":
        partial.rename(output)
    print(status, output if status == "COMPLETED" else partial)


if __name__ == "__main__":
    main()
