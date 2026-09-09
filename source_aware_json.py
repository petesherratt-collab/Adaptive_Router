"""Offline candidate for source-aware, proof-carrying JSON extraction.

This module is deliberately separate from the runtime router. It verifies a
narrow claim: a flat scalar JSON object was reconstructed from byte spans in
one caller-declared source record selected by a unique caller-declared literal.
It does not establish arbitrary semantic correctness or authorize local output.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "source_aware_json_verifier_v1"
PASS, FAIL = "PASS", "FAIL"
JSON_SCALAR_TYPES = frozenset({"boolean", "number", "string", "null"})
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class SourceAwareContractError(ValueError):
    """Trusted request metadata is malformed or internally inconsistent."""


@dataclass(frozen=True)
class SourceAwareVerificationResult:
    status: str
    detail: str
    checked_field_count: int = 0
    selected_record_index: int | None = None
    reconstructed: dict[str, Any] | None = None


@dataclass(frozen=True)
class SourceAwareRequest:
    source_text: str
    source_bytes: bytes
    source_sha256: str
    exact_keys: tuple[str, ...]
    explicit_types: dict[str, str]
    record_spans: tuple[tuple[int, int], ...]
    selector_literal: str
    selector_bytes: bytes
    candidate: Any
    evidence: Any

    @classmethod
    def from_mapping(cls, value: Any) -> "SourceAwareRequest":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "source_text",
            "contract",
            "candidate",
            "evidence",
        }:
            raise SourceAwareContractError("REQUEST_FIELDS_MISMATCH")
        if value["schema_version"] != SCHEMA_VERSION:
            raise SourceAwareContractError("REQUEST_SCHEMA_MISMATCH")
        source_text = value["source_text"]
        if not isinstance(source_text, str) or not source_text:
            raise SourceAwareContractError("INVALID_SOURCE_TEXT")
        source_bytes = source_text.encode("utf-8")

        contract = value["contract"]
        if not isinstance(contract, dict) or set(contract) != {
            "source_sha256",
            "exact_keys",
            "explicit_types",
            "record_spans",
            "selector_literal",
        }:
            raise SourceAwareContractError("CONTRACT_FIELDS_MISMATCH")

        source_sha256 = contract["source_sha256"]
        if not isinstance(source_sha256, str) or not SHA256_PATTERN.fullmatch(
            source_sha256
        ):
            raise SourceAwareContractError("INVALID_SOURCE_SHA256")
        if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
            raise SourceAwareContractError("SOURCE_HASH_MISMATCH")

        keys = contract["exact_keys"]
        types = contract["explicit_types"]
        if (
            not isinstance(keys, list)
            or not keys
            or any(not isinstance(key, str) or not key for key in keys)
            or len(set(keys)) != len(keys)
            or not isinstance(types, dict)
            or set(types) != set(keys)
            or any(
                not isinstance(type_name, str)
                or type_name not in JSON_SCALAR_TYPES
                for type_name in types.values()
            )
        ):
            raise SourceAwareContractError("INVALID_FLAT_SCALAR_SCHEMA")

        record_spans = _validated_record_spans(
            contract["record_spans"], len(source_bytes)
        )
        selector_literal = contract["selector_literal"]
        if not isinstance(selector_literal, str) or not selector_literal:
            raise SourceAwareContractError("INVALID_SELECTOR_LITERAL")

        return cls(
            source_text=source_text,
            source_bytes=source_bytes,
            source_sha256=source_sha256,
            exact_keys=tuple(keys),
            explicit_types=dict(types),
            record_spans=record_spans,
            selector_literal=selector_literal,
            selector_bytes=selector_literal.encode("utf-8"),
            candidate=value["candidate"],
            evidence=value["evidence"],
        )


def _validated_record_spans(value: Any, source_length: int) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, list) or not value:
        raise SourceAwareContractError("INVALID_RECORD_SPANS")
    spans: list[tuple[int, int]] = []
    previous_end = 0
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"start", "end"}:
            raise SourceAwareContractError("INVALID_RECORD_SPAN")
        start, end = item["start"], item["end"]
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or start >= end
            or end > source_length
            or (index > 0 and start < previous_end)
        ):
            raise SourceAwareContractError("INVALID_RECORD_SPAN")
        spans.append((start, end))
        previous_end = end
    return tuple(spans)


def _strict_json_loads(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SourceAwareContractError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(value):
        raise SourceAwareContractError("NON_FINITE_JSON_CONSTANT=" + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def load_source_aware_request(path: str | Path) -> SourceAwareRequest:
    try:
        value = _strict_json_loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SourceAwareContractError("REQUEST_FILE_ERROR") from exc
    except json.JSONDecodeError as exc:
        raise SourceAwareContractError("INVALID_REQUEST_JSON") from exc
    return SourceAwareRequest.from_mapping(value)


def _json_scalar_type(value: Any) -> str | None:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) in {int, float}:
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return "number"
    if isinstance(value, str):
        return "string"
    return None


def _selector_record_indexes(request: SourceAwareRequest) -> list[int]:
    indexes = []
    for index, (start, end) in enumerate(request.record_spans):
        record = request.source_bytes[start:end]
        if record.count(request.selector_bytes):
            indexes.append(index)
    return indexes


def _decode_proven_value(raw: bytes, declared_type: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("FIELD_SPAN_NOT_UTF8") from exc
    if declared_type == "string":
        return text
    try:
        value = _strict_json_loads(text)
    except (json.JSONDecodeError, SourceAwareContractError) as exc:
        raise ValueError("FIELD_SCALAR_PARSE_FAILED") from exc
    if _json_scalar_type(value) != declared_type:
        raise ValueError("FIELD_SOURCE_TYPE_MISMATCH")
    return value


def verify_source_aware_json(
    request: SourceAwareRequest,
) -> SourceAwareVerificationResult:
    """Verify and reconstruct a flat scalar object from source byte spans."""
    candidate = request.candidate
    if not isinstance(candidate, dict):
        return SourceAwareVerificationResult(FAIL, "CANDIDATE_NOT_OBJECT")
    if set(candidate) != set(request.exact_keys):
        return SourceAwareVerificationResult(FAIL, "KEY_SET_MISMATCH")
    for key in request.exact_keys:
        if _json_scalar_type(candidate[key]) != request.explicit_types[key]:
            return SourceAwareVerificationResult(FAIL, "VALUE_TYPE_MISMATCH")

    evidence = request.evidence
    if not isinstance(evidence, dict) or set(evidence) != {
        "record_index",
        "field_spans",
    }:
        return SourceAwareVerificationResult(FAIL, "EVIDENCE_FIELDS_MISMATCH")
    record_index = evidence["record_index"]
    if type(record_index) is not int or not 0 <= record_index < len(
        request.record_spans
    ):
        return SourceAwareVerificationResult(FAIL, "INVALID_RECORD_INDEX")

    selector_indexes = _selector_record_indexes(request)
    if len(selector_indexes) != 1:
        return SourceAwareVerificationResult(FAIL, "SELECTOR_NOT_UNIQUE")
    if selector_indexes[0] != record_index:
        return SourceAwareVerificationResult(FAIL, "SELECTED_RECORD_MISMATCH")

    field_spans = evidence["field_spans"]
    if not isinstance(field_spans, dict) or set(field_spans) != set(
        request.exact_keys
    ):
        return SourceAwareVerificationResult(FAIL, "EVIDENCE_KEY_SET_MISMATCH")

    record_start, record_end = request.record_spans[record_index]
    reconstructed: dict[str, Any] = {}
    for key in request.exact_keys:
        span = field_spans[key]
        if not isinstance(span, dict) or set(span) != {"start", "end"}:
            return SourceAwareVerificationResult(FAIL, "INVALID_FIELD_SPAN")
        start, end = span["start"], span["end"]
        if type(start) is not int or type(end) is not int or start >= end:
            return SourceAwareVerificationResult(FAIL, "INVALID_FIELD_SPAN")
        if start < record_start or end > record_end:
            return SourceAwareVerificationResult(FAIL, "FIELD_SPAN_OUTSIDE_RECORD")
        try:
            proven = _decode_proven_value(
                request.source_bytes[start:end], request.explicit_types[key]
            )
        except ValueError as exc:
            return SourceAwareVerificationResult(FAIL, str(exc))
        if proven != candidate[key]:
            return SourceAwareVerificationResult(FAIL, "FIELD_VALUE_MISMATCH")
        reconstructed[key] = proven

    return SourceAwareVerificationResult(
        PASS,
        "SOURCE_GROUNDED_FLAT_SCALARS",
        checked_field_count=len(request.exact_keys),
        selected_record_index=record_index,
        reconstructed=reconstructed,
    )
