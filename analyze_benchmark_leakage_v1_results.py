"""Analyze completed leakage-control evidence without rerunning providers."""

import json
from pathlib import Path

from analyze_benchmark_leakage_v1 import build_construct_validity_report


RUNS_PATH = Path("benchmark_leakage_v1_runs.jsonl")
BASELINE_PATH = Path("benchmark_leakage_v1_null_baseline_report.json")
TASKS_PATH = Path("benchmark_tasks_leakage_v1.json")
OUTPUT_PATH = Path("benchmark_leakage_v1_construct_validity_report.json")


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def build_report():
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    runs = _rows(RUNS_PATH)
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["rows"]
    model = [row for row in runs if row["condition"] == "model"]
    ablation = [row for row in runs if row["condition"] == "ablation"]
    return {
        "schema_version": "benchmark_leakage_v1_construct_validity_report",
        "run_rows": len(runs),
        "model_rows": len(model),
        "ablation_rows": len(ablation),
        "model_reason_counts": _counts(model, "reason_code"),
        "ablation_reason_counts": _counts(ablation, "reason_code"),
        "normalization_changed_verdict_count": sum(row["normalization_changed_verdict"] for row in runs),
        "construct_validity": build_construct_validity_report(
            tasks, baseline, model_rows=model, ablation_rows=ablation
        ),
    }


def _counts(rows, field):
    counts = {}
    for row in rows:
        counts[row[field]] = counts.get(row[field], 0) + 1
    return dict(sorted(counts.items()))


def main():
    report = build_report()
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "run_rows": report["run_rows"],
        "model_rows": report["model_rows"],
        "ablation_rows": report["ablation_rows"],
        "normalization_changed_verdict_count": report["normalization_changed_verdict_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
