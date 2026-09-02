"""Run the frozen runtime v0.2 prospective evaluation or its no-model dry run."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile

import requests
from dotenv import load_dotenv

import local
from local import LocalResult
import remote
from remote import RemoteResult
from probe import run_probe
from router import REMOTE_CONTRACT_FAILED, Router
from runtime_contracts import RuntimeRequest, validate_runtime_output
import runtime_v0_2_prospective_v1 as pv
from telemetry import collect_system_metrics


def fetch_installed_model_metadata(model, base_url, session=requests):
    """Read installed Ollama metadata without generation or model mutation."""
    response = session.get(base_url.rstrip("/") + "/api/tags", timeout=5)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("models"), list):
        raise pv.FrozenDesignError("INVALID_OLLAMA_TAGS_RESPONSE")
    for item in body["models"]:
        if model in (item.get("name"), item.get("model")):
            details = item.get("details") or {}
            return {
                "name": item.get("name") or item.get("model"),
                "digest": item.get("digest"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
                "format": details.get("format"),
                "package_size_bytes": item.get("size"),
            }
    raise pv.FrozenDesignError("REQUIRED_LOCAL_MODEL_NOT_INSTALLED")


def _config(root=pv.ROOT):
    return pv.strict_json_loads(
        (Path(root) / pv.CONFIG_NAME).read_text(encoding="utf-8")
    )


class CapturingProviders:
    def __init__(self, local_fn, remote_fn, budget):
        self.local_fn = local_fn
        self.remote_fn = remote_fn
        self.budget = budget
        self.local_results = []
        self.remote_results = []

    def local(self, prompt, config):
        self.budget.before_local()
        result = self.local_fn(prompt, config)
        self.budget.after_local()
        self.local_results.append(result)
        return result

    def remote(self, prompt, config, api_key):
        self.budget.before_remote()
        result = self.remote_fn(prompt, config, api_key)
        self.budget.after_remote(result)
        self.remote_results.append(result)
        return result


def _new_telemetry_record(path, offset):
    with Path(path).open(encoding="utf-8") as handle:
        handle.seek(offset)
        lines = handle.readlines()
        new_offset = handle.tell()
    if len(lines) != 1 or not lines[0].endswith("\n"):
        raise pv.FrozenDesignError("ROUTER_TELEMETRY_CARDINALITY")
    record = pv.strict_json_loads(lines[0])
    if not isinstance(record, dict) or not isinstance(record.get("request_id"), str):
        raise pv.FrozenDesignError("INVALID_ROUTER_TELEMETRY")
    return record, new_offset


def _contract_result(task, raw):
    contract = task["runtime_request"]["contract"]
    if contract["contract_type"] == "deterministic_executor":
        return {"name": "deterministic_executor_v1", "status": "PASS"}
    result = validate_runtime_output(contract, raw or "")
    return asdict(result)


def _observation(
    task,
    repetition,
    revision,
    identity,
    result,
    local_result,
    remote_result,
    telemetry,
    budget,
):
    final_oracle = pv.oracle(task, result["text"])
    local_raw = (
        local_result.text
        if local_result is not None and local_result.success
        else None
    )
    remote_raw = (
        remote_result.text
        if remote_result is not None and remote_result.success
        else None
    )
    local_oracle = pv.oracle(task, local_raw)
    remote_oracle = pv.oracle(task, remote_raw)
    returned = bool(result["text"])
    return {
        "schema_version": pv.SCHEMA_VERSION,
        "suite_id": pv.SUITE_ID,
        "plan_sha256": pv.PLAN_SHA256,
        "benchmark_sha256": pv.BENCHMARK_SHA256,
        "config_sha256": pv.CONFIG_SHA256,
        "implementation_revision": revision,
        "model_identity": dict(identity),
        "task_id": task["task_id"],
        "repetition": repetition,
        "cohort": task["cohort"],
        "task_class": task["runtime_request"]["task_class"],
        "contract_type": task["runtime_request"]["contract"]["contract_type"],
        "actual_route": result["route"],
        "actual_reason": result["reason"],
        "actual_trigger": result.get("trigger"),
        "final_visible_output": result["text"],
        "runtime_correct": final_oracle.correct,
        "runtime_oracle": asdict(final_oracle),
        "accepted_error": returned and not final_oracle.correct,
        "withheld": result["reason"] == REMOTE_CONTRACT_FAILED and not returned,
        "local": pv.result_record(local_result),
        "local_contract": _contract_result(task, local_raw),
        "local_oracle": asdict(local_oracle),
        "remote": pv.result_record(remote_result),
        "remote_contract": _contract_result(task, remote_raw),
        "remote_oracle": asdict(remote_oracle),
        "router_request_id": telemetry["request_id"],
        "router_decision": telemetry.get("decision"),
        "budget_after_observation": budget.snapshot(),
    }


def execute_observations(
    tasks,
    config,
    revision,
    identity,
    output_root,
    local_fn,
    remote_fn,
    metrics_fn,
    probe_fn,
    residency_fn,
    api_key,
):
    output_root = Path(output_root)
    pv.assert_empty_state(output_root)
    paths = pv.output_paths(output_root)
    runs_partial, runs_handle = pv.open_partial(paths["runs"])
    telemetry_partial = Path(str(paths["telemetry"]) + ".partial")
    if telemetry_partial.exists() or paths["telemetry"].exists():
        raise FileExistsError(str(paths["telemetry"]))
    budget = pv.EvidenceBudget()
    capture = CapturingProviders(local_fn, remote_fn, budget)
    router = Router(
        config,
        telemetry_partial,
        capture.local,
        capture.remote,
        metrics_fn,
        probe_fn,
        residency_fn,
        api_key,
    )
    rows = []
    telemetry_offset = 0
    try:
        for task in tasks:
            for repetition in range(1, pv.REPETITIONS + 1):
                local_before = len(capture.local_results)
                remote_before = len(capture.remote_results)
                request_mapping = {
                    key: value
                    for key, value in task["runtime_request"].items()
                }
                request = RuntimeRequest.from_mapping(request_mapping)
                result = router.route_request(request)
                actual_local = capture.local_results[local_before:]
                actual_remote = capture.remote_results[remote_before:]
                telemetry, telemetry_offset = _new_telemetry_record(
                    telemetry_partial, telemetry_offset
                )
                if task["cohort"] == "deterministic":
                    if actual_local or actual_remote:
                        raise pv.FrozenDesignError("DETERMINISTIC_PROVIDER_CALL")
                    local_result = remote_result = None
                else:
                    if len(actual_local) > 1 or len(actual_remote) > 1:
                        raise pv.FrozenDesignError("MULTIPLE_PROVIDER_LOGICAL_CALLS")
                    if not actual_local:
                        actual_local = [
                            capture.local(request.prompt, config["local"])
                        ]
                    if not actual_remote:
                        actual_remote = [
                            capture.remote(
                                request.prompt, config["remote"], api_key
                            )
                        ]
                    if len(actual_local) != 1 or len(actual_remote) != 1:
                        raise pv.FrozenDesignError("PROVIDER_ARM_CARDINALITY")
                    local_result, remote_result = actual_local[0], actual_remote[0]
                row = _observation(
                    task,
                    repetition,
                    revision,
                    identity,
                    result,
                    local_result,
                    remote_result,
                    telemetry,
                    budget,
                )
                rows.append(row)
                runs_handle.write(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                )
                runs_handle.flush()
                os.fsync(runs_handle.fileno())
        pv.validate_rows(rows, tasks, revision)
        if budget.local_logical_calls != pv.PROVIDER_OBSERVATION_COUNT:
            raise pv.FrozenDesignError("FINAL_LOCAL_CALL_COUNT")
        if budget.remote_logical_calls != pv.PROVIDER_OBSERVATION_COUNT:
            raise pv.FrozenDesignError("FINAL_REMOTE_CALL_COUNT")
        runs_handle.flush()
        os.fsync(runs_handle.fileno())
    finally:
        runs_handle.close()
    pv.publish_partial(runs_partial, paths["runs"])
    pv.publish_partial(telemetry_partial, paths["telemetry"])
    report = pv.summary(rows, revision, budget)
    report["runs_sha256"] = pv.file_sha256(paths["runs"])
    report["router_telemetry_sha256"] = pv.file_sha256(paths["telemetry"])
    pv.atomic_write_json(paths["summary"], report)
    return report


def _synthetic_text(task):
    expected = task["oracle"]["expected"]
    if task["oracle"]["kind"] == "json_object":
        return json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
    return expected


def dry_run():
    import analyze_runtime_v0_2_prospective_v1 as analyzer

    _, tasks, _ = pv.load_frozen_inputs()
    config = _config()
    pv.validate_config(config)
    prompt_outputs = {
        task["runtime_request"]["prompt"]: _synthetic_text(task)
        for task in tasks
    }
    calls = {"local": 0, "remote": 0}

    def local_fake(prompt, provider_config):
        calls["local"] += 1
        return LocalResult(
            True, prompt_outputs[prompt], 1.0, 2.0, 50.0, 100.0, 4, 80_000_000
        )

    def remote_fake(prompt, provider_config, api_key):
        calls["remote"] += 1
        return RemoteResult(
            True,
            prompt_outputs[prompt],
            3.0,
            provider_config["model"],
            status_code=200,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.000001,
            attempt_count=1,
            retry_count=0,
        )

    canonical_before = {
        name: path.exists() for name, path in pv.output_paths().items()
    }
    with tempfile.TemporaryDirectory() as directory:
        temporary_root = Path(directory)
        report = execute_observations(
            tasks,
            config,
            "synthetic-runtime-v0.2-pv1",
            pv.MODEL_SPEC,
            temporary_root,
            local_fake,
            remote_fake,
            lambda: {
                "available_ram_mb": 5000,
                "swap_used_mb": 0,
                "cpu_percent": 1,
                "load_average": [0, 0, 0],
                "ram_percent": 10,
                "swap_percent": 0,
                "swap_activity_sample_seconds": 0.1,
                "swap_in_bytes": 0,
                "swap_in_pages": 0,
                "swap_out_bytes": 0,
                "swap_out_pages": 0,
                "timestamp": "synthetic",
            },
            lambda iterations: 0.0,
            lambda provider_config: {"resident": True, "size_bytes": 291554930},
            "synthetic-key",
        )
        analysis = analyzer.write_analysis(temporary_root)
        if not all(
            pv.output_paths(temporary_root)[name].exists()
            for name in ("analysis_json", "analysis_csv")
        ):
            raise pv.StateError("DRY_RUN_ANALYSIS_OUTPUT_MISSING")
    canonical_after = {
        name: path.exists() for name, path in pv.output_paths().items()
    }
    if canonical_before != canonical_after:
        raise pv.StateError("DRY_RUN_CHANGED_REPOSITORY_OUTPUT_STATE")
    if calls != {"local": 90, "remote": 90}:
        raise pv.FrozenDesignError("DRY_RUN_PROVIDER_CALL_COUNT")
    return {
        "status": "PASS",
        "provider_network_requests": 0,
        "repository_outputs_created": 0,
        "runtime_observations": report["observation_count"],
        "synthetic_local_calls": calls["local"],
        "synthetic_remote_calls": calls["remote"],
        "runtime_correct_count": report["runtime_correct_count"],
        "bootstrap_draws": analysis["generative"]["bootstrap"]["draw_count"],
    }


def preflight_execution():
    load_dotenv(pv.ROOT / ".env")
    _, tasks, _ = pv.load_frozen_inputs()
    config = _config()
    pv.validate_config(config)
    pv.assert_empty_state()
    revision = pv.implementation_revision()
    if not os.getenv("OPENROUTER_API_KEY"):
        raise pv.FrozenDesignError("OPENROUTER_KEY_MISSING")
    identity = pv.verify_model_identity(
        fetch_installed_model_metadata(
            config["local"]["model"], config["local"]["base_url"]
        )
    )
    return tasks, config, revision, identity


def preflight_report():
    tasks, config, revision, identity = preflight_execution()
    return {
        "status": "PASS",
        "suite_id": pv.SUITE_ID,
        "implementation_revision": revision,
        "plan_sha256": pv.PLAN_SHA256,
        "benchmark_sha256": pv.BENCHMARK_SHA256,
        "config_sha256": pv.CONFIG_SHA256,
        "task_count": len(tasks),
        "runtime_observations": len(tasks) * pv.REPETITIONS,
        "local_model_identity": identity,
        "remote_model": config["remote"]["model"],
        "output_state": "EMPTY",
        "provider_generation_requests": 0,
    }


def execute():
    tasks, config, revision, identity = preflight_execution()
    return execute_observations(
        tasks,
        config,
        revision,
        identity,
        pv.ROOT,
        local.generate,
        remote.generate,
        collect_system_metrics,
        run_probe,
        local.model_residency,
        os.environ["OPENROUTER_API_KEY"],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        result = dry_run()
    elif args.preflight:
        result = preflight_report()
    else:
        result = execute()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
