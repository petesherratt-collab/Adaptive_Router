"""Offline analysis for the frozen corrected v2 leakage-control run."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from analyze_benchmark_leakage_v1 import analyze_null_baselines
from benchmark_leakage_preflight import load_separated_suite, validate_request_boundary, validate_variant_inventory


ROOT = Path(__file__).resolve().parent
TASKS_PATH = ROOT / "benchmark_tasks_leakage_v2.json"
ORACLE_PATH = ROOT / "benchmark_oracle_leakage_v2.json"
RUNS_PATH = ROOT / "benchmark_leakage_v2_corrected_runs.jsonl"
PLAN_PATH = ROOT / "BENCHMARK_LEAKAGE_V2_CORRECTED_PLAN.md"
REPORT_PATH = ROOT / "benchmark_leakage_v2_corrected_report.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows():
    return [json.loads(line) for line in RUNS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def score(row):
    return bool(row.get("oracle_correct_normalized", row.get("oracle_correct")))


def summarize(rows, key_fields):
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in key_fields)].append(row)
    result = {}
    for key, group in sorted(grouped.items()):
        result["|".join(str(value) for value in key)] = {
            "n": len(group),
            "normalized_passes": sum(score(row) for row in group),
            "raw_passes": sum(bool(row.get("oracle_correct_raw")) for row in group),
            "normalization_changed_verdict": sum(bool(row.get("normalization_changed_verdict")) for row in group),
            "status_counts": dict(sorted(Counter(row["status"] for row in group).items())),
            "reason_counts": dict(sorted(Counter(row["reason_code"] for row in group).items())),
        }
    return result


def main():
    tasks, oracle = load_separated_suite(TASKS_PATH, ORACLE_PATH)
    rows = load_rows()
    expected_models = ["gemma3:270m", "gemma3:1b", "gemma3:4b"]
    assert len(rows) == 540, len(rows)
    assert sorted({row["model"] for row in rows}) == sorted(expected_models)
    assert all(len([row for row in rows if row["model"] == model]) == 180 for model in expected_models)

    provenance_fields = ("config_sha256", "plan_sha256", "implementation_revision")
    provenance = {
        field: sorted({(row.get("run_metadata") or {}).get(field) for row in rows})
        for field in provenance_fields
    }
    model_digests = {
        model: sorted({(row.get("run_metadata") or {}).get("model_digest") for row in rows if row["model"] == model})
        for model in expected_models
    }

    null_rows, null_verdicts = analyze_null_baselines(tasks, oracle)
    task_classes = {task["task_id"]: task["task_class"] for task in tasks}
    variant_inventory = validate_variant_inventory(tasks)
    boundary = validate_request_boundary(tasks, oracle)

    ordinary = [row for row in rows if row["condition"] == "model"]
    ablations = [row for row in rows if row["condition"] == "ablation"]
    per_model_condition = summarize(rows, ("model", "condition"))
    per_model_task = summarize(rows, ("model", "condition", "task_id"))

    controls = {}
    for model in expected_models:
        for task in tasks:
            key = (model, task["task_id"], task["variant_id"])
            normal = [row for row in ordinary if (row["model"], row["task_id"], row["variant_id"]) == key]
            ablated = [row for row in ablations if (row["model"], row["task_id"], row["variant_id"]) == key]
            normal_passes = sum(score(row) for row in normal)
            ablated_passes = sum(score(row) for row in ablated)
            controls["|".join(key)] = {
                "model": model,
                "task_id": task["task_id"],
                "variant_id": task["variant_id"],
                "task_class": task["task_class"],
                "ordinary_normalized_passes": normal_passes,
                "ablation_normalized_passes": ablated_passes,
                "ordinary_reps": len(normal),
                "ablation_reps": len(ablated),
                "ordinary_passes_all_reps": normal_passes == len(normal),
                "ablation_passes_all_reps": ablated_passes == len(ablated),
                "ablation_suppressed_all_ordinary_passes": normal_passes > 0 and ablated_passes == 0,
            }

    report = {
        "schema_version": "benchmark_leakage_v2_corrected_report",
        "run_sha256": sha256(RUNS_PATH),
        "plan_sha256": sha256(PLAN_PATH),
        "tasks_sha256": sha256(TASKS_PATH),
        "oracle_sha256": sha256(ORACLE_PATH),
        "row_count": len(rows),
        "models": expected_models,
        "repetitions": sorted({row["rep"] for row in rows}),
        "condition_counts": dict(sorted(Counter(row["condition"] for row in rows).items())),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "reason_counts": dict(sorted(Counter(row["reason_code"] for row in rows).items())),
        "provenance": provenance,
        "model_digests": model_digests,
        "request_boundary": boundary,
        "variant_inventory": variant_inventory,
        "null_baseline_verdicts": null_verdicts,
        "null_baseline_rows": null_rows,
        "per_model_condition": per_model_condition,
        "per_model_task": per_model_task,
        "controls": controls,
        "task_classes": task_classes,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "row_count": len(rows),
        "run_sha256": report["run_sha256"],
        "status_counts": report["status_counts"],
        "provenance": report["provenance"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
