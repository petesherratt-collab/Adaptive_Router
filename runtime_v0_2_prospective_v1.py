"""Frozen schema, oracle, budget, and evidence rules for runtime v0.2 PV1."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any

from runtime_contracts import RuntimeRequest, execute_deterministic, validate_runtime_output


ROOT = Path(__file__).resolve().parent
PLAN_NAME = "RUNTIME_V0_2_PROSPECTIVE_V1_PLAN.md"
BENCHMARK_NAME = "benchmark_runtime_v0_2_prospective_v1.json"
CONFIG_NAME = "config.json"
PLAN_SHA256 = "d051be7261d708d3adef7f807b8899ca02b88c11531e4f9b3e28eb4ef3c3de98"
BENCHMARK_SHA256 = "384a64905d6bee062a51444442752737911d2c5c5b96a14eba0164a35c7c8acb"
CONFIG_SHA256 = "94fcd92eed2d045730fa49020219764c1f38aaabf9d2b0cae193117eff98811c"
SUITE_ID = "runtime_v0_2_prospective_v1"
SCHEMA_VERSION = "runtime_v0_2_prospective_observation_v1"
RELEASE_COMMIT = "307a47389fea10df38623bc2f238a14a11081269"
TASK_COUNT = 40
REPETITIONS = 3
OBSERVATION_COUNT = 120
PROVIDER_OBSERVATION_COUNT = 90
MAX_REMOTE_LOGICAL_CALLS = 90
MAX_REMOTE_HTTP_ATTEMPTS = 180
MAX_REPORTED_REMOTE_COST_USD = 0.02

COHORT_COUNTS = {
    "deterministic": 10,
    "structural_json": 12,
    "line_format": 8,
    "classification": 10,
}
CONTRACT_COUNTS = {
    "deterministic_executor": 10,
    "structured_json": 8,
    "json_format": 4,
    "bullet_format": 4,
    "label_format": 4,
    "classification_labels": 10,
}
MODEL_SPEC = {
    "name": "gemma3:270m",
    "digest": "e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be",
    "parameter_size": "268.10M",
    "quantization_level": "Q8_0",
    "format": "gguf",
    "package_size_bytes": 291554930,
}


class FrozenDesignError(ValueError):
    pass


class StateError(FrozenDesignError):
    pass


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class OracleResult:
    correct: bool
    normalized: Any = None
    error: str | None = None


@dataclass
class EvidenceBudget:
    local_logical_calls: int = 0
    remote_logical_calls: int = 0
    remote_http_attempts: int = 0
    reported_remote_cost_usd: float = 0.0

    def before_local(self):
        if self.local_logical_calls >= PROVIDER_OBSERVATION_COUNT:
            raise BudgetExceeded("LOCAL_LOGICAL_CALL_LIMIT")

    def after_local(self):
        self.local_logical_calls += 1

    def before_remote(self):
        if self.remote_logical_calls >= MAX_REMOTE_LOGICAL_CALLS:
            raise BudgetExceeded("REMOTE_LOGICAL_CALL_LIMIT")
        if self.remote_http_attempts > MAX_REMOTE_HTTP_ATTEMPTS - 2:
            raise BudgetExceeded("REMOTE_HTTP_ATTEMPT_LIMIT")
        if self.reported_remote_cost_usd > MAX_REPORTED_REMOTE_COST_USD:
            raise BudgetExceeded("REMOTE_REPORTED_COST_LIMIT")

    def after_remote(self, result):
        attempts = getattr(result, "attempt_count", 0)
        cost = getattr(result, "cost", None)
        if type(attempts) is not int or not 0 <= attempts <= 2:
            raise FrozenDesignError("INVALID_REMOTE_ATTEMPT_COUNT")
        if cost is not None and (
            type(cost) not in (int, float)
            or isinstance(cost, bool)
            or not math.isfinite(cost)
            or cost < 0
        ):
            raise FrozenDesignError("INVALID_REMOTE_COST")
        self.remote_logical_calls += 1
        self.remote_http_attempts += attempts
        self.reported_remote_cost_usd += float(cost or 0.0)
        if self.remote_http_attempts > MAX_REMOTE_HTTP_ATTEMPTS:
            raise BudgetExceeded("REMOTE_HTTP_ATTEMPT_LIMIT")

    def snapshot(self):
        return asdict(self)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_json_loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise FrozenDesignError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(value):
        raise FrozenDesignError("NON_FINITE_JSON_CONSTANT=" + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def validate_benchmark(document):
    top_fields = {
        "schema_version", "suite_id", "released_runtime_tag",
        "released_runtime_commit", "repetitions", "task_order", "tasks",
    }
    if not isinstance(document, dict) or set(document) != top_fields:
        raise FrozenDesignError("BENCHMARK_FIELDS_MISMATCH")
    if (
        document["schema_version"] != "runtime_v0_2_prospective_benchmark_v1"
        or document["suite_id"] != SUITE_ID
        or document["released_runtime_tag"] != "v0.2.0"
        or document["released_runtime_commit"] != RELEASE_COMMIT
        or document["repetitions"] != REPETITIONS
    ):
        raise FrozenDesignError("BENCHMARK_IDENTITY_MISMATCH")
    tasks, order = document["tasks"], document["task_order"]
    if not isinstance(tasks, list) or not isinstance(order, list):
        raise FrozenDesignError("BENCHMARK_COLLECTION_TYPE")
    if len(tasks) != TASK_COUNT or len(order) != TASK_COUNT:
        raise FrozenDesignError("BENCHMARK_COUNT_MISMATCH")
    ids = [task.get("task_id") if isinstance(task, dict) else None for task in tasks]
    if (
        len(set(ids)) != TASK_COUNT
        or len(set(order)) != TASK_COUNT
        or set(ids) != set(order)
        or any(not isinstance(task_id, str) or not task_id.startswith("rtv02pv1_") for task_id in ids)
    ):
        raise FrozenDesignError("TASK_ID_MISMATCH")
    inventory = {task["task_id"]: task for task in tasks}
    ordered = [inventory[task_id] for task_id in order]
    if Counter(task.get("cohort") for task in ordered) != Counter(COHORT_COUNTS):
        raise FrozenDesignError("COHORT_COUNT_MISMATCH")

    contract_types, operations = [], []
    for task in ordered:
        if set(task) != {"task_id", "cohort", "runtime_request", "oracle"}:
            raise FrozenDesignError("TASK_FIELDS_MISMATCH")
        mapping = task["runtime_request"]
        if not isinstance(mapping, dict) or set(mapping) != {
            "schema_version", "task_class", "prompt", "contract"
        }:
            raise FrozenDesignError("RUNTIME_REQUEST_FIELDS_MISMATCH")
        if "oracle" in set(_walk_keys(mapping)):
            raise FrozenDesignError("ORACLE_LEAK_IN_RUNTIME_REQUEST")
        request = RuntimeRequest.from_mapping(mapping)
        contract = request.contract
        contract_type = contract["contract_type"]
        contract_types.append(contract_type)
        cohort = task["cohort"]
        expected_cohort = (
            "deterministic" if contract_type == "deterministic_executor"
            else "classification" if contract_type == "classification_labels"
            else "line_format" if contract_type in {"bullet_format", "label_format"}
            else "structural_json"
        )
        if cohort != expected_cohort:
            raise FrozenDesignError("COHORT_CONTRACT_MISMATCH")
        oracle_value = task["oracle"]
        if not isinstance(oracle_value, dict) or set(oracle_value) != {"kind", "expected"}:
            raise FrozenDesignError("ORACLE_FIELDS_MISMATCH")
        expected = oracle_value["expected"]
        if contract_type == "deterministic_executor":
            operations.append(contract["operation"])
            if oracle_value["kind"] != "exact_text" or execute_deterministic(contract) != expected:
                raise FrozenDesignError("DETERMINISTIC_ORACLE_MISMATCH")
        elif contract_type == "classification_labels":
            if oracle_value["kind"] != "classification_label" or expected not in contract["permitted_labels"]:
                raise FrozenDesignError("CLASSIFICATION_ORACLE_MISMATCH")
        elif contract_type in {"structured_json", "json_format"}:
            rendered = json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
            if (
                oracle_value["kind"] != "json_object"
                or not isinstance(expected, dict)
                or set(expected) != set(contract["exact_keys"])
                or validate_runtime_output(contract, rendered).status != "PASS"
            ):
                raise FrozenDesignError("JSON_ORACLE_MISMATCH")
        elif (
            oracle_value["kind"] != "exact_lines"
            or not isinstance(expected, str)
            or validate_runtime_output(contract, expected).status != "PASS"
        ):
            raise FrozenDesignError("LINE_ORACLE_MISMATCH")
    if Counter(contract_types) != Counter(CONTRACT_COUNTS):
        raise FrozenDesignError("CONTRACT_COUNT_MISMATCH")
    if len(operations) != 10 or len(set(operations)) != 10:
        raise FrozenDesignError("OPERATION_COVERAGE_MISMATCH")
    return ordered, inventory


def load_frozen_inputs(root=ROOT):
    root = Path(root)
    if file_sha256(root / PLAN_NAME) != PLAN_SHA256:
        raise FrozenDesignError("PLAN_HASH_MISMATCH")
    if file_sha256(root / BENCHMARK_NAME) != BENCHMARK_SHA256:
        raise FrozenDesignError("BENCHMARK_HASH_MISMATCH")
    document = strict_json_loads((root / BENCHMARK_NAME).read_text(encoding="utf-8"))
    tasks, inventory = validate_benchmark(document)
    return document, tasks, inventory


def _line_normalize(raw):
    if not isinstance(raw, str):
        raise FrozenDesignError("INVALID_OUTPUT_TYPE")
    if "\r" in raw.replace("\r\n", ""):
        raise FrozenDesignError("LONE_CR")
    value = raw.replace("\r\n", "\n")
    return value[:-1] if value.endswith("\n") else value


def _json_candidate(raw):
    value = _line_normalize(raw)
    lines = value.split("\n")
    fence = chr(96) * 3
    if lines and lines[0] in {fence, fence + "json"}:
        if len(lines) < 2 or lines[-1] != fence:
            raise FrozenDesignError("INCOMPLETE_OUTER_FENCE")
        if any(fence in line for line in lines[1:-1]):
            raise FrozenDesignError("NESTED_OR_MULTIPLE_FENCE")
        return "\n".join(lines[1:-1])
    if any(fence in line for line in lines):
        raise FrozenDesignError("INCOMPLETE_OR_SURROUNDING_FENCE")
    return value


def _json_equal(left, right):
    if type(left) in (int, float) or type(right) in (int, float):
        return (
            type(left) in (int, float)
            and type(right) in (int, float)
            and math.isfinite(float(left))
            and math.isfinite(float(right))
            and left == right
        )
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def oracle(task, raw_output):
    if not isinstance(raw_output, str) or raw_output == "":
        return OracleResult(False, error="NO_OUTPUT")
    kind, expected = task["oracle"]["kind"], task["oracle"]["expected"]
    try:
        if kind == "json_object":
            parsed = strict_json_loads(_json_candidate(raw_output))
            if not isinstance(parsed, dict):
                return OracleResult(False, parsed, "NOT_JSON_OBJECT")
            return OracleResult(_json_equal(parsed, expected), parsed)
        normalized = _line_normalize(raw_output)
        if kind == "classification_label":
            lines = normalized.split("\n")
            if len(lines) != 1 or not lines[0]:
                return OracleResult(False, normalized, "LABEL_LINE_COUNT")
            normalized = lines[0].strip(" \t").translate(
                str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
            )
        return OracleResult(normalized == expected, normalized)
    except (FrozenDesignError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return OracleResult(False, error=str(exc))


def result_record(result):
    if result is None:
        return {"present": False}
    return {
        "present": True,
        "raw_output": result.text if result.success else None,
        **result.metadata(),
    }


def output_paths(root=ROOT):
    root = Path(root)
    return {
        "runs": root / "runtime_v0_2_prospective_v1_runs.jsonl",
        "telemetry": root / "runtime_v0_2_prospective_v1_router_telemetry.jsonl",
        "summary": root / "runtime_v0_2_prospective_v1_summary.json",
        "analysis_json": root / "runtime_v0_2_prospective_v1_analysis.json",
        "analysis_csv": root / "runtime_v0_2_prospective_v1_analysis.csv",
    }


def assert_empty_state(root=ROOT):
    for path in output_paths(root).values():
        if path.exists() or Path(str(path) + ".partial").exists():
            raise StateError("OUTPUT_STATE_NOT_EMPTY=" + path.name)


def open_partial(path):
    partial = Path(str(path) + ".partial")
    if path.exists() or partial.exists():
        raise FileExistsError(str(path))
    partial.parent.mkdir(parents=True, exist_ok=True)
    return partial, partial.open("x", encoding="utf-8", newline="\n")


def publish_partial(partial, canonical):
    if Path(canonical).exists():
        raise FileExistsError(str(canonical))
    os.replace(partial, canonical)


def atomic_write_json(path, value):
    partial, handle = open_partial(path)
    try:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    publish_partial(partial, path)


def implementation_revision(root=ROOT):
    root = Path(root)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", RELEASE_COMMIT, revision],
        cwd=root, check=True,
    )
    subprocess.run(["git", "diff", "--quiet"], cwd=root, check=True)
    subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root, check=True)
    if not revision:
        raise FrozenDesignError("EMPTY_IMPLEMENTATION_REVISION")
    return revision


def validate_config(config, root=ROOT):
    if file_sha256(Path(root) / CONFIG_NAME) != CONFIG_SHA256:
        raise FrozenDesignError("CONFIG_HASH_MISMATCH")
    try:
        local, remote = config["local"], config["remote"]
        valid = (
            local["model"] == "gemma3:270m"
            and local["temperature"] == 0
            and local["max_tokens"] == 256
            and local["keep_alive"] == -1
            and remote["model"] == "openai/gpt-5.6-luna"
            and remote["temperature"] == 0
            and remote["max_tokens"] == 256
            and remote["maximum_attempts"] == 2
            and remote["retry_backoff_seconds"] == 0.25
        )
    except (KeyError, TypeError):
        raise FrozenDesignError("CONFIG_SCHEMA_MISMATCH") from None
    if not valid:
        raise FrozenDesignError("CONFIG_VALUE_MISMATCH")


def verify_model_identity(actual):
    if not isinstance(actual, dict):
        raise FrozenDesignError("MISSING_MODEL_IDENTITY")
    details = actual.get("details") or {}
    normalized = {
        "name": actual.get("name") or actual.get("model"),
        "digest": actual.get("digest"),
        "parameter_size": actual.get("parameter_size") or details.get("parameter_size"),
        "quantization_level": actual.get("quantization_level") or details.get("quantization_level"),
        "format": actual.get("format") or details.get("format"),
        "package_size_bytes": actual.get("package_size_bytes", actual.get("size")),
    }
    if normalized != MODEL_SPEC:
        raise FrozenDesignError("INSTALLED_MODEL_IDENTITY_MISMATCH")
    return normalized


def expected_keys(tasks):
    return [
        (task["task_id"], repetition)
        for task in tasks
        for repetition in range(1, REPETITIONS + 1)
    ]


def validate_rows(rows, tasks, revision):
    if len(rows) != OBSERVATION_COUNT:
        raise FrozenDesignError("OBSERVATION_COUNT_MISMATCH")
    keys = [(row.get("task_id"), row.get("repetition")) for row in rows]
    if keys != expected_keys(tasks) or len(set(keys)) != len(keys):
        raise FrozenDesignError("OBSERVATION_ORDER_MISMATCH")
    for row in rows:
        if (
            row.get("schema_version") != SCHEMA_VERSION
            or row.get("suite_id") != SUITE_ID
            or row.get("plan_sha256") != PLAN_SHA256
            or row.get("benchmark_sha256") != BENCHMARK_SHA256
            or row.get("config_sha256") != CONFIG_SHA256
            or row.get("implementation_revision") != revision
            or not isinstance(row.get("router_request_id"), str)
        ):
            raise FrozenDesignError("OBSERVATION_IDENTITY_MISMATCH")
    generative = [row for row in rows if row["cohort"] != "deterministic"]
    deterministic = [row for row in rows if row["cohort"] == "deterministic"]
    if (
        len(generative) != PROVIDER_OBSERVATION_COUNT
        or len(deterministic) != 30
        or any(not row["local"]["present"] or not row["remote"]["present"] for row in generative)
        or any(row["local"]["present"] or row["remote"]["present"] for row in deterministic)
    ):
        raise FrozenDesignError("PROVIDER_ARM_COMPLETENESS_MISMATCH")


def summary(rows, revision, budget):
    return {
        "schema_version": "runtime_v0_2_prospective_summary_v1",
        "suite_id": SUITE_ID,
        "plan_sha256": PLAN_SHA256,
        "benchmark_sha256": BENCHMARK_SHA256,
        "config_sha256": CONFIG_SHA256,
        "implementation_revision": revision,
        "observation_count": len(rows),
        "runtime_correct_count": sum(bool(row["runtime_correct"]) for row in rows),
        "accepted_error_count": sum(bool(row["accepted_error"]) for row in rows),
        "withheld_count": sum(bool(row["withheld"]) for row in rows),
        "budget": budget.snapshot(),
    }
