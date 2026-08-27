"""Analyze the frozen local-model scaling comparison deterministically."""

import argparse
import csv
import io
import json
from pathlib import Path

import run_local_model_scaling as scaling
import run_oos_validation as oos
import validators


ROOT = Path(__file__).resolve().parent
ANALYSIS_ID = "local_model_scaling_v1_strict"

PLAN = ROOT / "LOCAL_MODEL_SCALING_V1_PLAN.md"
PLAN_SHA256 = (
    "97359083cc1f4b2352ea383e02076cc8"
    "ba6170336499d745be4f15742bf98363"
)
AMENDMENT = ROOT / "LOCAL_MODEL_SCALING_V1_AMENDMENT_1.md"
AMENDMENT_SHA256 = (
    "f10c2a890a8e543e97bb80f53a8dabc"
    "be3d5633caeafc40fe3cfef8bcbace71f"
)

MAXIMUM_TTFT_MS = 8000
MINIMUM_GENERATION_RATE = 1.5
GATE_REASONS = (
    "GENERATION_FAILED",
    "TTFT_EXCEEDED",
    "GENERATION_TOO_SLOW",
    "VALIDATOR_FAILED",
    "SURVIVED",
)

BASELINE_PATH = ROOT / "benchmark_runs_oos_local_v1.jsonl"
BASELINE_SHA256 = (
    "425fa9328781ff2e53f69ce0a054531e"
    "106be3a6ed1380c148e35ec3d47c8ca0"
)

JSON_OUTPUT = ROOT / "local_model_scaling_v1.json"
CSV_OUTPUT = ROOT / "local_model_scaling_v1.csv"

BASELINE_IDENTITY = {
    "name": "gemma3:270m",
    "digest": (
        "e7d36fb2c3b3293cfe56d55889867a064"
        "b3a2b22e98335f2e6e8a387e081d6be"
    ),
    "parameter_size": "268.10M",
    "quantization_level": "Q8_0",
    "format": "gguf",
    "family": "gemma3",
    "package_size_bytes": 291554930,
}

MODEL_ORDER = ("gemma3:270m", "gemma3:1b", "gemma3:4b")


def load_jsonl(path):
    records = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON on line {line_number}: {path}"
                ) from exc
    return records


def validate_keys(records, tasks):
    expected = oos.expected_keys(tasks)
    keys = [(record.get("task_id"), record.get("rep")) for record in records]
    if len(keys) != oos.OBSERVATION_COUNT:
        raise ValueError(
            f"expected {oos.OBSERVATION_COUNT} observations, found {len(keys)}"
        )
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate observation key")
    if set(keys) != expected:
        raise ValueError("observation key set mismatch")


def load_baseline(tasks, path=BASELINE_PATH):
    path = Path(path)
    if oos.file_sha256(path) != BASELINE_SHA256:
        raise ValueError("frozen 270M evidence SHA-256 mismatch")
    records = load_jsonl(path)
    validate_keys(records, tasks)
    task_by_id = {task["task_id"]: task for task in tasks}
    for record in records:
        task = task_by_id[record["task_id"]]
        if record.get("provider") != "ollama":
            raise ValueError("baseline provider mismatch")
        if record.get("requested_model") != "gemma3:270m":
            raise ValueError("baseline model mismatch")
        if record.get("benchmark_sha256") != oos.BENCHMARK_SHA256:
            raise ValueError("baseline benchmark mismatch")
        if (
            record.get("task_class") != task["task_class"]
            or record.get("capability_family") != task["capability_family"]
        ):
            raise ValueError("baseline task metadata mismatch")
    return records


def load_candidate(tasks, model, revision):
    spec = scaling.MODEL_SPECS[model]
    records = scaling.load_existing(spec["output"], tasks, spec, revision)
    validate_keys(records, tasks)
    expected_summary = scaling.make_summary(records, spec)
    scaling.verify_existing_summary(spec["summary"], expected_summary)
    return records


def bucket(records):
    records = list(records)
    count = len(records)
    passes = sum(bool(record.get("oracle_correct")) for record in records)
    return {
        "observation_count": count,
        "pass_count": passes,
        "pass_rate": passes / count if count else None,
    }


def grouped_metrics(records, field):
    groups = {}
    for record in records:
        groups.setdefault(record[field], []).append(record)
    return {key: bucket(value) for key, value in sorted(groups.items())}


def timing_metrics(records):
    records = list(records)
    return {
        "median_ttft_ms": oos.median_available(records, "ttft_ms"),
        "median_total_ms": oos.median_available(records, "total_ms"),
        "median_tokens_per_second": oos.median_available(
            records, "tokens_per_second"
        ),
    }


