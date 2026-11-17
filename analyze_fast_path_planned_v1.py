"""Analyse a planned-jobs run. Makes no provider call.

Primary comparison: arm C (planning router) against arm R (whole-task race):
ratio of median answer times and difference in share correct, with a paired
bootstrap that resamples whole shapes. C against A is reported beside it.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import statistics

from analyze_fast_path_timing_v1 import BOOTSTRAP_REPLICATES, bootstrap, by_shape, load, measures, percentile


TIME_RATIO_LIMIT = 1.0
CORRECTNESS_MARGIN = -0.02
ARMS = ("A", "R", "C")


def pair(grouped, first, second, replicates):
    renamed = {shape: {"A": arms[second], "C": arms[first]} for shape, arms in grouped.items()}
    ratio, difference = measures(renamed, sorted(renamed))
    ratio_interval, difference_interval = bootstrap(renamed, replicates)
    return {"time_ratio": ratio, "time_ratio_interval_95": ratio_interval,
            "correctness_difference": difference, "correctness_interval_95": difference_interval}


def arm_table(jobs):
    table = {}
    for arm in ARMS:
        mine = [r for r in jobs if r["arm"] == arm]
        if mine:
            times = [r["answer_ms"] for r in mine]
            table[arm] = {"jobs": len(mine), "correct": sum(r["correct"] for r in mine),
                          "unanswered": sum(not r["answered"] for r in mine),
                          "median_ms": statistics.median(times), "p90_ms": percentile(times, 0.9),
                          "mean_ms": statistics.fmean(times)}
    return table


def route_table(jobs):
    out = {}
    for route in ("plan", "race", "none"):
        mine = [r for r in jobs if r["arm"] == "C" and r["route"] == route]
        if mine:
            out[route] = {"jobs": len(mine), "correct": sum(r["correct"] for r in mine),
                          "median_ms": statistics.median(r["answer_ms"] for r in mine)}
    return out


def analyse(kinds, replicates=BOOTSTRAP_REPLICATES):
    jobs = kinds.get("job", [])
    shapes = kinds.get("shape", [])
    header = kinds["header"][0]
    footer = (kinds.get("footer") or [{}])[0]
    result = {
        "status": footer.get("status", "INCOMPLETE"), "label": header.get("label"),
        "task_clusters": len({r["shape"] for r in jobs}),
        "arms": arm_table(jobs), "arm_c_routes": route_table(jobs),
    }
    if result["status"] != "COMPLETED":
        result["decision"] = "NOT_ANALYSED"
        return result
    grouped = by_shape(jobs)
    primary = pair(grouped, "C", "R", replicates)
    time_met = primary["time_ratio_interval_95"][1] < TIME_RATIO_LIMIT
    correctness_met = primary["correctness_interval_95"][0] > CORRECTNESS_MARGIN
    first_plan = {}
    for row in sorted((r for r in jobs if r["arm"] == "C" and r["route"] == "plan"), key=lambda r: r["index"]):
        first_plan.setdefault(row["shape"], row["index"])
    steps = collections.Counter()
    for row in jobs:
        for step in row["steps"] or []:
            steps[f"{step['kind']}:{step['route']}"] += 1
    attempts = [a for s in shapes for a in s.get("plan_attempts", [])]
    result.update({
        "primary_c_vs_r": primary, "c_vs_a": pair(grouped, "C", "A", replicates),
        "r_vs_a": pair(grouped, "R", "A", replicates),
        "time_criterion_met": time_met, "correctness_criterion_met": correctness_met,
        "decision": "SUPPORTED" if time_met and correctness_met else "NOT_SUPPORTED",
        "shapes_with_plan_adopted": sum(bool(s.get("plan_adopted")) for s in shapes),
        "first_plan_job_index": first_plan,
        "plan_attempt_outcomes": dict(collections.Counter(a["outcome"] for a in attempts)),
        "plan_step_kinds": dict(collections.Counter(
            st["kind"] for s in shapes for st in s.get("plan_steps", []))),
        "plan_function_steps_promoted": sum(
            st["promoted"] for s in shapes for st in s.get("plan_steps", [])),
        "plan_demotions": sum(len(s.get("plan_demotions", [])) for s in shapes),
        "wrong_job_examples": sum(s.get("wrong_examples", 0) for s in shapes),
        "plan_step_routes": dict(steps),
        "per_shape": {
            shape: {arm: {"correct": sum(r["correct"] for r in rows),
                          "median_ms": statistics.median(r["answer_ms"] for r in rows)}
                    for arm, rows in arms.items()}
            for shape, arms in grouped.items()
        },
        "median_after_plan_ms": {
            arm: statistics.median(r["answer_ms"] for r in jobs if r["arm"] == arm
                                   and r["shape"] in first_plan and r["index"] >= first_plan[r["shape"]])
            for arm in ARMS
        } if first_plan else None,
    })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations")
    parser.add_argument("--output")
    args = parser.parse_args()
    text = json.dumps(analyse(load(args.observations)), indent=1)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
