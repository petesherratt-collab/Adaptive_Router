"""Execute the frozen leakage-control bundle with immutable local evidence."""

import json
import os
from pathlib import Path

from benchmark_leakage_preflight import (
    load_separated_suite,
    validate_mutation_pairs,
    validate_request_boundary,
    validate_variant_inventory,
)
from benchmark_leakage_runner import run_ablation_conditions, run_conditions
from local import generate


ROOT = Path(__file__).resolve().parent
TASKS_PATH = ROOT / "benchmark_tasks_leakage_v1.json"
ORACLE_PATH = ROOT / "benchmark_oracle_leakage_v1.json"
OUTPUT_PATH = ROOT / "benchmark_leakage_v1_runs.jsonl"
PARTIAL_PATH = Path(str(OUTPUT_PATH) + ".partial")
REPS = 3


def _preflight(config):
    tasks, oracle = load_separated_suite(TASKS_PATH, ORACLE_PATH)
    validate_variant_inventory(tasks)
    validate_mutation_pairs(tasks)
    validate_request_boundary(tasks, oracle, config["model"])
    if OUTPUT_PATH.exists() or PARTIAL_PATH.exists():
        raise FileExistsError("canonical or partial output already exists")
    if config.get("temperature") != 0 or config.get("max_tokens") != 256:
        raise ValueError("execution config does not match frozen parameters")
    return tasks, oracle


def _generate(prompt, model, config):
    result = generate(prompt, {**config, "model": model})
    return {"raw_output": result.text if result.success else "", "telemetry": result.metadata()}


def run(config=None):
    config = dict(config or json.loads((ROOT / "config.json").read_text())["local"])
    tasks, oracle = _preflight(config)
    generator = lambda prompt, model: _generate(prompt, model, config)
    rows = run_conditions(tasks, oracle, generator, config["model"], reps=REPS)
    rows.extend(run_ablation_conditions(tasks, oracle, generator, config["model"], reps=REPS))
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    PARTIAL_PATH.write_text(payload, encoding="utf-8")
    os.replace(PARTIAL_PATH, OUTPUT_PATH)
    return rows


if __name__ == "__main__":
    print(json.dumps({"rows": len(run())}, sort_keys=True))
