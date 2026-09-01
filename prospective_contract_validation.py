"""Frozen prospective contract-validation implementation.

The contract path in this module is deliberately isolated from benchmark and
prompt data.  ``contract_validate(contract, raw_output)`` has exactly those
two logical inputs.  Oracle evaluation and gate analysis are separate paths.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable

import validators


ROOT = Path(__file__).resolve().parent
PLAN_PATH = ROOT / "PROSPECTIVE_CONTRACT_VALIDATION_V1_PLAN.md"
SUITE_PATH = ROOT / "benchmark_prospective_contract_v1.json"
CONTRACTS_PATH = ROOT / "validator_contracts_prospective_v1.json"

PLAN_SHA256 = "dded9acc6dc40e2b93d666ba27db07a0200a0c2907b360e467540b29d981a9aa"
SUITE_SHA256 = "661e364d5fc11bd17f8bddc5326d77853fe1d2dae2d7ed5eb7d39c26af99b040"
CONTRACTS_SHA256 = "a7bf6044333c0dcb63024cb0086bda0a0deaaabff07a2621067c766b35f4fbd9"
SUITE_ID = "prospective_contract_validation_v1"
SCHEMA_VERSION = "prospective_contract_validation_v1"
TASK_COUNT = 40
REPETITIONS = 5
OBSERVATIONS_PER_MODEL = TASK_COUNT * REPETITIONS
PRIMARY_COHORTS = ("structural_schema", "format_conformance")
MODEL_ORDER = ("gemma3:270m", "gemma3:1b", "gemma3:4b")
MAXIMUM_TTFT_MS = 8000
MINIMUM_GENERATION_RATE = 1.5
BOOTSTRAP_SEED = "20260831"
BOOTSTRAP_DRAWS = 10000

MODEL_SPECS = {
    "gemma3:270m": {
        "name": "gemma3:270m",
        "digest": "e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be",
        "parameter_size": "268.10M",
        "quantization_level": "Q8_0",
        "format": "gguf",
        "family": "gemma3",
        "package_size_bytes": 291554930,
    },
    "gemma3:1b": {
        "name": "gemma3:1b",
        "digest": "8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc",
        "parameter_size": "999.89M",
        "quantization_level": "Q4_K_M",
        "format": "gguf",
        "family": "gemma3",
        "package_size_bytes": 815319791,
    },
    "gemma3:4b": {
        "name": "gemma3:4b",
        "digest": "a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a",
        "parameter_size": "4.3B",
        "quantization_level": "Q4_K_M",
        "format": "gguf",
        "family": "gemma3",
        "package_size_bytes": 3338801804,
    },
}

MODEL_IDENTITY_SOURCE_PATHS = {
    "scaling_audit": ROOT / "LOCAL_MODEL_SCALING_V1_AUDIT.md",
    "scaling_analysis": ROOT / "local_model_scaling_v1.json",
}
MODEL_IDENTITY_SOURCE_SHA256 = {
    "scaling_audit": "ed70eb18229c2a5aadab1999ae5855406ff202ccea026ff0372311409608f1ee",
    "scaling_analysis": "e93fc2be593256ffce0e7f5dcd587a21c7916d6611651dc1c626c285beb7e0ca",
}

EVIDENCE_PATHS = {
    "gemma3:270m": ROOT / "benchmark_prospective_contract_v1_gemma3_270m.jsonl",
    "gemma3:1b": ROOT / "benchmark_prospective_contract_v1_gemma3_1b.jsonl",
    "gemma3:4b": ROOT / "benchmark_prospective_contract_v1_gemma3_4b.jsonl",
}
SUMMARY_PATHS = {
    "gemma3:270m": ROOT / "benchmark_prospective_contract_v1_gemma3_270m_summary.json",
    "gemma3:1b": ROOT / "benchmark_prospective_contract_v1_gemma3_1b_summary.json",
    "gemma3:4b": ROOT / "benchmark_prospective_contract_v1_gemma3_4b_summary.json",
}
ANALYSIS_JSON_PATH = ROOT / "prospective_contract_validation_v1_analysis.json"
ANALYSIS_CSV_PATH = ROOT / "prospective_contract_validation_v1_analysis.csv"

FORBIDDEN_CONTRACT_NAMES = frozenset({
    "expected", "oracle", "oracle_correct", "normalized_output",
    "benchmark_validator", "model_output", "answer", "reference_answer",
    "gold", "target", "expected_value", "oracle_value", "correct_output",
    "semantic_value", "supplied_field_values", "ordered_fields", "items",
})
JSON_TYPE_NAMES = frozenset({"boolean", "number", "string", "array", "object", "null"})
CONTRACT_TYPES = frozenset({
    "structured_json", "json_format", "bullet_format", "label_format",
    "classification_labels", "deterministic_executor",
})
OPERATIONS = frozenset({
    "rotate_left_one", "rotate_right_two", "remove_vowels",
    "replace_letter_e_with_7", "collapse_whitespace_runs", "swap_ascii_case",
    "remove_hyphens", "sort_codepoints_ascending", "duplicate_final_character",
    "alphabetize_words",
})


class FrozenDesignError(ValueError):
    """A frozen design or its authenticated schema is invalid."""


class ContractSchemaError(FrozenDesignError):
    """A contract document or declaration is invalid."""


@dataclass(frozen=True)
class ContractResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class GateResult:
    survived: bool
    reason: str


@dataclass(frozen=True)
class ModelIdentity:
    name: str
    digest: str
    parameter_size: str
    quantization_level: str
    format: str
    family: str
    package_size_bytes: int

    def as_dict(self):
        return {
            "name": self.name,
            "digest": self.digest,
            "parameter_size": self.parameter_size,
            "quantization_level": self.quantization_level,
            "format": self.format,
            "family": self.family,
            "package_size_bytes": self.package_size_bytes,
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def authenticate_model_identity_sources():
    actual = {
        name: file_sha256(path)
        for name, path in MODEL_IDENTITY_SOURCE_PATHS.items()
    }
    if actual != MODEL_IDENTITY_SOURCE_SHA256:
        raise FrozenDesignError(
            "model-identity source SHA-256 mismatch: "
            + json.dumps({"expected": MODEL_IDENTITY_SOURCE_SHA256, "actual": actual}, sort_keys=True)
        )
    return dict(actual)


def implementation_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise FrozenDesignError("unable to read implementation Git revision") from exc


def _strict_json_loads(text: str):
    def reject_duplicate_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value

    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=reject_duplicate_pairs,
        parse_constant=reject_constant,
    )


def _ensure_finite(value):
    if type(value) in (int, float):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite JSON number")
    elif isinstance(value, dict):
        for item in value.values():
            _ensure_finite(item)
    elif isinstance(value, list):
        for item in value:
            _ensure_finite(item)


def _json_type(value):
    if type(value) is bool:
        return "boolean"
    if type(value) in (int, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return None


def _ascii_lower(value: str) -> str:
    return value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))


def _line_normalize(raw_output: str) -> str:
    if not isinstance(raw_output, str):
        raise ValueError("INVALID_OUTPUT_TYPE")
    if "\r" in raw_output.replace("\r\n", ""):
        raise ValueError("LONE_CR")
    value = raw_output.replace("\r\n", "\n")
    if value.endswith("\n"):
        value = value[:-1]
    return value


def _json_candidate(raw_output: str) -> str:
    value = _line_normalize(raw_output)
    lines = value.split("\n")
    if lines and lines[0] in ("```", "```json"):
        if len(lines) < 2 or lines[-1] != "```":
            raise ValueError("INCOMPLETE_OUTER_FENCE")
        body = lines[1:-1]
        if any("```" in line for line in body):
            raise ValueError("NESTED_OR_MULTIPLE_FENCE")
        return "\n".join(body)
    if any("```" in line for line in lines):
        raise ValueError("INCOMPLETE_OR_SURROUNDING_FENCE")
    return value


def _parse_json_object(raw_output: str):
    try:
        value = _strict_json_loads(_json_candidate(raw_output))
        _ensure_finite(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("NOT_A_JSON_OBJECT")
    return value


def _declared_types(contract: dict[str, Any], key: str) -> set[str]:
    declared = contract["explicit_types"][key]
    return set(declared) if isinstance(declared, list) else {declared}


def _validate_json_shape(contract: dict[str, Any], raw_output: str) -> ContractResult:
    try:
        value = _parse_json_object(raw_output)
    except ValueError as exc:
        return ContractResult(False, str(exc))
    keys = contract["exact_keys"]
    if set(value) != set(keys):
        return ContractResult(False, "KEY_SET_MISMATCH")
    for key in keys:
        if _json_type(value[key]) not in _declared_types(contract, key):
            return ContractResult(False, "JSON_VALUE_TYPE_MISMATCH")
    return ContractResult(True, "ACCEPTED")


def _fence_lines(contract: dict[str, Any], value: str):
    lines = value.split("\n")
    fence = contract.get("fence_rule", "forbidden")
    if fence == "forbidden":
        if any("```" in line for line in lines):
            raise ValueError("FENCE_FORBIDDEN")
        return lines, False
    if not isinstance(fence, dict) or fence.get("required") is not True:
        raise ValueError("INVALID_FENCE_RULE")
    language = fence.get("language")
    opening = "```" + language
    if len(lines) < 2 or lines[0] != opening or lines[-1] != "```":
        raise ValueError("OUTER_FENCE_MISMATCH")
    body = lines[1:-1]
    if any("```" in line for line in body):
        raise ValueError("NESTED_OR_MULTIPLE_FENCE")
    return body, True


def _validate_bullet_shape(contract: dict[str, Any], raw_output: str) -> ContractResult:
    try:
        value = _line_normalize(raw_output)
        lines, _ = _fence_lines(contract, value)
    except ValueError as exc:
        return ContractResult(False, str(exc))
    if len(lines) != contract["line_count"]:
        return ContractResult(False, "LINE_COUNT_MISMATCH")
    prefix = contract["marker"] + contract["separator"]
    if any(not line.startswith(prefix) or not line[len(prefix):] for line in lines):
        return ContractResult(False, "BULLET_SHAPE_MISMATCH")
    return ContractResult(True, "ACCEPTED")


def _validate_label_shape(contract: dict[str, Any], raw_output: str) -> ContractResult:
    try:
        value = _line_normalize(raw_output)
        lines, _ = _fence_lines(contract, value)
    except ValueError as exc:
        return ContractResult(False, str(exc))
    if len(lines) != contract["line_count"]:
        return ContractResult(False, "LINE_COUNT_MISMATCH")
    separator = contract["separator"]
    if any(not line or line.count(separator) != 1 for line in lines):
        return ContractResult(False, "LABEL_SEPARATOR_MISMATCH")
    return ContractResult(True, "ACCEPTED")


def _operation(source: str, operation: str) -> str:
    if operation == "rotate_left_one":
        return source[1:] + source[:1]
    if operation == "rotate_right_two":
        return source[-2:] + source[:-2]
    if operation == "remove_vowels":
        return "".join(char for char in source if char not in "aeiou")
    if operation == "replace_letter_e_with_7":
        return source.replace("e", "7")
    if operation == "collapse_whitespace_runs":
        return re.sub(r"\s+", " ", source)
    if operation == "swap_ascii_case":
        result = []
        for char in source:
            if "A" <= char <= "Z":
                result.append(char.lower())
            elif "a" <= char <= "z":
                result.append(char.upper())
            else:
                result.append(char)
        return "".join(result)
    if operation == "remove_hyphens":
        return source.replace("-", "")
    if operation == "sort_codepoints_ascending":
        return "".join(sorted(source, key=ord))
    if operation == "duplicate_final_character":
        return source + source[-1]
    if operation == "alphabetize_words":
        return " ".join(sorted(re.split(r" +", source)))
    raise ValueError("UNKNOWN_OPERATION")


def _failure_error(error):
    kind = str(error or "GENERATION_FAILED")
    messages = {
        "LOCAL_TIMEOUT": "local generation request timed out",
        "RETURNED_MODEL_IDENTITY_MISSING": "generation response did not identify the returned model",
    }
    return {"kind": kind, "message": messages.get(kind, kind)}


def _validate_contract_shape(contract: dict[str, Any]) -> str:
    if not isinstance(contract, dict):
        raise ContractSchemaError("MALFORMED_CONTRACT")
    contract_type = contract.get("contract_type")
    if contract_type not in CONTRACT_TYPES:
        raise ContractSchemaError("UNKNOWN_CONTRACT_TYPE")
    common = {"task_id", "cohort", "contract_type"}
    allowed = {
        "structured_json": common | {"exact_keys", "explicit_types"},
        "json_format": common | {"exact_keys", "explicit_types"},
        "bullet_format": common | {"line_count", "marker", "separator", "fence_rule"},
        "label_format": common | {"line_count", "separator", "separator_rule", "fence_rule"},
        "classification_labels": common | {"permitted_labels"},
        "deterministic_executor": common | {"role", "source_literal", "operation"},
    }[contract_type]
    if set(contract) != allowed:
        raise ContractSchemaError("CONTRACT_FIELDS_MISMATCH")
    if any(not isinstance(contract[key], str) or not contract[key] for key in common):
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    if contract_type == "structured_json" or contract_type == "json_format":
        keys = contract["exact_keys"]
        types = contract["explicit_types"]
        if (not isinstance(keys, list) or not keys or
                any(not isinstance(key, str) or not key for key in keys) or
                len(set(keys)) != len(keys) or
                not isinstance(types, dict) or set(types) != set(keys)):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        for value in types.values():
            values = value if isinstance(value, list) else [value]
            if not values or any(item not in JSON_TYPE_NAMES for item in values):
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        expected_class = "extract_structured" if contract_type == "structured_json" else "format_json"
        if contract["cohort"] != "structural_schema":
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        if contract_type == "structured_json" and expected_class != "extract_structured":
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    elif contract_type == "bullet_format":
        if contract["cohort"] != "format_conformance" or type(contract["line_count"]) is not int or contract["line_count"] <= 0:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        if not isinstance(contract["marker"], str) or not contract["marker"] or not isinstance(contract["separator"], str) or not contract["separator"]:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        _validate_fence_rule(contract["fence_rule"])
    elif contract_type == "label_format":
        if contract["cohort"] != "format_conformance" or type(contract["line_count"]) is not int or contract["line_count"] <= 0:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        if not isinstance(contract["separator"], str) or not contract["separator"] or contract["separator_rule"] != "exactly_once_per_line":
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        _validate_fence_rule(contract["fence_rule"])
    elif contract_type == "classification_labels":
        if contract["cohort"] != "label_conformance":
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        labels = contract["permitted_labels"]
        if (not isinstance(labels, list) or not labels or len(set(labels)) != len(labels) or
                any(not isinstance(label, str) or not label or label != _ascii_lower(label) for label in labels)):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    elif contract_type == "deterministic_executor":
        if (contract["cohort"] != "deterministic_executor" or
                contract["role"] != "executable_task" or
                not isinstance(contract["source_literal"], str) or
                contract["operation"] not in OPERATIONS):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    return contract_type


def _validate_fence_rule(rule):
    if rule == "forbidden":
        return
    if (not isinstance(rule, dict) or rule.get("required") is not True or
            rule.get("outer_only") is not True or not isinstance(rule.get("language"), str) or
            not rule["language"] or "```" in rule["language"]):
        raise ContractSchemaError("INVALID_FENCE_RULE")


def _reject_forbidden_names(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or key.lower() in FORBIDDEN_CONTRACT_NAMES:
                raise ContractSchemaError("FORBIDDEN_CONTRACT_FIELD")
            _reject_forbidden_names(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_names(nested)


def validate_contract_document(document: dict[str, Any], task_inventory: dict[str, dict[str, Any]] | None = None):
    _reject_forbidden_names(document)
    if not isinstance(document, dict) or set(document) != {"schema_version", "suite_id", "contract_count", "contracts"}:
        raise ContractSchemaError("CONTRACT_DOCUMENT_FIELDS_MISMATCH")
    if document["schema_version"] != "validator_contracts_prospective_v1" or document["suite_id"] != SUITE_ID:
        raise ContractSchemaError("CONTRACT_DOCUMENT_IDENTITY_MISMATCH")
    contracts = document["contracts"]
    if type(document["contract_count"]) is not int or document["contract_count"] != 40 or not isinstance(contracts, list) or len(contracts) != 40:
        raise ContractSchemaError("CONTRACT_COUNT_MISMATCH")
    ids = set()
    ordered_ids = []
    for contract in contracts:
        _validate_contract_shape(contract)
        task_id = contract["task_id"]
        if task_id in ids:
            raise ContractSchemaError("DUPLICATE_TASK_ID")
        ids.add(task_id)
        ordered_ids.append(task_id)
        if task_inventory is not None:
            task = task_inventory.get(task_id)
            if task is None or task["cohort"] != contract["cohort"] or task["contract_type"] != contract["contract_type"]:
                raise ContractSchemaError("CONTRACT_TASK_MISMATCH")
    if task_inventory is not None and ids != set(task_inventory):
        raise ContractSchemaError("CONTRACT_TASK_ID_SET_MISMATCH")
    if task_inventory is not None and ordered_ids != list(task_inventory):
        raise ContractSchemaError("CONTRACT_TASK_ORDER_MISMATCH")
    return document


def contract_validate(contract: dict[str, Any], raw_output: str) -> ContractResult:
    """Validate contract conformance using only ``contract`` and ``raw_output``."""
    try:
        contract_type = _validate_contract_shape(contract)
    except ContractSchemaError as exc:
        return ContractResult(False, exc.args[0])
    if contract_type in ("structured_json", "json_format"):
        return _validate_json_shape(contract, raw_output)
    if contract_type == "bullet_format":
        return _validate_bullet_shape(contract, raw_output)
    if contract_type == "label_format":
        return _validate_label_shape(contract, raw_output)
    if contract_type == "classification_labels":
        try:
            value = _line_normalize(raw_output)
        except ValueError as exc:
            return ContractResult(False, str(exc))
        lines = value.split("\n")
        if len(lines) != 1 or not lines[0]:
            return ContractResult(False, "CLASSIFICATION_LINE_COUNT_MISMATCH")
        candidate = _ascii_lower(lines[0].strip(" \t"))
        if candidate in contract["permitted_labels"]:
            return ContractResult(True, "ACCEPTED")
        return ContractResult(False, "LABEL_NOT_PERMITTED")
    if contract_type == "deterministic_executor":
        try:
            value = _line_normalize(raw_output)
            expected = _operation(contract["source_literal"], contract["operation"])
        except (ValueError, IndexError) as exc:
            return ContractResult(False, str(exc))
        return ContractResult(value == expected, "ACCEPTED" if value == expected else "EXECUTOR_MISMATCH")
    return ContractResult(False, "UNKNOWN_CONTRACT_TYPE")


def _values_equal(actual, expected) -> bool:
    if type(actual) is bool or type(expected) is bool:
        return type(actual) is type(expected) and actual == expected
    if type(actual) in (int, float) and type(expected) in (int, float):
        return math.isfinite(actual) and math.isfinite(expected) and actual == expected
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return set(actual) == set(expected) and all(_values_equal(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(_values_equal(a, e) for a, e in zip(actual, expected))
    return actual == expected


def _format_oracle_normalize(contract: dict[str, Any], raw_output: str) -> str:
    value = _line_normalize(raw_output)
    lines, fenced = _fence_lines(contract, value)
    if len(lines) != contract["line_count"] or any(not line for line in lines):
        raise ValueError("FORMAT_SHAPE_MISMATCH")
    if contract["contract_type"] == "bullet_format":
        prefix = contract["marker"] + contract["separator"]
        if any(not line.startswith(prefix) for line in lines):
            raise ValueError("BULLET_SHAPE_MISMATCH")
    else:
        separator = contract["separator"]
        if any(line.count(separator) != 1 for line in lines):
            raise ValueError("LABEL_SEPARATOR_MISMATCH")
    body = "\n".join(lines)
    if not fenced:
        return body
    rule = contract["fence_rule"]
    return "```" + rule["language"] + "\n" + body + "\n```"


def oracle_normalize(task: dict[str, Any], raw_output: str) -> str | dict[str, Any] | None:
    """Normalize a model response for oracle comparison; separate from gates."""
    try:
        if task["contract_type"] in ("structured_json", "json_format"):
            return _parse_json_object(raw_output)
        if task["contract_type"] in ("bullet_format", "label_format"):
            contract = task["_contract"]
            return _format_oracle_normalize(contract, raw_output)
        if task["contract_type"] == "classification_labels":
            value = _line_normalize(raw_output)
            lines = value.split("\n")
            if len(lines) != 1 or not lines[0]:
                return None
            return _ascii_lower(lines[0].strip(" \t"))
        if task["contract_type"] == "deterministic_executor":
            return _line_normalize(raw_output)
    except (TypeError, ValueError, IndexError):
        return None
    raise ValueError("UNKNOWN_TASK_CONTRACT_TYPE")


def oracle_correct(task: dict[str, Any], raw_output: str, contract: dict[str, Any]) -> tuple[Any, bool]:
    task_for_oracle = {**task, "_contract": contract}
    normalized = oracle_normalize(task_for_oracle, raw_output)
    if task["contract_type"] in ("structured_json", "json_format"):
        correct = normalized is not None and _values_equal(normalized, task["expected"])
    elif task["contract_type"] in ("bullet_format", "label_format", "classification_labels"):
        try:
            expected = oracle_normalize(task_for_oracle, task["expected"])
        except (TypeError, ValueError):
            expected = None
        correct = normalized == expected
    elif task["contract_type"] == "deterministic_executor":
        correct = normalized == _operation(contract["source_literal"], contract["operation"])
    else:
        raise ValueError("UNKNOWN_TASK_CONTRACT_TYPE")
    return normalized, correct


def load_frozen_inputs(plan_path=PLAN_PATH, suite_path=SUITE_PATH, contracts_path=CONTRACTS_PATH):
    paths_and_hashes = (
        (plan_path, PLAN_SHA256, "plan"),
        (suite_path, SUITE_SHA256, "suite"),
        (contracts_path, CONTRACTS_SHA256, "contracts"),
    )
    for path, expected, label in paths_and_hashes:
        if file_sha256(Path(path)) != expected:
            raise FrozenDesignError(f"frozen {label} SHA-256 mismatch")
    try:
        suite = _strict_json_loads(Path(suite_path).read_text(encoding="utf-8"))
        contracts_doc = _strict_json_loads(Path(contracts_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise FrozenDesignError("malformed frozen JSON design file") from exc
    tasks = suite.get("tasks") if isinstance(suite, dict) else None
    if not isinstance(suite, dict) or suite.get("suite_id") != SUITE_ID or suite.get("version") != 1 or suite.get("task_count") != TASK_COUNT or suite.get("repetitions_per_task") != REPETITIONS or not isinstance(tasks, list) or len(tasks) != TASK_COUNT:
        raise FrozenDesignError("frozen suite identity or count mismatch")
    expected_ids = (
        [f"pcv1_a_schema_{i:02d}" for i in range(1, 11)]
        + [f"pcv1_b_format_{i:02d}" for i in range(1, 11)]
        + [f"pcv1_c_label_{i:02d}" for i in range(1, 11)]
        + [f"pcv1_d_exec_{i:02d}" for i in range(1, 11)]
    )
    if [task.get("task_id") for task in tasks] != expected_ids:
        raise FrozenDesignError("frozen task order or IDs mismatch")
    required = {"task_id", "cohort", "task_class", "contract_type", "repetitions", "prompt", "expected"}
    for task in tasks:
        if not required <= set(task) or task["repetitions"] != REPETITIONS:
            raise FrozenDesignError(f"frozen task schema mismatch: {task.get('task_id')}")
    cohorts = Counter(task["cohort"] for task in tasks)
    if cohorts != Counter({"structural_schema": 10, "format_conformance": 10, "label_conformance": 10, "deterministic_executor": 10}):
        raise FrozenDesignError("frozen cohort counts mismatch")
    task_inventory = {task["task_id"]: task for task in tasks}
    validate_contract_document(contracts_doc, task_inventory)
    contracts = {contract["task_id"]: contract for contract in contracts_doc["contracts"]}
    operation_phrases = {
        "rotate_left_one": "rotate_left_one",
        "rotate_right_two": "rotate_right_two",
        "remove_vowels": "remove_vowels",
        "replace_letter_e_with_7": "replace_letter_e_with_7",
        "collapse_whitespace_runs": "Collapse each run of whitespace",
        "swap_ascii_case": "Swap the ASCII case",
        "remove_hyphens": "remove_hyphens",
        "sort_codepoints_ascending": "ascending code-point order",
        "duplicate_final_character": "duplicate_final_character",
        "alphabetize_words": "Alphabetize the two words",
    }
    for task in tasks:
        contract = contracts[task["task_id"]]
        if task["cohort"] == "deterministic_executor":
            if contract["source_literal"] not in task["prompt"]:
                raise FrozenDesignError(f"D source literal mismatch: {task['task_id']}")
            if operation_phrases[contract["operation"]] not in task["prompt"]:
                raise FrozenDesignError(f"D operation mismatch: {task['task_id']}")
    return suite, task_inventory, contracts


def public_identity(model: str) -> dict[str, Any]:
    if model not in MODEL_SPECS:
        raise FrozenDesignError(f"unknown model: {model}")
    return dict(MODEL_SPECS[model])


def verify_model_identity(actual: dict[str, Any], model: str) -> dict[str, Any]:
    expected = public_identity(model)
    normalized = {
        "name": actual.get("name") or actual.get("model"),
        "digest": actual.get("digest"),
        "parameter_size": actual.get("parameter_size") or (actual.get("details") or {}).get("parameter_size"),
        "quantization_level": actual.get("quantization_level") or (actual.get("details") or {}).get("quantization_level"),
        "format": actual.get("format") or (actual.get("details") or {}).get("format"),
        "family": actual.get("family") or (actual.get("details") or {}).get("family"),
        "package_size_bytes": actual.get("package_size_bytes", actual.get("size")),
    }
    authenticated_fields = (
        "name", "digest", "parameter_size", "quantization_level", "format",
        "package_size_bytes",
    )
    if any(normalized[field] != expected[field] for field in authenticated_fields):
        raise FrozenDesignError(
            "model identity mismatch: "
            + json.dumps({"expected": expected, "actual": normalized}, sort_keys=True)
        )
    return normalized


def legacy_baseline_gate(record: dict[str, Any], task: dict[str, Any]) -> GateResult:
    if not bool(record.get("success")):
        return GateResult(False, "GENERATION_FAILED")
    ttft = record.get("ttft_ms")
    if ttft is not None and ttft > MAXIMUM_TTFT_MS:
        return GateResult(False, "TTFT_EXCEEDED")
    rate = record.get("tokens_per_second")
    if rate is not None and rate < MINIMUM_GENERATION_RATE:
        return GateResult(False, "GENERATION_TOO_SLOW")
    result = validators.validate(task["task_class"], task["prompt"], record.get("raw_output", ""))
    if result.status == validators.FAIL:
        return GateResult(False, "VALIDATOR_FAILED")
    return GateResult(True, "SURVIVED")


def counterfactual_gate(record: dict[str, Any], task: dict[str, Any]) -> bool:
    if task["cohort"] == "deterministic_executor":
        return bool(record.get("baseline_gate_survived")) and bool(record.get("executor_accept"))
    return bool(record.get("baseline_gate_survived")) and bool(record.get("contract_accept"))


def make_result_row(task, contract, raw_output, result, model, returned_model, identity, revision, residency, source_hashes=None):
    success = bool(result.success)
    raw = result.text if success and isinstance(result.text, str) else None
    if raw is None:
        normalized, correct = None, False
        contract_result = ContractResult(False, "NO_OUTPUT")
    else:
        normalized, correct = oracle_correct(task, raw, contract)
        contract_result = contract_validate(contract, raw)
    baseline = legacy_baseline_gate({
        "success": success,
        "ttft_ms": result.ttft_ms,
        "tokens_per_second": result.tokens_per_second,
        "raw_output": raw or "",
    }, task)
    executor_accept = contract_result.accepted if task["cohort"] == "deterministic_executor" else False
    contract_accept = executor_accept if task["cohort"] == "deterministic_executor" else contract_result.accepted
    row = {
        "schema_version": SCHEMA_VERSION,
        "suite_id": SUITE_ID,
        "plan_sha256": PLAN_SHA256,
        "benchmark_sha256": SUITE_SHA256,
        "contracts_sha256": CONTRACTS_SHA256,
        "implementation_revision": revision,
        "provider": "ollama",
        "requested_model": model,
        "returned_model": returned_model,
        "model_identity": identity,
        "model_identity_source_sha256": dict(source_hashes or MODEL_IDENTITY_SOURCE_SHA256),
        "task_id": task["task_id"],
        "rep": task.get("_rep"),
        "task_class": task["task_class"],
        "cohort": task["cohort"],
        "contract_type": task["contract_type"],
        "raw_output": raw,
        "normalized_output": normalized,
        "oracle_correct": bool(correct),
        "executor_accept": bool(executor_accept),
        "contract_accept": bool(contract_accept),
        "contract_reason": contract_result.reason,
        "baseline_gate_survived": baseline.survived,
        "baseline_reason": baseline.reason,
        "counterfactual_gate_survived": counterfactual_gate({
            "baseline_gate_survived": baseline.survived,
            "contract_accept": contract_accept,
            "executor_accept": executor_accept,
        }, task),
        "success": success,
        "task_success": success,
        "ttft_ms": result.ttft_ms,
        "total_ms": result.total_ms,
        "tokens_per_second": result.tokens_per_second,
        "model_residency": residency,
        "error": None if success else _failure_error(result.error),
    }
    return row


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


TRANSITION_KEYS = tuple(
    f"baseline_{baseline}__counterfactual_{counterfactual}__oracle_{oracle}"
    for baseline in ("survive", "fail")
    for counterfactual in ("survive", "fail")
    for oracle in ("correct", "incorrect")
)


def _assert_metrics_invariants(metrics):
    assert metrics["counterfactual_gate_survived_count"] <= metrics["baseline_gate_survived_count"]
    assert metrics["newly_admitted_incorrect_count"] == 0
    transitions = metrics["transition_counts"]
    assert transitions["baseline_fail__counterfactual_survive__oracle_correct"] == 0
    assert transitions["baseline_fail__counterfactual_survive__oracle_incorrect"] == 0
    assert metrics["false_accepts_caught_count"] + metrics["false_accepts_remaining_count"] == metrics["baseline_false_accept_count"]
    assert metrics["counterfactual_false_accept_count"] == metrics["false_accepts_remaining_count"]
    assert metrics["newly_rejected_correct_count"] <= metrics["baseline_correct_survivor_count"]
    assert sum(transitions.values()) == metrics["observation_count"]


def metrics_for_rows(rows: Iterable[dict[str, Any]], scope_name="scope"):
    rows = list(rows)
    transitions = {key: 0 for key in TRANSITION_KEYS}
    for row in rows:
        baseline = "survive" if row["baseline_gate_survived"] else "fail"
        counterfactual = "survive" if row["counterfactual_gate_survived"] else "fail"
        oracle = "correct" if row["oracle_correct"] else "incorrect"
        transitions[f"baseline_{baseline}__counterfactual_{counterfactual}__oracle_{oracle}"] += 1
    baseline_false = sum(row["baseline_gate_survived"] and not row["oracle_correct"] for row in rows)
    caught = sum(row["baseline_gate_survived"] and not row["oracle_correct"] and not row["counterfactual_gate_survived"] for row in rows)
    remaining = sum(row["baseline_gate_survived"] and row["counterfactual_gate_survived"] and not row["oracle_correct"] for row in rows)
    newly_admitted = sum(not row["baseline_gate_survived"] and row["counterfactual_gate_survived"] and not row["oracle_correct"] for row in rows)
    newly_rejected = sum(row["baseline_gate_survived"] and row["oracle_correct"] and not row["counterfactual_gate_survived"] for row in rows)
    baseline_correct = sum(row["baseline_gate_survived"] and row["oracle_correct"] for row in rows)
    result = {
        "scope": scope_name,
        "observation_count": len(rows),
        "task_success_count": sum(row["task_success"] for row in rows),
        "oracle_correct_count": sum(row["oracle_correct"] for row in rows),
        "baseline_gate_survived_count": sum(row["baseline_gate_survived"] for row in rows),
        "counterfactual_gate_survived_count": sum(row["counterfactual_gate_survived"] for row in rows),
        "baseline_false_accept_count": baseline_false,
        "false_accepts_caught_count": caught,
        "false_accepts_remaining_count": remaining,
        "newly_admitted_incorrect_count": newly_admitted,
        "counterfactual_false_accept_count": sum(row["counterfactual_gate_survived"] and not row["oracle_correct"] for row in rows),
        "newly_rejected_correct_count": newly_rejected,
        "baseline_correct_survivor_count": baseline_correct,
        "false_accept_catch_rate": _ratio(caught, baseline_false),
        "correct_rejection_rate_among_baseline_correct_survivors": _ratio(newly_rejected, baseline_correct),
        "contract_accept_count": sum(row["contract_accept"] for row in rows),
        "wrong_but_permitted_label_count": sum(row["cohort"] == "label_conformance" and row["contract_accept"] and not row["oracle_correct"] for row in rows),
        "transition_counts": transitions,
    }
    _assert_metrics_invariants(result)
    return result


def _percentile_type7(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    h = (len(ordered) - 1) * probability
    j = math.floor(h)
    g = h - j
    if j == len(ordered) - 1:
        return ordered[j]
    return ordered[j] + g * (ordered[j + 1] - ordered[j])


def bootstrap_primary(rows):
    rows = list(rows)
    canonical_tasks = []
    by_task = defaultdict(list)
    for row in rows:
        if row["cohort"] in PRIMARY_COHORTS:
            by_task[row["task_id"]].append(row)
    for task_id in sorted(by_task, key=lambda value: (value.split("_")[1], int(value.rsplit("_", 1)[1]))):
        canonical_tasks.append(task_id)
    if len(canonical_tasks) != 20:
        raise ValueError("bootstrap requires exactly 20 primary tasks")
    values = []
    undefined = 0
    prefix = b"prospective_contract_validation_v1"
    seed = BOOTSTRAP_SEED.encode("ascii")
    for draw in range(BOOTSTRAP_DRAWS):
        selected = []
        for slot in range(20):
            message = prefix + b"|" + seed + b"|" + str(draw).encode("ascii") + b"|" + str(slot).encode("ascii")
            digest = hashlib.sha256(message).digest()
            index = int.from_bytes(digest[:8], "big", signed=False) % 20
            selected.extend(by_task[canonical_tasks[index]])
        metrics = metrics_for_rows(selected, "bootstrap_draw")
        denominator = metrics["baseline_false_accept_count"]
        if denominator == 0:
            undefined += 1
        else:
            values.append(metrics["false_accepts_caught_count"] / denominator)
    return {
        "draw_count": BOOTSTRAP_DRAWS,
        "seed": int(BOOTSTRAP_SEED),
        "sampler": "sha256_counter_first8_be_mod20",
        "undefined_draw_count": undefined,
        "defined_draw_count": len(values),
        "percentile_method": "hyndman_fan_type_7_linear_interpolation",
        "interval_95": {
            "lower": _percentile_type7(values, 0.025),
            "upper": _percentile_type7(values, 0.975),
        },
    }


def _group_metrics(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return {key: metrics_for_rows(groups[key], key) for key in sorted(groups)}


def analyze_rows(rows: Iterable[dict[str, Any]], task_inventory: dict[str, dict[str, Any]], contracts: dict[str, dict[str, Any]], revision=None):
    rows = list(rows)
    if not rows:
        raise ValueError("no rows to analyze")
    for row in rows:
        if row["task_id"] not in task_inventory or row["task_id"] not in contracts:
            raise ValueError("unknown task in analysis rows")
        task = task_inventory[row["task_id"]]
        if row["cohort"] != task["cohort"] or row["contract_type"] != task["contract_type"]:
            raise ValueError("analysis row task metadata mismatch")
        expected_cf = counterfactual_gate(row, task)
        if row["counterfactual_gate_survived"] != expected_cf:
            raise AssertionError("counterfactual gate mismatch")
        if row.get("model_identity_source_sha256") != MODEL_IDENTITY_SOURCE_SHA256:
            raise FrozenDesignError("analysis row model-identity source provenance mismatch")
    primary = [row for row in rows if row["cohort"] in PRIMARY_COHORTS]
    labels = [row for row in rows if row["cohort"] == "label_conformance"]
    executors = [row for row in rows if row["cohort"] == "deterministic_executor"]
    report = {
        "schema_version": SCHEMA_VERSION,
        "suite_id": SUITE_ID,
        "plan_sha256": PLAN_SHA256,
        "benchmark_sha256": SUITE_SHA256,
        "contracts_sha256": CONTRACTS_SHA256,
        "model_identity_source_sha256": dict(MODEL_IDENTITY_SOURCE_SHA256),
        "implementation_revision": revision,
        "primary": {
            "overall": metrics_for_rows(primary, "overall"),
            "by_model": {model: metrics_for_rows([row for row in primary if row["requested_model"] == model], model) for model in MODEL_ORDER},
            "by_cohort": _group_metrics(primary, "cohort"),
            "by_contract_type": _group_metrics(primary, "contract_type"),
            "by_task": _group_metrics(primary, "task_id"),
            "bootstrap": bootstrap_primary(primary),
        },
        "label_conformance": {
            "overall": metrics_for_rows(labels, "overall"),
            "by_model": {model: metrics_for_rows([row for row in labels if row["requested_model"] == model], model) for model in MODEL_ORDER},
            "by_task": _group_metrics(labels, "task_id"),
        },
        "deterministic_executor": {
            "overall": metrics_for_rows(executors, "overall"),
            "by_model": {model: metrics_for_rows([row for row in executors if row["requested_model"] == model], model) for model in MODEL_ORDER},
            "by_task": _group_metrics(executors, "task_id"),
            "interpretation": "descriptive deterministic bypass counterfactual; excluded from validator effectiveness claims",
        },
    }
    return report


def _csv_rows(report):
    rows = []
    metric_fields = (
        "observation_count", "task_success_count", "oracle_correct_count",
        "baseline_gate_survived_count", "counterfactual_gate_survived_count",
        "baseline_false_accept_count", "false_accepts_caught_count",
        "false_accepts_remaining_count", "newly_admitted_incorrect_count",
        "counterfactual_false_accept_count", "newly_rejected_correct_count",
        "baseline_correct_survivor_count", "false_accept_catch_rate",
        "correct_rejection_rate_among_baseline_correct_survivors",
        "contract_accept_count", "wrong_but_permitted_label_count",
    )
    for section in ("primary", "label_conformance", "deterministic_executor"):
        block = report[section]
        for scope_name in ("overall",):
            metric = block[scope_name]
            rows.append([section, scope_name, "", ""] + [metric.get(field) for field in metric_fields])
        for dimension in ("by_model", "by_cohort", "by_contract_type", "by_task"):
            for key, metric in block.get(dimension, {}).items():
                rows.append([section, dimension, key, ""] + [metric.get(field) for field in metric_fields])
    return metric_fields, rows


def render_csv(report) -> str:
    metric_fields, rows = _csv_rows(report)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["section", "dimension", "key", "model"] + list(metric_fields))
    writer.writerows(rows)
    return output.getvalue()


def atomic_write_text(path: Path, content: str, *, require_absent=True):
    path = Path(path)
    if require_absent and path.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {path}")
    partial = Path(str(path) + ".partial")
    if partial.exists():
        raise FileExistsError(f"refusing to use existing partial path: {partial}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("x", encoding="utf-8", newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {path}")
    os.rename(partial, path)


def atomic_write_json(path: Path, document: Any):
    atomic_write_text(path, json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def canonical_paths():
    return tuple(EVIDENCE_PATHS.values()) + tuple(SUMMARY_PATHS.values()) + (ANALYSIS_JSON_PATH, ANALYSIS_CSV_PATH)


def preflight_output_paths():
    existing = []
    for path in canonical_paths():
        if path.exists():
            existing.append(str(path))
        if Path(str(path) + ".partial").exists():
            existing.append(str(path) + ".partial")
    if existing:
        raise FileExistsError("prospective output preflight failed: " + ", ".join(existing))


def validate_result_rows(rows, task_inventory, model):
    if len(rows) != OBSERVATIONS_PER_MODEL:
        raise ValueError(f"expected {OBSERVATIONS_PER_MODEL} rows, found {len(rows)}")
    keys = [(row.get("task_id"), row.get("rep")) for row in rows]
    expected = {(task_id, rep) for task_id in task_inventory for rep in range(1, REPETITIONS + 1)}
    if len(set(keys)) != len(keys) or set(keys) != expected:
        raise ValueError("result row key set mismatch")
    for row in rows:
        if row.get("requested_model") != model:
            raise ValueError("result model identity mismatch")
        if row.get("success") and row.get("returned_model") != model:
            raise ValueError("successful result returned model identity mismatch")
        if not row.get("success") and row.get("returned_model") not in (None, model):
            raise ValueError("failed result returned model identity mismatch")
        if type(row.get("success")) is not bool or type(row.get("task_success")) is not bool or row["success"] != row["task_success"]:
            raise ValueError("result task_success schema mismatch")
        if type(row.get("oracle_correct")) is not bool or type(row.get("executor_accept")) is not bool or type(row.get("contract_accept")) is not bool:
            raise ValueError("result decision schema mismatch")
        if row.get("model_identity_source_sha256") != MODEL_IDENTITY_SOURCE_SHA256:
            raise FrozenDesignError("result model-identity source provenance mismatch")
    return rows
