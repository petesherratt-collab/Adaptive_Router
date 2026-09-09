import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from source_aware_json import (
    SourceAwareContractError,
    SourceAwareRequest,
    load_source_aware_request,
    verify_source_aware_json,
)


SOURCE = "ID A1 | name Ada | count 2\nID B2 | name Grace | count 7\n"


def byte_span(source, literal, start=0):
    encoded = source.encode("utf-8")
    first = encoded.index(literal.encode("utf-8"), start)
    return {"start": first, "end": first + len(literal.encode("utf-8"))}


def record_spans(source=SOURCE):
    encoded = source.encode("utf-8")
    split = encoded.index(b"\n") + 1
    return [{"start": 0, "end": split}, {"start": split, "end": len(encoded)}]


def mapping(candidate=None, evidence=None, source=SOURCE, selector="ID B2"):
    records = record_spans(source)
    second_start = records[1]["start"] if len(records) > 1 else 0
    source_name = "Gráce" if "Gráce" in source else "Grace"
    return {
        "schema_version": "source_aware_json_verifier_v1",
        "source_text": source,
        "contract": {
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "exact_keys": ["name", "count"],
            "explicit_types": {"name": "string", "count": "number"},
            "record_spans": records,
            "selector_literal": selector,
        },
        "candidate": candidate or {"name": "Grace", "count": 7},
        "evidence": evidence
        or {
            "record_index": 1,
            "field_spans": {
                "name": byte_span(source, source_name, second_start),
                "count": byte_span(source, "7", second_start),
            },
        },
    }


class SourceAwareJsonTests(unittest.TestCase):
    def test_reconstructs_grounded_flat_scalar_object(self):
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(mapping()))
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.reconstructed, {"name": "Grace", "count": 7})
        self.assertEqual(result.checked_field_count, 2)
        self.assertEqual(result.selected_record_index, 1)

    def test_rejects_fabricated_value(self):
        request = SourceAwareRequest.from_mapping(
            mapping(candidate={"name": "Hopper", "count": 7})
        )
        self.assertEqual(
            verify_source_aware_json(request).detail, "FIELD_VALUE_MISMATCH"
        )

    def test_rejects_wrong_selected_record(self):
        value = mapping()
        value["evidence"]["record_index"] = 0
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "SELECTED_RECORD_MISMATCH")

    def test_rejects_cross_record_splicing(self):
        value = mapping()
        value["candidate"]["name"] = "Ada"
        value["evidence"]["field_spans"]["name"] = byte_span(SOURCE, "Ada")
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "FIELD_SPAN_OUTSIDE_RECORD")

    def test_rejects_type_substitution(self):
        value = mapping(candidate={"name": "Grace", "count": "7"})
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "VALUE_TYPE_MISMATCH")

    def test_json_numbers_compare_by_numeric_value(self):
        value = mapping(candidate={"name": "Grace", "count": 7.0})
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.reconstructed, {"name": "Grace", "count": 7})

    def test_rejects_candidate_key_drift(self):
        value = mapping(candidate={"name": "Grace", "total": 7})
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "KEY_SET_MISMATCH")

    def test_rejects_missing_or_extra_proof(self):
        for field_spans in (
            {"name": byte_span(SOURCE, "Grace")},
            {
                "name": byte_span(SOURCE, "Grace"),
                "count": byte_span(SOURCE, "7"),
                "extra": byte_span(SOURCE, "B2"),
            },
        ):
            with self.subTest(fields=set(field_spans)):
                value = mapping()
                value["evidence"]["field_spans"] = field_spans
                result = verify_source_aware_json(
                    SourceAwareRequest.from_mapping(value)
                )
                self.assertEqual(result.detail, "EVIDENCE_KEY_SET_MISMATCH")

    def test_rejects_selector_ambiguity(self):
        source = "ID B2 | name Ada | count 2\nID B2 | name Grace | count 7\n"
        value = mapping(source=source)
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "SELECTOR_NOT_UNIQUE")

    def test_rejects_nested_candidate(self):
        value = mapping(candidate={"name": {"first": "Grace"}, "count": 7})
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "VALUE_TYPE_MISMATCH")

    def test_rejects_field_span_that_splits_utf8(self):
        source = "ID A1 | name Ada | count 2\nID B2 | name Gráce | count 7\n"
        value = mapping(
            source=source, candidate={"name": "Gráce", "count": 7}
        )
        accent = source.encode("utf-8").index("á".encode("utf-8"))
        value["evidence"]["field_spans"]["name"] = {
            "start": accent + 1,
            "end": accent + 2,
        }
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "FIELD_SPAN_NOT_UTF8")

    def test_source_hash_mismatch_is_fatal_contract_error(self):
        value = mapping()
        value["contract"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(SourceAwareContractError, "SOURCE_HASH_MISMATCH"):
            SourceAwareRequest.from_mapping(value)

    def test_record_spans_must_be_ordered_and_nonoverlapping(self):
        value = mapping()
        value["contract"]["record_spans"][1]["start"] = 1
        with self.assertRaisesRegex(SourceAwareContractError, "INVALID_RECORD_SPAN"):
            SourceAwareRequest.from_mapping(value)

    def test_record_span_cannot_exceed_source(self):
        value = mapping()
        value["contract"]["record_spans"][1]["end"] += 1
        with self.assertRaisesRegex(SourceAwareContractError, "INVALID_RECORD_SPAN"):
            SourceAwareRequest.from_mapping(value)

    def test_malformed_type_declaration_uses_contract_error(self):
        value = mapping()
        value["contract"]["explicit_types"]["count"] = ["number"]
        with self.assertRaisesRegex(
            SourceAwareContractError, "INVALID_FLAT_SCALAR_SCHEMA"
        ):
            SourceAwareRequest.from_mapping(value)

    def test_loader_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(
                '{"schema_version":"source_aware_json_verifier_v1",'
                '"source_text":"x","source_text":"y",'
                '"contract":{},"candidate":{},"evidence":{}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SourceAwareContractError, "DUPLICATE_JSON_KEY"):
                load_source_aware_request(path)

    def test_loader_rejects_non_finite_json_constant(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            text = json.dumps(mapping()).replace('"count": 7', '"count": NaN', 1)
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(
                SourceAwareContractError, "NON_FINITE_JSON_CONSTANT"
            ):
                load_source_aware_request(path)

    def test_boolean_cannot_satisfy_number(self):
        value = mapping(candidate={"name": "Grace", "count": True})
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.detail, "VALUE_TYPE_MISMATCH")

    def test_request_round_trips_through_json_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(mapping()), encoding="utf-8")
            result = verify_source_aware_json(load_source_aware_request(path))
        self.assertEqual(result.status, "PASS")

    def test_same_type_field_role_swap_is_a_known_limitation(self):
        source = "ID B2 | city London | owner Grace\n"
        encoded = source.encode("utf-8")
        value = {
            "schema_version": "source_aware_json_verifier_v1",
            "source_text": source,
            "contract": {
                "source_sha256": hashlib.sha256(encoded).hexdigest(),
                "exact_keys": ["city", "owner"],
                "explicit_types": {"city": "string", "owner": "string"},
                "record_spans": [{"start": 0, "end": len(encoded)}],
                "selector_literal": "ID B2",
            },
            "candidate": {"city": "Grace", "owner": "London"},
            "evidence": {
                "record_index": 0,
                "field_spans": {
                    "city": byte_span(source, "Grace"),
                    "owner": byte_span(source, "London"),
                },
            },
        }
        result = verify_source_aware_json(SourceAwareRequest.from_mapping(value))
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.reconstructed, {"city": "Grace", "owner": "London"})
