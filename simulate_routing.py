"""Offline routing-policy replay over frozen Simulation Zero v2 observations."""

import argparse
import csv
import json
from pathlib import Path


REMOTE_SUCCESS_RATES = (0.80, 0.90, 0.95, 1.00)

SENTIMENT_TASKS = {
    "classify_sentiment",
    "classify_sentiment_negative",
    "classify_sentiment_neutral",
}

JSON_FORMAT_TASKS = {
    "format_json",
    "format_json_contact",
    "format_json_coordinates",
}


def route(policy, row):
    """Return 'local' or 'remote' using information available before outcome."""
    if policy == "always_local":
        return "local"

    if policy == "always_remote":
        return "remote"

    if policy == "coarse_class":
        if row["task_class"] in {"extract_structured", "classification"}:
            return "local"
        return "remote"

    if policy == "fine_capability":
        if row["task_class"] == "extract_structured":
            return "local"
        if row["task_id"] in SENTIMENT_TASKS | JSON_FORMAT_TASKS:
            return "local"
        return "remote"

    raise ValueError(f"Unknown policy: {policy}")


def local_correct(row, interpretation):
    """Return frozen strict correctness or the documented audited interpretation."""
    if interpretation == "audited" and row["task_id"] == "extract_person_2":
        return True
    return bool(row["oracle_correct"])


def simulate(rows, policy, interpretation, remote_success_rate):
    local_rows = [row for row in rows if route(policy, row) == "local"]
    remote_rows = [row for row in rows if route(policy, row) == "remote"]

    local_passes = sum(local_correct(row, interpretation) for row in local_rows)
    missed_escalations = len(local_rows) - local_passes

    unnecessary_escalations = sum(
        local_correct(row, interpretation) for row in remote_rows
    )

    expected_remote_passes = len(remote_rows) * remote_success_rate
    expected_total_passes = local_passes + expected_remote_passes

    local_total_ms = sum(
        row["total_ms"] for row in local_rows if row["total_ms"] is not None
    )
    return {
        "policy": policy,
        "interpretation": interpretation,
        "remote_success_rate_assumption": remote_success_rate,
        "observations": len(rows),
        "local_calls": len(local_rows),
        "remote_calls": len(remote_rows),
        "local_passes": local_passes,
        "missed_escalations": missed_escalations,
        "unnecessary_escalations": unnecessary_escalations,
        "expected_remote_passes": expected_remote_passes,
        "expected_total_passes": expected_total_passes,
        "expected_success_rate": expected_total_passes / len(rows),
        "observed_local_work_ms": local_total_ms,
        "remote_call_rate": len(remote_rows) / len(rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="benchmark_runs_simzero_v2.jsonl",
    )
    parser.add_argument(
        "--output",
        default="routing_simulation_zero_v1.csv",
    )
    args = parser.parse_args()

    with Path(args.input).open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]

    policies = (
        "always_local",
        "always_remote",
        "coarse_class",
        "fine_capability",
    )

    results = [
        simulate(rows, policy, interpretation, remote_rate)
        for interpretation in ("strict", "audited")
        for policy in policies
        for remote_rate in REMOTE_SUCCESS_RATES
    ]

    output = Path(args.output)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0])
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote {len(results)} counterfactual policy rows to {output}")
    print()
    print("Empirical routing counts (remote success assumption does not affect these):")

    for interpretation in ("strict", "audited"):
        print(f"\n{interpretation.upper()}")
        for policy in policies:
            result = simulate(rows, policy, interpretation, 1.0)
            print(
                f"{policy:18} "
                f"local={result['local_calls']:3} "
                f"remote={result['remote_calls']:3} "
                f"local_pass={result['local_passes']:3} "
                f"missed={result['missed_escalations']:3} "
                f"unnecessary={result['unnecessary_escalations']:3}"
            )


if __name__ == "__main__":
    main()