def post_generation_gate(record, task):
    """Return the first post-generation outcome in live-router order."""
    if not bool(record.get("success")):
        return "GENERATION_FAILED"
    ttft_ms = record.get("ttft_ms")
    if ttft_ms is not None and ttft_ms > MAXIMUM_TTFT_MS:
        return "TTFT_EXCEEDED"
    tokens_per_second = record.get("tokens_per_second")
    if (
        tokens_per_second is not None
        and tokens_per_second < MINIMUM_GENERATION_RATE
    ):
        return "GENERATION_TOO_SLOW"
    result = validators.validate(
        task["task_class"], task["prompt"], record.get("raw_output", "")
    )
    if result.status == validators.FAIL:
        return "VALIDATOR_FAILED"
    return "SURVIVED"


def gate_metrics(records, tasks):
    records = list(records)
    task_by_id = {task["task_id"]: task for task in tasks}
    reason_counts = {reason: 0 for reason in GATE_REASONS}
    survivor_count = 0
    strict_survivor_passes = 0
    false_accept_count = 0
    rejected_correct_count = 0

    for record in records:
        task_id = record.get("task_id")
        if task_id not in task_by_id:
            raise ValueError(f"unknown task_id in gate replay: {task_id}")
        reason = post_generation_gate(record, task_by_id[task_id])
        reason_counts[reason] += 1
        correct = bool(record.get("oracle_correct"))
        if reason == "SURVIVED":
            survivor_count += 1
            if correct:
                strict_survivor_passes += 1
            else:
                false_accept_count += 1
        elif correct:
            rejected_correct_count += 1

    count = len(records)
    return {
        "observation_count": count,
        "survivor_count": survivor_count,
        "survivor_rate": survivor_count / count if count else None,
        "strict_pass_count_among_survivors": strict_survivor_passes,
        "strict_pass_rate_among_survivors": (
            strict_survivor_passes / survivor_count if survivor_count else None
        ),
        "false_accept_count": false_accept_count,
        "rejected_correct_count": rejected_correct_count,
        "missing_ttft_count": sum(
            record.get("ttft_ms") is None for record in records
        ),
        "missing_throughput_count": sum(
            record.get("tokens_per_second") is None for record in records
        ),
        "first_outcome_counts": reason_counts,
    }


def model_metrics(records, identity, tasks=None):
    records = list(records)
    resident, nonresident, unknown = scaling.residency_buckets(records)
    result = {
        **bucket(records),
        "model_identity": identity,
        "successful_response_count": sum(
            bool(record.get("success")) for record in records
        ),
        "empty_output_count": sum(
            record.get("raw_output") == "" for record in records
        ),
        "error_count": sum(
            not bool(record.get("success")) for record in records
        ),
        "timing": timing_metrics(records),
        "residency": {
            "resident_observation_count": len(resident),
            "nonresident_observation_count": len(nonresident),
            "unknown_observation_count": len(unknown),
            "resident_timing": timing_metrics(resident),
            "nonresident_timing": timing_metrics(nonresident),
        },
        "per_family": grouped_metrics(records, "capability_family"),
        "per_task": grouped_metrics(records, "task_id"),
    }
    # Optional only to preserve the small unit-test helper API. Production
    # analysis always supplies the frozen task suite.
    if tasks is not None:
        result["post_generation_gate_simulation"] = {
            "maximum_ttft_ms": MAXIMUM_TTFT_MS,
            "minimum_generation_rate": MINIMUM_GENERATION_RATE,
            "overall": gate_metrics(records, tasks),
            "residency": {
                "resident": gate_metrics(resident, tasks),
                "nonresident": gate_metrics(nonresident, tasks),
                "unknown": gate_metrics(unknown, tasks),
            },
        }
    return result


def paired_comparison(baseline, candidate):
    baseline_by_key = {
        (record["task_id"], record["rep"]): record for record in baseline
    }
    candidate_by_key = {
        (record["task_id"], record["rep"]): record for record in candidate
    }
    if set(baseline_by_key) != set(candidate_by_key):
        raise ValueError("paired key set mismatch")
    gained = lost = both_pass = both_fail = 0
    for key in sorted(baseline_by_key):
        baseline_pass = bool(baseline_by_key[key].get("oracle_correct"))
        candidate_pass = bool(candidate_by_key[key].get("oracle_correct"))
        if candidate_pass and not baseline_pass:
            gained += 1
        elif baseline_pass and not candidate_pass:
            lost += 1
        elif baseline_pass and candidate_pass:
            both_pass += 1
        else:
            both_fail += 1
    count = len(baseline_by_key)
    baseline_passes = sum(
        bool(record.get("oracle_correct")) for record in baseline_by_key.values()
    )
    candidate_passes = sum(
        bool(record.get("oracle_correct")) for record in candidate_by_key.values()
    )
    return {
        "observation_count": count,
        "baseline_passes": baseline_passes,
        "candidate_passes": candidate_passes,
        "pass_difference": candidate_passes - baseline_passes,
        "pass_rate_difference": (candidate_passes - baseline_passes) / count,
        "gained_passes": gained,
        "lost_passes": lost,
        "both_pass": both_pass,
        "both_fail": both_fail,
    }


