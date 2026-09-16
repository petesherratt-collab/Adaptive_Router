"""No-provider preflight and null-baseline adapter for separated suites."""

import json
from pathlib import Path

from benchmark_leakage_controls import (
    ablate_prompt,
    assert_no_expected_value_leakage,
    evaluate_null_baselines,
)


REQUIRED_TASK_FIELDS = frozenset({"task_id", "task_class", "prompt", "variant_id"})


def _reject_expected_fields(value, path="task"):
    if isinstance(value, dict):
        if "expected" in value:
            raise ValueError(f"oracle field found in task data at {path}")
        for key, child in value.items():
            _reject_expected_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_expected_fields(child, f"{path}[{index}]")


def load_separated_suite(tasks_path, oracle_path):
    """Load and validate task prompts separately from oracle values."""
    tasks_document = json.loads(Path(tasks_path).read_text(encoding="utf-8"))
    oracle_document = json.loads(Path(oracle_path).read_text(encoding="utf-8"))
    if not isinstance(tasks_document, list) or not isinstance(oracle_document, dict):
        raise ValueError("tasks must be a list and oracle must be an object")
    _reject_expected_fields(tasks_document)

    tasks = []
    keys = set()
    for task in tasks_document:
        if not isinstance(task, dict) or not REQUIRED_TASK_FIELDS.issubset(task):
            raise ValueError("task is missing a required separated-suite field")
        key = f"{task['task_id']}__{task['variant_id']}"
        if key in keys:
            raise ValueError(f"duplicate task variant: {key}")
        keys.add(key)
        tasks.append(dict(task))
    if keys != set(oracle_document):
        raise ValueError("task and oracle variant keys do not match")
    return tasks, oracle_document


def build_request_payload(task, model):
    """Build the only payload shape allowed to reach a provider."""
    if set(task) - REQUIRED_TASK_FIELDS:
        raise ValueError("request task contains fields outside the prompt boundary")
    return {
        "model": model,
        "task_id": task["task_id"],
        "variant_id": task["variant_id"],
        "prompt": task["prompt"],
    }


def validate_request_boundary(tasks, oracle, model="test"):
    """Prove that oracle values do not enter request payload metadata."""
    def string_leaves(value):
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            leaves = []
            for child in value.values():
                leaves.extend(string_leaves(child))
            return leaves
        if isinstance(value, list):
            leaves = []
            for child in value:
                leaves.extend(string_leaves(child))
            return leaves
        return []

    expected_values = []
    for value in oracle.values():
        if isinstance(value, dict) and "expected" in value:
            expected_values.extend(string_leaves(value["expected"]))
    for task in tasks:
        payload = build_request_payload(task, model)
        assert_no_expected_value_leakage(payload, expected_values)
    return {"task_count": len(tasks), "oracle_values_checked": len(expected_values)}


def validate_variant_inventory(tasks):
    """Require a base and at least one distinct mutant for every task family."""
    grouped = {}
    for task in tasks:
        grouped.setdefault(task["task_id"], set()).add(task["variant_id"])
    missing = [task_id for task_id, variants in grouped.items()
               if "base" not in variants or len(variants) < 2]
    if missing:
        raise ValueError("tasks missing a base or mutant variant: " + ", ".join(sorted(missing)))
    return {task_id: sorted(variants) for task_id, variants in sorted(grouped.items())}


def build_ablation_conditions(tasks):
    """Build model-run inputs for both deterministic input-ablation modes."""
    conditions = []
    for task in tasks:
        for mode in ("input_removed", "input_shuffled"):
            conditions.append({
                "task_id": task["task_id"],
                "variant_id": task["variant_id"],
                "task_class": task["task_class"],
                "condition": "ablation",
                "ablation_mode": mode,
                "prompt": ablate_prompt(task["prompt"], mode),
            })
    return conditions


def validate_mutation_pairs(tasks):
    """Validate that each mutant preserves task class and changes the prompt."""
    by_task = {}
    for task in tasks:
        by_task.setdefault(task["task_id"], {})[task["variant_id"]] = task
    errors = []
    for task_id, variants in by_task.items():
        base = variants.get("base")
        if base is None:
            continue
        for variant_id, mutant in variants.items():
            if variant_id == "base":
                continue
            if mutant["task_class"] != base["task_class"]:
                errors.append(f"{task_id}:{variant_id}:task_class")
            if mutant["prompt"] == base["prompt"]:
                errors.append(f"{task_id}:{variant_id}:prompt_unchanged")
    if errors:
        raise ValueError("invalid mutation pairs: " + ", ".join(sorted(errors)))
    return True


def run_null_baseline_preflight(tasks, oracle_correct, baselines=None):
    """Run deterministic baselines and return rows plus per-task verdicts."""
    rows = evaluate_null_baselines(tasks, oracle_correct, baselines=baselines)
    by_task = {}
    for row in rows:
        by_task.setdefault(row["task_id"], {})[row["baseline_id"]] = row["oracle_correct"]
    return rows, by_task
