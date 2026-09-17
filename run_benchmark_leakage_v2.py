"""Execute the frozen three-model leakage-control expansion."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

import requests

from benchmark_leakage_preflight import (
    load_separated_suite,
    validate_mutation_pairs,
    validate_request_boundary,
    validate_variant_inventory,
)
from benchmark_leakage_runner import run_ablation_conditions, run_conditions
from local import generate


ROOT = Path(__file__).resolve().parent
TASKS_PATH = ROOT / "benchmark_tasks_leakage_v2.json"
ORACLE_PATH = ROOT / "benchmark_oracle_leakage_v2.json"
PLAN_PATH = ROOT / "BENCHMARK_LEAKAGE_V2_EXECUTION_PLAN.md"
OUTPUT_PATH = ROOT / "benchmark_leakage_v2_runs.jsonl"
PARTIAL_PATH = Path(str(OUTPUT_PATH) + ".partial")
MODEL_ORDER = ("gemma3:270m", "gemma3:1b", "gemma3:4b")
REPS = 3

EXPECTED_IDENTITIES = {
    "gemma3:270m": {
        "digest": "e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be",
        "parameter_size": "268.10M", "quantization_level": "Q8_0", "size": 291554930,
    },
    "gemma3:1b": {
        "digest": "8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc",
        "parameter_size": "999.89M", "quantization_level": "Q4_K_M", "size": 815319791,
    },
    "gemma3:4b": {
        "digest": "a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a",
        "parameter_size": "4.3B", "quantization_level": "Q4_K_M", "size": 3338801804,
    },
}


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _revision():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def authenticate_model(model, base_url, session=requests):
    tags = session.get(base_url.rstrip("/") + "/api/tags", timeout=3).json().get("models", [])
    installed = next((item for item in tags if model in (item.get("name"), item.get("model"))), None)
    if installed is None:
        raise RuntimeError(f"model not installed: {model}")
    expected = EXPECTED_IDENTITIES[model]
    details = installed.get("details") or {}
    for field in ("digest", "size"):
        if installed.get(field) != expected[field]:
            raise RuntimeError(f"{model} {field} identity mismatch")
    for field in ("parameter_size", "quantization_level"):
        if details.get(field) != expected[field]:
            raise RuntimeError(f"{model} {field} identity mismatch")
    ps = session.get(base_url.rstrip("/") + "/api/ps", timeout=3).json().get("models", [])
    resident = next((item for item in ps if model in (item.get("name"), item.get("model"))), None)
    if resident is None:
        raise RuntimeError(f"model not resident: {model}")
    return {"tag": installed.get("name") or installed.get("model"), "digest": installed["digest"], "details": details, "resident_size_bytes": resident.get("size")}


def _preflight(config):
    tasks, oracle = load_separated_suite(TASKS_PATH, ORACLE_PATH)
    validate_variant_inventory(tasks)
    validate_mutation_pairs(tasks)
    validate_request_boundary(tasks, oracle)
    if OUTPUT_PATH.exists() or PARTIAL_PATH.exists():
        raise FileExistsError("canonical or partial output already exists")
    if config.get("temperature") != 0 or config.get("max_tokens") != 256:
        raise ValueError("execution config does not match frozen parameters")
    return tasks, oracle


def run(config=None, session=requests):
    config = dict(config or json.loads((ROOT / "config.json").read_text())["local"])
    tasks, oracle = _preflight(config)
    revision = _revision()
    run_metadata_base = {
        "config_sha256": _sha256(ROOT / "config.json"),
        "plan_sha256": _sha256(PLAN_PATH),
        "implementation_revision": revision,
    }
    PARTIAL_PATH.write_text("", encoding="utf-8")
    total_rows = 0
    try:
        with PARTIAL_PATH.open("a", encoding="utf-8") as handle:
            for model in MODEL_ORDER:
                identity = authenticate_model(model, config["base_url"], session)
                metadata = {**run_metadata_base, "requested_model": model, "model_digest": identity["digest"], "model_identity": identity}
                generator = lambda prompt, requested_model, cfg={**config, "model": model}: {
                    "raw_output": (result := generate(prompt, cfg)).text if result.success else "",
                    "telemetry": result.metadata(),
                }
                rows = run_conditions(tasks, oracle, generator, model, reps=REPS, run_metadata=metadata)
                rows.extend(run_ablation_conditions(tasks, oracle, generator, model, reps=REPS, run_metadata=metadata))
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                total_rows += len(rows)
        if total_rows != 540:
            raise RuntimeError(f"unexpected row count: {total_rows}")
        os.replace(PARTIAL_PATH, OUTPUT_PATH)
    except Exception:
        raise
    return total_rows


if __name__ == "__main__":
    print(json.dumps({"rows": run()}, sort_keys=True))
