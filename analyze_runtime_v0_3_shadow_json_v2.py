"""Authenticate and analyze runtime v0.3 structural-JSON shadow evidence."""

from __future__ import annotations

from collections import Counter
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

import runtime_v0_3_shadow_json_v2 as pv


BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = "20260908-runtime-v0.3-shadow-json-v2"


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


def clopper_pearson_upper(k, n, alpha=0.05):
    if type(k) is not int or type(n) is not int or not 0 <= k <= n or n <= 0:
        raise pv.FrozenDesignError("INVALID_BINOMIAL_COUNT")
    if k == n:
        return 1.0
    if k == 0:
        return 1.0 - alpha ** (1.0 / n)

    def probability_at_most(value):
        return sum(
            math.comb(n, i) * value**i * (1.0 - value) ** (n - i)
            for i in range(k + 1)
        )

    low, high = 0.0, 1.0
    for _ in range(100):
        middle = (low + high) / 2.0
        if probability_at_most(middle) > alpha:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _counterfactual(row):
    use_local = row["local_contract"]["status"] == "PASS"
    correct = (
        row["local_oracle"]["correct"] if use_local
        else row["remote_oracle"]["correct"]
    )
    latency = row["local"]["total_ms"]
    if not use_local:
        latency += row["remote"]["total_ms"]
    return use_local, bool(correct), latency


def _scope(rows):
    total = len(rows)
    local_correct = sum(bool(row["local_oracle"]["correct"]) for row in rows)
    remote_correct = sum(bool(row["remote_oracle"]["correct"]) for row in rows)
    local_pass = sum(row["local_contract"]["status"] == "PASS" for row in rows)
    remote_pass = sum(row["remote_contract"]["status"] == "PASS" for row in rows)
    local_accepted_errors = sum(
        row["local_contract"]["status"] == "PASS"
        and not row["local_oracle"]["correct"] for row in rows
    )
    local_correct_rejections = sum(
        row["local_contract"]["status"] != "PASS"
        and row["local_oracle"]["correct"] for row in rows
    )
    selections = [_counterfactual(row) for row in rows]
    counterfactual_correct = sum(item[1] for item in selections)
    both = sum(
        row["local_oracle"]["correct"] and row["remote_oracle"]["correct"]
        for row in rows
    )
    local_only = sum(
        row["local_oracle"]["correct"] and not row["remote_oracle"]["correct"]
        for row in rows
    )
    remote_only = sum(
        not row["local_oracle"]["correct"] and row["remote_oracle"]["correct"]
        for row in rows
    )
    neither = total - both - local_only - remote_only
    local_success = sum(row["local"]["success"] is True for row in rows)
    remote_success = sum(row["remote"]["success"] is True for row in rows)
    return {
        "observation_count": total,
        "runtime_correct_count": sum(bool(row["runtime_correct"]) for row in rows),
        "local_correct_count": local_correct,
        "remote_correct_count": remote_correct,
        "local_provider_success_count": local_success,
        "remote_provider_success_count": remote_success,
        "local_provider_error_count": total - local_success,
        "remote_provider_error_count": total - remote_success,
        "local_provider_errors": dict(Counter(
            row["local"].get("error") for row in rows
            if row["local"]["success"] is False
        )),
        "remote_provider_errors": dict(Counter(
            row["remote"].get("error") for row in rows
            if row["remote"]["success"] is False
        )),
        "local_correct_given_provider_success_count": local_correct,
        "local_correct_given_provider_success_rate": (
            local_correct / local_success if local_success else None
        ),
        "remote_correct_given_provider_success_count": remote_correct,
        "remote_correct_given_provider_success_rate": (
            remote_correct / remote_success if remote_success else None
        ),
        "local_contract_pass_count": local_pass,
        "remote_contract_pass_count": remote_pass,
        "local_accepted_error_count": local_accepted_errors,
        "local_correct_rejection_count": local_correct_rejections,
        "counterfactual_correct_count": counterfactual_correct,
        "counterfactual_minus_runtime_count": (
            counterfactual_correct
            - sum(bool(row["runtime_correct"]) for row in rows)
        ),
        "counterfactual_minus_remote_count": counterfactual_correct - remote_correct,
        "remote_calls_avoided": sum(item[0] for item in selections),
        "overlap": {
            "both": both, "local_only": local_only,
            "remote_only": remote_only, "neither": neither,
        },
        "actual_routes": dict(Counter(row["actual_route"] for row in rows)),
        "actual_reasons": dict(Counter(row["actual_reason"] for row in rows)),
        "remote_reported_cost_usd": sum(
            float(row["remote"].get("cost") or 0.0) for row in rows
        ),
        "remote_unreported_failure_cost_count": sum(
            row["remote"].get("cost") is None for row in rows
        ),
        "remote_reserved_failure_cost_usd": sum(
            pv.UNREPORTED_FAILURE_COST_RESERVE_USD
            for row in rows
            if row["remote"].get("cost") is None
        ),
        "remote_http_attempts": sum(
            int(row["remote"].get("attempt_count") or 0) for row in rows
        ),
        "remote_median_ms": _median(row["remote"].get("total_ms") for row in rows),
        "local_median_ms": _median(row["local"].get("total_ms") for row in rows),
        "actual_runtime_median_ms": _median(
            row["router_decision"].get("total_ms") for row in rows
        ),
        "counterfactual_request_median_ms": _median(
            item[2] for item in selections
        ),
    }


