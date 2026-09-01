"""Sequential V2 runner with monotonic preflight and no-model dry-run."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import tempfile

import requests

from local import LocalResult
import prospective_contract_validation_v2 as pcv


TIMEOUT_SECONDS = 45


def fetch_installed_model_metadata(model: str, base_url: str, session=requests):
    """Read-only installed-model metadata; never pulls, updates, or generates."""
    response = session.get(base_url.rstrip("/") + "/api/tags", timeout=5)
    response.raise_for_status()
    for item in response.json().get("models", []):
        if model in (item.get("name"), item.get("model")):
            details = item.get("details") or {}
            return {"name": item.get("name") or item.get("model"), "digest": item.get("digest"), "parameter_size": details.get("parameter_size"), "quantization_level": details.get("quantization_level"), "format": details.get("format"), "family": details.get("family"), "package_size_bytes": item.get("size")}
    raise ValueError(f"required model is not installed: {model}")


def fetch_residency(model: str, base_url: str, session=requests):
    response = session.get(base_url.rstrip("/") + "/api/ps", timeout=2)
    response.raise_for_status()
    for item in response.json().get("models", []):
        if model in (item.get("name"), item.get("model")):
            return {"resident": True, "size_bytes": item.get("size")}
    return {"resident": False, "size_bytes": None}


def generate_one(prompt: str, model: str, base_url: str, timeout_seconds=TIMEOUT_SECONDS, session=requests):
    started = time.perf_counter(); first = None; chunks = []; final = {}; returned_model = None
    try:
        response = session.post(base_url.rstrip("/") + "/api/generate", json={"model":model,"prompt":prompt,"stream":True,"options":{"temperature":pcv.TEMPERATURE,"num_predict":pcv.MAX_OUTPUT_TOKENS},"keep_alive":-1}, timeout=timeout_seconds, stream=True)
        response.raise_for_status()
        for line in response.iter_lines():
            if not line: continue
            item = json.loads(line)
            response_model = item.get("model")
            if not isinstance(response_model, str) or not response_model:
                return LocalResult(False, total_ms=(time.perf_counter()-started)*1000, error="RETURNED_MODEL_IDENTITY_MISSING"), None
            if response_model != model:
                return LocalResult(False, total_ms=(time.perf_counter()-started)*1000, error="RETURNED_MODEL_IDENTITY_MISMATCH"), response_model
            returned_model = response_model
            text = item.get("response", "")
            if text and first is None: first = time.perf_counter()
            chunks.append(text)
            if item.get("done"): final = item
        total_ms=(time.perf_counter()-started)*1000
        if returned_model is None: return LocalResult(False, total_ms=total_ms, error="RETURNED_MODEL_IDENTITY_MISSING"), None
        count, duration = final.get("eval_count"), final.get("eval_duration")
        rate = count/(duration/1e9) if count and duration else None
        return LocalResult(True, "".join(chunks), (first-started)*1000 if first else None, total_ms, rate, error=None), returned_model
    except requests.Timeout:
        return LocalResult(False, total_ms=(time.perf_counter()-started)*1000, error="LOCAL_TIMEOUT"), None
    except Exception as exc:
        return LocalResult(False, total_ms=(time.perf_counter()-started)*1000, error=type(exc).__name__), None


def _load_config():
    config = json.loads((pcv.ROOT / "config.json").read_text(encoding="utf-8"))
    local = dict(config["local"]); local.setdefault("timeout_seconds", TIMEOUT_SECONDS)
    return local


def preflight():
    suite, inventory, contracts = pcv.load_frozen_inputs()
    revision = pcv.implementation_revision()
    if not revision: raise pcv.FrozenDesignError("empty implementation revision")
    return suite, inventory, contracts, revision


def _summary(model, rows, prior_hashes):
    summary = {"schema_version":pcv.SCHEMA_VERSION,"suite_id":pcv.SUITE_ID,"model":model,"model_identity":pcv.public_identity(model),"implementation_revision":rows[0]["implementation_revision"],"plan_sha256":pcv.PLAN_SHA256,"benchmark_sha256":pcv.SUITE_SHA256,"contracts_sha256":pcv.CONTRACTS_SHA256,"observation_count":len(rows),"task_success_count":sum(row["task_success"] for row in rows),"oracle_correct_count":sum(row["oracle_correct"] for row in rows),"prior_stratum_sha256":dict(prior_hashes)}
    return summary


def run_stratum(model: str, inventory, contracts, revision, config=None, generate_fn=generate_one, metadata_fn=fetch_installed_model_metadata, residency_fn=fetch_residency):
    if model not in pcv.MODEL_ORDER: raise ValueError("unknown model stratum")
    if config is None:
        config = dict(_load_config()); config["model"] = model
    else:
        config = dict(config)
    if config.get("model") != model: raise ValueError("config model differs from stratum")
    pre = pcv.preflight_stratum(model, inventory, pcv.ROOT, revision)
    identity = pcv.verify_model_identity(metadata_fn(model, config["base_url"]), model)
    paths = pcv.v2_paths(); partial, handle = pcv._open_partial(paths["evidence"][model]); rows=[]
    try:
        for task in inventory.values():
            contract = contracts[task["task_id"]]
            for rep in range(1, pcv.REPETITIONS+1):
                try: residency = residency_fn(model, config["base_url"])
                except Exception: residency = {"resident":None,"size_bytes":None}
                result, returned_model = generate_fn(task["prompt"], model, config["base_url"], config.get("timeout_seconds", TIMEOUT_SECONDS))
                if returned_model is not None and returned_model != model: raise pcv.FrozenDesignError(f"returned model mismatch: {returned_model!r}")
                row = pcv.make_result_row({**task,"_rep":rep}, contract, result, model, returned_model, identity, revision, residency, pre["prior_stratum_sha256"])
                rows.append(row); handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"); handle.flush()
        pcv.validate_result_rows(rows, inventory, model, revision)
        handle.flush(); pcv.os.fsync(handle.fileno())
    finally:
        handle.close()
    pcv.publish_partial(partial, paths["evidence"][model])
    evidence_hash = pcv.file_sha256(paths["evidence"][model])
    summary = _summary(model, rows, pre["prior_stratum_sha256"]); summary["evidence_sha256"] = evidence_hash; summary["summary_payload_sha256"] = pcv._summary_payload_hash(summary)
    pcv.atomic_write_json(paths["summaries"][model], summary)
    pcv.authenticate_stratum(model, inventory, pcv.ROOT, revision)
    return rows


def _synthetic_rows(inventory, model, revision, prior_hashes=None):
    rows=[]; identity=pcv.public_identity(model)
    for task in inventory.values():
        for rep in range(1, pcv.REPETITIONS+1):
            result=LocalResult(True, "synthetic", 1.0, 2.0, 10.0)
            rows.append(pcv.make_result_row({**task,"_rep":rep}, {"task_id":task["task_id"],"cohort":task["cohort"],"contract_type":task["contract_type"], **({"exact_keys":[],"explicit_types":{}} if task["cohort"]=="structural_schema" else {})}, result, model, model, identity, revision, {"resident":True,"size_bytes":1}, prior_hashes))
    return rows


def _write_synthetic_stratum(root, model, inventory, revision, prior_hashes=None):
    paths=pcv.v2_paths(root); rows=[]
    for task in inventory.values():
        for rep in range(1, pcv.REPETITIONS+1):
            task_row={**task,"_rep":rep}; contract={"task_id":task["task_id"],"cohort":task["cohort"],"contract_type":task["contract_type"]}
            if task["contract_type"] in ("structured_json","json_format"): contract.update({"exact_keys":list(task["expected"]),"explicit_types":{k:pcv._json_type(v) for k,v in task["expected"].items()}})
            elif task["contract_type"]=="bullet_format": contract.update({"line_count":len(task["expected"].split("\n")),"marker":task["expected"][0],"separator":" ","fence_rule":"forbidden"})
            elif task["contract_type"]=="label_format": contract.update({"line_count":len(task["expected"].split("\n")),"separator":" = ","separator_rule":"exactly_once_per_line","fence_rule":"forbidden"})
            elif task["contract_type"]=="classification_labels": contract.update({"permitted_labels":["positive","negative","neutral"] if task["expected"] in ("positive","negative","neutral") else ["high","medium","low"]})
            else: contract.update({"role":"executable_task","source_literal":"x","operation":"rotate_left_one"})
            # State tests need row shape/provenance, not semantic contract execution.
            row={"schema_version":pcv.SCHEMA_VERSION,"suite_id":pcv.SUITE_ID,"plan_sha256":pcv.PLAN_SHA256,"benchmark_sha256":pcv.SUITE_SHA256,"contracts_sha256":pcv.CONTRACTS_SHA256,"implementation_revision":revision,"requested_model":model,"returned_model":model,"model_identity":pcv.public_identity(model),"prior_stratum_sha256":dict(prior_hashes or {}),"task_id":task["task_id"],"rep":rep,"task_class":task["task_class"],"cohort":task["cohort"],"contract_type":task["contract_type"],"raw_output":"synthetic","normalized_output":"synthetic","oracle_correct":True,"executor_accept":True,"contract_accept":True,"baseline_gate_survived":True,"counterfactual_gate_survived":True,"success":True,"task_success":True,"ttft_ms":1.0,"total_ms":2.0,"tokens_per_second":10.0,"model_residency":{"resident":True},"error":None}
            rows.append(row)
    pcv.validate_result_rows(rows, inventory, model, revision)
    pcv.atomic_write_text(paths["evidence"][model], "".join(json.dumps(row,separators=(",", ":"))+"\n" for row in rows))
    summary=_summary(model,rows,prior_hashes or {}); summary["evidence_sha256"]=pcv.file_sha256(paths["evidence"][model]); summary["summary_payload_sha256"]=pcv._summary_payload_hash(summary); pcv.atomic_write_json(paths["summaries"][model],summary)
    return rows


def _expect_state_failure(callback):
    try:
        callback()
    except (pcv.StateMachineError, pcv.FrozenDesignError):
        return
    raise AssertionError("illegal synthetic filesystem state was accepted")


def _exercise_state_machine(inventory, revision):
    """Exercise every V2 state transition using disposable synthetic files."""
    with tempfile.TemporaryDirectory(prefix="pcv2-state-dry-") as directory:
        root = Path(directory)
        assert pcv.detect_state(root) == "EMPTY"
        pcv.preflight_stratum("gemma3:270m", inventory, root, revision)
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:1b", inventory, root, revision))
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:4b", inventory, root, revision))
        _expect_state_failure(lambda: pcv.preflight_analysis(inventory, root, revision))

    with tempfile.TemporaryDirectory(prefix="pcv2-state-dry-") as directory:
        root = Path(directory)
        _write_synthetic_stratum(root, "gemma3:270m", inventory, revision)
        before = pcv.file_sha256(pcv.v2_paths(root)["evidence"]["gemma3:270m"])
        pre = pcv.preflight_stratum("gemma3:1b", inventory, root, revision)
        assert pre["state"] == "270M_COMPLETE"
        assert pcv.file_sha256(pcv.v2_paths(root)["evidence"]["gemma3:270m"]) == before
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:270m", inventory, root, revision))
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:4b", inventory, root, revision))

        paths = pcv.v2_paths(root)
        pcv.atomic_write_text(paths["evidence"]["gemma3:4b"], "unexpected\n")
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:1b", inventory, root, revision))

    for partial_model in ("gemma3:270m", "gemma3:1b", "gemma3:4b"):
        with tempfile.TemporaryDirectory(prefix="pcv2-state-dry-") as directory:
            root = Path(directory); paths = pcv.v2_paths(root)
            Path(str(paths["evidence"][partial_model]) + ".partial").write_text("quarantined\n", encoding="utf-8")
            _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:270m", inventory, root, revision))

    with tempfile.TemporaryDirectory(prefix="pcv2-state-dry-") as directory:
        root = Path(directory)
        _write_synthetic_stratum(root, "gemma3:270m", inventory, revision)
        prior = pcv.preflight_stratum("gemma3:1b", inventory, root, revision)["prior_stratum_sha256"]
        _write_synthetic_stratum(root, "gemma3:1b", inventory, revision, prior)
        assert pcv.preflight_stratum("gemma3:4b", inventory, root, revision)["state"] == "1B_COMPLETE"
        _expect_state_failure(lambda: pcv.preflight_analysis(inventory, root, revision))
        prior_evidence = pcv.v2_paths(root)["evidence"]["gemma3:270m"]
        with prior_evidence.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:4b", inventory, root, revision))

    with tempfile.TemporaryDirectory(prefix="pcv2-state-dry-") as directory:
        root = Path(directory)
        _write_synthetic_stratum(root, "gemma3:270m", inventory, revision)
        prior = pcv.preflight_stratum("gemma3:1b", inventory, root, revision)["prior_stratum_sha256"]
        _write_synthetic_stratum(root, "gemma3:1b", inventory, revision, prior)
        prior = pcv.preflight_stratum("gemma3:4b", inventory, root, revision)["prior_stratum_sha256"]
        _write_synthetic_stratum(root, "gemma3:4b", inventory, revision, prior)
        assert pcv.preflight_analysis(inventory, root, revision)["rows"]
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:4b", inventory, root, revision))
        pcv.atomic_write_json(pcv.v2_paths(root)["analysis_json"], {"synthetic": True})
        _expect_state_failure(lambda: pcv.preflight_analysis(inventory, root, revision))

    with tempfile.TemporaryDirectory(prefix="pcv2-state-dry-") as directory:
        root = Path(directory); paths = pcv.v2_paths(root)
        pcv.atomic_write_json(paths["analysis_json"], {"premature": True})
        _expect_state_failure(lambda: pcv.preflight_stratum("gemma3:270m", inventory, root, revision))


def dry_run():
    suite, inventory, contracts, revision = preflight()
    # Exercise isolated contract paths with synthetic content only.
    for task in inventory.values():
        contract=contracts[task["task_id"]]
        if task["contract_type"] in ("structured_json","json_format"):
            raw=json.dumps({key: 0 if contract["explicit_types"][key]=="number" else False if contract["explicit_types"][key]=="boolean" else "synthetic" for key in contract["exact_keys"]})
        elif task["contract_type"]=="classification_labels": raw=contract["permitted_labels"][0]
        elif task["contract_type"]=="deterministic_executor": raw=pcv._operation(contract["source_literal"],contract["operation"]); pcv.execute_deterministic(contract, raw)
        else: raw="\n".join((contract.get("marker","")+contract.get("separator"," ")+"synthetic") for _ in range(contract["line_count"]))
        pcv.contract_validate(contract,raw)
    # This temporary exercise never touches V2 repository output paths.
    _exercise_state_machine(inventory, revision)
    synthetic=[]
    for model in pcv.MODEL_ORDER:
        for task in inventory.values():
            for rep in range(1,pcv.REPETITIONS+1):
                synthetic.append({"schema_version":pcv.SCHEMA_VERSION,"suite_id":pcv.SUITE_ID,"plan_sha256":pcv.PLAN_SHA256,"benchmark_sha256":pcv.SUITE_SHA256,"contracts_sha256":pcv.CONTRACTS_SHA256,"implementation_revision":revision,"requested_model":model,"returned_model":model,"model_identity":pcv.public_identity(model),"prior_stratum_sha256":{},"task_id":task["task_id"],"rep":rep,"task_class":task["task_class"],"cohort":task["cohort"],"contract_type":task["contract_type"],"raw_output":"synthetic","normalized_output":"synthetic","oracle_correct":True,"executor_accept":True,"contract_accept":True,"baseline_gate_survived":True,"counterfactual_gate_survived":True,"success":True,"task_success":True})
    pcv.analyze_rows(synthetic,inventory,contracts,revision)
    return {"status":"PASS","model_generation_requests":0,"canonical_outputs_created":0,"fixture_rows":len(synthetic),"state_machine_exercised":True,"suite_id":suite["suite_id"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--dry-run",action="store_true"); parser.add_argument("--model",choices=pcv.MODEL_ORDER); args=parser.parse_args(argv)
    if args.dry_run: print(json.dumps(dry_run(),sort_keys=True)); return 0
    suite, inventory, contracts, revision = preflight()
    models=(args.model,) if args.model else pcv.MODEL_ORDER
    for model in models: run_stratum(model,inventory,contracts,revision)
    return 0


if __name__ == "__main__": raise SystemExit(main())
