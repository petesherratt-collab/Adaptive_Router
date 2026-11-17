"""Analyse a multi-step jobs run. Makes no provider call.

Primary measures compare arm C (pipeline over the fast path) with arm A (one
direct whole-job call): the ratio of median answer times and the difference in
share of jobs correct, with a paired bootstrap that resamples whole shapes.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import statistics

from analyze_fast_path_timing_v1 import BOOTSTRAP_REPLICATES, bootstrap, by_shape, load, measures, percentile


TIME_RATIO_LIMIT = 0.75
CORRECTNESS_MARGIN = -0.02
ARMS = ("A", "R", "B", "C")


def arm_table(jobs):
    table = {}
    for arm in ARMS:
        mine = [r for r in jobs if r["arm"] == arm]
        if not mine:
            continue
        times = [r["answer_ms"] for r in mine]
        table[arm] = {
            "jobs": len(mine),
            "correct": sum(r["correct"] for r in mine),
            "unanswered": sum(not r["answered"] for r in mine),
            "median_ms": statistics.median(times),
            "p90_ms": percentile(times, 0.9),
            "mean_ms": statistics.fmean(times),
        }
    return table


def step_table(jobs, arm):
    """Per step kind and route: how many step executions, how many wrong."""
    counts = collections.defaultdict(lambda: {"steps": 0, "wrong": 0, "ms": []})
    for row in jobs:
        if row["arm"] != arm or not row["steps"]:
            continue
        for step in row["steps"]:
            entry = counts[f"{step['kind']}:{step['route']}"]
            entry["steps"] += 1
            entry["wrong"] += not step["correct"]
            entry["ms"].append(step["ms"])
    return {
        key: {"steps": v["steps"], "wrong": v["wrong"], "median_ms": statistics.median(v["ms"])}
        for key, v in sorted(counts.items())
    }


def first_error_kinds(jobs, arm):
    """For each wrong job, the kind of its earliest-started wrong step."""
    kinds = collections.Counter()
    for row in jobs:
        if row["arm"] != arm or row["correct"] or not row["steps"]:
            continue
        wrong = [s for s in sorted(row["steps"], key=lambda s: s["started_ms"]) if not s["correct"]]
        kinds[f"{wrong[0]['kind']}:{wrong[0]['route']}" if wrong else "no_wrong_step"] += 1
    return dict(kinds)


def pair(grouped, first, second, replicates):
    renamed = {
        shape: {"A": arms[second], "C": arms[first]} for shape, arms in grouped.items()
    }
    ratio, difference = measures(renamed, sorted(renamed))
    ratio_interval, difference_interval = bootstrap(renamed, replicates)
    return {
        "time_ratio": ratio, "time_ratio_interval_95": ratio_interval,
        "correctness_difference": difference, "correctness_interval_95": difference_interval,
    }


def analyse(kinds, replicates=BOOTSTRAP_REPLICATES, baseline="A", time_limit=TIME_RATIO_LIMIT):
    """``baseline`` is the arm C is judged against; ``time_limit`` the bound
    the time ratio's upper interval must lie below."""
    jobs = kinds.get("job", [])
    shapes = kinds.get("shape", [])
    header = kinds["header"][0]
    footer = (kinds.get("footer") or [{}])[0]
    prospective = header.get("label") == "primary" and header.get("override") is None
    result = {
        "scope": "PROSPECTIVE" if prospective else "DESCRIPTIVE_SENSITIVITY",
        "status": footer.get("status", "INCOMPLETE"),
        "label": header.get("label"),
        "task_clusters": len({r["shape"] for r in jobs}),
        "arms": arm_table(jobs),
    }
    if result["status"] != "COMPLETED":
        result["decision"] = "NOT_ANALYSED"
        return result
    grouped = by_shape(jobs)
    primary = pair(grouped, "C", baseline, replicates)
    time_met = primary["time_ratio_interval_95"][1] < time_limit
    correctness_met = primary["correctness_interval_95"][0] > CORRECTNESS_MARGIN
    functions = [f for s in shapes for f in s["function_steps"]]
    c_jobs = [r for r in jobs if r["arm"] == "C"]
    result.update({
        "primary_c_vs_a": pair(grouped, "C", "A", replicates),
        "primary": {"baseline": baseline, "time_limit": time_limit, **primary},
        "time_criterion_met": time_met,
        "correctness_criterion_met": correctness_met,
        "decision": "SUPPORTED" if time_met and correctness_met else "NOT_SUPPORTED",
        "secondary": {
            "c_vs_r": pair(grouped, "C", "R", replicates),
            "b_vs_a": pair(grouped, "B", "A", replicates),
            "r_vs_a": pair(grouped, "R", "A", replicates),
        },
        "steps_arm_b": step_table(jobs, "B"),
        "steps_arm_c": step_table(jobs, "C"),
        "first_error_arm_b": first_error_kinds(jobs, "B"),
        "first_error_arm_c": first_error_kinds(jobs, "C"),
        "function_steps": len(functions),
        "function_steps_promoted": sum(f["promoted"] for f in functions),
        "function_steps_gold_wrong": sum(f["function_gold_correct"] is False for f in functions),
        "function_steps_with_demotion": sum(bool(f["demotions"]) for f in functions),
        "wrong_stored_examples": sum(f["wrong_examples"] for f in functions),
        "judgement_shapes_stored": sum(s["judgement_shapes_stored"] for s in shapes),
        "jobs_fully_on_code_for_functions": sum(
            all(s["route"] == "code" for s in r["steps"] if s["kind"] == "function")
            for r in c_jobs if r["steps"]
        ),
    })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations")
    parser.add_argument("--output")
    parser.add_argument("--baseline", choices=ARMS, default="A")
    parser.add_argument("--time-limit", type=float, default=TIME_RATIO_LIMIT)
    args = parser.parse_args()
    result = analyse(load(args.observations), baseline=args.baseline, time_limit=args.time_limit)
    text = json.dumps(result, indent=1)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
