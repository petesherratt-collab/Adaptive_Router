"""Replay frozen routing policies with paired measured local and remote outcomes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path


LOCAL_RUNS = "benchmark_runs_simzero_v2.jsonl"
REMOTE_RUNS = "benchmark_runs_openrouter_luna_v1.jsonl"
LOCAL_SHA256 = "5637130c56894a0263c534bb87c5037901f0e535df28e658f68d5e85c03f7f6e"
REMOTE_SHA256 = "341d203f34f3789e489329030895970e719483334e42d2ac144080516e3c0405"

POLICIES = (
    "always_local",
    "always_remote",
    "coarse_class",
    "fine_capability",
)
INTERPRETATIONS = ("strict", "audited")

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
LOCAL_AUDITED_CORRECT_TASKS = {"extract_person_2"}
REMOTE_AUDITED_CORRECT_TASKS = {
    "extract_event_2",
    "format_labels_contact",
    "format_labels_ticket",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path, expected_sha256: str) -> list[dict]:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {expected_sha256}, got {actual}"
        )
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if len(rows) != 150:
        raise ValueError(f"Expected 150 observations in {path}, got {len(rows)}")
    return rows


def pair_rows(local_rows: list[dict], remote_rows: list[dict]) -> list[tuple[dict, dict]]:
    def index(rows: list[dict], source: str) -> dict[tuple[str, int], dict]:
        indexed: dict[tuple[str, int], dict] = {}
        for row in rows:
            key = (row["task_id"], row["rep"])
            if key in indexed:
                raise ValueError(f"Duplicate {source} task/rep key: {key}")
            indexed[key] = row
        return indexed

    local = index(local_rows, "local")
    remote = index(remote_rows, "remote")
    if set(local) != set(remote):
        missing_remote = sorted(set(local) - set(remote))
        missing_local = sorted(set(remote) - set(local))
        raise ValueError(
            "Paired key mismatch: "
            f"missing_remote={missing_remote}, missing_local={missing_local}"
        )

    pairs = []
    for key in sorted(local):
        local_row = local[key]
        remote_row = remote[key]
        if local_row["task_class"] != remote_row["task_class"]:
            raise ValueError(f"Task-class mismatch for {key}")
        pairs.append((local_row, remote_row))
    return pairs


def route(policy: str, row: dict) -> str:
    """Choose a route using only task identity available before generation."""
    if policy == "always_local":
        return "local"
    if policy == "always_remote":
        return "remote"
    if policy == "coarse_class":
        return (
            "local"
            if row["task_class"] in {"extract_structured", "classification"}
            else "remote"
        )
    if policy == "fine_capability":
        if row["task_class"] == "extract_structured":
            return "local"
        if row["task_id"] in SENTIMENT_TASKS | JSON_FORMAT_TASKS:
            return "local"
        return "remote"
    raise ValueError(f"Unknown policy: {policy}")


def interpreted_correct(source: str, row: dict, interpretation: str) -> bool:
    if interpretation not in INTERPRETATIONS:
        raise ValueError(f"Unknown interpretation: {interpretation}")
    if bool(row["oracle_correct"]):
        return True
    if interpretation == "strict":
        return False
    if source == "local":
        return row["task_id"] in LOCAL_AUDITED_CORRECT_TASKS
    if source == "remote":
        return row["task_id"] in REMOTE_AUDITED_CORRECT_TASKS
    raise ValueError(f"Unknown source: {source}")


def overlap_counts(pairs: list[tuple[dict, dict]], interpretation: str) -> dict:
    counts = {"both_correct": 0, "local_only": 0, "remote_only": 0, "neither": 0}
    for local_row, remote_row in pairs:
        local_ok = interpreted_correct("local", local_row, interpretation)
        remote_ok = interpreted_correct("remote", remote_row, interpretation)
        if local_ok and remote_ok:
            counts["both_correct"] += 1
        elif local_ok:
            counts["local_only"] += 1
        elif remote_ok:
            counts["remote_only"] += 1
        else:
            counts["neither"] += 1
    counts["oracle_selector_passes"] = (
        counts["both_correct"] + counts["local_only"] + counts["remote_only"]
    )
    counts["oracle_selector_pass_rate"] = counts["oracle_selector_passes"] / len(pairs)
    return counts


def simulate(
    pairs: list[tuple[dict, dict]], policy: str, interpretation: str
) -> dict:
    selected_correct = []
    selected_latencies = []
    remote_cost = 0.0
    remote_calls_with_reported_cost = 0
    remote_transport_failures = 0
    local_calls = 0
    remote_calls = 0

    for local_row, remote_row in pairs:
        selected_source = route(policy, local_row)
        if selected_source == "local":
            local_calls += 1
            selected = local_row
        else:
            remote_calls += 1
            selected = remote_row
            if remote_row.get("cost") is not None:
                remote_cost += remote_row["cost"]
                remote_calls_with_reported_cost += 1
            if not remote_row.get("success", False):
                remote_transport_failures += 1

        selected_correct.append(
            interpreted_correct(selected_source, selected, interpretation)
        )
        if selected.get("total_ms") is not None:
            selected_latencies.append(selected["total_ms"])

    passes = sum(selected_correct)
    return {
        "policy": policy,
        "interpretation": interpretation,
        "observations": len(pairs),
        "local_calls": local_calls,
        "remote_calls": remote_calls,
        "remote_call_rate": remote_calls / len(pairs),
        "passes": passes,
        "failures": len(pairs) - passes,
        "pass_rate": passes / len(pairs),
        "reported_remote_cost_usd": round(remote_cost, 12),
        "remote_calls_with_reported_cost": remote_calls_with_reported_cost,
        "remote_transport_failures": remote_transport_failures,
        "selected_latency_observation_count": len(selected_latencies),
        "median_selected_total_ms": statistics.median(selected_latencies),
        "summed_selected_total_ms": sum(selected_latencies),
    }


def build_analysis(local_path: Path, remote_path: Path) -> dict:
    local_rows = load_jsonl(local_path, LOCAL_SHA256)
    remote_rows = load_jsonl(remote_path, REMOTE_SHA256)
    pairs = pair_rows(local_rows, remote_rows)

    interpretations = {}
    for interpretation in INTERPRETATIONS:
        policies = [simulate(pairs, policy, interpretation) for policy in POLICIES]
        always_remote = next(x for x in policies if x["policy"] == "always_remote")
        for result in policies:
            result["pass_delta_vs_always_remote"] = (
                result["passes"] - always_remote["passes"]
            )
            result["remote_calls_saved_vs_always_remote"] = (
                always_remote["remote_calls"] - result["remote_calls"]
            )
            result["reported_remote_cost_saved_usd"] = round(
                always_remote["reported_remote_cost_usd"]
                - result["reported_remote_cost_usd"],
                12,
            )
        interpretations[interpretation] = {
            "overlap": overlap_counts(pairs, interpretation),
            "policies": policies,
        }

    return {
        "analysis": "measured_paired_routing_replay_v1",
        "source_identity": {
            "local_jsonl": LOCAL_RUNS,
            "local_sha256": LOCAL_SHA256,
            "remote_jsonl": REMOTE_RUNS,
            "remote_sha256": REMOTE_SHA256,
            "paired_observations": len(pairs),
        },
        "interpretation_rules": {
            "strict": "Frozen oracle_correct values without adjustment.",
            "audited": {
                "local_tasks_reclassified_correct": sorted(LOCAL_AUDITED_CORRECT_TASKS),
                "remote_tasks_reclassified_correct": sorted(REMOTE_AUDITED_CORRECT_TASKS),
                "indeterminate_remote_tasks_left_incorrect": ["classify_priority_medium"],
            },
        },
        "interpretations": interpretations,
        "boundaries": [
            "Policies are replayed in-sample and are not prospectively validated.",
            "Reported cost is the OpenRouter cost field recorded in the frozen run.",
            "Selected latency is a replay of one chosen path, not a measured live router.",
            "No retry, contract fallback, or deterministic executor is simulated here.",
        ],
    }


def policy_rows(analysis: dict) -> list[dict]:
    rows = []
    for interpretation in INTERPRETATIONS:
        overlap = analysis["interpretations"][interpretation]["overlap"]
        for policy in analysis["interpretations"][interpretation]["policies"]:
            rows.append(
                {
                    **policy,
                    "both_correct": overlap["both_correct"],
                    "local_only": overlap["local_only"],
                    "remote_only": overlap["remote_only"],
                    "neither": overlap["neither"],
                    "oracle_selector_passes": overlap["oracle_selector_passes"],
                }
            )
    return rows


def write_outputs(analysis: dict, json_path: Path, csv_path: Path) -> None:
    for path in (json_path, csv_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    json_path.write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    rows = policy_rows(analysis)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def print_summary(analysis: dict) -> None:
    for interpretation in INTERPRETATIONS:
        section = analysis["interpretations"][interpretation]
        overlap = section["overlap"]
        print(f"{interpretation.upper()}")
        print(
            "overlap "
            f"both={overlap['both_correct']} local_only={overlap['local_only']} "
            f"remote_only={overlap['remote_only']} neither={overlap['neither']} "
            f"oracle_selector={overlap['oracle_selector_passes']}/150"
        )
        for row in section["policies"]:
            print(
                f"{row['policy']:18} passes={row['passes']:3}/150 "
                f"remote={row['remote_calls']:3} "
                f"cost=${row['reported_remote_cost_usd']:.8f} "
                f"median_ms={row['median_selected_total_ms']:.3f}"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", type=Path, default=Path(LOCAL_RUNS))
    parser.add_argument("--remote", type=Path, default=Path(REMOTE_RUNS))
    parser.add_argument(
        "--json-output", type=Path, default=Path("routing_simulation_measured_v1.json")
    )
    parser.add_argument(
        "--csv-output", type=Path, default=Path("routing_simulation_measured_v1.csv")
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    analysis = build_analysis(args.local, args.remote)
    print_summary(analysis)
    if args.write:
        write_outputs(analysis, args.json_output, args.csv_output)
        print(f"Wrote {args.json_output} and {args.csv_output}")
    else:
        print("Dry run only; no output files were created.")


if __name__ == "__main__":
    main()