def _bootstrap(rows, task_ids):
    by_task = {
        task_id: [row for row in rows if row["task_id"] == task_id]
        for task_id in task_ids
    }
    if any(len(cluster) != pv.REPETITIONS for cluster in by_task.values()):
        raise pv.FrozenDesignError("BOOTSTRAP_TASK_CLUSTER_SIZE")
    differences, avoided, undefined = [], [], 0
    slots = len(task_ids)
    for draw in range(BOOTSTRAP_DRAWS):
        sampled = []
        for slot in range(slots):
            digest = hashlib.sha256(
                f"{pv.SUITE_ID}|{BOOTSTRAP_SEED}|{draw}|{slot}".encode("ascii")
            ).digest()
            sampled.extend(by_task[task_ids[int.from_bytes(digest[:8], "big") % slots]])
        if not sampled:
            undefined += 1
            continue
        runtime_correct = sum(row["runtime_correct"] for row in sampled)
        selected = [_counterfactual(row) for row in sampled]
        counterfactual_correct = sum(item[1] for item in selected)
        differences.append(
            (counterfactual_correct - runtime_correct) / len(sampled)
        )
        avoided.append(sum(item[0] for item in selected))
    return {
        "draw_count": BOOTSTRAP_DRAWS,
        "undefined_draw_count": undefined,
        "namespace": pv.SUITE_ID,
        "seed": BOOTSTRAP_SEED,
        "counterfactual_minus_runtime_rate_ci95": [
            percentile_type7(differences, 0.025),
            percentile_type7(differences, 0.975),
        ],
        "remote_calls_avoided_ci95": [
            percentile_type7(avoided, 0.025),
            percentile_type7(avoided, 0.975),
        ],
    }


