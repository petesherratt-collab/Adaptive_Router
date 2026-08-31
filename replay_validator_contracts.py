"""Authenticate and replay the frozen validator contracts in memory."""

import argparse
import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

import validators
from validator_contracts import (
    BENCHMARK_SHA256,
    ContractSchemaError,
    contract_validate,
    validate_contract_document,
)


ROOT = Path(__file__).resolve().parent
PLAN_SHA256 = "ac7cb2ee4b47ee07c4a0a63b122d56ce47d49dffb88ff82e19fd9a32d638edf0"
CONTRACT_SHA256 = "ea585eaf7775426ca9d58e8b8276a7bc18d7789545f84bb370aae6ac4ce6a1f0"
EVIDENCE_SHA256 = {
    "gemma3:270m": "425fa9328781ff2e53f69ce0a054531e106be3a6ed1380c148e35ec3d47c8ca0",
    "gemma3:1b": "a3bde560ccf875658f9129c3eaa321b51c6c29f3f5a7096d9a97eca070310622",
    "gemma3:4b": "c0576396252f39523840ca1d970648a84ec03960ca746451a10c0ef83b6cb676",
}
EVIDENCE_PATHS = {
    "gemma3:270m": ROOT / "benchmark_runs_oos_local_v1.jsonl",
    "gemma3:1b": ROOT / "benchmark_runs_scaling_gemma3_1b_v1.jsonl",
    "gemma3:4b": ROOT / "benchmark_runs_scaling_gemma3_4b_v1.jsonl",
}
BENCHMARK_PATH = ROOT / "benchmark_oos_v1.json"
CONTRACT_PATH = ROOT / "validator_contracts_oos_v1.json"
RESULT_JSON = ROOT / "validator_contract_replay_v1.json"
RESULT_CSV = ROOT / "validator_contract_replay_v1.csv"

SUITE_ID = "oos_validation_v1"
TASK_COUNT = 40
REPS = 5
OBSERVATIONS_PER_MODEL = 200
MAXIMUM_TTFT_MS = 8000
MINIMUM_GENERATION_RATE = 1.5
EXPECTED_FAMILY_COUNTS = {
    "structured_extraction": 10,
    "sentiment": 5,
    "json_format": 5,
    "priority": 5,
    "markdown_bullets": 5,
    "key_value_labels": 5,
    "transformation": 5,
}
EVIDENCE_COMMON_FIELDS = {
    "benchmark_sha256", "capability_family", "code_revision", "error",
    "model_residency", "normalized_output", "oracle_correct", "provider",
    "raw_output", "rep", "requested_model", "returned_model", "success",
    "task_class", "task_id", "tokens_per_second", "total_ms", "ttft_ms",
    "validator", "validator_status",
}
EVIDENCE_SCALING_FIELDS = EVIDENCE_COMMON_FIELDS | {
    "comparison_id", "model_identity",
}
TRANSITION_KEYS = tuple(
    f"baseline_{baseline}__counterfactual_{counterfactual}__oracle_{oracle}"
    for baseline in ("survive", "fail")
    for counterfactual in ("survive", "fail")
    for oracle in ("correct", "incorrect")
)


@dataclass(frozen=True)
class EvidenceObservation:
    model: str
    task_id: str
    rep: int
    task_class: str
    capability_family: str
    raw_output: str
    success: bool
    ttft_ms: float | int | None
    tokens_per_second: float | int | None
    oracle_correct: bool


@dataclass(frozen=True)
class ReplayObservation:
    model: str
    task_id: str
    capability_family: str
    contract_type: str
    contract_accepted: bool
    contract_reason: str
    baseline_gate_survived: bool
    baseline_reason: str
    hardware_generation_gates_survived: bool
    counterfactual_gate_survived: bool
    oracle_correct: bool


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json_loads(text):
    def no_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    def no_nonstandard_constant(value):
        raise ValueError(f"nonstandard JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=no_duplicate_keys,
        parse_constant=no_nonstandard_constant,
    )


def implementation_revision():
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("unable to read implementation Git revision") from exc


def authenticate_plan():
    actual = file_sha256(ROOT / "VALIDATOR_CONTRACT_REPLAY_V1_PLAN.md")
    if actual != PLAN_SHA256:
        raise ValueError("plan SHA-256 mismatch")
    return actual


