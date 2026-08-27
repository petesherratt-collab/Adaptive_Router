"""Run the frozen local-model scaling comparison safely."""

import argparse
import json
from pathlib import Path

import requests

from local import LocalResult, generate as generate_local, model_residency
import run_oos_validation as oos


ROOT = Path(__file__).resolve().parent
COMPARISON_ID = "local_model_scaling_v1"

MODEL_SPECS = {
    "gemma3:1b": {
        "name": "gemma3:1b",
        "digest": (
            "8648f39daa8fbf5b18c7b4e6a8fb4990"
            "c692751d49917417b8842ca5758e7ffc"
        ),
        "parameter_size": "999.89M",
        "quantization_level": "Q4_K_M",
        "format": "gguf",
        "family": "gemma3",
        "package_size_bytes": 815319791,
        "output": ROOT / "benchmark_runs_scaling_gemma3_1b_v1.jsonl",
        "summary": ROOT / "benchmark_summary_scaling_gemma3_1b_v1.json",
    },
    "gemma3:4b": {
        "name": "gemma3:4b",
        "digest": (
            "a2af6cc3eb7fa8be8504abaf9b04e88f"
            "17a119ec3f04a3addf55f92841195f5a"
        ),
        "parameter_size": "4.3B",
        "quantization_level": "Q4_K_M",
        "format": "gguf",
        "family": "gemma3",
        "package_size_bytes": 3338801804,
        "output": ROOT / "benchmark_runs_scaling_gemma3_4b_v1.jsonl",
        "summary": ROOT / "benchmark_summary_scaling_gemma3_4b_v1.json",
    },
}

MODEL_ORDER = ("gemma3:1b", "gemma3:4b")


def public_identity(spec):
    return {
        "name": spec["name"],
        "digest": spec["digest"],
        "parameter_size": spec["parameter_size"],
        "quantization_level": spec["quantization_level"],
        "format": spec["format"],
        "family": spec["family"],
        "package_size_bytes": spec["package_size_bytes"],
    }


def fetch_installed_identity(model, base_url, session=requests):
    response = session.get(
        base_url.rstrip("/") + "/api/tags",
        timeout=5,
    )
    response.raise_for_status()

    for item in response.json().get("models", []):
        if model not in (item.get("name"), item.get("model")):
            continue

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


def verify_installed_identity(actual, spec):
    expected = public_identity(spec)
    if actual != expected:
        raise ValueError(
            "installed model identity mismatch:\n"
            f"expected={json.dumps(expected, sort_keys=True)}\n"
            f"actual={json.dumps(actual, sort_keys=True)}"
        )


def load_existing(path, tasks, spec, revision):
    records = oos.load_existing(
        path,
        tasks,
        "ollama",
        spec["name"],
        revision,
    )
    expected_identity = public_identity(spec)

    for record in records:
        if record.get("comparison_id") != COMPARISON_ID:
            raise ValueError(
                "existing observation uses wrong comparison_id"
            )
        if record.get("model_identity") != expected_identity:
            raise ValueError(
                "existing observation uses wrong model identity"
            )

    return records


def residency_buckets(records):
    resident = []
    nonresident = []
    unknown = []

    for record in records:
        state = (record.get("model_residency") or {}).get("resident")
        if state is True:
            resident.append(record)
        elif state is False:
            nonresident.append(record)
        else:
            unknown.append(record)

    return resident, nonresident, unknown


def make_summary(records, spec):
    records = list(records)
    summary = oos.make_summary(records, "ollama", spec["name"])
    resident, nonresident, unknown = residency_buckets(records)

    summary.update({
        "comparison_id": COMPARISON_ID,
        "model_identity": public_identity(spec),
        "resident_observation_count": len(resident),
        "nonresident_observation_count": len(nonresident),
        "unknown_residency_observation_count": len(unknown),
        "resident_median_ttft_ms": oos.median_available(
            resident, "ttft_ms"
        ),
        "resident_median_total_ms": oos.median_available(
            resident, "total_ms"
        ),
        "nonresident_median_ttft_ms": oos.median_available(
            nonresident, "ttft_ms"
        ),
        "nonresident_median_total_ms": oos.median_available(
            nonresident, "total_ms"
        ),
        "error_count": sum(
            not bool(record.get("success")) for record in records
        ),
        "resident_sizes_bytes": sorted({
            value
            for record in records
            if isinstance(
                value := (
                    record.get("model_residency") or {}
                ).get("size_bytes"),
                int,
            )
        }),
    })
    return summary


def verify_existing_summary(path, expected):
    path = Path(path)
    if not path.exists():
        raise RuntimeError(f"required summary does not exist: {path}")

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("existing summary is not valid JSON") from exc

    if existing != expected:
        raise ValueError("existing summary does not match evidence")

    return existing