def analyze_rows(rows, tasks, revision):
    pv.validate_rows(rows, tasks, revision)
    overall = _scope(rows)
    by_stratum = {
        name: _scope([row for row in rows if row["stratum"] == name])
        for name in pv.STRATUM_COUNTS
    }
    accepted_upper = (
        clopper_pearson_upper(
            overall["local_accepted_error_count"],
            overall["local_contract_pass_count"],
        )
        if overall["local_contract_pass_count"]
        else 1.0
    )
    conditions = {
        "complete_authenticated_arms": len(rows) == pv.OBSERVATION_COUNT,
        "zero_local_accepted_errors": overall["local_accepted_error_count"] == 0,
        "at_least_60_local_contract_passes": overall["local_contract_pass_count"] >= 60,
        "accepted_error_upper_at_most_0_05": accepted_upper <= 0.05,
        "counterfactual_success_at_least_runtime": (
            overall["counterfactual_correct_count"] >= overall["runtime_correct_count"]
        ),
        "at_least_60_remote_calls_avoided": overall["remote_calls_avoided"] >= 60,
        "counterfactual_median_at_most_remote_provider": (
            overall["counterfactual_request_median_ms"]
            <= overall["remote_median_ms"]
        ),
        "no_instrumentation_or_execution_failure": True,
    }
    report = {
        "schema_version": "runtime_v0_3_shadow_json_analysis_v2",
        "suite_id": pv.SUITE_ID,
        "plan_sha256": pv.PLAN_SHA256,
        "benchmark_sha256": pv.BENCHMARK_SHA256,
        "config_sha256": pv.CONFIG_SHA256,
        "implementation_revision": revision,
        "overall": overall,
        "by_stratum": by_stratum,
        "accepted_error_bound": {
            "method": "exact_one_sided_95_clopper_pearson",
            "errors": overall["local_accepted_error_count"],
            "denominator": overall["local_contract_pass_count"],
            "upper": accepted_upper,
        },
        "bootstrap": _bootstrap(rows, [task["task_id"] for task in tasks]),
        "promotion": {
            "conditions": conditions,
            "decision": (
                "PROMOTION_CANDIDATE" if all(conditions.values())
                else "DO_NOT_PROMOTE"
            ),
        },
    }
    if (
        sum(overall["overlap"].values()) != pv.OBSERVATION_COUNT
        or sum(value["observation_count"] for value in by_stratum.values())
        != pv.OBSERVATION_COUNT
        or overall["actual_routes"] != {"remote": pv.OBSERVATION_COUNT}
    ):
        raise pv.FrozenDesignError("ANALYSIS_RECONCILIATION_FAILED")
    return report


