"""Run only the missing 4B stratum after the documented residency warm-up."""

import hashlib
import json
from pathlib import Path

from benchmark_leakage_preflight import load_separated_suite, validate_mutation_pairs, validate_request_boundary, validate_variant_inventory
from benchmark_leakage_runner import run_ablation_conditions, run_conditions
from local import generate
from run_benchmark_leakage_v2 import EXPECTED_IDENTITIES, _sha256, authenticate_model, _generate, ROOT, TASKS_PATH, ORACLE_PATH, REPS


MODEL = "gemma3:4b"
PLAN_PATH = ROOT / "BENCHMARK_LEAKAGE_V2_4B_CONTINUATION_PLAN.md"
OUTPUT_PATH = ROOT / "benchmark_leakage_v2_4b_runs.jsonl"
WARMUP_PATH = ROOT / "benchmark_leakage_v2_4b_warmup.json"


def warmup(config):
    if WARMUP_PATH.exists():
        raise FileExistsError("warm-up record already exists")
    result = generate("Reply with the single word READY.", {**config, "model": MODEL})
    record = {"model": MODEL, "success": result.success, "error": result.error, "total_ms": result.total_ms, "raw_output_sha256": hashlib.sha256(result.text.encode()).hexdigest()}
    WARMUP_PATH.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    return record


def run(config=None):
    config = dict(config or json.loads((ROOT / "config.json").read_text())["local"])
    tasks, oracle = load_separated_suite(TASKS_PATH, ORACLE_PATH)
    validate_variant_inventory(tasks); validate_mutation_pairs(tasks); validate_request_boundary(tasks, oracle)
    if OUTPUT_PATH.exists() or Path(str(OUTPUT_PATH) + ".partial").exists():
        raise FileExistsError("4B output already exists")
    if config.get("temperature") != 0 or config.get("max_tokens") != 256:
        raise ValueError("execution config mismatch")
    if WARMUP_PATH.exists():
        identity = authenticate_model(MODEL, config["base_url"])
    else:
        try:
            identity = authenticate_model(MODEL, config["base_url"])
        except RuntimeError as exc:
            if "not resident" not in str(exc):
                raise
            warmup(config)
            identity = authenticate_model(MODEL, config["base_url"])
    if not identity:
        raise RuntimeError("4B identity unavailable")
    metadata = {"config_sha256": _sha256(ROOT / "config.json"), "plan_sha256": _sha256(PLAN_PATH), "implementation_revision": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "requested_model": MODEL, "model_digest": identity["digest"], "model_identity": identity}
    generator = lambda prompt, requested_model: _generate(prompt, {**config, "model": MODEL})
    rows = run_conditions(tasks, oracle, generator, MODEL, reps=REPS, run_metadata=metadata)
    rows.extend(run_ablation_conditions(tasks, oracle, generator, MODEL, reps=REPS, run_metadata=metadata))
    if len(rows) != 180:
        raise RuntimeError(f"unexpected 4B row count: {len(rows)}")
    partial = Path(str(OUTPUT_PATH) + ".partial")
    partial.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    partial.replace(OUTPUT_PATH)
    return len(rows)


if __name__ == "__main__":
    print(json.dumps({"rows": run()}, sort_keys=True))
