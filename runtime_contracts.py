"""Runtime request contracts for the product router.

The runtime contract is supplied by the caller. It describes observable output
shape; it never contains an expected answer and never claims semantic
correctness. Deterministic executor requests bypass both language models.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "runtime_request_v1"
PASS, FAIL = "PASS", "FAIL"
JSON_TYPES = frozenset({"boolean", "number", "string", "array", "object", "null"})
LOCAL_CONTRACT_TYPES = frozenset(
    {"structured_json", "json_format", "bullet_format", "label_format"}
)
REMOTE_ONLY_CONTRACT_TYPES = frozenset({"classification_labels"})
DETERMINISTIC_CONTRACT_TYPE = "deterministic_executor"
CONTRACT_TYPES = (
    LOCAL_CONTRACT_TYPES
    | REMOTE_ONLY_CONTRACT_TYPES
    | {DETERMINISTIC_CONTRACT_TYPE}
)
OPERATIONS = frozenset(
    {
        "rotate_left_one",
        "rotate_right_two",
        "remove_vowels",
        "replace_letter_e_with_7",
        "collapse_whitespace_runs",
        "swap_ascii_case",
        "remove_hyphens",
        "sort_codepoints_ascending",
        "duplicate_final_character",
        "alphabetize_words",
    }
)


class RuntimeContractError(ValueError):
    """The caller supplied a malformed or internally inconsistent request."""


@dataclass(frozen=True)
class RuntimeRequest:
    schema_version: str
    task_class: str
    prompt: str
    contract: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: Any) -> "RuntimeRequest":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "task_class",
            "prompt",
            "contract",
        }:
            raise RuntimeContractError("REQUEST_FIELDS_MISMATCH")
        if value["schema_version"] != SCHEMA_VERSION:
            raise RuntimeContractError("REQUEST_SCHEMA_MISMATCH")
        if not isinstance(value["task_class"], str) or not value["task_class"]:
            raise RuntimeContractError("INVALID_TASK_CLASS")
        if not isinstance(value["prompt"], str) or not value["prompt"].strip():
            raise RuntimeContractError("INVALID_PROMPT")
        contract = _validated_contract(value["contract"])
        _check_task_contract_pair(value["task_class"], contract["contract_type"])
        return cls(
            schema_version=SCHEMA_VERSION,
            task_class=value["task_class"],
            prompt=value["prompt"],
            contract=contract,
        )


@dataclass(frozen=True)
class RuntimeValidationResult:
    name: str
    status: str
    detail: str | None = None
    value_types_checked: bool = False


def _strict_json_loads(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RuntimeContractError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(value):
        raise RuntimeContractError("NON_FINITE_JSON_CONSTANT=" + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def load_runtime_request(path: str | Path) -> RuntimeRequest:
    try:
        value = _strict_json_loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeContractError("REQUEST_FILE_ERROR") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeContractError("INVALID_REQUEST_JSON") from exc
    return RuntimeRequest.from_mapping(value)


def _require_exact_fields(contract: dict[str, Any], fields: set[str]) -> None:
    if set(contract) != fields:
        raise RuntimeContractError("CONTRACT_FIELDS_MISMATCH")


def _validated_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeContractError("MALFORMED_CONTRACT")
    kind = value.get("contract_type")
    if kind not in CONTRACT_TYPES:
        raise RuntimeContractError("UNKNOWN_CONTRACT_TYPE")

    if kind in {"structured_json", "json_format"}:
        _require_exact_fields(value, {"contract_type", "exact_keys", "explicit_types"})
        keys, types = value["exact_keys"], value["explicit_types"]
        if (
            not isinstance(keys, list)
            or not keys
            or len(set(keys)) != len(keys)
            or any(not isinstance(key, str) or not key for key in keys)
            or not isinstance(types, dict)
            or set(types) != set(keys)
        ):
            raise RuntimeContractError("INVALID_JSON_CONTRACT")
        for declared in types.values():
            choices = declared if isinstance(declared, list) else [declared]
            if not choices or any(choice not in JSON_TYPES for choice in choices):
                raise RuntimeContractError("INVALID_JSON_TYPE")
    elif kind == "bullet_format":
        _require_exact_fields(
            value, {"contract_type", "line_count", "marker", "separator"}
        )
        if (
            type(value["line_count"]) is not int
            or value["line_count"] <= 0
            or not isinstance(value["marker"], str)
            or not value["marker"]
            or "\n" in value["marker"]
            or not isinstance(value["separator"], str)
            or not value["separator"]
            or "\n" in value["separator"]
        ):
            raise RuntimeContractError("INVALID_BULLET_CONTRACT")
    elif kind == "label_format":
        _require_exact_fields(value, {"contract_type", "line_count", "separator"})
        if (
            type(value["line_count"]) is not int
            or value["line_count"] <= 0
            or not isinstance(value["separator"], str)
            or not value["separator"]
            or "\n" in value["separator"]
        ):
            raise RuntimeContractError("INVALID_LABEL_CONTRACT")
    elif kind == "classification_labels":
        _require_exact_fields(value, {"contract_type", "permitted_labels"})
        labels = value["permitted_labels"]
        if (
            not isinstance(labels, list)
            or not labels
            or len(set(labels)) != len(labels)
            or any(not isinstance(label, str) or not label for label in labels)
        ):
            raise RuntimeContractError("INVALID_CLASSIFICATION_CONTRACT")
    else:
        _require_exact_fields(
            value, {"contract_type", "source_literal", "operation"}
        )
        if (
            not isinstance(value["source_literal"], str)
            or not value["source_literal"]
            or not isinstance(value["operation"], str)
            or value["operation"] not in OPERATIONS
        ):
            raise RuntimeContractError("INVALID_EXECUTOR_CONTRACT")
    return dict(value)


def _check_task_contract_pair(task_class: str, kind: str) -> None:
    valid = {
        "structured_json": {"extract_structured"},
        "json_format": {"format"},
        "bullet_format": {"format"},
        "label_format": {"format"},
        "classification_labels": {"classification"},
        "deterministic_executor": {"deterministic"},
    }
    if task_class not in valid[kind]:
        raise RuntimeContractError("TASK_CONTRACT_MISMATCH")


def contract_route(contract: dict[str, Any]) -> str:
    kind = contract["contract_type"]
    if kind in LOCAL_CONTRACT_TYPES:
        return "local"
    if kind in REMOTE_ONLY_CONTRACT_TYPES:
        return "remote"
    return "deterministic"


def _line_normalize(raw: str) -> str:
    if not isinstance(raw, str):
        raise ValueError("INVALID_OUTPUT_TYPE")
    if "\r" in raw.replace("\r\n", ""):
        raise ValueError("LONE_CR")
    value = raw.replace("\r\n", "\n")
    return value[:-1] if value.endswith("\n") else value


def _json_candidate(raw: str) -> str:
    """Allow only the frozen V2 contract's narrow outer-fence normalization."""
    value = _line_normalize(raw)
    lines = value.split("\n")
    if lines and lines[0] in {"```", "```json"}:
        if len(lines) < 2 or lines[-1] != "```":
            raise ValueError("INCOMPLETE_OUTER_FENCE")
        body = lines[1:-1]
        if any("```" in line for line in body):
            raise ValueError("NESTED_OR_MULTIPLE_FENCE")
        return "\n".join(body)
    if any("```" in line for line in lines):
        raise ValueError("INCOMPLETE_OR_SURROUNDING_FENCE")
    return value


