"""Offline scoring and reporting for the separated leakage-control bundle."""

import json
from pathlib import Path

from benchmark_leakage_controls import construct_validity, evaluate_null_baselines, null_baselines
from benchmark_leakage_controls import mutation_verdict
from benchmark_leakage_preflight import load_separated_suite, validate_request_boundary, validate_variant_inventory


def normalize_output(raw_output, match_mode):
    if not isinstance(raw_output, str):
        return ""
    if match_mode == "classification":
        return raw_output.strip().lower()
    if match_mode == "structured_json":
        try:
            return json.dumps(json.loads(raw_output), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            return raw_output.strip()
    if match_mode == "text":
        return raw_output.strip()
    raise ValueError(f"unsupported match mode: {match_mode}")


def oracle_correct(oracle_entry, raw_output):
    """Return raw and normalized correctness without semantic repair."""
    mode = oracle_entry["match_mode"]
    expected = oracle_entry["expected"]
    if mode == "structured_json":
        expected = json.dumps(expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        expected = str(expected)
    raw_correct = raw_output == expected
    normalized = normalize_output(raw_output, mode)
    normalized_correct = normalized == normalize_output(expected, mode)
    return raw_correct, normalized_correct


def analyze_null_baselines(tasks, oracle, baselines=None):
    """Return rows and construct-validity status for every task variant."""
    oracle_by_key = oracle

    def score(task, raw_output):
        key = f"{task['task_id']}__{task['variant_id']}"
        return oracle_correct(oracle_by_key[key], raw_output)[1]

    rows = evaluate_null_baselines(tasks, score, baselines=baselines)
    by_variant = {}
    for row in rows:
        key = f"{row['task_id']}__{row['variant_id']}"
        by_variant.setdefault(key, {})[row["baseline_id"]] = row["oracle_correct"]
    verdicts = {key: construct_validity(results) for key, results in sorted(by_variant.items())}
    return rows, verdicts


def _passes_by_variant(rows):
    passes = {}
    for row in rows or []:
        key = (row["task_id"], row.get("variant_id", "base"))
        passes[key] = passes.get(key, False) or bool(row.get("oracle_correct_normalized", row.get("oracle_correct")))
    return passes


def build_construct_validity_report(tasks, baseline_rows, *, model_rows=None, ablation_rows=None):
    """Combine condition results without treating absent model runs as passes."""
    baseline_passes = _passes_by_variant(baseline_rows)
    model_passes = _passes_by_variant(model_rows)
    ablation_passes = _passes_by_variant(ablation_rows)
    by_task = {}
    for task in tasks:
        key = (task["task_id"], task.get("variant_id", "base"))
        by_task.setdefault(task["task_id"], {})[task.get("variant_id", "base")] = {
            "baseline_pass": baseline_passes.get(key, False),
            "model_pass": model_passes.get(key) if model_rows is not None else None,
            "ablation_pass": ablation_passes.get(key, False) if ablation_rows is not None else None,
        }

    result = {}
    for task_id, variants in sorted(by_task.items()):
        baseline_status = construct_validity({variant: data["baseline_pass"] for variant, data in variants.items()})
        model_status = None
        mutation_status = None
        if model_rows is not None:
            model_status = "MODEL_PASS" if any(data["model_pass"] for data in variants.values()) else "MODEL_FAIL"
            if "base" in variants:
                mutant_values = [data["model_pass"] for variant, data in variants.items() if variant != "base"]
                if mutant_values:
                    mutation_status = mutation_verdict(variants["base"]["model_pass"], mutant_values[0])
        ablation_status = None
        if ablation_rows is not None:
            ablation_status = "CV_ABLATION_PASSES" if any(data["ablation_pass"] for data in variants.values()) else "CV_ABLATION_FAILS"
        if baseline_status == "CV_NULL_BASELINE_PASSES":
            final_status = baseline_status
        elif ablation_status == "CV_ABLATION_PASSES":
            final_status = ablation_status
        elif mutation_status == "CV_MUTANT_DIVERGENCE":
            final_status = mutation_status
        elif model_rows is None or ablation_rows is None:
            final_status = "CV_PENDING_MODEL_CONTROLS"
        else:
            final_status = "CV_OK"
        result[task_id] = {
            "variants": variants,
            "baseline_status": baseline_status,
            "model_status": model_status,
            "ablation_status": ablation_status,
            "mutation_status": mutation_status,
            "final_status": final_status,
        }
    return result


def build_report(tasks_path="benchmark_tasks_leakage_v1.json", oracle_path="benchmark_oracle_leakage_v1.json"):
    tasks, oracle = load_separated_suite(tasks_path, oracle_path)
    boundary = validate_request_boundary(tasks, oracle)
    variants = validate_variant_inventory(tasks)
    rows, verdicts = analyze_null_baselines(tasks, oracle)
    return {
        "schema_version": "benchmark_leakage_v1_null_baseline_report",
        "task_count": len(tasks),
        "variant_count": len(tasks),
        "request_boundary": boundary,
        "variants": variants,
        "baseline_ids": list(null_baselines()),
        "rows": rows,
        "construct_validity": verdicts,
        "model_runs_executed": 0,
        "ablation_runs_executed": 0,
    }


def main():
    report = build_report()
    Path("benchmark_leakage_v1_null_baseline_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "task_count": report["task_count"],
        "variant_count": report["variant_count"],
        "model_runs_executed": report["model_runs_executed"],
        "ablation_runs_executed": report["ablation_runs_executed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