def load_benchmark_inventory(path=BENCHMARK_PATH):
    path = Path(path)
    if file_sha256(path) != BENCHMARK_SHA256:
        raise ValueError("frozen benchmark SHA-256 mismatch")
    try:
        document = _strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("malformed benchmark") from exc
    if not isinstance(document, dict) or document.get("suite_id") != SUITE_ID:
        raise ValueError("unexpected benchmark suite")
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != TASK_COUNT:
        raise ValueError("benchmark task count mismatch")
    inventory = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("malformed benchmark task")
        required = {
            "task_id", "task_class", "capability_family", "normalization",
            "prompt", "expected",
        }
        if not required.issubset(task):
            raise ValueError("benchmark task schema mismatch")
        task_id = task["task_id"]
        if not isinstance(task_id, str) or not task_id or task_id in inventory:
            raise ValueError("duplicate or malformed benchmark task_id")
        if not isinstance(task["task_class"], str) or not isinstance(
            task["capability_family"], str
        ) or not isinstance(task["prompt"], str):
            raise ValueError("malformed benchmark task metadata")
        inventory[task_id] = {
            "task_id": task_id,
            "task_class": task["task_class"],
            "capability_family": task["capability_family"],
            "prompt": task["prompt"],
        }
    counts = {}
    for task in inventory.values():
        family = task["capability_family"]
        counts[family] = counts.get(family, 0) + 1
    if counts != EXPECTED_FAMILY_COUNTS:
        raise ValueError("benchmark family counts mismatch")
    return inventory


def load_contracts(path=CONTRACT_PATH, task_inventory=None):
    path = Path(path)
    if file_sha256(path) != CONTRACT_SHA256:
        raise ValueError("contract SHA-256 mismatch")
    try:
        document = _strict_json_loads(path.read_text(encoding="utf-8"))
        validate_contract_document(document, task_inventory)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid contract document: {exc}") from exc
    return {item["task_id"]: item for item in document["contracts"]}


def _expected_identity(model):
    if model == "gemma3:270m":
        return {"provider": "ollama", "requested_model": "gemma3:270m"}
    return {
        "comparison_id": "local_model_scaling_v1",
        "requested_model": model,
        "model_identity": {
            "name": model,
            "digest": {
                "gemma3:1b": "8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc",
                "gemma3:4b": "a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a",
            }[model],
            "parameter_size": {"gemma3:1b": "999.89M", "gemma3:4b": "4.3B"}[model],
            "quantization_level": "Q4_K_M",
            "format": "gguf",
            "family": "gemma3",
            "package_size_bytes": {
                "gemma3:1b": 815319791,
                "gemma3:4b": 3338801804,
            }[model],
        },
    }


def _number_or_none(value):
    if value is None:
        return True
    return type(value) in (int, float)


