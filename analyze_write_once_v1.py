"""Analyse a write-once run (arm W). Makes no provider call.

Primary comparison: W (write the job once, race only its readings) against R
(whole-task race), with the same shape-cluster bootstrap as the planned-jobs
analysis. Also W against D (the ceiling: reference code, raced readings) and
against E (code only), where those arms ran, and, for reference only, the
planning router's figures from an earlier run on the same jobs.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import statistics

from analyze_fast_path_planned_v1 import pair
from analyze_fast_path_timing_v1 import BOOTSTRAP_REPLICATES, by_shape, load, percentile

ARMS = ("A", "R", "C", "D", "E", "W", "P")


def arm_table(jobs):
    table = {}
    for arm in ARMS:
        mine = [r for r in jobs if r["arm"] == arm]
        if mine:
            times = [r["answer_ms"] for r in mine]
            late = [r["answer_ms"] for r in mine if r["index"] >= max(x["index"] for x in mine) - 4]
            table[arm] = {"jobs": len(mine), "correct": sum(r["correct"] for r in mine),
                          "unanswered": sum(not r["answered"] for r in mine),
                          "median_ms": statistics.median(times), "p90_ms": percentile(times, 0.9),
                          "last_five_median_ms": statistics.median(late)}
    return table


def analyse(kinds, replicates=BOOTSTRAP_REPLICATES, reference=None, primary_arm="W"):
    jobs = kinds.get("job", [])
    shapes = kinds.get("shape", [])
    footer = (kinds.get("footer") or [{}])[0]
    result = {"status": footer.get("status", "INCOMPLETE"), "label": kinds["header"][0].get("label"),
              "task_clusters": len({r["shape"] for r in jobs}), "arms": arm_table(jobs)}
    if result["status"] != "COMPLETED":
        return result
    grouped = by_shape(jobs)
    present = {r["arm"] for r in jobs}
    first = {}
    for row in sorted((r for r in jobs if r["arm"] == primary_arm and r["route"] == "program"),
                      key=lambda r: r["index"]):
        first.setdefault(row["shape"], row["index"])
    routes = collections.defaultdict(lambda: {"jobs": 0, "correct": 0, "ms": []})
    for row in jobs:
        if row["arm"] == primary_arm:
            entry = routes[row["route"]]
            entry["jobs"] += 1
            entry["correct"] += row["correct"]
            entry["ms"].append(row["answer_ms"])
    summary_key = "write_once_probed" if primary_arm == "P" else "write_once"
    attempts = [a for s in shapes for a in (s.get(summary_key) or {}).get("attempts", [])]
    after = {arm: [r["answer_ms"] for r in jobs if r["arm"] == arm and r["shape"] in first
                   and r["index"] >= first[r["shape"]]] for arm in present}
    result.update({
        "primary_arm": primary_arm,
        "w_vs_r": pair(grouped, "W", "R", replicates) if "W" in present else None,
        "p_vs_r": pair(grouped, "P", "R", replicates) if "P" in present else None,
        "p_vs_w": pair(grouped, "P", "W", replicates) if {"P", "W"} <= present else None,
        "p_vs_d": pair(grouped, "P", "D", replicates) if {"P", "D"} <= present else None,
        "probe_summaries": [a.get("probes") for a in attempts],
        "w_vs_d": pair(grouped, "W", "D", replicates) if {"W", "D"} <= present else None,
        "w_vs_e": pair(grouped, "W", "E", replicates) if {"W", "E"} <= present else None,
        "w_vs_c": pair(grouped, "W", "C", replicates) if {"W", "C"} <= present else None,
        "c_vs_r": pair(grouped, "C", "R", replicates) if "C" in present else None,
        "first_program_job_index": first,
        "shapes_with_program": len(first),
        "w_routes": {route: {"jobs": v["jobs"], "correct": v["correct"],
                             "median_ms": statistics.median(v["ms"])} for route, v in routes.items()},
        "attempt_outcomes": dict(collections.Counter(a["outcome"] for a in attempts)),
        "readings_per_program": [a.get("readings") for a in attempts if a["outcome"] == "ADOPTED"],
        "median_after_program_ms": {arm: statistics.median(v) for arm, v in after.items() if v},
        "per_shape": {shape: {arm: {"correct": sum(r["correct"] for r in rows),
                                    "median_ms": statistics.median(r["answer_ms"] for r in rows)}
                              for arm, rows in arms.items()} for shape, arms in grouped.items()},
        "usage_per_arm": {arm: {k: sum(s.get("usage", {}).get(arm, {}).get(k, 0) for s in shapes)
                                for k in ("calls", "prompt_tokens", "completion_tokens")}
                          for arm in sorted(present - {"E"})},
    })
    primary = result["p_vs_r" if primary_arm == "P" else "w_vs_r"]
    time_met = primary["time_ratio_interval_95"][1] < 1.0
    correct_met = primary["correctness_interval_95"][0] > -0.02
    result.update({"time_criterion_met": time_met, "correctness_criterion_met": correct_met,
                   "decision": "SUPPORTED" if time_met and correct_met else "NOT_SUPPORTED"})
    if reference:
        ref = [r for r in reference.get("job", []) if r["arm"] == "C"]
        result["reference_c_from_earlier_run"] = {
            "correct": sum(r["correct"] for r in ref), "jobs": len(ref),
            "median_ms": statistics.median(r["answer_ms"] for r in ref),
            "note": "different run on the same jobs; descriptive only"}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations")
    parser.add_argument("--reference", help="earlier run on the same jobs with arm C")
    parser.add_argument("--output")
    parser.add_argument("--primary", default="W", choices=("W", "P"))
    args = parser.parse_args()
    reference = load(args.reference) if args.reference else None
    text = json.dumps(analyse(load(args.observations), reference=reference, primary_arm=args.primary),
                      indent=1)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
