"""Replay routing policies over paired measured local and remote outcomes."""

import argparse
import csv
import json
from pathlib import Path
from statistics import median

from simulate_routing import route


ROOT = Path(__file__).resolve().parent
DEFAULT_LOCAL = ROOT / "benchmark_runs_simzero_v2.jsonl"
DEFAULT_REMOTE = ROOT / "benchmark_runs_openrouter_luna_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "routing_simulation_paired_v1.csv"

POLICIES = (
    "always_local",
    "always_remote",
    "coarse_class",
    "fine_capability",
)

REMOTE_SPECIFICATION_ADJUSTMENTS = {
    "extract_event_2",
    "format_labels_contact",
    "format_labels_ticket",
}


def load_jsonl(path):
    records = []

    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON on line {line_number}: {path}"
                ) from exc

            records.append(record)

    return records


def index_records(records, source_name):
    indexed = {}

    for record in records:
        key = (record.get("task_id"), record.get("rep"))

        if None in key:
            raise ValueError(
                f"{source_name} contains an incomplete key: {key}"
            )

        if key in indexed:
            raise ValueError(
                f"{source_name} contains a duplicate key: {key}"
            )

        indexed[key] = record

    return indexed


def pair_records(local_records, remote_records):
    local_index = index_records(local_records, "local")
    remote_index = index_records(remote_records, "remote")

    if set(local_index) != set(remote_index):
        missing_remote = sorted(set(local_index) - set(remote_index))
        missing_local = sorted(set(remote_index) - set(local_index))
        raise ValueError(
            "paired key mismatch: "
            f"missing_remote={missing_remote}, "
            f"missing_local={missing_local}"
        )

    pairs = []

    for local in local_records:
        key = (local["task_id"], local["rep"])
        remote = remote_index[key]

        if local["task_class"] != remote["task_class"]:
            raise ValueError(
                f"task-class mismatch for paired key: {key}"
            )

        pairs.append((local, remote))

    return pairs


def local_correct(record, interpretation):
    if (
        interpretation == "audited"
        and record["task_id"] == "extract_person_2"
    ):
        return True

    return bool(record.get("oracle_correct"))


def remote_correct(record, interpretation):
    if (
        interpretation == "audited"
        and record.get("success")
        and record["task_id"] in REMOTE_SPECIFICATION_ADJUSTMENTS
    ):
        return True

    return bool(record.get("oracle_correct"))


def available_median(values):
    available = [
        value
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
    ]
    return median(available) if available else None


def available_sum(values):
    return sum(
        value
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
    )


def simulate(pairs, policy, interpretation):
    selected_passes = 0
    local_calls = 0
    remote_calls = 0
    beneficial_escalations = 0
    unnecessary_escalations = 0
    harmful_escalations = 0
    missed_escalations = 0
    unrecoverable_local_failures = 0
    selected_transport_failures = 0
    selected_times = []
    selected_remote_costs = []

    oracle_ceiling_passes = 0

    for local, remote in pairs:
        decision = route(policy, local)
        local_ok = local_correct(local, interpretation)
        remote_ok = remote_correct(remote, interpretation)

        if local_ok or remote_ok:
            oracle_ceiling_passes += 1

        if decision == "local":
            local_calls += 1
            selected = local
            selected_ok = local_ok

            if not local_ok and remote_ok:
                missed_escalations += 1

            if not local_ok and not remote_ok:
                unrecoverable_local_failures += 1

        elif decision == "remote":
            remote_calls += 1
            selected = remote
            selected_ok = remote_ok

            if not local_ok and remote_ok:
                beneficial_escalations += 1

            if local_ok:
                unnecessary_escalations += 1

            if local_ok and not remote_ok:
                harmful_escalations += 1

            if isinstance(remote.get("cost"), (int, float)):
                selected_remote_costs.append(remote["cost"])

        else:
            raise ValueError(f"unsupported route: {decision}")

        if selected_ok:
            selected_passes += 1

        if not selected.get("success"):
            selected_transport_failures += 1

        selected_times.append(selected.get("total_ms"))

    observations = len(pairs)

    return {
        "policy": policy,
        "interpretation": interpretation,
        "observations": observations,
        "selected_passes": selected_passes,
        "selected_pass_rate": (
            selected_passes / observations
            if observations
            else None
        ),
        "local_calls": local_calls,
        "remote_calls": remote_calls,
        "remote_call_rate": (
            remote_calls / observations
            if observations
            else None
        ),
        "beneficial_escalations": beneficial_escalations,
        "unnecessary_escalations": unnecessary_escalations,
        "harmful_escalations": harmful_escalations,
        "missed_escalations": missed_escalations,
        "unrecoverable_local_failures": (
            unrecoverable_local_failures
        ),
        "selected_transport_failures": (
            selected_transport_failures
        ),
        "oracle_ceiling_passes": oracle_ceiling_passes,
        "oracle_ceiling_rate": (
            oracle_ceiling_passes / observations
            if observations
            else None
        ),
        "median_selected_total_ms": available_median(
            selected_times
        ),
        "summed_selected_work_ms": available_sum(
            selected_times
        ),
        "reported_remote_cost": available_sum(
            selected_remote_costs
        ),
        "remote_calls_with_reported_cost": len(
            selected_remote_costs
        ),
    }


def write_results(results, path=DEFAULT_OUTPUT):
    path = Path(path)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(results[0]),
        )
        writer.writeheader()
        writer.writerows(results)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "--local",
        type=Path,
        default=DEFAULT_LOCAL,
    )
    parser.add_argument(
        "--remote",
        type=Path,
        default=DEFAULT_REMOTE,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args(argv)

    local_records = load_jsonl(args.local)
    remote_records = load_jsonl(args.remote)
    pairs = pair_records(local_records, remote_records)

    results = [
        simulate(pairs, policy, interpretation)
        for interpretation in ("strict", "audited")
        for policy in POLICIES
    ]

    write_results(results, args.output)

    print(f"Paired observations: {len(pairs)}")
    print(f"Wrote {len(results)} policy rows to {args.output}")

    for interpretation in ("strict", "audited"):
        print(f"\n{interpretation.upper()}")

        for result in results:
            if result["interpretation"] != interpretation:
                continue

            print(
                f"{result['policy']:18} "
                f"pass={result['selected_passes']:3}/"
                f"{result['observations']} "
                f"remote={result['remote_calls']:3} "
                f"beneficial="
                f"{result['beneficial_escalations']:2} "
                f"missed={result['missed_escalations']:2} "
                f"unnecessary="
                f"{result['unnecessary_escalations']:2} "
                f"harmful="
                f"{result['harmful_escalations']:2} "
                f"cost=$"
                f"{result['reported_remote_cost']:.6f}"
            )


if __name__ == "__main__":
    main()
