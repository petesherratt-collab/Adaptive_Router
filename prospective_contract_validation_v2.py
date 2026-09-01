"""Prospective Contract Validation v2 core, schema, state machine, and analysis."""

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
from typing import Any, Iterable

import validators


ROOT = Path(__file__).resolve().parent
PLAN_PATH = ROOT / "PROSPECTIVE_CONTRACT_VALIDATION_V2_PLAN.md"
SUITE_PATH = ROOT / "benchmark_prospective_contract_v2.json"
CONTRACTS_PATH = ROOT / "validator_contracts_prospective_v2.json"
PLAN_SHA256 = "5eb789d210360e5ade44755cfdc3a1e54f3f67f08d95f3f11a66da33a0a62528"
SUITE_SHA256 = "9932a510ed5592801b8a2bc3ab4cc3dbbebd3042a3b434fe6d683e48daf50e27"
CONTRACTS_SHA256 = "cfbb36c1d9c3dc2ecc755348ffc9e4ca620d56220501b0879580a0f4d6868007"
SUITE_ID = "prospective_contract_validation_v2"
SCHEMA_VERSION = "prospective_contract_validation_v2"
TASK_COUNT = 40
REPETITIONS = 5
OBSERVATIONS_PER_MODEL = 200
PRIMARY_COHORTS = ("structural_schema", "format_conformance")
MODEL_ORDER = ("gemma3:270m", "gemma3:1b", "gemma3:4b")
TEMPERATURE = 0
MAX_OUTPUT_TOKENS = 256
MAX_TTFT_MS = 8000
MIN_TOKENS_PER_SECOND = 1.5
BOOTSTRAP_NAMESPACE = "prospective_contract_validation_v2"
BOOTSTRAP_SEED = "20260901"
BOOTSTRAP_DRAWS = 10000

MODEL_SPECS = {
    "gemma3:270m": {"name":"gemma3:270m","digest":"e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be","parameter_size":"268.10M","quantization_level":"Q8_0","format":"gguf","family":"gemma3","package_size_bytes":291554930},
    "gemma3:1b": {"name":"gemma3:1b","digest":"8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc","parameter_size":"999.89M","quantization_level":"Q4_K_M","format":"gguf","family":"gemma3","package_size_bytes":815319791},
    "gemma3:4b": {"name":"gemma3:4b","digest":"a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a","parameter_size":"4.3B","quantization_level":"Q4_K_M","format":"gguf","family":"gemma3","package_size_bytes":3338801804},
}

FORBIDDEN_CONTRACT_NAMES = frozenset({
    "expected", "oracle", "oracle_correct", "normalized_output", "benchmark_validator",
    "model_output", "answer", "reference_answer", "gold", "target", "expected_value",
    "oracle_value", "correct_output", "semantic_value", "supplied_field_values", "ordered_fields",
})
JSON_TYPES = frozenset({"boolean", "number", "string", "array", "object", "null"})
CONTRACT_TYPES = frozenset({"structured_json", "json_format", "bullet_format", "label_format", "classification_labels", "deterministic_executor"})
OPERATIONS = frozenset({"rotate_left_one", "rotate_right_two", "remove_vowels", "replace_letter_e_with_7", "collapse_whitespace_runs", "swap_ascii_case", "remove_hyphens", "sort_codepoints_ascending", "duplicate_final_character", "alphabetize_words"})


class FrozenDesignError(ValueError):
    pass


class ContractSchemaError(FrozenDesignError):
    pass


class StateMachineError(FrozenDesignError):
    pass


@dataclass(frozen=True)
class ContractResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class GateResult:
    survived: bool
    reason: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def implementation_revision() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise FrozenDesignError("unable to read implementation revision") from exc


def _strict_json_loads(text: str):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value
    def constant(value):
        raise ValueError("non-finite JSON constant: " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def _json_type(value):
    if type(value) is bool: return "boolean"
    if type(value) in (int, float): return "number"
    if isinstance(value, str): return "string"
    if isinstance(value, list): return "array"
    if isinstance(value, dict): return "object"
    if value is None: return "null"
    return None


def _finite(value):
    if type(value) is float and not math.isfinite(value): raise ValueError("non-finite number")
    if isinstance(value, dict):
        for item in value.values(): _finite(item)
    if isinstance(value, list):
        for item in value: _finite(item)


def _ascii_lower(value: str) -> str:
    return value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))


def _line_normalize(raw: str) -> str:
    if not isinstance(raw, str): raise ValueError("INVALID_OUTPUT_TYPE")
    if "\r" in raw.replace("\r\n", ""): raise ValueError("LONE_CR")
    value = raw.replace("\r\n", "\n")
    return value[:-1] if value.endswith("\n") else value


def _json_candidate(raw: str) -> str:
    value = _line_normalize(raw)
    lines = value.split("\n")
    if lines and lines[0] in ("```", "```json"):
        if len(lines) < 2 or lines[-1] != "```": raise ValueError("INCOMPLETE_OUTER_FENCE")
        body = lines[1:-1]
        if any("```" in line for line in body): raise ValueError("NESTED_OR_MULTIPLE_FENCE")
        return "\n".join(body)
    if any("```" in line for line in lines): raise ValueError("INCOMPLETE_OR_SURROUNDING_FENCE")
    return value