def _read_evidence_lines(path):
    records = []
    try:
        with Path(path).open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    raise ValueError(f"blank evidence line {line_number}")
                try:
                    records.append(_strict_json_loads(line))
                except (ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid evidence JSON line {line_number}") from exc
    except OSError as exc:
        raise ValueError(f"cannot read evidence file: {path}") from exc
    return records


def load_evidence(model, task_inventory, path=None):
    if model not in EVIDENCE_SHA256:
        raise ValueError(f"unknown evidence model: {model}")
    path = Path(path or EVIDENCE_PATHS[model])
    if file_sha256(path) != EVIDENCE_SHA256[model]:
        raise ValueError(f"{model} evidence SHA-256 mismatch")
    records = _read_evidence_lines(path)
    if len(records) != OBSERVATIONS_PER_MODEL:
        raise ValueError(f"{model} evidence count mismatch")
    expected_keys = {
        (task_id, rep)
        for task_id in task_inventory
        for rep in range(1, REPS + 1)
    }
    actual_keys = []
    expected_identity = _expected_identity(model)
    expected_fields = (
        EVIDENCE_COMMON_FIELDS
        if model == "gemma3:270m"
        else EVIDENCE_SCALING_FIELDS
    )
    projected = []
    for record in records:
        if not isinstance(record, dict) or set(record) != expected_fields:
            raise ValueError(f"{model} evidence schema mismatch")
        task_id = record.get("task_id")
        rep = record.get("rep")
        if not isinstance(task_id, str) or type(rep) is not int or not 1 <= rep <= REPS:
            raise ValueError("malformed observation key")
        if task_id not in task_inventory:
            raise ValueError("unknown observation task_id")
        actual_keys.append((task_id, rep))
        if record["benchmark_sha256"] != BENCHMARK_SHA256:
            raise ValueError("observation benchmark hash mismatch")
        task = task_inventory[task_id]
        if record["task_class"] != task["task_class"] or record["capability_family"] != task["capability_family"]:
            raise ValueError("observation task metadata mismatch")
        safe_string_fields = (
            "task_class", "capability_family", "benchmark_sha256", "code_revision",
            "provider", "raw_output", "requested_model", "returned_model", "task_id",
        )
        if any(not isinstance(record[field], str) for field in safe_string_fields):
            raise ValueError("observation string field type mismatch")
        if type(record["success"]) is not bool or type(record["oracle_correct"]) is not bool:
            raise ValueError("observation field type mismatch")
        if not _number_or_none(record["ttft_ms"]) or not _number_or_none(record["tokens_per_second"]) or not _number_or_none(record["total_ms"]):
            raise ValueError("observation timing type mismatch")
        if record["error"] is not None and not isinstance(record["error"], str):
            raise ValueError("observation error type mismatch")
        residency = record["model_residency"]
        if (
            not isinstance(residency, dict)
            or set(residency) != {"resident", "size_bytes"}
            or type(residency["resident"]) is not bool
            or (residency["size_bytes"] is not None and type(residency["size_bytes"]) is not int)
        ):
            raise ValueError("observation residency type mismatch")
        for field, expected in expected_identity.items():
            if record.get(field) != expected:
                raise ValueError(f"{model} identity mismatch: {field}")
        if record["returned_model"] != model:
            raise ValueError(f"{model} returned model mismatch")
        projected.append(
            EvidenceObservation(
                model=model,
                task_id=task_id,
                rep=rep,
                task_class=record["task_class"],
                capability_family=record["capability_family"],
                raw_output=record["raw_output"],
                success=record["success"],
                ttft_ms=record["ttft_ms"],
                tokens_per_second=record["tokens_per_second"],
                oracle_correct=record["oracle_correct"],
            )
        )
    if len(actual_keys) != len(set(actual_keys)):
        raise ValueError("duplicate observation key")
    if set(actual_keys) != expected_keys:
        raise ValueError("observation key set mismatch")
    return projected


def hardware_generation_gate(record):
    """Return the frozen generation/TTFT/throughput decision."""
    if not record.success:
        return False, "GENERATION_FAILED"
    if record.ttft_ms is not None and record.ttft_ms > MAXIMUM_TTFT_MS:
        return False, "TTFT_EXCEEDED"
    if record.tokens_per_second is not None and record.tokens_per_second < MINIMUM_GENERATION_RATE:
        return False, "GENERATION_TOO_SLOW"
    return True, "SURVIVED"


def baseline_gate(record, task):
    hardware_survived, reason = hardware_generation_gate(record)
    if not hardware_survived:
        return False, reason
    result = validators.validate(
        task["task_class"], task["prompt"], record.raw_output
    )
    if result.status == validators.FAIL:
        return False, "VALIDATOR_FAILED"
    return True, "SURVIVED"


def replay_records(records_by_model, contracts, task_inventory):
    results = []
    for model, records in records_by_model.items():
        for record in records:
            task = task_inventory[record.task_id]
            contract = contracts[record.task_id]
            contract_result = contract_validate(contract, record.raw_output)
            hardware_survived, _ = hardware_generation_gate(record)
            baseline_survived, baseline_reason = baseline_gate(record, task)
            results.append(
                ReplayObservation(
                    model=model,
                    task_id=record.task_id,
                    capability_family=record.capability_family,
                    contract_type=contract["contract_type"],
                    contract_accepted=contract_result.accepted,
                    contract_reason=contract_result.primary_reason,
                    baseline_gate_survived=baseline_survived,
                    baseline_reason=baseline_reason,
                    hardware_generation_gates_survived=hardware_survived,
                    counterfactual_gate_survived=hardware_survived and contract_result.accepted,
                    oracle_correct=record.oracle_correct,
                )
            )
    return results


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _metrics(rows):
    rows = list(rows)
    correct = sum(row.oracle_correct for row in rows)
    accepted = sum(row.contract_accepted for row in rows)
    baseline_survived = sum(row.baseline_gate_survived for row in rows)
    counterfactual_survived = sum(row.counterfactual_gate_survived for row in rows)
    false_before = sum(row.baseline_gate_survived and not row.oracle_correct for row in rows)
    caught = sum(
        row.baseline_gate_survived and not row.oracle_correct
        and not row.counterfactual_gate_survived for row in rows
    )
    remaining = sum(
        row.baseline_gate_survived and row.counterfactual_gate_survived
        and not row.oracle_correct for row in rows
    )
    newly_admitted = sum(
        not row.baseline_gate_survived and row.counterfactual_gate_survived
        and not row.oracle_correct for row in rows
    )
    counterfactual_false = sum(
        row.counterfactual_gate_survived and not row.oracle_correct
        for row in rows
    )
    raw_rejected = sum(not row.contract_accepted for row in rows)
    raw_correct_rejected = sum(
        row.oracle_correct and not row.contract_accepted for row in rows
    )
    newly_rejected_correct = sum(
        row.baseline_gate_survived and row.oracle_correct
        and not row.counterfactual_gate_survived for row in rows
    )
    newly_recovered_correct = sum(
        not row.baseline_gate_survived and row.counterfactual_gate_survived
        and row.oracle_correct for row in rows
    )
    reasons = {}
    baseline_reasons = {}
    for row in rows:
        reasons[row.contract_reason] = reasons.get(row.contract_reason, 0) + 1
        baseline_reasons[row.baseline_reason] = baseline_reasons.get(row.baseline_reason, 0) + 1
    transitions = {key: 0 for key in TRANSITION_KEYS}
    for row in rows:
        baseline = "survive" if row.baseline_gate_survived else "fail"
        counterfactual = "survive" if row.counterfactual_gate_survived else "fail"
        oracle = "correct" if row.oracle_correct else "incorrect"
        key = f"baseline_{baseline}__counterfactual_{counterfactual}__oracle_{oracle}"
        transitions[key] += 1
    classifications = [row for row in rows if row.contract_type == "classification"]
    class_conformant = sum(row.contract_accepted for row in classifications)
    class_incorrect = sum(not row.oracle_correct for row in classifications)
    return {
        "observation_count": len(rows),
        "oracle_correct_count": correct,
        "oracle_incorrect_count": len(rows) - correct,
        "contract_accept_count": accepted,
        "contract_reject_count": raw_rejected,
        "false_accept_count_before_replay": false_before,
        "false_accept_caught_count": caught,
        "false_accept_remaining_count": remaining,
        "newly_admitted_incorrect_count": newly_admitted,
        "counterfactual_false_accept_count": counterfactual_false,
        "correct_rejected_count": raw_correct_rejected,
        "newly_rejected_correct_count": newly_rejected_correct,
        "newly_recovered_correct_count": newly_recovered_correct,
        "false_accept_catch_rate": _ratio(caught, false_before),
        "precision_among_contract_accepted_observations": _ratio(
            sum(row.contract_accepted and row.oracle_correct for row in rows),
            accepted,
        ),
        "baseline_gate_survived_count": baseline_survived,
        "counterfactual_gate_survived_count": counterfactual_survived,
        "raw_contract_rejection_reason_counts": dict(sorted(reasons.items())),
        "baseline_gate_rejection_reason_counts": dict(sorted(baseline_reasons.items())),
        "classification_label_conformant_count": class_conformant,
        "classification_label_nonconformant_count": len(classifications) - class_conformant,
        "classification_oracle_correct_count": sum(row.oracle_correct for row in classifications),
        "classification_oracle_incorrect_count": class_incorrect,
        "classification_wrong_permitted_label_accepted_count": sum(
            row.contract_accepted and not row.oracle_correct for row in classifications
        ),
        "paired_transition_counts": transitions,
        "identity_false_accept_before": false_before == caught + remaining,
        "identity_counterfactual_false_accept": counterfactual_false == remaining + newly_admitted,
        "transition_count_sum": sum(transitions.values()),
    }


def _grouped(rows, attribute):
    groups = {}
    for row in rows:
        groups.setdefault(getattr(row, attribute), []).append(row)
    return {key: _metrics(groups[key]) for key in sorted(groups)}


def build_report(results, implementation_git_revision=None):
    by_model = {}
    grouped_by_model = {}
    for model in EVIDENCE_SHA256:
        model_rows = [row for row in results if row.model == model]
        by_model[model] = _metrics(model_rows)
        grouped_by_model[model] = {
            "capability_family": _grouped(model_rows, "capability_family"),
            "task_id": _grouped(model_rows, "task_id"),
            "contract_type": _grouped(model_rows, "contract_type"),
        }
    overall = _metrics(results)
    checks = {}
    for model, metrics in by_model.items():
        checks[model] = {
            "observation_count_is_200": metrics["observation_count"] == 200,
            "transition_count_sum_is_200": metrics["transition_count_sum"] == 200,
            "false_accept_identity_holds": metrics["identity_false_accept_before"],
            "counterfactual_identity_holds": metrics["identity_counterfactual_false_accept"],
        }
    checks["overall"] = {
        "observation_count_is_600": overall["observation_count"] == 600,
        "transition_count_sum_is_600": overall["transition_count_sum"] == 600,
        "false_accept_identity_holds": overall["identity_false_accept_before"],
        "counterfactual_identity_holds": overall["identity_counterfactual_false_accept"],
    }
    if not all(all(values.values()) for values in checks.values()):
        raise ValueError("replay identity check failed")
    return {
        "schema_version": "validator_contract_replay_v1",
        "plan_sha256": PLAN_SHA256,
        "contract_file_sha256": CONTRACT_SHA256,
        "evidence_sha256": dict(EVIDENCE_SHA256),
        "benchmark_sha256": BENCHMARK_SHA256,
        "implementation_git_revision": implementation_git_revision,
        "models": by_model,
        "overall": overall,
        "grouped": {
            "capability_family": _grouped(results, "capability_family"),
            "task_id": _grouped(results, "task_id"),
            "contract_type": _grouped(results, "contract_type"),
        },
        "grouped_by_model": grouped_by_model,
        "identity_checks": checks,
    }


def _csv_text(report):
    output = io.StringIO(newline="")
    fields = [
        "plan_sha256", "contract_file_sha256", "benchmark_sha256",
        "evidence_sha256_270m", "evidence_sha256_1b", "evidence_sha256_4b",
        "implementation_git_revision", "scope", "group", "model", "metric", "value",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    metadata = {
        "plan_sha256": report["plan_sha256"],
        "contract_file_sha256": report["contract_file_sha256"],
        "benchmark_sha256": report["benchmark_sha256"],
        "evidence_sha256_270m": report["evidence_sha256"]["gemma3:270m"],
        "evidence_sha256_1b": report["evidence_sha256"]["gemma3:1b"],
        "evidence_sha256_4b": report["evidence_sha256"]["gemma3:4b"],
        "implementation_git_revision": report["implementation_git_revision"],
    }
    records = [("overall", "overall", "overall", report["overall"])]
    records.extend(("model", model, model, metrics) for model, metrics in report["models"].items())
    for dimension, groups in report["grouped"].items():
        records.extend((dimension, group, "overall", metrics) for group, metrics in groups.items())
    for model, dimensions in report["grouped_by_model"].items():
        for dimension, groups in dimensions.items():
            records.extend(
                (f"{dimension}_by_model", group, model, metrics)
                for group, metrics in groups.items()
            )
    for scope, group, model, metrics in records:
        for metric, value in metrics.items():
            writer.writerow({
                **metadata,
                "scope": scope,
                "group": group,
                "model": model,
                "metric": metric,
                "value": json.dumps(value, sort_keys=True),
            })
    return output.getvalue()


def _write_no_overwrite(path, content):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(content)


def run(write=False, json_path=RESULT_JSON, csv_path=RESULT_CSV):
    if write and (Path(json_path).exists() or Path(csv_path).exists()):
        raise FileExistsError("refusing to overwrite replay result file")
    authenticate_plan()
    inventory = load_benchmark_inventory()
    contracts = load_contracts(task_inventory=inventory)
    records_by_model = {
        model: load_evidence(model, inventory)
        for model in EVIDENCE_SHA256
    }
    results = replay_records(records_by_model, contracts, inventory)
    report = build_report(results, implementation_revision())
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    csv_text = _csv_text(report)
    if write:
        _write_no_overwrite(json_path, json_text)
        try:
            _write_no_overwrite(csv_path, csv_text)
        except Exception:
            Path(json_path).unlink(missing_ok=True)
            raise
    else:
        print(
            "DRY RUN: authenticated 3 evidence files, 40 contracts, "
            "600 observations; no result or audit files written."
        )
        print(
            "DRY RUN: baseline survivors="
            f"{report['overall']['baseline_gate_survived_count']}, "
            "counterfactual survivors="
            f"{report['overall']['counterfactual_gate_survived_count']}, "
            "raw contract accepts="
            f"{report['overall']['contract_accept_count']}"
        )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        run(write=args.write)
    except (FileExistsError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
