"""Canonical sequential runner and no-model dry-run for Prospective Contract Validation v1."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

from local import LocalResult
import prospective_contract_validation as pcv


TEMPERATURE = 0
MAX_OUTPUT_TOKENS = 256
TIMEOUT_SECONDS = 45


def fetch_installed_model_metadata(model: str, base_url: str, session=requests):
    """Read ``/api/tags`` only; never pulls, updates, or generates."""
    response = session.get(base_url.rstrip("/") + "/api/tags", timeout=5)
    response.raise_for_status()
    for item in response.json().get("models", []):
        if model in (item.get("name"), item.get("model")):
            details = item.get("details") or {}
            return {
                "name": item.get("name") or item.get("model"),
                "digest": item.get("digest"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
                "format": details.get("format"),
                "family": details.get("family"),
                "package_size_bytes": item.get("size"),
            }
    raise ValueError(f"required model is not installed: {model}")


def fetch_residency(model: str, base_url: str, session=requests):
    response = session.get(base_url.rstrip("/") + "/api/ps", timeout=2)
    response.raise_for_status()
    for item in response.json().get("models", []):
        if model in (item.get("name"), item.get("model")):
            return {"resident": True, "size_bytes": item.get("size")}
    return {"resident": False, "size_bytes": None}


def generate_one(prompt: str, model: str, base_url: str, timeout_seconds=TIMEOUT_SECONDS, session=requests):
    started = time.perf_counter()
    first = None
    chunks = []
    final = {}
    returned_model = None
    try:
        response = session.post(
            base_url.rstrip("/") + "/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": TEMPERATURE, "num_predict": MAX_OUTPUT_TOKENS},
                "keep_alive": -1,
            },
            timeout=timeout_seconds,
            stream=True,
        )
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            item = json.loads(line)
            response_model = item.get("model")
            if not isinstance(response_model, str) or not response_model:
                return LocalResult(False, total_ms=(time.perf_counter() - started) * 1000, error="RETURNED_MODEL_IDENTITY_MISSING"), None
            if response_model != model:
                return LocalResult(False, total_ms=(time.perf_counter() - started) * 1000, error="RETURNED_MODEL_IDENTITY_MISMATCH"), response_model
            returned_model = response_model
            text = item.get("response", "")
            if text and first is None:
                first = time.perf_counter()
            chunks.append(text)
            if item.get("done"):
                final = item
        completed = time.perf_counter()
        text = "".join(chunks)
        total_ms = (completed - started) * 1000
        if returned_model is None:
            return LocalResult(False, total_ms=total_ms, error="RETURNED_MODEL_IDENTITY_MISSING"), None
        count = final.get("eval_count")
        duration = final.get("eval_duration")
        rate = count / (duration / 1e9) if count and duration else None
        return LocalResult(
            True,
            text,
            (first - started) * 1000 if first else None,
            total_ms,
            rate,
            error=None,
        ), returned_model or model
    except requests.Timeout:
        return LocalResult(False, total_ms=(time.perf_counter() - started) * 1000, error="LOCAL_TIMEOUT"), None
    except Exception as exc:
        return LocalResult(False, total_ms=(time.perf_counter() - started) * 1000, error=type(exc).__name__), None


def _load_config():
    config = json.loads((pcv.ROOT / "config.json").read_text(encoding="utf-8"))
    local = dict(config["local"])
    local.setdefault("timeout_seconds", TIMEOUT_SECONDS)
    return local


def preflight():
    suite, task_inventory, contracts = pcv.load_frozen_inputs()
    pcv.preflight_output_paths()
    source_hashes = pcv.authenticate_model_identity_sources()
    revision = pcv.implementation_revision()
    if not revision:
        raise RuntimeError("empty implementation revision")
    return suite, task_inventory, contracts, revision, source_hashes


def run_stratum(model: str, task_inventory, contracts, revision, config=None, generate_fn=generate_one, metadata_fn=fetch_installed_model_metadata, residency_fn=fetch_residency):
    if model not in pcv.MODEL_ORDER:
        raise ValueError(f"unknown model stratum: {model}")
    if config is None:
        config = dict(_load_config())
        config["model"] = model
    else:
        config = dict(config)
    if config.get("model") != model:
        raise ValueError(f"config model differs from frozen stratum: {model}")
    source_hashes = pcv.authenticate_model_identity_sources()
    actual = metadata_fn(model, config["base_url"])
    identity = pcv.verify_model_identity(actual, model)
    rows = []
    for task in task_inventory.values():
        contract = contracts[task["task_id"]]
        for rep in range(1, pcv.REPETITIONS + 1):
            task_with_rep = {**task, "_rep": rep}
            try:
                residency = residency_fn(model, config["base_url"])
            except Exception:
                residency = {"resident": None, "size_bytes": None}
            result, returned_model = generate_fn(
                task["prompt"], model, config["base_url"], config.get("timeout_seconds", TIMEOUT_SECONDS)
            )
            if returned_model is not None and returned_model != model:
                raise pcv.FrozenDesignError(f"returned model mismatch: {returned_model!r}")
            row = pcv.make_result_row(
                task_with_rep, contract, result.text if result.success else None,
                result, model, returned_model, identity, revision, residency, source_hashes,
            )
            rows.append(row)
    pcv.validate_result_rows(rows, task_inventory, model)
    return rows


def write_stratum(rows, model, task_inventory):
    path = pcv.EVIDENCE_PATHS[model]
    pcv.validate_result_rows(rows, task_inventory, model)
    content = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    pcv.atomic_write_text(path, content)
    return path


def write_summary(rows, model):
    summary = {
        "schema_version": pcv.SCHEMA_VERSION,
        "suite_id": pcv.SUITE_ID,
        "model": model,
        "model_identity": pcv.public_identity(model),
        "model_identity_source_sha256": dict(rows[0]["model_identity_source_sha256"]),
        "benchmark_sha256": pcv.SUITE_SHA256,
        "contracts_sha256": pcv.CONTRACTS_SHA256,
        "implementation_revision": rows[0]["implementation_revision"],
        "observation_count": len(rows),
        "task_success_count": sum(row["task_success"] for row in rows),
        "oracle_correct_count": sum(row["oracle_correct"] for row in rows),
    }
    pcv.atomic_write_json(pcv.SUMMARY_PATHS[model], summary)
    return summary


def dry_run():
    suite, task_inventory, contracts, revision, source_hashes = preflight()
    synthetic = []
    for model in pcv.MODEL_ORDER:
        identity = pcv.public_identity(model)
        for task in task_inventory.values():
            contract = contracts[task["task_id"]]
            raw = "{}" if task["contract_type"] in ("structured_json", "json_format") else ("positive" if task["contract_type"] == "classification_labels" else ("* x" if task["contract_type"] == "bullet_format" else ("x = y" if task["contract_type"] == "label_format" else pcv._operation(contract["source_literal"], contract["operation"]))))
            result = LocalResult(True, raw, 1.0, 2.0, 10.0)
            synthetic.append(pcv.make_result_row({**task, "_rep": 1}, contract, raw, result, model, model, identity, revision, {"resident": True, "size_bytes": 1}, source_hashes))
    # The dry-run fixture is intentionally one row per task/model; it exercises
    # oracle, contract, gate, row construction, and analyzer invariants without
    # any output path.
    assert len(synthetic) == 120
    for row in synthetic:
        assert isinstance(row["contract_accept"], bool)
    report = pcv.analyze_rows(synthetic, task_inventory, contracts, revision)
    assert report["primary"]["overall"]["observation_count"] == 60
    assert report["label_conformance"]["overall"]["observation_count"] == 30
    assert report["deterministic_executor"]["overall"]["observation_count"] == 30
    return {"status": "PASS", "model_generation_requests": 0, "canonical_outputs_created": 0, "fixture_rows": len(synthetic), "analyzer_exercised": True, "suite_id": suite["suite_id"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", choices=pcv.MODEL_ORDER)
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps(dry_run(), sort_keys=True))
        return 0
    suite, task_inventory, contracts, revision, source_hashes = preflight()
    models = (args.model,) if args.model else pcv.MODEL_ORDER
    for model in models:
        rows = run_stratum(model, task_inventory, contracts, revision)
        write_stratum(rows, model, task_inventory)
        write_summary(rows, model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
