"""Authenticate and analyze completed runtime v0.2 prospective evidence."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

import runtime_v0_2_prospective_v1 as pv


BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = "20260902"


def percentile_type7(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    fraction = position - lower
    if lower == len(ordered) - 1:
        return ordered[lower]
    return ordered[lower] + fraction * (ordered[lower + 1] - ordered[lower])


def _median(values):
    clean = [float(value) for value in values if value is not None]
    return statistics.median(clean) if clean else None


def _scope(rows):
    total = len(rows)
    runtime_correct = sum(bool(row["runtime_correct"]) for row in rows)
    local_correct = sum(bool(row["local_oracle"]["correct"]) for row in rows)
    remote_correct = sum(bool(row["remote_oracle"]["correct"]) for row in rows)
    both = sum(
        bool(row["local_oracle"]["correct"])
        and bool(row["remote_oracle"]["correct"])
        for row in rows
    )
    local_only = sum(
        bool(row["local_oracle"]["correct"])
        and not bool(row["remote_oracle"]["correct"])
        for row in rows
    )
    remote_only = sum(
        not bool(row["local_oracle"]["correct"])
        and bool(row["remote_oracle"]["correct"])
        for row in rows
    )
    neither = total - both - local_only - remote_only
    actual_remote = [row for row in rows if row["actual_route"] == "remote"]
    return {
        "observation_count": total,
        "runtime_correct_count": runtime_correct,
        "runtime_correct_rate": runtime_correct / total if total else None,
        "accepted_error_count": sum(bool(row["accepted_error"]) for row in rows),
        "withheld_count": sum(bool(row["withheld"]) for row in rows),
        "local_correct_count": local_correct,
        "remote_correct_count": remote_correct,
        "paired_runtime_minus_local": runtime_correct - local_correct,
        "paired_runtime_minus_remote": runtime_correct - remote_correct,
        "overlap": {
            "both": both,
            "local_only": local_only,
            "remote_only": remote_only,
            "neither": neither,
        },
        "actual_routes": dict(Counter(row["actual_route"] for row in rows)),
        "actual_reasons": dict(Counter(row["actual_reason"] for row in rows)),
        "actual_remote_logical_calls": len(actual_remote),
        "actual_remote_reported_cost_usd": sum(
            float(row["remote"].get("cost") or 0.0) for row in actual_remote
        ),
        "actual_runtime_median_ms": _median(
            (row.get("router_decision") or {}).get("total_ms") for row in rows
        ),
        "paired_local_median_ms": _median(
            row["local"].get("total_ms") for row in rows
        ),
        "paired_remote_median_ms": _median(
            row["remote"].get("total_ms") for row in rows
        ),
    }


def _bootstrap(generative_rows, generative_task_ids):
    by_task = {
        task_id: [row for row in generative_rows if row["task_id"] == task_id]
        for task_id in generative_task_ids
    }
    if any(len(rows) != pv.REPETITIONS for rows in by_task.values()):
        raise pv.FrozenDesignError("BOOTSTRAP_TASK_CLUSTER_SIZE")
    runtime_rates, differences = [], []
    slots = len(generative_task_ids)
    for draw in range(BOOTSTRAP_DRAWS):
        sampled = []
        for slot in range(slots):
            digest = hashlib.sha256(
                (
                    pv.SUITE_ID
                    + "|"
                    + BOOTSTRAP_SEED
                    + "|"
                    + str(draw)
                    + "|"
                    + str(slot)
                ).encode("ascii")
            ).digest()
            index = int.from_bytes(digest[:8], "big") % slots
            sampled.extend(by_task[generative_task_ids[index]])
        denominator = len(sampled)
        runtime_count = sum(bool(row["runtime_correct"]) for row in sampled)
        remote_count = sum(
            bool(row["remote_oracle"]["correct"]) for row in sampled
        )
        runtime_rates.append(runtime_count / denominator)
        differences.append((runtime_count - remote_count) / denominator)
    return {
        "draw_count": BOOTSTRAP_DRAWS,
        "undefined_draw_count": 0,
        "namespace": pv.SUITE_ID,
        "seed": BOOTSTRAP_SEED,
        "runtime_correct_rate_ci95": [
            percentile_type7(runtime_rates, 0.025),
            percentile_type7(runtime_rates, 0.975),
        ],
        "runtime_minus_remote_rate_ci95": [
            percentile_type7(differences, 0.025),
            percentile_type7(differences, 0.975),
        ],
    }


def analyze_rows(rows, tasks, revision):
    pv.validate_rows(rows, tasks, revision)
    generative = [row for row in rows if row["cohort"] != "deterministic"]
    deterministic = [row for row in rows if row["cohort"] == "deterministic"]
    task_ids = [
        task["task_id"] for task in tasks if task["cohort"] != "deterministic"
    ]
    by_cohort = {
        cohort: _scope([row for row in generative if row["cohort"] == cohort])
        for cohort in ("structural_json", "line_format", "classification")
    }
    contract_types = (
        "structured_json", "json_format", "bullet_format",
        "label_format", "classification_labels",
    )
    by_contract = {
        kind: _scope(
            [row for row in generative if row["contract_type"] == kind]
        )
        for kind in contract_types
    }
    overall = _scope(generative)
    actual_remote = overall["actual_remote_logical_calls"]
    overall["remote_calls_avoided_vs_always_remote"] = (
        pv.PROVIDER_OBSERVATION_COUNT - actual_remote
    )
    report = {
        "schema_version": "runtime_v0_2_prospective_analysis_v1",
        "suite_id": pv.SUITE_ID,
        "plan_sha256": pv.PLAN_SHA256,
        "benchmark_sha256": pv.BENCHMARK_SHA256,
        "config_sha256": pv.CONFIG_SHA256,
        "implementation_revision": revision,
        "generative": {
            "overall": overall,
            "by_cohort": by_cohort,
            "by_contract_type": by_contract,
            "bootstrap": _bootstrap(generative, task_ids),
        },
        "deterministic": {
            "observation_count": len(deterministic),
            "runtime_correct_count": sum(
                bool(row["runtime_correct"]) for row in deterministic
            ),
            "provider_call_count": sum(
                bool(row["local"]["present"]) + bool(row["remote"]["present"])
                for row in deterministic
            ),
        },
        "paired_provider_totals": {
            "local_logical_calls": sum(
                bool(row["local"]["present"]) for row in rows
            ),
            "remote_logical_calls": sum(
                bool(row["remote"]["present"]) for row in rows
            ),
            "remote_http_attempts": sum(
                int(row["remote"].get("attempt_count") or 0) for row in rows
            ),
            "reported_remote_cost_usd": sum(
                float(row["remote"].get("cost") or 0.0) for row in rows
            ),
        },
    }
    if (
        sum(overall["overlap"].values()) != len(generative)
        or report["deterministic"]["provider_call_count"] != 0
        or report["paired_provider_totals"]["local_logical_calls"] != 90
        or report["paired_provider_totals"]["remote_logical_calls"] != 90
    ):
        raise pv.FrozenDesignError("ANALYSIS_RECONCILIATION_FAILED")
    return report


def authenticate_complete(root=pv.ROOT):
    root = Path(root)
    _, tasks, _ = pv.load_frozen_inputs()
    paths = pv.output_paths(root)
    required = ("runs", "telemetry", "summary")
    if any(not paths[name].exists() for name in required):
        raise pv.StateError("COMPLETE_OUTPUT_MISSING")
    if any(Path(str(path) + ".partial").exists() for path in paths.values()):
        raise pv.StateError("PARTIAL_OUTPUT_PRESENT")
    if paths["analysis_json"].exists() or paths["analysis_csv"].exists():
        raise pv.StateError("ANALYSIS_ALREADY_EXISTS")
    summary = pv.strict_json_loads(paths["summary"].read_text(encoding="utf-8"))
    revision = summary.get("implementation_revision")
    def read_jsonl(path):
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n") or any(not line for line in text.splitlines()):
            raise pv.FrozenDesignError("MALFORMED_OR_TRUNCATED_JSONL")
        return [pv.strict_json_loads(line) for line in text.splitlines()]

    rows = read_jsonl(paths["runs"])
    telemetry = read_jsonl(paths["telemetry"])
    pv.validate_rows(rows, tasks, revision)
    if (
        summary.get("schema_version") != "runtime_v0_2_prospective_summary_v1"
        or summary.get("suite_id") != pv.SUITE_ID
        or summary.get("plan_sha256") != pv.PLAN_SHA256
        or summary.get("benchmark_sha256") != pv.BENCHMARK_SHA256
        or summary.get("config_sha256") != pv.CONFIG_SHA256
        or len(telemetry) != pv.OBSERVATION_COUNT
        or [row["router_request_id"] for row in rows]
        != [record.get("request_id") for record in telemetry]
        or any(
            record.get("request_mode") != "explicit_contract"
            or record.get("task_class") != row.get("task_class")
            or record.get("contract_type") != row.get("contract_type")
            or record.get("decision") != row.get("router_decision")
            for row, record in zip(rows, telemetry)
        )
        or summary.get("runs_sha256") != pv.file_sha256(paths["runs"])
        or summary.get("router_telemetry_sha256")
        != pv.file_sha256(paths["telemetry"])
        or summary.get("observation_count") != pv.OBSERVATION_COUNT
        or summary.get("runtime_correct_count")
        != sum(bool(row["runtime_correct"]) for row in rows)
        or summary.get("accepted_error_count")
        != sum(bool(row["accepted_error"]) for row in rows)
        or summary.get("withheld_count")
        != sum(bool(row["withheld"]) for row in rows)
        or summary.get("budget") != rows[-1]["budget_after_observation"]
    ):
        raise pv.FrozenDesignError("COMPLETE_AUTHENTICATION_FAILED")
    return rows, tasks, revision


def _csv_rows(report):
    rows = []
    scopes = [("overall", "generative", report["generative"]["overall"])]
    scopes.extend(
        ("cohort", name, value)
        for name, value in report["generative"]["by_cohort"].items()
    )
    scopes.extend(
        ("contract_type", name, value)
        for name, value in report["generative"]["by_contract_type"].items()
    )
    for scope_type, scope_name, value in scopes:
        rows.append({
            "scope_type": scope_type,
            "scope_name": scope_name,
            "observation_count": value["observation_count"],
            "runtime_correct_count": value["runtime_correct_count"],
            "local_correct_count": value["local_correct_count"],
            "remote_correct_count": value["remote_correct_count"],
            "accepted_error_count": value["accepted_error_count"],
            "withheld_count": value["withheld_count"],
            "actual_remote_logical_calls": value["actual_remote_logical_calls"],
        })
    return rows


def write_analysis(root=pv.ROOT):
    root = Path(root)
    rows, tasks, revision = authenticate_complete(root)
    report = analyze_rows(rows, tasks, revision)
    paths = pv.output_paths(root)
    pv.atomic_write_json(paths["analysis_json"], report)
    partial, handle = pv.open_partial(paths["analysis_csv"])
    try:
        fields = list(_csv_rows(report)[0])
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(_csv_rows(report))
        handle.flush()
        __import__("os").fsync(handle.fileno())
    finally:
        handle.close()
    pv.publish_partial(partial, paths["analysis_csv"])
    return report


def main():
    report = write_analysis()
    print(json.dumps(report["generative"]["overall"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
