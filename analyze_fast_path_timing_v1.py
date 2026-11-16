"""Analyse a fast-path timing run. Makes no provider call.

Primary measures compare arm C (fast path) with arm A (direct): the ratio of
median answer times and the difference in share correct. Intervals come from a
paired bootstrap that resamples whole shapes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import statistics


BOOTSTRAP_SEED = 20261116
BOOTSTRAP_REPLICATES = 10000
TIME_RATIO_LIMIT = 0.5
CORRECTNESS_MARGIN = -0.02


def load(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
    kinds = {}
    for row in rows:
        kinds.setdefault(row["record_type"], []).append(row)
    return kinds


def percentile(values, q):
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def by_shape(requests):
    grouped = {}
    for row in requests:
        grouped.setdefault(row["shape"], {}).setdefault(row["arm"], []).append(row)
    return grouped


def measures(grouped, shapes):
    """Return (time ratio C/A, correctness C minus A) over the given shapes."""
    times = {"A": [], "C": []}
    correct = {"A": [], "C": []}
    for name in shapes:
        for arm in ("A", "C"):
            times[arm].extend(r["answer_ms"] for r in grouped[name][arm])
            correct[arm].extend(r["correct"] for r in grouped[name][arm])
    ratio = statistics.median(times["C"]) / statistics.median(times["A"])
    difference = statistics.fmean(correct["C"]) - statistics.fmean(correct["A"])
    return ratio, difference


def bootstrap(grouped, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED):
    names = sorted(grouped)
    rng = random.Random(seed)
    ratios, differences = [], []
    for _ in range(replicates):
        ratio, difference = measures(grouped, [rng.choice(names) for _ in names])
        ratios.append(ratio)
        differences.append(difference)
    return (
        [percentile(ratios, 0.025), percentile(ratios, 0.975)],
        [percentile(differences, 0.025), percentile(differences, 0.975)],
    )


def arm_table(requests):
    table = {}
    for arm in "ABC":
        mine = [r for r in requests if r["arm"] == arm]
        if not mine:
            continue
        times = [r["answer_ms"] for r in mine]
        table[arm] = {
            "requests": len(mine),
            "correct": sum(r["correct"] for r in mine),
            "unanswered": sum(not r["answered"] for r in mine),
            "median_ms": statistics.median(times),
            "p90_ms": percentile(times, 0.9),
        }
    return table


def route_table(requests):
    table = {}
    for route in ("code", "model", "none"):
        mine = [r for r in requests if r["arm"] == "C" and r["route"] == route]
        if mine:
            table[route] = {
                "requests": len(mine),
                "correct": sum(r["correct"] for r in mine),
                "median_ms": statistics.median(r["answer_ms"] for r in mine),
            }
    return table


def analyse(kinds, replicates=BOOTSTRAP_REPLICATES):
    requests = kinds.get("request", [])
    shapes = kinds.get("shape", [])
    footer = (kinds.get("footer") or [{}])[0]
    result = {
        "status": footer.get("status", "INCOMPLETE"),
        "label": kinds["header"][0].get("label"),
        "override": kinds["header"][0].get("override"),
        "task_clusters": len({r["shape"] for r in requests}),
        "arms": arm_table(requests),
        "arm_c_routes": route_table(requests),
    }
    if result["status"] != "COMPLETED":
        result["decision"] = "NOT_ANALYSED"
        return result
    grouped = by_shape(requests)
    ratio, difference = measures(grouped, sorted(grouped))
    ratio_interval, difference_interval = bootstrap(grouped, replicates)
    time_met = ratio_interval[1] < TIME_RATIO_LIMIT
    correctness_met = difference_interval[0] > CORRECTNESS_MARGIN
    promoted = [s for s in shapes if s["promoted_at_index"] is not None]
    code_rows = [r for r in requests if r["arm"] == "C" and r["route"] == "code"]
    result.update(
        {
            "time_ratio_c_over_a": ratio,
            "time_ratio_interval_95": ratio_interval,
            "correctness_c_minus_a": difference,
            "correctness_interval_95": difference_interval,
            "time_criterion_met": time_met,
            "correctness_criterion_met": correctness_met,
            "decision": "SUPPORTED" if time_met and correctness_met else "NOT_SUPPORTED",
            "shapes_promoted": len(promoted),
            "median_promotion_index": (
                statistics.median(s["promoted_at_index"] for s in promoted)
                if promoted else None
            ),
            "shapes_with_gold_wrong_function": sum(
                s["function_gold_correct"] is False for s in shapes
            ),
            "shapes_with_demotion": sum(bool(s["demotions"]) for s in shapes),
            "wrong_stored_examples": sum(s["wrong_examples"] for s in shapes),
            "code_served_wrong": sum(not r["correct"] for r in code_rows),
            "shapes_with_code_served_wrong": len(
                {r["shape"] for r in code_rows if not r["correct"]}
            ),
            "median_background_ms_arm_c": statistics.median(
                r["background_ms"] for r in requests if r["arm"] == "C"
            ),
        }
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyse(load(args.observations))
    text = json.dumps(result, indent=1)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