def analyze(tasks, revision):
    if oos.file_sha256(PLAN) != PLAN_SHA256:
        raise ValueError("scaling plan SHA-256 mismatch")
    if oos.file_sha256(AMENDMENT) != AMENDMENT_SHA256:
        raise ValueError("scaling amendment SHA-256 mismatch")
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    routing = config["routing"]
    if routing["maximum_ttft_ms"] != MAXIMUM_TTFT_MS:
        raise ValueError("maximum TTFT threshold mismatch")
    if routing["minimum_generation_rate"] != MINIMUM_GENERATION_RATE:
        raise ValueError("minimum generation-rate threshold mismatch")

    baseline = load_baseline(tasks)
    one_b = load_candidate(tasks, "gemma3:1b", revision)
    four_b = load_candidate(tasks, "gemma3:4b", revision)
    records_by_model = {
        "gemma3:270m": baseline,
        "gemma3:1b": one_b,
        "gemma3:4b": four_b,
    }
    identities = {
        "gemma3:270m": BASELINE_IDENTITY,
        "gemma3:1b": scaling.public_identity(scaling.MODEL_SPECS["gemma3:1b"]),
        "gemma3:4b": scaling.public_identity(scaling.MODEL_SPECS["gemma3:4b"]),
    }
    return {
        "analysis_id": ANALYSIS_ID,
        "comparison_id": scaling.COMPARISON_ID,
        "interpretation": "strict",
        "plan_sha256": PLAN_SHA256,
        "amendment_sha256": AMENDMENT_SHA256,
        "benchmark_sha256": oos.BENCHMARK_SHA256,
        "baseline_evidence_sha256": BASELINE_SHA256,
        "execution_revision": revision,
        "model_order": list(MODEL_ORDER),
        "models": {
            model: model_metrics(
                records_by_model[model], identities[model], tasks
            )
            for model in MODEL_ORDER
        },
        "paired_against_270m": {
            model: paired_comparison(baseline, records_by_model[model])
            for model in ("gemma3:1b", "gemma3:4b")
        },
        "interpretation_boundaries": [
            "Frozen-suite regression comparison, not new OOS validation.",
            "Qualification prompts exposed representative failure types.",
            "Quantization differs between 270M and larger packages.",
            "No energy inference is made.",
            "Gate results simulate post-generation gates only.",
            "Gate survival does not imply strict correctness.",
        ],
    }


def render_csv(document):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "model",
            "scope",
            "scope_value",
            "observation_count",
            "pass_count",
            "pass_rate",
            "median_ttft_ms",
            "median_total_ms",
            "median_tokens_per_second",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for model in MODEL_ORDER:
        metrics = document["models"][model]
        writer.writerow(
            {
                "model": model,
                "scope": "overall",
                "scope_value": "all",
                "observation_count": metrics["observation_count"],
                "pass_count": metrics["pass_count"],
                "pass_rate": metrics["pass_rate"],
                "median_ttft_ms": metrics["timing"]["median_ttft_ms"],
                "median_total_ms": metrics["timing"]["median_total_ms"],
                "median_tokens_per_second": metrics["timing"]
                ["median_tokens_per_second"],
            }
        )
        for family, family_metrics in metrics["per_family"].items():
            writer.writerow(
                {
                    "model": model,
                    "scope": "capability_family",
                    "scope_value": family,
                    "observation_count": family_metrics["observation_count"],
                    "pass_count": family_metrics["pass_count"],
                    "pass_rate": family_metrics["pass_rate"],
                    "median_ttft_ms": "",
                    "median_total_ms": "",
                    "median_tokens_per_second": "",
                }
            )
    return output.getvalue()


def write_outputs(document):
    if JSON_OUTPUT.exists() or CSV_OUTPUT.exists():
        raise FileExistsError("refusing to overwrite existing scaling analysis")
    json_content = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    JSON_OUTPUT.write_text(json_content, encoding="utf-8")
    CSV_OUTPUT.write_text(render_csv(document), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="analyze complete evidence and write JSON and CSV"
    )
    args = parser.parse_args(argv)
    document = oos.load_suite()
    tasks = document["tasks"]
    revision = oos.code_revision()
    if not revision:
        raise RuntimeError("unable to identify Git revision")

    print(f"Analysis: {ANALYSIS_ID}")
    print(f"Plan SHA-256: {PLAN_SHA256}")
    print(f"Amendment SHA-256: {AMENDMENT_SHA256}")
    print(f"Benchmark SHA-256: {oos.BENCHMARK_SHA256}")
    print(f"Baseline: {BASELINE_PATH}")
    for model in scaling.MODEL_ORDER:
        spec = scaling.MODEL_SPECS[model]
        print(f"{model} evidence: {spec['output']}")
        print(f"{model} summary: {spec['summary']}")
    if not args.write:
        missing = [
            str(path)
            for spec in scaling.MODEL_SPECS.values()
            for path in (spec["output"], spec["summary"])
            if not path.exists()
        ]
        print(f"Missing future evidence files: {len(missing)}")
        print("Dry run only; no analysis files were created.")
        return
    analysis = analyze(tasks, revision)
    write_outputs(analysis)
    print(f"Wrote: {JSON_OUTPUT}")
    print(f"Wrote: {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