def _parse_json_object(raw: str):
    try:
        value = _strict_json_loads(_json_candidate(raw))
        _finite(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_JSON") from exc
    if not isinstance(value, dict): raise ValueError("NOT_A_JSON_OBJECT")
    return value


def _fence_rule(rule):
    if rule == "forbidden": return
    if not isinstance(rule, dict) or rule.get("required") is not True or rule.get("outer_only") is not True or not isinstance(rule.get("language"), str) or not rule["language"] or "```" in rule["language"]:
        raise ContractSchemaError("INVALID_FENCE_RULE")


def _contract_shape(contract: dict[str, Any]) -> str:
    if not isinstance(contract, dict): raise ContractSchemaError("MALFORMED_CONTRACT")
    kind = contract.get("contract_type")
    if kind not in CONTRACT_TYPES: raise ContractSchemaError("UNKNOWN_CONTRACT_TYPE")
    common = {"task_id", "cohort", "contract_type"}
    allowed = {
        "structured_json": common | {"exact_keys", "explicit_types"},
        "json_format": common | {"exact_keys", "explicit_types"},
        "bullet_format": common | {"line_count", "marker", "separator", "fence_rule"},
        "label_format": common | {"line_count", "separator", "separator_rule", "fence_rule"},
        "classification_labels": common | {"permitted_labels"},
        "deterministic_executor": common | {"role", "source_literal", "operation"},
    }[kind]
    if set(contract) != allowed: raise ContractSchemaError("CONTRACT_FIELDS_MISMATCH")
    if any(not isinstance(contract[key], str) or not contract[key] for key in common): raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    if kind in ("structured_json", "json_format"):
        keys, types = contract["exact_keys"], contract["explicit_types"]
        if not isinstance(keys, list) or not keys or len(set(keys)) != len(keys) or any(not isinstance(key, str) or not key for key in keys) or not isinstance(types, dict) or set(types) != set(keys): raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        for value in types.values():
            values = value if isinstance(value, list) else [value]
            if not values or any(item not in JSON_TYPES for item in values): raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        if contract["cohort"] != "structural_schema": raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    elif kind == "bullet_format":
        if contract["cohort"] != "format_conformance" or type(contract["line_count"]) is not int or contract["line_count"] <= 0 or not isinstance(contract["marker"], str) or not contract["marker"] or not isinstance(contract["separator"], str) or not contract["separator"]: raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        _fence_rule(contract["fence_rule"])
    elif kind == "label_format":
        if contract["cohort"] != "format_conformance" or type(contract["line_count"]) is not int or contract["line_count"] <= 0 or not isinstance(contract["separator"], str) or not contract["separator"] or contract["separator_rule"] != "exactly_once_per_line": raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        _fence_rule(contract["fence_rule"])
    elif kind == "classification_labels":
        labels = contract["permitted_labels"]
        if contract["cohort"] != "label_conformance" or not isinstance(labels, list) or not labels or len(set(labels)) != len(labels) or any(not isinstance(label, str) or not label or label != _ascii_lower(label) for label in labels): raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    elif kind == "deterministic_executor":
        if contract["cohort"] != "deterministic_executor" or contract["role"] != "executable_task" or not isinstance(contract["source_literal"], str) or not contract["source_literal"] or contract["operation"] not in OPERATIONS: raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    return kind


def _reject_names(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or key.lower() in FORBIDDEN_CONTRACT_NAMES: raise ContractSchemaError("FORBIDDEN_CONTRACT_FIELD")
            _reject_names(nested)
    elif isinstance(value, list):
        for nested in value: _reject_names(nested)


def _operation(source: str, operation: str) -> str:
    if operation == "rotate_left_one": return source[1:] + source[:1]
    if operation == "rotate_right_two": return source[-2:] + source[:-2]
    if operation == "remove_vowels": return "".join(char for char in source if char not in "aeiou")
    if operation == "replace_letter_e_with_7": return source.replace("e", "7")
    if operation == "collapse_whitespace_runs": return re.sub(r"\s+", " ", source)
    if operation == "swap_ascii_case": return "".join(char.lower() if "A" <= char <= "Z" else char.upper() if "a" <= char <= "z" else char for char in source)
    if operation == "remove_hyphens": return source.replace("-", "")
    if operation == "sort_codepoints_ascending": return "".join(sorted(source, key=ord))
    if operation == "duplicate_final_character": return source + source[-1]
    if operation == "alphabetize_words": return " ".join(sorted(re.split(r" +", source)))
    raise ValueError("UNKNOWN_OPERATION")


def validate_contract_document(document: dict[str, Any], task_inventory=None):
    _reject_names(document)
    if not isinstance(document, dict) or set(document) != {"schema_version", "suite_id", "contract_count", "contracts"} or document["schema_version"] != "validator_contracts_prospective_v2" or document["suite_id"] != SUITE_ID: raise ContractSchemaError("CONTRACT_DOCUMENT_IDENTITY_MISMATCH")
    contracts = document["contracts"]
    if document["contract_count"] != 40 or not isinstance(contracts, list) or len(contracts) != 40: raise ContractSchemaError("CONTRACT_COUNT_MISMATCH")
    seen, ordered = set(), []
    for contract in contracts:
        _contract_shape(contract)
        if contract["task_id"] in seen: raise ContractSchemaError("DUPLICATE_TASK_ID")
        seen.add(contract["task_id"]); ordered.append(contract["task_id"])
        if task_inventory is not None:
            task = task_inventory.get(contract["task_id"])
            if task is None or task["cohort"] != contract["cohort"] or task["contract_type"] != contract["contract_type"]: raise ContractSchemaError("CONTRACT_TASK_MISMATCH")
    if task_inventory is not None and (seen != set(task_inventory) or ordered != list(task_inventory)): raise ContractSchemaError("CONTRACT_TASK_ORDER_MISMATCH")
    return document


def _declared_types(contract, key):
    value = contract["explicit_types"][key]
    return set(value) if isinstance(value, list) else {value}


def _fenced_lines(contract, value):
    lines = value.split("\n")
    rule = contract.get("fence_rule", "forbidden")
    if rule == "forbidden":
        if any("```" in line for line in lines): raise ValueError("FENCE_FORBIDDEN")
        return lines, False
    opening = "```" + rule["language"]
    if len(lines) < 2 or lines[0] != opening or lines[-1] != "```": raise ValueError("OUTER_FENCE_MISMATCH")
    body = lines[1:-1]
    if any("```" in line for line in body): raise ValueError("NESTED_OR_MULTIPLE_FENCE")
    return body, True


def contract_validate(contract: dict[str, Any], raw_output: str) -> ContractResult:
    """Contract-only boundary: the declaration and raw output are the inputs."""
    try: kind = _contract_shape(contract)
    except ContractSchemaError as exc: return ContractResult(False, str(exc))
    if kind == "deterministic_executor":
        return ContractResult(False, "D_REQUIRES_EXECUTOR")
    try:
        if kind in ("structured_json", "json_format"):
            value = _parse_json_object(raw_output)
            if set(value) != set(contract["exact_keys"]): return ContractResult(False, "KEY_SET_MISMATCH")
            if any(_json_type(value[key]) not in _declared_types(contract, key) for key in contract["exact_keys"]): return ContractResult(False, "JSON_VALUE_TYPE_MISMATCH")
            return ContractResult(True, "ACCEPTED")
        value = _line_normalize(raw_output)
        if kind in ("bullet_format", "label_format"):
            lines, _ = _fenced_lines(contract, value)
            if len(lines) != contract["line_count"]: return ContractResult(False, "LINE_COUNT_MISMATCH")
            if kind == "bullet_format":
                prefix = contract["marker"] + contract["separator"]
                if any(not line.startswith(prefix) or not line[len(prefix):] for line in lines): return ContractResult(False, "BULLET_SHAPE_MISMATCH")
            elif any(not line or line.count(contract["separator"]) != 1 for line in lines): return ContractResult(False, "LABEL_SEPARATOR_MISMATCH")
            return ContractResult(True, "ACCEPTED")
        if kind == "classification_labels":
            lines = value.split("\n")
            if len(lines) != 1 or not lines[0]: return ContractResult(False, "CLASSIFICATION_LINE_COUNT_MISMATCH")
            candidate = _ascii_lower(lines[0].strip(" \t"))
            return ContractResult(candidate in contract["permitted_labels"], "ACCEPTED" if candidate in contract["permitted_labels"] else "LABEL_NOT_PERMITTED")
    except (TypeError, ValueError, KeyError, IndexError) as exc:
        return ContractResult(False, str(exc))


def execute_deterministic(contract: dict[str, Any], raw_output: str) -> ContractResult:
    """Execute a D declaration; this is intentionally not validator logic."""
    try:
        if _contract_shape(contract) != "deterministic_executor":
            return ContractResult(False, "NOT_DETERMINISTIC_EXECUTOR")
        value = _line_normalize(raw_output)
        expected = _operation(contract["source_literal"], contract["operation"])
        return ContractResult(value == expected, "ACCEPTED" if value == expected else "EXECUTOR_MISMATCH")
    except (TypeError, ValueError, KeyError, IndexError) as exc:
        return ContractResult(False, str(exc))


def _values_equal(actual, expected):
    if type(actual) is bool or type(expected) is bool: return type(actual) is type(expected) and actual == expected
    if type(actual) in (int, float) and type(expected) in (int, float): return math.isfinite(actual) and math.isfinite(expected) and actual == expected
    if type(actual) is not type(expected): return False
    if isinstance(actual, dict): return set(actual) == set(expected) and all(_values_equal(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list): return len(actual) == len(expected) and all(_values_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _format_normalize(contract, raw):
    value = _line_normalize(raw); lines, fenced = _fenced_lines(contract, value)
    if len(lines) != contract["line_count"] or any(not line for line in lines): raise ValueError("FORMAT_SHAPE_MISMATCH")
    if contract["contract_type"] == "bullet_format":
        prefix = contract["marker"] + contract["separator"]
        if any(not line.startswith(prefix) for line in lines): raise ValueError("BULLET_SHAPE_MISMATCH")
    elif any(line.count(contract["separator"]) != 1 for line in lines): raise ValueError("LABEL_SEPARATOR_MISMATCH")
    body = "\n".join(lines)
    return "```" + contract["fence_rule"]["language"] + "\n" + body + "\n```" if fenced else body


def oracle_normalize(task, raw, contract):
    try:
        kind = task["contract_type"]
        if kind in ("structured_json", "json_format"): return _parse_json_object(raw)
        if kind in ("bullet_format", "label_format"): return _format_normalize(contract, raw)
        if kind == "classification_labels":
            value = _line_normalize(raw).split("\n")
            return _ascii_lower(value[0].strip(" \t")) if len(value) == 1 and value[0] else None
        if kind == "deterministic_executor": return _line_normalize(raw)
    except (TypeError, ValueError, KeyError, IndexError): return None
    raise ValueError("UNKNOWN_CONTRACT_TYPE")


def oracle_correct(task, raw, contract):
    normalized = oracle_normalize(task, raw, contract)
    kind = task["contract_type"]
    if kind in ("structured_json", "json_format"): correct = normalized is not None and _values_equal(normalized, task["expected"])
    elif kind in ("bullet_format", "label_format", "classification_labels"): correct = normalized == oracle_normalize(task, task["expected"], contract)
    elif kind == "deterministic_executor": correct = normalized == _operation(contract["source_literal"], contract["operation"])
    else: raise ValueError("UNKNOWN_CONTRACT_TYPE")
    return normalized, correct


def load_frozen_inputs():
    for path, expected in ((PLAN_PATH, PLAN_SHA256), (SUITE_PATH, SUITE_SHA256), (CONTRACTS_PATH, CONTRACTS_SHA256)):
        if file_sha256(path) != expected: raise FrozenDesignError("frozen design hash mismatch: " + str(path))
    suite = _strict_json_loads(SUITE_PATH.read_text(encoding="utf-8"))
    contracts_doc = _strict_json_loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    tasks = suite.get("tasks") if isinstance(suite, dict) else None
    if not isinstance(suite, dict) or suite.get("suite_id") != SUITE_ID or suite.get("version") != 2 or suite.get("task_count") != 40 or suite.get("repetitions_per_task") != 5 or not isinstance(tasks, list) or len(tasks) != 40: raise FrozenDesignError("frozen suite identity/count mismatch")
    ids = [f"pcv2_a_schema_{i:02d}" for i in range(1,11)] + [f"pcv2_b_format_{i:02d}" for i in range(1,11)] + [f"pcv2_c_label_{i:02d}" for i in range(1,11)] + [f"pcv2_d_exec_{i:02d}" for i in range(1,11)]
    if [task.get("task_id") for task in tasks] != ids: raise FrozenDesignError("frozen task order/IDs mismatch")
    required = {"task_id", "cohort", "task_class", "contract_type", "repetitions", "prompt", "expected"}
    if any(not required <= set(task) or task["repetitions"] != 5 for task in tasks): raise FrozenDesignError("frozen task schema mismatch")
    if Counter(task["cohort"] for task in tasks) != Counter({"structural_schema":10,"format_conformance":10,"label_conformance":10,"deterministic_executor":10}): raise FrozenDesignError("frozen cohort count mismatch")
    inventory = {task["task_id"]: task for task in tasks}
    validate_contract_document(contracts_doc, inventory)
    contracts = {contract["task_id"]: contract for contract in contracts_doc["contracts"]}
    for task in tasks:
        contract = contracts[task["task_id"]]
        if task["cohort"] in ("structural_schema", "format_conformance", "label_conformance"):
            if task["cohort"] == "structural_schema":
                if not isinstance(task["expected"], dict) or set(task["expected"]) != set(contract["exact_keys"]): raise FrozenDesignError("A oracle/schema mismatch")
                if any(_json_type(task["expected"][key]) not in _declared_types(contract, key) for key in contract["exact_keys"]): raise FrozenDesignError("A oracle/type mismatch")
            elif not isinstance(task["expected"], str): raise FrozenDesignError("B/C expected type mismatch")
        if task["cohort"] == "label_conformance" and task["expected"] not in contract["permitted_labels"]: raise FrozenDesignError("C oracle label not permitted")
        if task["cohort"] == "deterministic_executor":
            if contract["source_literal"] not in task["prompt"] or contract["operation"] not in task["prompt"] or _operation(contract["source_literal"], contract["operation"]) != task["expected"]: raise FrozenDesignError("D source/operation/oracle mismatch")
    return suite, inventory, contracts


def public_identity(model):
    if model not in MODEL_SPECS: raise FrozenDesignError("unknown model")
    return dict(MODEL_SPECS[model])


def verify_model_identity(actual, model):
    if not isinstance(actual, dict):
        raise FrozenDesignError("missing model identity")
    expected = public_identity(model); details = actual.get("details") or {}
    normalized = {"name": actual.get("name") or actual.get("model"), "digest": actual.get("digest"), "parameter_size": actual.get("parameter_size") or details.get("parameter_size"), "quantization_level": actual.get("quantization_level") or details.get("quantization_level"), "format": actual.get("format") or details.get("format"), "family": actual.get("family") or details.get("family"), "package_size_bytes": actual.get("package_size_bytes", actual.get("size"))}
    fields = ("name", "digest", "parameter_size", "quantization_level", "format", "package_size_bytes")
    if any(normalized[field] != expected[field] for field in fields): raise FrozenDesignError("installed model identity mismatch")
    return normalized


def legacy_baseline_gate(record, task):
    if not bool(record.get("success")): return GateResult(False, "GENERATION_FAILED")
    if record.get("ttft_ms") is not None and record["ttft_ms"] > MAX_TTFT_MS: return GateResult(False, "TTFT_EXCEEDED")
    if record.get("tokens_per_second") is not None and record["tokens_per_second"] < MIN_TOKENS_PER_SECOND: return GateResult(False, "GENERATION_TOO_SLOW")
    if validators.validate(task["task_class"], task["prompt"], record.get("raw_output", "")).status == validators.FAIL: return GateResult(False, "VALIDATOR_FAILED")
    return GateResult(True, "SURVIVED")


def counterfactual_gate(row, task):
    return bool(row.get("baseline_gate_survived")) and bool(row.get("executor_accept" if task["cohort"] == "deterministic_executor" else "contract_accept"))


def _failure(error):
    kind = str(error or "GENERATION_FAILED")
    return {"kind": kind, "message": kind}


def make_result_row(task, contract, result, model, returned_model, identity, revision, residency, prior_hashes=None):
    success = bool(result.success); raw = result.text if success and isinstance(result.text, str) else None
    if raw is None:
        normalized, correct, cresult = None, False, ContractResult(False, "NO_OUTPUT")
    else:
        normalized, correct = oracle_correct(task, raw, contract)
        cresult = execute_deterministic(contract, raw) if task["cohort"] == "deterministic_executor" else contract_validate(contract, raw)
    baseline = legacy_baseline_gate({"success":success,"ttft_ms":result.ttft_ms,"tokens_per_second":result.tokens_per_second,"raw_output":raw or ""}, task)
    executor = cresult.accepted if task["cohort"] == "deterministic_executor" else False
    contract_accept = executor if task["cohort"] == "deterministic_executor" else cresult.accepted
    row = {"schema_version":SCHEMA_VERSION,"suite_id":SUITE_ID,"plan_sha256":PLAN_SHA256,"benchmark_sha256":SUITE_SHA256,"contracts_sha256":CONTRACTS_SHA256,"implementation_revision":revision,"requested_model":model,"returned_model":returned_model,"model_identity":identity,"prior_stratum_sha256":dict(prior_hashes or {}),"task_id":task["task_id"],"rep":task.get("_rep"),"task_class":task["task_class"],"cohort":task["cohort"],"contract_type":task["contract_type"],"raw_output":raw,"normalized_output":normalized,"oracle_correct":bool(correct),"executor_accept":bool(executor),"contract_accept":bool(contract_accept),"contract_reason":cresult.reason,"baseline_gate_survived":baseline.survived,"baseline_reason":baseline.reason,"counterfactual_gate_survived":counterfactual_gate({"baseline_gate_survived":baseline.survived,"contract_accept":contract_accept,"executor_accept":executor},task),"success":success,"task_success":success,"ttft_ms":result.ttft_ms,"total_ms":result.total_ms,"tokens_per_second":result.tokens_per_second,"model_residency":residency,"error":None if success else _failure(result.error)}
    return row


def validate_result_rows(rows, inventory, model, revision=None):
    rows = list(rows)
    if len(rows) != OBSERVATIONS_PER_MODEL: raise FrozenDesignError("wrong observation count")
    expected = {(task_id, rep) for task_id in inventory for rep in range(1, REPETITIONS+1)}
    actual = {(row.get("task_id"), row.get("rep")) for row in rows}
    if actual != expected or len(actual) != len(rows): raise FrozenDesignError("task/repetition inventory mismatch")
    for row in rows:
        task = inventory.get(row.get("task_id"))
        if task is None or row.get("task_class") != task["task_class"] or row.get("cohort") != task["cohort"] or row.get("contract_type") != task["contract_type"] or type(row.get("rep")) is not int or not 1 <= row["rep"] <= REPETITIONS: raise FrozenDesignError("row task metadata mismatch")
        if row.get("schema_version") != SCHEMA_VERSION or row.get("suite_id") != SUITE_ID or row.get("plan_sha256") != PLAN_SHA256 or row.get("benchmark_sha256") != SUITE_SHA256 or row.get("contracts_sha256") != CONTRACTS_SHA256: raise FrozenDesignError("row frozen provenance mismatch")
        if revision is not None and row.get("implementation_revision") != revision: raise FrozenDesignError("row implementation revision mismatch")
        if row.get("requested_model") != model or (row.get("success") and row.get("returned_model") != model) or (not row.get("success") and row.get("returned_model") not in (None, model)): raise FrozenDesignError("row model identity mismatch")
        verify_model_identity(row.get("model_identity"), model)
        if type(row.get("success")) is not bool or type(row.get("task_success")) is not bool or row["success"] != row["task_success"]: raise FrozenDesignError("row success schema mismatch")
        for key in ("oracle_correct","executor_accept","contract_accept","baseline_gate_survived","counterfactual_gate_survived"):
            if type(row.get(key)) is not bool: raise FrozenDesignError("row decision schema mismatch")
    return rows


def v2_paths(root=ROOT):
    root = Path(root)
    evidence = {model: root / f"benchmark_prospective_contract_v2_{model.replace(':','_')}.jsonl" for model in MODEL_ORDER}
    summaries = {model: root / f"benchmark_prospective_contract_v2_{model.replace(':','_')}_summary.json" for model in MODEL_ORDER}
    return {"evidence": evidence, "summaries": summaries, "analysis_json": root / "prospective_contract_validation_v2_analysis.json", "analysis_csv": root / "prospective_contract_validation_v2_analysis.csv"}


def _partial(path): return Path(str(path) + ".partial")


def detect_state(root=ROOT):
    paths = v2_paths(root); all_paths = list(paths["evidence"].values()) + list(paths["summaries"].values()) + [paths["analysis_json"], paths["analysis_csv"]]
    partials = [_partial(path) for path in all_paths if _partial(path).exists()]
    if partials: raise StateMachineError("quarantined partial blocks execution")
    analysis = [paths["analysis_json"].exists(), paths["analysis_csv"].exists()]
    if any(analysis):
        if not all(analysis) or not all(paths["evidence"][m].exists() and paths["summaries"][m].exists() for m in MODEL_ORDER): raise StateMachineError("impossible analysis state")
        return "ANALYZED"
    pairs = [(paths["evidence"][m].exists(), paths["summaries"][m].exists()) for m in MODEL_ORDER]
    if any(a != b for a,b in pairs): raise StateMachineError("evidence/summary pair mismatch")
    count = sum(a for a,b in pairs)
    if count == 0: return "EMPTY"
    if count == 1 and pairs[0][0]: return "270M_COMPLETE"
    if count == 2 and all(pairs[i][0] for i in (0,1)): return "1B_COMPLETE"
    if count == 3 and all(a for a,b in pairs): return "4B_COMPLETE"
    raise StateMachineError("impossible mixed stratum state")


def _canonical_json(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _summary_payload_hash(summary):
    payload = dict(summary); payload.pop("summary_payload_sha256", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def load_evidence(path, inventory, model, revision):
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip(): raise FrozenDesignError("blank evidence line")
            try: rows.append(_strict_json_loads(line))
            except (ValueError, json.JSONDecodeError) as exc: raise FrozenDesignError(f"invalid evidence JSON line {number}") from exc
    return validate_result_rows(rows, inventory, model, revision)


def authenticate_stratum(model, inventory, root=ROOT, revision=None):
    revision = revision or implementation_revision(); paths = v2_paths(root); evidence, summary_path = paths["evidence"][model], paths["summaries"][model]
    if not evidence.exists() or not summary_path.exists() or _partial(evidence).exists() or _partial(summary_path).exists(): raise StateMachineError("incomplete stratum pair")
    rows = load_evidence(evidence, inventory, model, revision)
    try: summary = _strict_json_loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc: raise StateMachineError("invalid summary") from exc
    try:
        verify_model_identity(summary.get("model_identity"), model)
    except FrozenDesignError as exc:
        raise StateMachineError("summary model identity mismatch") from exc
    if summary.get("schema_version") != SCHEMA_VERSION or summary.get("suite_id") != SUITE_ID or summary.get("model") != model or summary.get("implementation_revision") != revision or summary.get("plan_sha256") != PLAN_SHA256 or summary.get("benchmark_sha256") != SUITE_SHA256 or summary.get("contracts_sha256") != CONTRACTS_SHA256 or summary.get("observation_count") != 200 or summary.get("task_success_count") != sum(row["task_success"] for row in rows) or summary.get("oracle_correct_count") != sum(row["oracle_correct"] for row in rows) or summary.get("evidence_sha256") != file_sha256(evidence) or summary.get("summary_payload_sha256") != _summary_payload_hash(summary): raise StateMachineError("stratum provenance mismatch")
    return {"evidence": file_sha256(evidence), "summary": file_sha256(summary_path), "summary_document": summary, "rows": rows}


def preflight_stratum(model, inventory, root=ROOT, revision=None):
    revision = revision or implementation_revision(); state = detect_state(root); prior = {}
    if state == "EMPTY":
        if model != MODEL_ORDER[0]: raise StateMachineError("only 270M may start from EMPTY")
    elif state == "270M_COMPLETE":
        if model != MODEL_ORDER[1]: raise StateMachineError("270M_COMPLETE permits only 1B")
        auth = authenticate_stratum(MODEL_ORDER[0], inventory, root, revision); prior[MODEL_ORDER[0]] = {"evidence":auth["evidence"],"summary":auth["summary"]}
    elif state == "1B_COMPLETE":
        if model != MODEL_ORDER[2]: raise StateMachineError("1B_COMPLETE permits only 4B")
        for prior_model in MODEL_ORDER[:2]:
            auth = authenticate_stratum(prior_model, inventory, root, revision); prior[prior_model] = {"evidence":auth["evidence"],"summary":auth["summary"]}
        recorded = auth["summary_document"].get("prior_stratum_sha256")
        if recorded != {MODEL_ORDER[0]: prior[MODEL_ORDER[0]]}: raise StateMachineError("1B prior-stratum hashes mismatch")
    elif state == "4B_COMPLETE": raise StateMachineError("all strata complete; model execution forbidden")
    elif state == "ANALYZED": raise StateMachineError("analysis complete; model execution forbidden")
    return {"state":state,"prior_stratum_sha256":prior,"revision":revision}


def preflight_analysis(inventory, root=ROOT, revision=None):
    revision = revision or implementation_revision(); state = detect_state(root)
    if state != "4B_COMPLETE": raise StateMachineError("analysis requires three complete strata")
    all_rows, hashes, authenticated = [], {}, {}
    for model in MODEL_ORDER:
        auth = authenticate_stratum(model, inventory, root, revision)
        authenticated[model] = auth
        all_rows.extend(auth["rows"])
        hashes[model] = {"evidence":auth["evidence"],"summary":auth["summary"]}
    for index, model in enumerate(MODEL_ORDER):
        expected_prior = {prior_model: hashes[prior_model] for prior_model in MODEL_ORDER[:index]}
        if authenticated[model]["summary_document"].get("prior_stratum_sha256") != expected_prior:
            raise StateMachineError("prior-stratum hash chain mismatch")
    return {"rows":all_rows,"prior_stratum_sha256":hashes,"revision":revision}


def atomic_write_text(path, content):
    path = Path(path); partial = _partial(path)
    if path.exists(): raise FileExistsError(f"refusing overwrite: {path}")
    if partial.exists(): raise FileExistsError(f"refusing partial: {partial}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("x", encoding="utf-8", newline="") as handle:
        handle.write(content); handle.flush(); os.fsync(handle.fileno())
    if path.exists(): raise FileExistsError(f"refusing overwrite: {path}")
    os.rename(partial, path)


def atomic_write_json(path, document): atomic_write_text(path, json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _open_partial(path):
    path = Path(path); partial = _partial(path)
    if path.exists() or partial.exists(): raise FileExistsError("canonical or partial output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    return partial, partial.open("x", encoding="utf-8", newline="")


def publish_partial(partial, canonical):
    partial = Path(partial); canonical = Path(canonical)
    if canonical.exists(): raise FileExistsError("refusing overwrite")
    os.rename(partial, canonical)


TRANSITION_KEYS = tuple(f"baseline_{b}__counterfactual_{c}__oracle_{o}" for b in ("survive","fail") for c in ("survive","fail") for o in ("correct","incorrect"))


def metrics_for_rows(rows, scope="scope"):
    rows = list(rows); transitions = {key:0 for key in TRANSITION_KEYS}
    for row in rows:
        b = "survive" if row["baseline_gate_survived"] else "fail"; c = "survive" if row["counterfactual_gate_survived"] else "fail"; o = "correct" if row["oracle_correct"] else "incorrect"; transitions[f"baseline_{b}__counterfactual_{c}__oracle_{o}"] += 1
    baseline_false = sum(r["baseline_gate_survived"] and not r["oracle_correct"] for r in rows); caught = sum(r["baseline_gate_survived"] and not r["oracle_correct"] and not r["counterfactual_gate_survived"] for r in rows); remaining = sum(r["baseline_gate_survived"] and r["counterfactual_gate_survived"] and not r["oracle_correct"] for r in rows)
    result = {"scope":scope,"observation_count":len(rows),"task_success_count":sum(r["task_success"] for r in rows),"oracle_correct_count":sum(r["oracle_correct"] for r in rows),"baseline_gate_survived_count":sum(r["baseline_gate_survived"] for r in rows),"counterfactual_gate_survived_count":sum(r["counterfactual_gate_survived"] for r in rows),"baseline_false_accept_count":baseline_false,"false_accepts_caught_count":caught,"false_accepts_remaining_count":remaining,"newly_admitted_incorrect_count":sum(not r["baseline_gate_survived"] and r["counterfactual_gate_survived"] and not r["oracle_correct"] for r in rows),"counterfactual_false_accept_count":sum(r["counterfactual_gate_survived"] and not r["oracle_correct"] for r in rows),"newly_rejected_correct_count":sum(r["baseline_gate_survived"] and r["oracle_correct"] and not r["counterfactual_gate_survived"] for r in rows),"baseline_correct_survivor_count":sum(r["baseline_gate_survived"] and r["oracle_correct"] for r in rows),"false_accept_catch_rate":caught/baseline_false if baseline_false else None,"correct_rejection_rate_among_baseline_correct_survivors":(sum(r["baseline_gate_survived"] and r["oracle_correct"] and not r["counterfactual_gate_survived"] for r in rows)/sum(r["baseline_gate_survived"] and r["oracle_correct"] for r in rows)) if sum(r["baseline_gate_survived"] and r["oracle_correct"] for r in rows) else None,"contract_accept_count":sum(r["contract_accept"] for r in rows),"wrong_but_permitted_label_count":sum(r["cohort"]=="label_conformance" and r["contract_accept"] and not r["oracle_correct"] for r in rows),"transition_counts":transitions}
    if result["counterfactual_gate_survived_count"] > result["baseline_gate_survived_count"]:
        raise FrozenDesignError("counterfactual survivors exceed baseline survivors")
    if result["newly_admitted_incorrect_count"] != 0:
        raise FrozenDesignError("newly admitted incorrect output")
    if transitions["baseline_fail__counterfactual_survive__oracle_correct"] != 0 or transitions["baseline_fail__counterfactual_survive__oracle_incorrect"] != 0:
        raise FrozenDesignError("baseline failure survived counterfactual gate")
    if caught + remaining != baseline_false or result["counterfactual_false_accept_count"] != remaining:
        raise FrozenDesignError("false-accept accounting mismatch")
    if result["newly_rejected_correct_count"] > result["baseline_correct_survivor_count"]:
        raise FrozenDesignError("newly rejected correct count exceeds baseline correct survivors")
    if sum(transitions.values()) != len(rows):
        raise FrozenDesignError("transition table total mismatch")
    return result


def _percentile_type7(values, p):
    if not values: return None
    values = sorted(values); h = (len(values)-1)*p; j = math.floor(h); g = h-j
    return values[j] if j == len(values)-1 else values[j] + g*(values[j+1]-values[j])


def bootstrap_primary(rows, inventory):
    by_task = defaultdict(list)
    for row in rows:
        if row["cohort"] in PRIMARY_COHORTS: by_task[row["task_id"]].append(row)
    tasks = [task_id for task_id, task in inventory.items() if task["cohort"] in PRIMARY_COHORTS]
    if len(tasks) != 20 or set(tasks) != set(by_task): raise FrozenDesignError("bootstrap task scope mismatch")
    values=[]; undefined=0
    for draw in range(BOOTSTRAP_DRAWS):
        selected=[]
        for slot in range(20):
            digest=hashlib.sha256(f"{BOOTSTRAP_NAMESPACE}|{BOOTSTRAP_SEED}|{draw}|{slot}".encode("ascii")).digest(); selected.extend(by_task[tasks[int.from_bytes(digest[:8],"big")%20]])
        metric=metrics_for_rows(selected,"bootstrap")
        if metric["baseline_false_accept_count"] == 0: undefined += 1
        else: values.append(metric["false_accepts_caught_count"]/metric["baseline_false_accept_count"])
    return {"draw_count":BOOTSTRAP_DRAWS,"namespace":BOOTSTRAP_NAMESPACE,"seed":int(BOOTSTRAP_SEED),"undefined_draw_count":undefined,"defined_draw_count":len(values),"sampler":"sha256_counter_first8_be_mod20","percentile_method":"hyndman_fan_type_7_linear_interpolation","interval_95":{"lower":_percentile_type7(values,.025),"upper":_percentile_type7(values,.975)}}


def _group(rows, field):
    groups=defaultdict(list)
    for row in rows: groups[row[field]].append(row)
    return {key:metrics_for_rows(groups[key],key) for key in sorted(groups)}


def analyze_rows(rows, inventory, contracts, revision, prior_hashes=None):
    rows=list(rows)
    if len(rows) != 600: raise FrozenDesignError("analysis requires 600 observations")
    for model in MODEL_ORDER:
        model_rows = [row for row in rows if row.get("requested_model") == model]
        validate_result_rows(model_rows, inventory, model, revision)
    for row in rows:
        task=inventory.get(row.get("task_id"))
        if task is None or row["cohort"] != task["cohort"] or row["contract_type"] != task["contract_type"] or row["counterfactual_gate_survived"] != counterfactual_gate(row,task): raise FrozenDesignError("analysis row mismatch")
    primary=[r for r in rows if r["cohort"] in PRIMARY_COHORTS]; labels=[r for r in rows if r["cohort"]=="label_conformance"]; executors=[r for r in rows if r["cohort"]=="deterministic_executor"]
    return {"schema_version":SCHEMA_VERSION,"suite_id":SUITE_ID,"plan_sha256":PLAN_SHA256,"benchmark_sha256":SUITE_SHA256,"contracts_sha256":CONTRACTS_SHA256,"implementation_revision":revision,"prior_stratum_sha256":dict(prior_hashes or {}),"primary":{"overall":metrics_for_rows(primary,"overall"),"by_model":{m:metrics_for_rows([r for r in primary if r["requested_model"]==m],m) for m in MODEL_ORDER},"by_cohort":_group(primary,"cohort"),"by_contract_type":_group(primary,"contract_type"),"by_task":_group(primary,"task_id"),"bootstrap":bootstrap_primary(primary,inventory)},"label_conformance":{"overall":metrics_for_rows(labels,"overall"),"by_model":{m:metrics_for_rows([r for r in labels if r["requested_model"]==m],m) for m in MODEL_ORDER},"by_task":_group(labels,"task_id")},"deterministic_executor":{"overall":metrics_for_rows(executors,"overall"),"by_model":{m:metrics_for_rows([r for r in executors if r["requested_model"]==m],m) for m in MODEL_ORDER},"by_task":_group(executors,"task_id"),"interpretation":"descriptive deterministic bypass counterfactual; excluded from validator effectiveness claims"}}


def render_csv(report):
    fields=("observation_count","task_success_count","oracle_correct_count","baseline_gate_survived_count","counterfactual_gate_survived_count","baseline_false_accept_count","false_accepts_caught_count","false_accepts_remaining_count","newly_admitted_incorrect_count","counterfactual_false_accept_count","newly_rejected_correct_count","baseline_correct_survivor_count","false_accept_catch_rate","correct_rejection_rate_among_baseline_correct_survivors")
    output=io.StringIO(newline=""); writer=csv.writer(output,lineterminator="\n"); writer.writerow(["section","dimension","key"]+list(fields))
    for section in ("primary","label_conformance","deterministic_executor"):
        block=report[section]; writer.writerow([section,"overall",""]+[block["overall"].get(f) for f in fields])
        for dimension in ("by_model","by_cohort","by_contract_type","by_task"):
            for key, metric in block.get(dimension,{}).items(): writer.writerow([section,dimension,key]+[metric.get(f) for f in fields])
    return output.getvalue()
