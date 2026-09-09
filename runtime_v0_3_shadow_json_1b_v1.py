"""Frozen schema, oracle, budget, and evidence rules for runtime v0.3 shadow JSON 1B V1."""

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

from runtime_contracts import RuntimeRequest, validate_runtime_output


ROOT = Path(__file__).resolve().parent
PLAN_NAME = "RUNTIME_V0_3_SHADOW_JSON_1B_V1_PLAN.md"
BENCHMARK_NAME = "benchmark_runtime_v0_3_shadow_json_1b_v1.json"
CONFIG_NAME = "config_runtime_v0_3_shadow_json_1b_v1.json"
PLAN_SHA256 = "a608ac5b5a5d77061992c75a44425428aa05dbce90b1e1e6a2467da050ec0ee1"
BENCHMARK_SHA256 = "54fd3f5c253dbe0bf7b558c8cba807bfc341c48187df04a2815ec5153b1a60d1"
CONFIG_SHA256 = "0285d0b79dba88c2f6714b1c9742910fd9508b24115e4defa3ee65df87a4192c"
SUITE_ID = "runtime_v0_3_shadow_json_1b_v1"
SCHEMA_VERSION = "runtime_v0_3_shadow_json_1b_observation_v1"
RELEASE_COMMIT = "f67273d04ef9b8a3964ed4371390808bf6ba8ffe"
TASK_COUNT = 40
REPETITIONS = 3
OBSERVATION_COUNT = 120
MAX_REMOTE_LOGICAL_CALLS = 120
MAX_REMOTE_HTTP_ATTEMPTS = 240
MAX_LOCAL_LOGICAL_CALLS = 120
MAX_REPORTED_REMOTE_COST_USD = 0.03
UNREPORTED_FAILURE_COST_RESERVE_USD = 0.001
STRATUM_COUNTS = {
    "flat_scalar": 10,
    "record_selection": 10,
    "type_boundary": 10,
    "nested_collection": 10,
}
MODEL_SPEC = {
    "name": "gemma3:1b",
    "digest": "8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc",
    "parameter_size": "999.89M",
    "quantization_level": "Q4_K_M",
    "format": "gguf",
    "package_size_bytes": 815319791,
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
    unreported_remote_failure_count: int = 0
    reserved_unreported_failure_cost_usd: float = 0.0

    def before_remote(self):
        if self.remote_logical_calls >= MAX_REMOTE_LOGICAL_CALLS:
            raise BudgetExceeded("REMOTE_LOGICAL_CALL_LIMIT")
        if self.local_logical_calls >= MAX_LOCAL_LOGICAL_CALLS:
            raise BudgetExceeded("LOCAL_HEADROOM_UNAVAILABLE")
        if self.remote_http_attempts > MAX_REMOTE_HTTP_ATTEMPTS - 2:
            raise BudgetExceeded("REMOTE_HTTP_ATTEMPT_LIMIT")
        accounted_cost = (
            self.reported_remote_cost_usd
            + self.reserved_unreported_failure_cost_usd
        )
        if accounted_cost > MAX_REPORTED_REMOTE_COST_USD:
            raise BudgetExceeded("REMOTE_REPORTED_COST_LIMIT")

    def after_remote(self, result):
        attempts = getattr(result, "attempt_count", 0)
        retries = getattr(result, "retry_count", None)
        cost = getattr(result, "cost", None)
        success = getattr(result, "success", None)
        if (
            type(success) is not bool
            or type(attempts) is not int
            or not 1 <= attempts <= 2
            or type(retries) is not int
            or retries != attempts - 1
        ):
            raise FrozenDesignError("INVALID_REMOTE_ATTEMPT_COUNT")
        if cost is None:
            if success:
                raise FrozenDesignError("MISSING_SUCCESSFUL_REMOTE_COST")
            self.unreported_remote_failure_count += 1
            self.reserved_unreported_failure_cost_usd += (
                UNREPORTED_FAILURE_COST_RESERVE_USD
            )
        else:
            if (
                type(cost) not in (int, float)
                or isinstance(cost, bool)
                or not math.isfinite(cost)
                or cost < 0
            ):
                raise FrozenDesignError("INVALID_REMOTE_COST")
            self.reported_remote_cost_usd += float(cost)
        self.remote_logical_calls += 1
        self.remote_http_attempts += attempts
        if self.remote_http_attempts > MAX_REMOTE_HTTP_ATTEMPTS:
            raise BudgetExceeded("REMOTE_HTTP_ATTEMPT_LIMIT")

    def before_local(self):
        if self.local_logical_calls >= MAX_LOCAL_LOGICAL_CALLS:
            raise BudgetExceeded("LOCAL_LOGICAL_CALL_LIMIT")

    def after_local(self):
        self.local_logical_calls += 1

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
    fields = {
        "schema_version", "suite_id", "created_date", "task_count",
        "repetitions", "observation_count", "strata", "tasks",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise FrozenDesignError("BENCHMARK_FIELDS_MISMATCH")
    if (
        document["schema_version"] != "runtime_v0_3_shadow_json_1b_benchmark_v1"
        or document["suite_id"] != SUITE_ID
        or document["created_date"] != "2026-09-09"
        or document["task_count"] != TASK_COUNT
        or document["repetitions"] != REPETITIONS
        or document["observation_count"] != OBSERVATION_COUNT
        or document["strata"] != STRATUM_COUNTS
    ):
        raise FrozenDesignError("BENCHMARK_IDENTITY_MISMATCH")
    tasks = document["tasks"]
    if not isinstance(tasks, list) or len(tasks) != TASK_COUNT:
        raise FrozenDesignError("BENCHMARK_COUNT_MISMATCH")
    ids = [task.get("task_id") if isinstance(task, dict) else None for task in tasks]
    if (
        len(set(ids)) != TASK_COUNT
        or any(not isinstance(task_id, str) for task_id in ids)
        or Counter(task.get("stratum") for task in tasks) != Counter(STRATUM_COUNTS)
    ):
        raise FrozenDesignError("TASK_ID_OR_STRATUM_MISMATCH")
    for task in tasks:
        if set(task) != {"task_id", "stratum", "runtime_request", "oracle"}:
            raise FrozenDesignError("TASK_FIELDS_MISMATCH")
        mapping = task["runtime_request"]
        if not isinstance(mapping, dict) or set(mapping) != {
            "schema_version", "task_class", "prompt", "contract"
        }:
            raise FrozenDesignError("RUNTIME_REQUEST_FIELDS_MISMATCH")
        if "oracle" in set(_walk_keys(mapping)):
            raise FrozenDesignError("ORACLE_LEAK_IN_RUNTIME_REQUEST")
        request = RuntimeRequest.from_mapping(mapping)
        if request.task_class != "extract_structured":
            raise FrozenDesignError("TASK_CLASS_MISMATCH")
        contract = request.contract
        if contract["contract_type"] != "structured_json":
            raise FrozenDesignError("CONTRACT_TYPE_MISMATCH")
        oracle_value = task["oracle"]
        if not isinstance(oracle_value, dict) or set(oracle_value) != {
            "oracle_type", "expected_json"
        }:
            raise FrozenDesignError("ORACLE_FIELDS_MISMATCH")
        expected = oracle_value["expected_json"]
        rendered = json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
        if (
            oracle_value["oracle_type"] != "exact_json_value_v1"
            or not isinstance(expected, dict)
            or list(expected) != contract["exact_keys"]
            or validate_runtime_output(contract, rendered).status != "PASS"
        ):
            raise FrozenDesignError("JSON_ORACLE_MISMATCH")
    return tasks, {task["task_id"]: task for task in tasks}


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
        return set(left) == set(right) and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def oracle(task, raw_output):
    if not isinstance(raw_output, str) or raw_output == "":
        return OracleResult(False, error="NO_OUTPUT")
    try:
        parsed = strict_json_loads(_json_candidate(raw_output))
        if not isinstance(parsed, dict):
            return OracleResult(False, parsed, "NOT_JSON_OBJECT")
        return OracleResult(
            _json_equal(parsed, task["oracle"]["expected_json"]), parsed
        )
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


def validate_provider_result(result, arm):
    if result is None or type(getattr(result, "success", None)) is not bool:
        raise FrozenDesignError("INVALID_PROVIDER_RESULT=" + arm)
    text = getattr(result, "text", None)
    error = getattr(result, "error", None)
    total_ms = getattr(result, "total_ms", None)
    if not isinstance(text, str):
        raise FrozenDesignError("INVALID_PROVIDER_TEXT=" + arm)
    if error is not None and not isinstance(error, str):
        raise FrozenDesignError("INVALID_PROVIDER_ERROR=" + arm)
    if result.success and error is not None:
        raise FrozenDesignError("SUCCESS_WITH_PROVIDER_ERROR=" + arm)
    if not result.success and not error:
        raise FrozenDesignError("PROVIDER_FAILURE_WITHOUT_ERROR=" + arm)
    if not result.success and text != "":
        raise FrozenDesignError("PROVIDER_FAILURE_WITH_OUTPUT=" + arm)
    if (
        type(total_ms) not in (int, float)
        or isinstance(total_ms, bool)
        or not math.isfinite(total_ms)
        or total_ms < 0
    ):
        raise FrozenDesignError("INVALID_PROVIDER_LATENCY=" + arm)
    metadata = result.metadata()
    if not isinstance(metadata, dict) or metadata.get("success") is not result.success:
        raise FrozenDesignError("INVALID_PROVIDER_METADATA=" + arm)


def output_paths(root=ROOT):
    root = Path(root)
    prefix = "runtime_v0_3_shadow_json_1b_v1_"
    return {
        "runs": root / (prefix + "runs.jsonl"),
        "telemetry": root / (prefix + "router_telemetry.jsonl"),
        "summary": root / (prefix + "summary.json"),
        "analysis_json": root / (prefix + "analysis.json"),
        "analysis_csv": root / (prefix + "analysis.csv"),
        "failure": root / (prefix + "failure.json"),
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
            local["model"] == "gemma3:1b"
            and local["temperature"] == 0
            and local["max_tokens"] == 256
            and local["keep_alive"] == -1
            and remote["model"] == "openai/gpt-5.6-luna"
            and remote["temperature"] == 0
            and remote["max_tokens"] == 256
            and remote["maximum_attempts"] == 2
            and remote["retry_backoff_seconds"] == 0.25
            and config["routing"]["allow_user_visible_local"] is False
            and config["shadow"]["enabled"] is True
            and config["shadow"]["execute"] is True
            and config["shadow"]["sample_rate"] == 1.0
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


def _contains_text(record):
    forbidden = {"text", "raw_output", "prompt", "final_visible_output"}
    if isinstance(record, dict):
        return any(key in forbidden or _contains_text(value) for key, value in record.items())
    if isinstance(record, list):
        return any(_contains_text(value) for value in record)
    return False


def validate_rows(rows, tasks, revision):
    if len(rows) != OBSERVATION_COUNT:
        raise FrozenDesignError("OBSERVATION_COUNT_MISMATCH")
    keys = [(row.get("task_id"), row.get("repetition")) for row in rows]
    if keys != expected_keys(tasks) or len(set(keys)) != len(keys):
        raise FrozenDesignError("OBSERVATION_ORDER_MISMATCH")
    inventory = {task["task_id"]: task for task in tasks}
    remote_attempts = 0
    reported_remote_cost = 0.0
    unreported_failure_count = 0
    for observation_number, row in enumerate(rows, start=1):
        task = inventory.get(row.get("task_id"))
        decision, telemetry = row.get("router_decision"), row.get("router_telemetry")
        if (
            task is None
            or row.get("schema_version") != SCHEMA_VERSION
            or row.get("suite_id") != SUITE_ID
            or row.get("plan_sha256") != PLAN_SHA256
            or row.get("benchmark_sha256") != BENCHMARK_SHA256
            or row.get("config_sha256") != CONFIG_SHA256
            or row.get("implementation_revision") != revision
            or row.get("model_identity") != MODEL_SPEC
            or row.get("actual_route") != "remote"
            or row.get("stratum") != task["stratum"]
            or row.get("task_class") != "extract_structured"
            or row.get("contract_type") != "structured_json"
            or row.get("actual_trigger") != "SAFE_REMOTE_POLICY"
            or not isinstance(row.get("router_request_id"), str)
            or not isinstance(decision, dict)
            or decision.get("route") != row.get("actual_route")
            or decision.get("reason") != row.get("actual_reason")
            or decision.get("trigger") != row.get("actual_trigger")
            or type(decision.get("total_ms")) not in (int, float)
            or isinstance(decision.get("total_ms"), bool)
            or not math.isfinite(decision.get("total_ms"))
            or decision.get("total_ms") < 0
            or not row.get("local", {}).get("present")
            or not row.get("remote", {}).get("present")
            or not isinstance(telemetry, dict)
            or _contains_text(telemetry)
        ):
            raise FrozenDesignError("OBSERVATION_IDENTITY_MISMATCH")
        shadow = telemetry.get("shadow")
        if (
            type(row["local"].get("success")) is not bool
            or type(row["remote"].get("success")) is not bool
        ):
            raise FrozenDesignError("PROVIDER_SUCCESS_TYPE_MISMATCH")
        local_success = row["local"].get("success") is True
        remote_success = row["remote"].get("success") is True
        if any(
            type(latency) not in (int, float)
            or isinstance(latency, bool)
            or not math.isfinite(latency)
            or latency < 0
            for latency in (
                row["local"].get("total_ms"),
                row["remote"].get("total_ms"),
            )
        ):
            raise FrozenDesignError("PROVIDER_LATENCY_MISMATCH")
        local_raw = row["local"].get("raw_output")
        remote_raw = row["remote"].get("raw_output")
        final_raw = row.get("final_visible_output")
        expected_local_oracle = asdict(oracle(task, local_raw))
        expected_remote_oracle = asdict(oracle(task, remote_raw))
        expected_runtime_oracle = asdict(oracle(task, final_raw))
        expected_local_contract = asdict(
            validate_runtime_output(task["runtime_request"]["contract"], local_raw or "")
        )
        expected_remote_contract = asdict(
            validate_runtime_output(task["runtime_request"]["contract"], remote_raw or "")
        )
        expected_final = (
            remote_raw
            if remote_success and expected_remote_contract["status"] == "PASS"
            else ""
        )
        expected_reason = (
            "SAFE_REMOTE_POLICY"
            if remote_success and expected_remote_contract["status"] == "PASS"
            else "REMOTE_CONTRACT_FAILED" if remote_success else "REMOTE_ERROR"
        )
        if (
            (local_success and not isinstance(local_raw, str))
            or (not local_success and local_raw is not None)
            or (remote_success and not isinstance(remote_raw, str))
            or (not remote_success and remote_raw is not None)
            or final_raw != expected_final
            or row.get("actual_reason") != expected_reason
            or row.get("local_oracle") != expected_local_oracle
            or row.get("remote_oracle") != expected_remote_oracle
            or row.get("runtime_oracle") != expected_runtime_oracle
            or row.get("runtime_correct") is not expected_runtime_oracle["correct"]
            or row.get("runtime_accepted_error")
            is not (bool(final_raw) and not expected_runtime_oracle["correct"])
            or row.get("local_contract") != expected_local_contract
            or row.get("remote_contract") != expected_remote_contract
        ):
            raise FrozenDesignError("OBSERVATION_OUTCOME_MISMATCH")
        remote_metadata = {
            key: value for key, value in row["remote"].items()
            if key not in {"present", "raw_output"}
        }
        local_metadata = {
            key: value for key, value in row["local"].items()
            if key not in {"present", "raw_output"}
        }
        if (
            not isinstance(shadow, dict)
            or shadow.get("selected") is not True
            or shadow.get("executed") is not True
            or telemetry.get("decision") != decision
        ):
            raise FrozenDesignError("SHADOW_TELEMETRY_MISMATCH")
        if telemetry.get("remote") != remote_metadata:
            raise FrozenDesignError("REMOTE_RESULT_TELEMETRY_MISMATCH")
        if any(shadow.get(key) != value for key, value in local_metadata.items()):
            raise FrozenDesignError("LOCAL_RESULT_TELEMETRY_MISMATCH")
        if local_success:
            if (
                shadow.get("reason") != "MEASURED"
                or shadow.get("validator") != row.get("local_contract")
            ):
                raise FrozenDesignError("SHADOW_TELEMETRY_MISMATCH")
        elif (
            shadow.get("validator") is not None
            or shadow.get("reason") != row["local"].get("error")
        ):
            raise FrozenDesignError("SHADOW_FAILURE_TELEMETRY_MISMATCH")
        if remote_success:
            if telemetry.get("remote_validator") != row.get("remote_contract"):
                raise FrozenDesignError("REMOTE_TELEMETRY_MISMATCH")
        elif "remote_validator" in telemetry:
            raise FrozenDesignError("REMOTE_FAILURE_TELEMETRY_MISMATCH")
        attempts = row["remote"].get("attempt_count")
        retries = row["remote"].get("retry_count")
        cost = row["remote"].get("cost")
        budget = row.get("budget_after_observation")
        if (
            type(attempts) is not int
            or not 1 <= attempts <= 2
            or type(retries) is not int
            or retries != attempts - 1
            or remote_success
            and cost is None
            or cost is not None
            and (
                type(cost) not in (int, float)
                or isinstance(cost, bool)
                or not math.isfinite(cost)
                or cost < 0
            )
            or not isinstance(budget, dict)
            or set(budget) != {
                "local_logical_calls",
                "remote_logical_calls",
                "remote_http_attempts",
                "reported_remote_cost_usd",
                "unreported_remote_failure_count",
                "reserved_unreported_failure_cost_usd",
            }
        ):
            raise FrozenDesignError("OBSERVATION_BUDGET_MISMATCH")
        remote_attempts += attempts
        if cost is None:
            unreported_failure_count += 1
        else:
            reported_remote_cost += float(cost)
        reserved_cost = (
            unreported_failure_count * UNREPORTED_FAILURE_COST_RESERVE_USD
        )
        if (
            budget["local_logical_calls"] != observation_number
            or budget["remote_logical_calls"] != observation_number
            or budget["remote_http_attempts"] != remote_attempts
            or not math.isclose(
                budget["reported_remote_cost_usd"],
                reported_remote_cost,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
            or budget["unreported_remote_failure_count"]
            != unreported_failure_count
            or not math.isclose(
                budget["reserved_unreported_failure_cost_usd"],
                reserved_cost,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        ):
            raise FrozenDesignError("OBSERVATION_BUDGET_MISMATCH")


def summary(rows, revision, budget):
    return {
        "schema_version": "runtime_v0_3_shadow_json_1b_summary_v1",
        "suite_id": SUITE_ID,
        "plan_sha256": PLAN_SHA256,
        "benchmark_sha256": BENCHMARK_SHA256,
        "config_sha256": CONFIG_SHA256,
        "implementation_revision": revision,
        "observation_count": len(rows),
        "runtime_correct_count": sum(bool(row["runtime_correct"]) for row in rows),
        "runtime_accepted_error_count": sum(bool(row["runtime_accepted_error"]) for row in rows),
        "local_accepted_error_count": sum(
            row["local_contract"]["status"] == "PASS"
            and not row["local_oracle"]["correct"] for row in rows
        ),
        "local_provider_success_count": sum(
            row["local"]["success"] is True for row in rows
        ),
        "remote_provider_success_count": sum(
            row["remote"]["success"] is True for row in rows
        ),
        "local_provider_errors": dict(Counter(
            row["local"]["error"] for row in rows
            if row["local"]["success"] is False
        )),
        "remote_provider_errors": dict(Counter(
            row["remote"]["error"] for row in rows
            if row["remote"]["success"] is False
        )),
        "budget": budget.snapshot(),
    }
