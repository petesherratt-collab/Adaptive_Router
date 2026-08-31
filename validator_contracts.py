"""Pure deterministic validation of the preregistered contract vocabulary."""

from dataclasses import dataclass
import json
import re


SCHEMA_VERSION = "validator_contracts_oos_v1"
BENCHMARK_SHA256 = "6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295"

CONTRACT_TYPES = frozenset({
    "extract_structured",
    "format_json",
    "format_bullets",
    "format_labels",
    "transform",
    "classification",
})
FORBIDDEN_FIELD_NAMES = frozenset({
    "expected",
    "oracle_correct",
    "normalized_output",
    "validator",
    "passed",
    "answer",
    "reference_answer",
})
JSON_TYPE_NAMES = frozenset({
    "null", "boolean", "number", "string", "array", "object",
})
TRANSFORM_OPERATIONS = frozenset({
    "reverse",
    "uppercase",
    "remove_spaces",
    "replace_spaces_with_underscores",
    "replace_lowercase_o_with_0",
})

COMMON_FIELDS = frozenset({
    "task_id", "task_class", "capability_family", "contract_type",
})
TYPE_FIELDS = {
    "extract_structured": frozenset({"exact_keys", "explicit_types"}),
    "format_json": frozenset({
        "exact_keys", "explicit_types", "supplied_field_values",
    }),
    "format_bullets": frozenset({
        "line_count", "marker", "separator", "items",
    }),
    "format_labels": frozenset({
        "line_count", "separator", "spacing", "ordered_fields",
    }),
    "transform": frozenset({"source_literal", "operation"}),
    "classification": frozenset({"permitted_labels"}),
}
CONTRACT_METADATA = {
    "extract_structured": ("extract_structured", {"structured_extraction"}),
    "format_json": ("format", {"json_format"}),
    "format_bullets": ("format", {"markdown_bullets"}),
    "format_labels": ("format", {"key_value_labels"}),
    "transform": ("transform", {"transformation"}),
    "classification": ("classification", {"sentiment", "priority"}),
}

ACCEPTED = "ACCEPTED"


@dataclass(frozen=True)
class ContractValidationResult:
    accepted: bool
    primary_reason: str
    reasons: tuple[str, ...]