def finish_summary(records, path, spec):
    path = Path(path)

    if len(records) != oos.OBSERVATION_COUNT:
        raise RuntimeError(
            f"incomplete run: expected {oos.OBSERVATION_COUNT}, "
            f"found {len(records)}"
        )

    expected = make_summary(records, spec)

    if path.exists():
        verify_existing_summary(path, expected)
        print(f"Verified existing summary; left untouched: {path}")
        return expected

    path.write_text(
        json.dumps(
            expected,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return expected


def require_completed_1b(tasks, revision):
    spec = MODEL_SPECS["gemma3:1b"]
    records = load_existing(
        spec["output"],
        tasks,
        spec,
        revision,
    )

    if len(records) != oos.OBSERVATION_COUNT:
        raise RuntimeError(
            "the complete 1B run is required before the 4B run"
        )

    expected = make_summary(records, spec)
    verify_existing_summary(spec["summary"], expected)


def run_model(
    tasks,
    spec,
    model_config,
    generate_fn=generate_local,
    residency_fn=model_residency,
    identity_fn=fetch_installed_identity,
):
    revision = oos.code_revision()
    if not revision:
        raise RuntimeError("unable to identify Git revision")

    if model_config.get("model") != spec["name"]:
        raise ValueError("model configuration differs from frozen model")

    if spec["name"] == "gemma3:4b":
        require_completed_1b(tasks, revision)

    actual_identity = identity_fn(
        spec["name"],
        model_config["base_url"],
    )
    verify_installed_identity(actual_identity, spec)

    output_path = spec["output"]
    summary_path = spec["summary"]
    records = load_existing(
        output_path,
        tasks,
        spec,
        revision,
    )
    completed = {
        (record["task_id"], record["rep"])
        for record in records
    }

    if summary_path.exists() and len(records) != oos.OBSERVATION_COUNT:
        raise RuntimeError("summary exists for an incomplete run")

    with output_path.open("a", encoding="utf-8") as handle:
        for task in tasks:
            for rep in range(1, oos.REPS + 1):
                key = (task["task_id"], rep)
                if key in completed:
                    continue

                try:
                    residency = residency_fn(model_config)
                except Exception:
                    residency = {
                        "resident": None,
                        "size_bytes": None,
                    }

                try:
                    result = generate_fn(task["prompt"], model_config)
                except Exception as exc:
                    result = LocalResult(
                        False,
                        error=type(exc).__name__,
                    )

                raw_output = (
                    result.text
                    if isinstance(result.text, str)
                    else ""
                )
                normalized, correct, validator = oos.evaluate_oracle(
                    task,
                    raw_output,
                )

                record = {
                    "comparison_id": COMPARISON_ID,
                    "task_id": task["task_id"],
                    "rep": rep,
                    "task_class": task["task_class"],
                    "capability_family": task["capability_family"],
                    "provider": "ollama",
                    "requested_model": spec["name"],
                    "returned_model": spec["name"],
                    "model_identity": public_identity(spec),
                    "benchmark_sha256": oos.BENCHMARK_SHA256,
                    "code_revision": revision,
                    "raw_output": raw_output,
                    "normalized_output": normalized,
                    "oracle_correct": correct,
                    "validator": validator,
                    "validator_status": validator["status"],
                    "ttft_ms": result.ttft_ms,
                    "total_ms": result.total_ms,
                    "tokens_per_second": result.tokens_per_second,
                    "model_residency": residency,
                    "success": result.success,
                    "error": result.error,
                }
                oos.append_record(handle, record)
                records.append(record)
                completed.add(key)

                print(
                    f"{spec['name']} {len(completed):3}/"
                    f"{oos.OBSERVATION_COUNT} "
                    f"{task['task_id']} rep={rep} "
                    f"resident={residency.get('resident')} "
                    f"oracle={validator['status']}",
                    flush=True,
                )

    return finish_summary(records, summary_path, spec)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        required=True,
        choices=MODEL_ORDER,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="execute or safely resume the frozen model run",
    )
    args = parser.parse_args(argv)

    document = oos.load_suite()
    tasks = document["tasks"]
    spec = MODEL_SPECS[args.model]

    print(f"Comparison: {COMPARISON_ID}")
    print(f"Suite: {oos.SUITE_ID}")
    print(f"Benchmark SHA-256: {oos.BENCHMARK_SHA256}")
    print(f"Model: {spec['name']}")
    print(f"Digest: {spec['digest']}")
    print(f"Tasks: {len(tasks)}")
    print(f"Repetitions: {oos.REPS}")
    print(f"Observations: {oos.OBSERVATION_COUNT}")
    print(f"Output: {spec['output']}")
    print(f"Summary: {spec['summary']}")

    if not args.execute:
        print("Dry run only; no model calls were made.")
        return

    config = json.loads(
        (ROOT / "config.json").read_text(encoding="utf-8")
    )
    model_config = dict(config["local"])
    model_config["model"] = spec["name"]

    summary = run_model(tasks, spec, model_config)
    print(
        f"Passes: {summary['pass_count']}/"
        f"{summary['observation_count']}"
    )
    print(f"Pass rate: {summary['pass_rate']:.3f}")
    print(f"Summary: {spec['summary']}")


if __name__ == "__main__":
    main()
