"""Provider-neutral result runner for future leakage-control experiments."""

from analyze_benchmark_leakage_v1 import oracle_correct
from benchmark_leakage_controls import normalization_delta
from benchmark_leakage_preflight import build_ablation_conditions


def _reason(raw_output, raw_correct, normalized_correct, telemetry):
    if telemetry.get("success") is False:
        return "PROVIDER_FAILURE"
    if raw_correct:
        return "PASS_MODEL"
    if normalized_correct:
        return "PASS_VIA_NORMALIZATION"
    if raw_output == "":
        return "FAIL_EMPTY_OUTPUT"
    return "FAIL_ORACLE_MISMATCH"


def run_conditions(tasks, oracle, generate_fn, model, *, reps=1, condition="model", run_metadata=None):
    """Run supplied tasks through an injected generator and return result rows.

    ``generate_fn`` is deliberately injected so preflight and tests can use a
    deterministic stub. The function itself performs no provider discovery or
    network operation.
    """
    if reps < 1:
        raise ValueError("reps must be at least 1")
    rows = []
    for task in tasks:
        key = f"{task['task_id']}__{task['variant_id']}"
        entry = oracle[key]
        for rep in range(1, reps + 1):
            generated = generate_fn(task["prompt"], model)
            telemetry = {}
            if isinstance(generated, dict):
                raw_output = generated.get("raw_output", "")
                telemetry = dict(generated.get("telemetry") or {})
            else:
                raw_output = generated
            if not isinstance(raw_output, str):
                raw_output = ""
            raw_correct, normalized_correct = oracle_correct(entry, raw_output)
            delta = normalization_delta(
                raw_output,
                lambda value: _normalize_for_entry(value, entry),
                lambda value: oracle_correct(entry, value)[0],
            )
            rows.append({
                "task_id": task["task_id"],
                "variant_id": task["variant_id"],
                "task_class": task["task_class"],
                "condition": condition,
                "rep": rep,
                "model": model,
                **delta,
                "status": "OK" if normalized_correct else "FAIL",
                "reason_code": _reason(raw_output, raw_correct, normalized_correct, telemetry),
                "telemetry": telemetry,
                "run_metadata": dict(run_metadata or {}),
            })
    return rows


def _normalize_for_entry(raw_output, entry):
    from analyze_benchmark_leakage_v1 import normalize_output

    return normalize_output(raw_output, entry["match_mode"])


def run_ablation_conditions(tasks, oracle, generate_fn, model, *, reps=1, run_metadata=None):
    """Run generated ablation prompts through the same result path."""
    ablated = build_ablation_conditions(tasks)
    rows = []
    for condition in ablated:
        task = dict(condition)
        task_key = f"{task['task_id']}__{task['variant_id']}"
        rows.extend(run_conditions([task], oracle, generate_fn, model, reps=reps, condition="ablation", run_metadata=run_metadata))
        for row in rows[-reps:]:
            row["ablation_mode"] = condition["ablation_mode"]
    return rows