class ContractSchemaError(ValueError):
    """A contract document or entry is not a valid frozen schema."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _result(accepted, reason=None):
    if accepted:
        return ContractValidationResult(True, ACCEPTED, ())
    reason = reason or "MALFORMED_CONTRACT"
    return ContractValidationResult(False, reason, (reason,))


def _reject_forbidden_fields(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_FIELD_NAMES:
                raise ContractSchemaError("FORBIDDEN_FIELD")
            _reject_forbidden_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_fields(nested)


def _require_nonempty_string(value):
    if not isinstance(value, str) or not value:
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")


def _require_unique_strings(value):
    if not isinstance(value, list) or not value:
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    if any(not isinstance(item, str) or not item for item in value):
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    if len(set(value)) != len(value):
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")


def _json_type(value):
    if value is None:
        return "null"
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
    return None


def _validate_explicit_types(exact_keys, explicit_types, allow_alternatives):
    if not isinstance(explicit_types, dict) or set(explicit_types) != set(exact_keys):
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    for declared in explicit_types.values():
        if isinstance(declared, list) and allow_alternatives:
            _require_unique_strings(declared)
            if any(item not in JSON_TYPE_NAMES for item in declared):
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        elif not isinstance(declared, str) or declared not in JSON_TYPE_NAMES:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")


def _validate_common(contract):
    if not isinstance(contract, dict):
        raise ContractSchemaError("MALFORMED_CONTRACT")
    contract_type = contract.get("contract_type")
    if not isinstance(contract_type, str) or contract_type not in CONTRACT_TYPES:
        raise ContractSchemaError("UNKNOWN_CONTRACT_TYPE")
    expected_fields = COMMON_FIELDS | TYPE_FIELDS[contract_type]
    actual_fields = set(contract)
    if actual_fields - expected_fields:
        raise ContractSchemaError("UNEXPECTED_CONTRACT_FIELD")
    if expected_fields - actual_fields:
        raise ContractSchemaError("MALFORMED_CONTRACT")
    for field in COMMON_FIELDS:
        _require_nonempty_string(contract[field])
    expected_class, expected_families = CONTRACT_METADATA[contract_type]
    if contract["task_class"] != expected_class:
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    if (
        not isinstance(contract["capability_family"], str)
        or contract["capability_family"] not in expected_families
    ):
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    return contract_type


def _validate_entry(contract):
    _reject_forbidden_fields(contract)
    contract_type = _validate_common(contract)

    if contract_type == "extract_structured":
        _require_unique_strings(contract["exact_keys"])
        _validate_explicit_types(
            contract["exact_keys"], contract["explicit_types"], False
        )
        return

    if contract_type == "format_json":
        exact_keys = contract["exact_keys"]
        _require_unique_strings(exact_keys)
        explicit_types = contract["explicit_types"]
        _validate_explicit_types(exact_keys, explicit_types, True)
        supplied = contract["supplied_field_values"]
        if not isinstance(supplied, dict) or set(supplied) != set(exact_keys):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")

        explicit_type_list_keys = {
            key for key, value in explicit_types.items() if isinstance(value, list)
        }
        supplied_value_list_keys = {
            key for key, value in supplied.items() if isinstance(value, list)
        }
        expected_ambiguous_keys = (
            {"port"} if contract["task_id"] == "oos_json_server" else set()
        )
        if explicit_type_list_keys != expected_ambiguous_keys:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        if supplied_value_list_keys != expected_ambiguous_keys:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")

        for key, supplied_value in supplied.items():
            declared = explicit_types[key]
            allowed_types = set(declared) if isinstance(declared, list) else {declared}
            values = supplied_value if isinstance(supplied_value, list) else [supplied_value]
            if isinstance(supplied_value, list) and not isinstance(declared, list):
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
            if not values or any(_json_type(value) not in allowed_types for value in values):
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")

        if contract["task_id"] == "oos_json_server":
            if explicit_types.get("port") != ["number", "string"]:
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
            if supplied.get("port") != [8443, "8443"]:
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        return

    if contract_type == "format_bullets":
        line_count = contract["line_count"]
        if type(line_count) is not int or line_count <= 0:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        _require_nonempty_string(contract["marker"])
        _require_nonempty_string(contract["separator"])
        _require_unique_strings(contract["items"])
        if line_count != len(contract["items"]):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        return

    if contract_type == "format_labels":
        line_count = contract["line_count"]
        if type(line_count) is not int or line_count <= 0:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        _require_nonempty_string(contract["separator"])
        _require_nonempty_string(contract["spacing"])
        fields = contract["ordered_fields"]
        if not isinstance(fields, list) or len(fields) != line_count:
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        keys = []
        for field in fields:
            if not isinstance(field, dict) or set(field) != {"key", "value"}:
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
            _require_nonempty_string(field["key"])
            if not isinstance(field["value"], str):
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
            keys.append(field["key"])
        if len(set(keys)) != len(keys):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        return

    if contract_type == "transform":
        if not isinstance(contract["source_literal"], str):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        if (
            not isinstance(contract["operation"], str)
            or contract["operation"] not in TRANSFORM_OPERATIONS
        ):
            raise ContractSchemaError("INVALID_CONTRACT_VALUE")
        return

    if contract_type == "classification":
        _require_unique_strings(contract["permitted_labels"])


def validate_contract_document(document, task_inventory=None):
    """Validate the complete contract document before any replay."""
    _reject_forbidden_fields(document)
    if not isinstance(document, dict):
        raise ContractSchemaError("MALFORMED_CONTRACT")
    if set(document) != {"schema_version", "benchmark_sha256", "contracts"}:
        raise ContractSchemaError("UNEXPECTED_CONTRACT_FIELD")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    if document["benchmark_sha256"] != BENCHMARK_SHA256:
        raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    contracts = document["contracts"]
    if not isinstance(contracts, list) or len(contracts) != 40:
        raise ContractSchemaError("MALFORMED_CONTRACT")

    task_ids = set()
    for contract in contracts:
        _validate_entry(contract)
        task_id = contract["task_id"]
        if task_id in task_ids:
            raise ContractSchemaError("DUPLICATE_TASK_ID")
        task_ids.add(task_id)
        if task_inventory is not None:
            task = task_inventory.get(task_id)
            if task is None:
                raise ContractSchemaError("CONTRACT_TASK_ID_MISMATCH")
            if (
                contract["task_class"] != task["task_class"]
                or contract["capability_family"] != task["capability_family"]
            ):
                raise ContractSchemaError("INVALID_CONTRACT_VALUE")
    if task_inventory is not None and task_ids != set(task_inventory):
        raise ContractSchemaError("CONTRACT_TASK_ID_MISMATCH")
    return document


def _reject_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"nonstandard JSON constant: {value}")


def _strict_json_loads(text):
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_constant,
    )


_JSON_FENCE = re.compile(
    r"```[ \t]*json[ \t]*\r?\n(?P<body>.*?)\r?\n```",
    flags=re.IGNORECASE | re.DOTALL,
)


def _parse_json(raw_output):
    if not isinstance(raw_output, str):
        raise TypeError("raw output must be a string")
    stripped = raw_output.strip()
    match = re.fullmatch(
        _JSON_FENCE.pattern + r"[ \t]*",
        stripped,
        flags=_JSON_FENCE.flags,
    )
    candidate = match.group("body").strip() if match else raw_output
    return _strict_json_loads(candidate)


def _parse_object(raw_output):
    try:
        value = _parse_json(raw_output)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None, "INVALID_JSON"
    if not isinstance(value, dict):
        return None, "NOT_A_JSON_OBJECT"
    return value, None


def _allowed_types(declared):
    return set(declared) if isinstance(declared, list) else {declared}


def _same_value(actual, supplied):
    if isinstance(supplied, list):
        return any(_same_value(actual, candidate) for candidate in supplied)
    if type(actual) is bool or type(supplied) is bool:
        return type(actual) is type(supplied) and actual == supplied
    if type(actual) in (int, float) and type(supplied) in (int, float):
        return actual == supplied
    return type(actual) is type(supplied) and actual == supplied


def _validate_extract(contract, raw_output):
    value, reason = _parse_object(raw_output)
    if reason:
        return _result(False, reason)
    keys = contract["exact_keys"]
    if set(value) != set(keys):
        return _result(False, "KEY_SET_MISMATCH")
    for key in keys:
        if _json_type(value[key]) not in _allowed_types(contract["explicit_types"][key]):
            return _result(False, "JSON_VALUE_TYPE_MISMATCH")
    return _result(True)


def _validate_format_json(contract, raw_output):
    value, reason = _parse_object(raw_output)
    if reason:
        return _result(False, reason)
    keys = contract["exact_keys"]
    if set(value) != set(keys):
        return _result(False, "KEY_SET_MISMATCH")
    supplied = contract["supplied_field_values"]
    for key in keys:
        if _json_type(value[key]) not in _allowed_types(contract["explicit_types"][key]):
            return _result(False, "JSON_VALUE_TYPE_MISMATCH")
        if not _same_value(value[key], supplied[key]):
            return _result(False, "SUPPLIED_VALUE_MISMATCH")
    return _result(True)


def _split_lines(raw_output):
    return raw_output.splitlines() if isinstance(raw_output, str) else None


def _validate_bullets(contract, raw_output):
    lines = _split_lines(raw_output)
    if lines is None:
        return _result(False, "INVALID_OUTPUT_TYPE")
    if len(lines) != contract["line_count"]:
        return _result(False, "LINE_COUNT_MISMATCH")
    expected = [
        contract["marker"] + contract["separator"] + item
        for item in contract["items"]
    ]
    return _result(lines == expected, "LINE_CONTENT_MISMATCH")


def _validate_labels(contract, raw_output):
    lines = _split_lines(raw_output)
    if lines is None:
        return _result(False, "INVALID_OUTPUT_TYPE")
    if len(lines) != contract["line_count"]:
        return _result(False, "LINE_COUNT_MISMATCH")
    expected = [
        field["key"] + contract["separator"] + contract["spacing"] + field["value"]
        for field in contract["ordered_fields"]
    ]
    return _result(lines == expected, "LINE_CONTENT_MISMATCH")


def _transform(source, operation):
    if operation == "reverse":
        return source[::-1]
    if operation == "uppercase":
        return source.upper()
    if operation == "remove_spaces":
        return source.replace(" ", "")
    if operation == "replace_spaces_with_underscores":
        return source.replace(" ", "_")
    if operation == "replace_lowercase_o_with_0":
        return source.replace("o", "0")
    raise ValueError("invalid transform operation")


def _validate_transform(contract, raw_output):
    if not isinstance(raw_output, str):
        return _result(False, "INVALID_OUTPUT_TYPE")
    return _result(
        raw_output == _transform(contract["source_literal"], contract["operation"]),
        "TRANSFORM_MISMATCH",
    )


def _validate_classification(contract, raw_output):
    if not isinstance(raw_output, str):
        return _result(False, "INVALID_OUTPUT_TYPE")
    candidate = raw_output.strip()
    if candidate in contract["permitted_labels"]:
        return _result(True)
    return _result(False, "LABEL_NOT_PERMITTED")


def contract_validate(contract, raw_output):
    """Validate one raw output using only the contract and raw output inputs."""
    try:
        contract_type = _validate_common(contract)
        _reject_forbidden_fields(contract)
        _validate_entry(contract)
    except ContractSchemaError as exc:
        return _result(False, exc.reason)

    if contract_type == "extract_structured":
        return _validate_extract(contract, raw_output)
    if contract_type == "format_json":
        return _validate_format_json(contract, raw_output)
    if contract_type == "format_bullets":
        return _validate_bullets(contract, raw_output)
    if contract_type == "format_labels":
        return _validate_labels(contract, raw_output)
    if contract_type == "transform":
        return _validate_transform(contract, raw_output)
    if contract_type == "classification":
        return _validate_classification(contract, raw_output)
    return _result(False, "UNKNOWN_CONTRACT_TYPE")
