"""Three-arm run for jobs given as plain-language tasks. Makes provider calls.

Every job of every shape is served by three arms in a seeded random order:

  A  one direct call: the baseline model carries out the whole task;
  R  the whole-task prompt raced across the roster, first usable answer wins;
  C  the planning router: races the task until it has written, checked and
     adopted a plan, then runs that plan over the fast path.

Answer time is wall-clock time until the job's value is returned. Background
work (examples, planning, plan trials, function learning) is drained, untimed,
before the next job of the same shape.
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
import planner
import remote
from run_fast_path_jobs_v1 import direct, same
from run_fast_path_timing_v1 import BASELINE_MODEL, ProviderMonitor, parse_override, sha256_file
import sandbox
import write_once


ROOT = Path(__file__).resolve().parent
ARMS = ("A", "R", "C")
READING_FIXES = {"batch_readings": True, "uncertainty_gate": True, "adaptive_width": {"width": 2, "after": 5}}
ARM_ORDER_SEED = 20261117
HASHED_FILES = (
    "config_fast_path.json", "fast_path.py", "pipeline.py", "planner.py", "sandbox.py", "remote.py",
    "run_fast_path_planned_v1.py", "analyze_fast_path_planned_v1.py", "write_once.py",
)


def load_bench(path):
    spec = importlib.util.spec_from_file_location("planned_bench", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PURPOSES = (
    ("Carry out the task below", "whole_task"),
    ("Work out what the function described below returns", "step_answer"),
    ("Plan how to compute", "plan"),
    ("Write a Python function", "synthesis"),
    ("List boundary and edge-case inputs", "probe_proposal"),
)


def purpose_of(prompt):
    """Name what a provider call was for, from the start of its prompt.
    ``step_answer`` covers step races and probe answers alike."""
    for prefix, name in PURPOSES:
        if prompt.startswith(prefix):
            return name
    return "other"


class UsageMeter:
    """Wrap a remote call and add up calls and tokens, background work
    included, in total and by purpose."""

    def __init__(self, remote_fn):
        self.remote_fn = remote_fn
        self.calls = self.prompt_tokens = self.completion_tokens = 0
        self.by_purpose = {}
        self._lock = threading.Lock()

    def __call__(self, prompt, config, api_key):
        result = self.remote_fn(prompt, config, api_key)
        prompt_tokens = getattr(result, "prompt_tokens", None) or 0
        completion_tokens = getattr(result, "completion_tokens", None) or 0
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            entry = self.by_purpose.setdefault(
                purpose_of(prompt), {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
            entry["calls"] += 1
            entry["prompt_tokens"] += prompt_tokens
            entry["completion_tokens"] += completion_tokens
        return result

    def report(self):
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "by_purpose": {k: dict(v) for k, v in sorted(self.by_purpose.items())}}


def ceiling_answer(shape, reading, inputs, router):
    """Arm D: the reading step raced exactly as arm C races its judgement
    steps, then the benchmark's own reference code for everything else. With
    ``item_field`` the reading is made on every item of a list input, each
    raced in parallel, giving a list of labels.

    Returns ``(answered, value, label)``. A label the reference code cannot use
    makes the job wrong, not unanswered.
    """
    def read(text):
        return router.handle(
            {"schema_version": fast_path.SCHEMA_VERSION,
             "task": {"spec": reading["spec"], "signature": reading["signature"]},
             "args": [text]},
            learn=False,
        )
    if reading.get("item_field"):
        texts = [item[reading["item_field"]] for item in inputs[reading["field"]]]
        with ThreadPoolExecutor(max(1, len(texts))) as pool:
            results = list(pool.map(read, texts))
        if any(r["route"] == "none" for r in results):
            return False, None, None
        label = [r["value"] for r in results]
    else:
        result = read(inputs[reading["field"]])
        if result["route"] == "none":
            return False, None, None
        label = result["value"]
    try:
        return True, shape["reference"](inputs, {reading["label"]: label}), label
    except Exception:
        return True, None, label


def code_only_answer(shape, rules, inputs):
    """Arm E: no model at all. The reading step is the hand-written keyword
    rule, everything else the benchmark's reference code.

    Returns ``(value, label)``; a rule that raises leaves the job wrong."""
    field, label_name, _ = shape["reading"]
    try:
        label = rules[shape["name"]](inputs[field])
        return shape["reference"](inputs, {label_name: label}), label
    except Exception:
        return None, None


def run_shape(shape, instances, golds, remote_config, settings, remote_fn, api_key,
              workdir, should_stop=lambda: False, arrival="drained", ceiling=None, code_only=None,
              only=None, write_arm=False, probes=0, early=False, fixes=False, flagged=False, alongside=False):
    base = Path(workdir) / shape["name"]
    arms = (ARMS + (("D",) if ceiling else ()) + (("E",) if code_only else ()) + (("W",) if write_arm else ())
            + (("P",) if probes else ()) + (("Q",) if early else ()) + (("B",) if fixes else ())
            + (("F", "M") if flagged else ()) + (("S",) if alongside else ()))
    if only:
        arms = tuple(arm for arm in arms if arm in only)
    meters = {arm: UsageMeter(remote_fn) for arm in ("A", "R", "C", "D", "W", "P", "Q", "B", "F", "M", "S")}
    reading = ceiling[shape["name"]] if ceiling else None
    ceiling_router = fast_path.FastPathRouter(
        {"remote": remote_config, "fast_path": {**settings, "synthesis_enabled": False}},
        base / "ceiling_store", base / "ceiling_runs.jsonl",
        remote_fn=meters["D"], api_key=api_key) if ceiling else None
    learning = fast_path.FastPathRouter({"remote": remote_config, "fast_path": settings},
                                        base / "store", base / "runs.jsonl",
                                        remote_fn=meters["C"], api_key=api_key)
    racing = fast_path.FastPathRouter({"remote": remote_config,
                                       "fast_path": {**settings, "synthesis_enabled": False}},
                                      base / "race_store", base / "race_runs.jsonl",
                                      remote_fn=meters["R"], api_key=api_key)
    planning = planner.PlanningRouter(learning, base / "templates", base / "tasks.jsonl")
    writer_router = fast_path.FastPathRouter(
        {"remote": remote_config, "fast_path": {**settings, "synthesis_enabled": False,
                                                "program_probes": 0, "write_early": False}},
        base / "write_store", base / "write_runs.jsonl",
        remote_fn=meters["W"], api_key=api_key) if "W" in arms else None
    writer = write_once.WriteOnceRouter(writer_router) if writer_router else None
    prober_router = fast_path.FastPathRouter(
        {"remote": remote_config, "fast_path": {**settings, "synthesis_enabled": False,
                                                "program_probes": probes, "write_early": False}},
        base / "probe_store", base / "probe_runs.jsonl",
        remote_fn=meters["P"], api_key=api_key) if "P" in arms else None
    prober = write_once.WriteOnceRouter(prober_router) if prober_router else None
    early_router = fast_path.FastPathRouter(
        {"remote": remote_config, "fast_path": {**settings, "synthesis_enabled": False,
                                                "program_probes": probes, "write_early": True}},
        base / "early_store", base / "early_runs.jsonl",
        remote_fn=meters["Q"], api_key=api_key) if "Q" in arms else None
    early_writer = write_once.WriteOnceRouter(early_router) if early_router else None
    fixed_router = fast_path.FastPathRouter(
        {"remote": remote_config, "fast_path": {**settings, "synthesis_enabled": False,
                                                "program_probes": probes, "write_early": False,
                                                **READING_FIXES}},
        base / "fixed_store", base / "fixed_runs.jsonl",
        remote_fn=meters["B"], api_key=api_key) if "B" in arms else None
    fixed_writer = write_once.WriteOnceRouter(fixed_router) if fixed_router else None

    def variant(arm, extra):  # as P, with Phase B settings
        if arm not in arms:
            return None
        router = fast_path.FastPathRouter(
            {"remote": remote_config, "fast_path": {**settings, "synthesis_enabled": False,
                                                    "program_probes": probes, "write_early": False, **extra}},
            base / f"{arm}_store", base / f"{arm}_runs.jsonl", remote_fn=meters[arm], api_key=api_key)
        return write_once.WriteOnceRouter(router)
    fallback_writer = variant("F", {"uncertainty_gate": True, "flag_fallback": "majority"})
    majority_writer = variant("M", {"decision": "majority"})
    alongside_writer = variant("S", {"uncertainty_gate": True, "race_alongside": True})
    order_rng = random.Random(f"{ARM_ORDER_SEED}:{shape['name']}")
    rows = []
    for index, ((inputs, labels), gold) in enumerate(zip(instances, golds)):
        if should_stop():
            break
        expected = gold[shape["output"]]
        prompt = planner.build_task_prompt(shape["description"], inputs)
        order = list(arms)
        order_rng.shuffle(order)
        for position, arm in enumerate(order):
            started = time.perf_counter()
            error, model, route, steps = None, None, None, None
            reading_correct = None
            uncertain = None
            program_correct = None
            if arm == "A":
                answered, value, error = direct(prompt, remote_config, settings, meters["A"], api_key)
                model, route = BASELINE_MODEL, "direct"
            elif arm == "D":
                answered, value, label = ceiling_answer(shape, reading, inputs, ceiling_router)
                route = "ceiling"
                reading_correct = answered and label == labels.get(reading["label"])
            elif arm == "E":
                value, label = code_only_answer(shape, code_only, inputs)
                answered, route = True, "code_only"
                reading_correct = label == labels.get(shape["reading"][1])
            elif arm in ("W", "P", "Q", "B", "F", "M", "S"):
                result = {"W": writer, "P": prober, "Q": early_writer, "B": fixed_writer, "F": fallback_writer,
                          "M": majority_writer, "S": alongside_writer}[arm].handle({"schema_version": planner.SCHEMA_VERSION,
                                        "description": shape["description"], "inputs": inputs})
                value, route, model = result["value"], result["route"], result["model"]
                answered = route != planner.NO_ANSWER
                uncertain = result.get("uncertain")
                if "program_value" in result:  # F: what the flagged program would have served
                    program_correct = same(result["program_value"], expected)
            elif arm == "R":
                model, value = racing.race_prompt(prompt)
                answered, route = model is not None, "race"
            else:
                result = planning.handle({"schema_version": planner.SCHEMA_VERSION,
                                          "description": shape["description"], "inputs": inputs})
                value, route, model = result["value"], result["route"], result["model"]
                answered = route != planner.NO_ANSWER
                if result["steps"]:
                    steps = [{"id": s["id"], "kind": s["kind"], "route": s["route"], "ms": s["ms"]}
                             for s in result["steps"]]
            answer_ms = (time.perf_counter() - started) * 1000
            background_ms = 0.0
            if arm in ("C", "W", "P", "Q", "B", "F", "M", "S") and arrival == "drained":
                started = time.perf_counter()
                {"C": planning, "W": writer, "P": prober, "Q": early_writer, "B": fixed_writer,
                 "F": fallback_writer, "M": majority_writer, "S": alongside_writer}[arm].drain()
                background_ms = (time.perf_counter() - started) * 1000
            rows.append({
                "record_type": "job", "shape": shape["name"], "index": index, "arm": arm,
                "position": position, "answer_ms": answer_ms, "background_ms": background_ms,
                "answered": answered, "error": error, "model": model, "route": route,
                "correct": answered and same(value, expected),
                "value": value if answered else None, "steps": steps,
                "reading_correct": reading_correct, "uncertain": uncertain,
                "program_correct": program_correct,
            })
    template = planner.template_key(shape["description"], instances[0][0])
    planning.close()
    record = planning.store.get(template)
    learning.close()
    racing.close()
    summary = shape_summary(shape, instances, golds, record, learning)
    if writer is not None:
        writer.close()
        summary["write_once"] = writer.summary(template)
        writer_router.close()
    if prober is not None:
        prober.close()
        summary["write_once_probed"] = prober.summary(template)
        prober_router.close()
    if early_writer is not None:
        early_writer.close()
        summary["write_once_early"] = early_writer.summary(template)
        early_router.close()
    if fixed_writer is not None:
        fixed_writer.close()
        summary["write_once_fixed"] = fixed_writer.summary(template)
        fixed_router.close()
    for key, extra_writer in (("write_once_fallback", fallback_writer), ("write_once_majority", majority_writer),
                              ("write_once_alongside", alongside_writer)):
        if extra_writer is not None:
            extra_writer.close()
            summary[key] = extra_writer.summary(template)
            extra_writer.router.close()
    if ceiling_router is not None:
        ceiling_router.close()
    summary["jobs_completed"] = len(rows) // len(arms)
    summary["usage"] = {arm: meter.report() for arm, meter in meters.items() if arm in arms}
    return rows, summary


def shape_summary(shape, instances, golds, record, learning):
    if record is None:
        return {"record_type": "shape", "shape": shape["name"], "plan_adopted": False}
    gold_by_inputs = {sandbox.canonical(i): g[shape["output"]] for (i, _), g in zip(instances, golds)}
    wrong_examples = sum(
        not same(gold_by_inputs.get(sandbox.canonical(e["inputs"])), e["expected"])
        for e in record["examples"]
    )
    plan = record["plan"]
    plan_steps = []
    if plan is not None:
        for step in plan["document"]["steps"]:
            entry = {"id": step["id"], "kind": step["kind"], "spec": step["task"]["spec"],
                     "signature": step["task"]["signature"], "promoted": False}
            if step["kind"] == "function":
                stored = learning.store.get(fast_path.shape_key(step["task"]["spec"],
                                                                step["task"]["signature"]))
                entry["promoted"] = bool(stored and stored["function"])
                if stored:
                    entry["learning"] = {
                        "examples": len(stored["examples"]),
                        "disagreements": stored.get("disagreements", 0),
                        "example_conflicts": stored.get("example_conflicts", 0),
                        "probes": stored.get("probes"),
                        "attempts": [{"outcome": a["outcome"],
                                      "gate": a.get("gate", {}).get("reason"),
                                      "passed": a.get("gate", {}).get("passed"),
                                      "examples": a.get("gate", {}).get("examples"),
                                      "repair": "repair" in a, "error": a.get("error")}
                                     for a in stored["synthesis_attempts"]],
                    }
            plan_steps.append(entry)
    return {
        "record_type": "shape", "shape": shape["name"],
        "examples": len(record["examples"]), "wrong_examples": wrong_examples,
        "disagreements": record["disagreements"],
        "plan_attempts": record["plan_attempts"], "plan_adopted": plan is not None,
        "plan_mode": plan.get("mode", "live") if plan else None,
        "live_after_shadow_runs": plan.get("live_after_shadow_runs") if plan else None,
        "shadow_ms": plan.get("shadow_ms") if plan else None,
        "race_ms": record.get("race_ms"),
        "plan_demotions": record["demotions"], "plan_steps": plan_steps,
        "plan_document": plan["document"] if plan else None,
    }


def execute(shapes, bench, remote_config, settings, remote_fn, api_key, workers, write,
            monitor=None, arrival="drained", ceiling=None, code_only=None, only=None, write_arm=False, probes=0, early=False,
            fixes=False, flagged=False, alongside=False):
    should_stop = monitor.tripped if monitor is not None else (lambda: False)

    def job(shape):
        instances = bench.stream(shape)
        return run_shape(shape, instances, bench.gold(shape, instances), remote_config,
                         settings, remote_fn, api_key, workdir, should_stop, arrival, ceiling,
                         code_only, only, write_arm, probes, early, fixes, flagged, alongside)

    with tempfile.TemporaryDirectory() as workdir, ThreadPoolExecutor(workers) as pool:
        for rows, summary in pool.map(job, shapes):
            for row in rows + [summary]:
                write(row)
    return "PROVIDER_FAILURE_STOP" if should_stop() else "COMPLETED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", default=str(ROOT / "fast_path_planned_bench_v1.py"))
    parser.add_argument("--output", required=True, help="observations JSONL (must not exist)")
    parser.add_argument("--label", default="primary")
    parser.add_argument("--set", dest="override", metavar="NAME=VALUE", action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--arrival", choices=("drained", "immediate"), default="drained")
    parser.add_argument("--ceiling", help="module of hand-written reading steps; adds arm D")
    parser.add_argument("--code-only", help="module of keyword reading RULES; adds arm E (no model)")
    parser.add_argument("--write-once", action="store_true", help="add arm W (write the job once)")
    parser.add_argument("--probes", type=int, default=0,
                        help="add arm P: write once, checked also on this many edge-case jobs")
    parser.add_argument("--early", action="store_true",
                        help="add arm Q: as P, but the program is written on first sight")
    parser.add_argument("--fixes", action="store_true",
                        help="add arm B: as P, with batched readings, the uncertainty gate and adaptive width")
    parser.add_argument("--flagged", action="store_true",
                        help="add arms F (as P; a flagged answer is served from a majority race) and M (as P, readings by majority)")
    parser.add_argument("--alongside", action="store_true",
                        help="add arm S (as P; the whole-task race starts with the program, first trusted answer served)")
    parser.add_argument("--arms", help="comma-separated arms to run, e.g. R,D,E,W (default: all)")
    parser.add_argument("--shapes", help="comma-separated shape names to run (default: all)")
    parser.add_argument("--limit-shapes", type=int)
    parser.add_argument("--limit-jobs", type=int)
    parser.add_argument("--jobs", type=int, help="jobs per shape, drawn from the bench's seeded stream")
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
    override = []
    for text in args.override:
        name, value = parse_override(text)
        if name not in settings:
            parser.error(f"unknown fast_path setting: {name}")
        override.append({"name": name, "from": settings[name], "to": value})
        settings[name] = value
    override = override or None
    bench = load_bench(args.bench)
    ceiling = load_bench(args.ceiling).READING if args.ceiling else None
    code_only = load_bench(args.code_only).RULES if args.code_only else None
    shapes = bench.SHAPES[: args.limit_shapes] if args.limit_shapes else bench.SHAPES
    if args.shapes:
        wanted = args.shapes.split(",")
        unknown = set(wanted) - {s["name"] for s in shapes}
        if unknown:
            parser.error(f"unknown shapes: {sorted(unknown)}")
        shapes = [s for s in shapes if s["name"] in wanted]
    if args.jobs:
        full_stream = bench.stream
        bench.stream = lambda shape: full_stream(shape, length=args.jobs)
    if args.limit_jobs:
        full = bench.stream
        bench.stream = lambda shape: full(shape)[: args.limit_jobs]

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
            "shapes": len(shapes), "stream_seed": bench.STREAM_SEED,
            "jobs_per_shape": args.limit_jobs or args.jobs or bench.STREAM_LENGTH,
            "arm_order_seed": ARM_ORDER_SEED, "workers": args.workers, "arrival": args.arrival,
            "ceiling": ({"name": Path(args.ceiling).name, "sha256": sha256_file(args.ceiling)}
                        if args.ceiling else None),
            "arms": args.arms, "write_once": args.write_once, "probes": args.probes, "early": args.early, "fixes": args.fixes, "flagged": args.flagged, "alongside": args.alongside,
            "code_only": ({"name": Path(args.code_only).name, "sha256": sha256_file(args.code_only)}
                          if args.code_only else None),
            "files": {name: sha256_file(ROOT / name) for name in HASHED_FILES},
        })
        monitor = ProviderMonitor(remote.generate)
        status = execute(shapes, bench, remote_config, settings, monitor, api_key,
                         args.workers, write, monitor, args.arrival, ceiling, code_only,
                         tuple(args.arms.split(",")) if args.arms else None, args.write_once, args.probes,
                         args.early, args.fixes, args.flagged, args.alongside)
        write({"record_type": "footer", "status": status, "provider": monitor.report()})
    if status == "COMPLETED":
        partial.rename(output)
    print(status, output if status == "COMPLETED" else partial)


if __name__ == "__main__":
    main()