def _read_jsonl(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.endswith("\n") or any(not line for line in text.splitlines()):
        raise pv.FrozenDesignError("MALFORMED_OR_TRUNCATED_JSONL")
    return [pv.strict_json_loads(line) for line in text.splitlines()]


def authenticate_complete(root=pv.ROOT, frozen_root=None):
    root = Path(root)
    frozen_root = Path(frozen_root or pv.ROOT)
    _, tasks, _ = pv.load_frozen_inputs(frozen_root)
    paths = pv.output_paths(root)
    if paths["failure"].exists():
        raise pv.StateError("FAILURE_MANIFEST_PRESENT")
    if any(not paths[name].exists() for name in ("runs", "telemetry", "summary")):
        raise pv.StateError("COMPLETE_OUTPUT_MISSING")
    if any(Path(str(path) + ".partial").exists() for path in paths.values()):
        raise pv.StateError("PARTIAL_OUTPUT_PRESENT")
    if paths["analysis_json"].exists() or paths["analysis_csv"].exists():
        raise pv.StateError("ANALYSIS_ALREADY_EXISTS")
    summary = pv.strict_json_loads(paths["summary"].read_text(encoding="utf-8"))
    revision = summary.get("implementation_revision")
    rows, telemetry = _read_jsonl(paths["runs"]), _read_jsonl(paths["telemetry"])
    pv.validate_rows(rows, tasks, revision)
    budget = summary.get("budget")
    if not isinstance(budget, dict) or set(budget) != {
        "local_logical_calls",
        "remote_logical_calls",
        "remote_http_attempts",
        "reported_remote_cost_usd",
        "unreported_remote_failure_count",
        "reserved_unreported_failure_cost_usd",
    }:
        raise pv.FrozenDesignError("COMPLETE_AUTHENTICATION_FAILED")
    expected_summary = pv.summary(rows, revision, pv.EvidenceBudget(**budget))
    if (
        summary.get("schema_version") != "runtime_v0_3_shadow_json_summary_v2"
        or summary.get("suite_id") != pv.SUITE_ID
        or summary.get("plan_sha256") != pv.PLAN_SHA256
        or summary.get("benchmark_sha256") != pv.BENCHMARK_SHA256
        or summary.get("config_sha256") != pv.CONFIG_SHA256
        or len(telemetry) != pv.OBSERVATION_COUNT
        or [row["router_request_id"] for row in rows]
        != [record.get("request_id") for record in telemetry]
        or any(row["router_telemetry"] != record for row, record in zip(rows, telemetry))
        or summary.get("runs_sha256") != pv.file_sha256(paths["runs"])
        or summary.get("router_telemetry_sha256") != pv.file_sha256(paths["telemetry"])
        or summary.get("observation_count") != pv.OBSERVATION_COUNT
        or summary.get("budget") != rows[-1]["budget_after_observation"]
        or budget.get("local_logical_calls") != pv.OBSERVATION_COUNT
        or budget.get("remote_logical_calls") != pv.OBSERVATION_COUNT
        or type(budget.get("remote_http_attempts")) is not int
        or not pv.OBSERVATION_COUNT
        <= budget["remote_http_attempts"]
        <= pv.MAX_REMOTE_HTTP_ATTEMPTS
        or type(budget.get("reported_remote_cost_usd")) not in (int, float)
        or isinstance(budget.get("reported_remote_cost_usd"), bool)
        or not math.isfinite(budget["reported_remote_cost_usd"])
        or budget["reported_remote_cost_usd"] < 0
        or type(budget.get("unreported_remote_failure_count")) is not int
        or not 0
        <= budget["unreported_remote_failure_count"]
        <= pv.OBSERVATION_COUNT
        or type(budget.get("reserved_unreported_failure_cost_usd"))
        not in (int, float)
        or isinstance(budget.get("reserved_unreported_failure_cost_usd"), bool)
        or not math.isfinite(budget["reserved_unreported_failure_cost_usd"])
        or not math.isclose(
            budget["reserved_unreported_failure_cost_usd"],
            budget["unreported_remote_failure_count"]
            * pv.UNREPORTED_FAILURE_COST_RESERVE_USD,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        or any(
            summary.get(key) != value
            for key, value in expected_summary.items()
            if key != "budget"
        )
    ):
        raise pv.FrozenDesignError("COMPLETE_AUTHENTICATION_FAILED")
    return rows, tasks, revision


def _csv_rows(report):
    scopes = [("overall", "all", report["overall"])]
    scopes.extend(
        ("stratum", name, value) for name, value in report["by_stratum"].items()
    )
    return [{
        "scope_type": kind,
        "scope_name": name,
        "observation_count": value["observation_count"],
        "local_correct_count": value["local_correct_count"],
        "remote_correct_count": value["remote_correct_count"],
        "local_provider_success_count": value["local_provider_success_count"],
        "remote_provider_success_count": value["remote_provider_success_count"],
        "local_provider_error_count": value["local_provider_error_count"],
        "remote_provider_error_count": value["remote_provider_error_count"],
        "local_contract_pass_count": value["local_contract_pass_count"],
        "local_accepted_error_count": value["local_accepted_error_count"],
        "counterfactual_correct_count": value["counterfactual_correct_count"],
        "remote_calls_avoided": value["remote_calls_avoided"],
    } for kind, name, value in scopes]


def build_analysis(root=pv.ROOT, frozen_root=None):
    rows, tasks, revision = authenticate_complete(root, frozen_root)
    return analyze_rows(rows, tasks, revision)


def write_analysis(root=pv.ROOT, frozen_root=None):
    report = build_analysis(root, frozen_root)
    paths = pv.output_paths(root)
    pv.atomic_write_json(paths["analysis_json"], report)
    partial, handle = pv.open_partial(paths["analysis_csv"])
    try:
        rows = _csv_rows(report)
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        __import__("os").fsync(handle.fileno())
    finally:
        handle.close()
    pv.publish_partial(partial, paths["analysis_csv"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    report = write_analysis() if args.write else build_analysis()
    print(json.dumps({
        **report["overall"],
        "accepted_error_upper_95": report["accepted_error_bound"]["upper"],
        "promotion_decision": report["promotion"]["decision"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