def _finite(value: Any) -> None:
    if type(value) is float and not math.isfinite(value):
        raise ValueError("NON_FINITE_NUMBER")
    if isinstance(value, dict):
        for item in value.values():
            _finite(item)
    elif isinstance(value, list):
        for item in value:
            _finite(item)


def _json_type(value: Any) -> str:
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
    raise ValueError("UNKNOWN_JSON_TYPE")


def _json_object(raw: str) -> dict[str, Any]:
    value = _strict_json_loads(_json_candidate(raw))
    _finite(value)
    if not isinstance(value, dict):
        raise ValueError("NOT_A_JSON_OBJECT")
    return value


def validate_runtime_output(
    contract: dict[str, Any], raw_output: str
) -> RuntimeValidationResult:
    kind = contract["contract_type"]
    if kind not in LOCAL_CONTRACT_TYPES:
        return RuntimeValidationResult(
            "runtime_contract_v1", FAIL, "CONTRACT_NOT_LOCAL"
        )
    try:
        value = _line_normalize(raw_output)
        if kind in {"structured_json", "json_format"}:
            parsed = _json_object(value)
            if set(parsed) != set(contract["exact_keys"]):
                return RuntimeValidationResult(kind + "_v1", FAIL, "KEY_SET_MISMATCH")
            for key in contract["exact_keys"]:
                declared = contract["explicit_types"][key]
                choices = set(declared if isinstance(declared, list) else [declared])
                if _json_type(parsed[key]) not in choices:
                    return RuntimeValidationResult(
                        kind + "_v1", FAIL, "JSON_VALUE_TYPE_MISMATCH", True
                    )
            return RuntimeValidationResult(kind + "_v1", PASS, "SHAPE_AND_TYPES", True)
        lines = value.split("\n")
        if len(lines) != contract["line_count"]:
            return RuntimeValidationResult(kind + "_v1", FAIL, "LINE_COUNT_MISMATCH")
        if kind == "bullet_format":
            prefix = contract["marker"] + contract["separator"]
            accepted = all(line.startswith(prefix) and line[len(prefix):] for line in lines)
            return RuntimeValidationResult(
                kind + "_v1",
                PASS if accepted else FAIL,
                "SHAPE_ONLY" if accepted else "BULLET_SHAPE_MISMATCH",
            )
        accepted = all(
            line and line.count(contract["separator"]) == 1 for line in lines
        )
        return RuntimeValidationResult(
            kind + "_v1",
            PASS if accepted else FAIL,
            "SHAPE_ONLY" if accepted else "LABEL_SEPARATOR_MISMATCH",
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return RuntimeValidationResult(kind + "_v1", FAIL, str(exc))


def execute_deterministic(contract: dict[str, Any]) -> str:
    if contract["contract_type"] != DETERMINISTIC_CONTRACT_TYPE:
        raise RuntimeContractError("NOT_DETERMINISTIC_EXECUTOR")
    source, operation = contract["source_literal"], contract["operation"]
    if operation == "rotate_left_one":
        return source[1:] + source[:1]
    if operation == "rotate_right_two":
        return source[-2:] + source[:-2]
    if operation == "remove_vowels":
        return "".join(character for character in source if character not in "aeiou")
    if operation == "replace_letter_e_with_7":
        return source.replace("e", "7")
    if operation == "collapse_whitespace_runs":
        return re.sub(r"\s+", " ", source)
    if operation == "swap_ascii_case":
        return "".join(
            character.lower()
            if "A" <= character <= "Z"
            else character.upper()
            if "a" <= character <= "z"
            else character
            for character in source
        )
    if operation == "remove_hyphens":
        return source.replace("-", "")
    if operation == "sort_codepoints_ascending":
        return "".join(sorted(source, key=ord))
    if operation == "duplicate_final_character":
        return source + source[-1]
    if operation == "alphabetize_words":
        return " ".join(sorted(re.split(r" +", source)))
    raise RuntimeContractError("UNKNOWN_OPERATION")
