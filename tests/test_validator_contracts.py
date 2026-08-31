import copy
import inspect
import json
from pathlib import Path
import unittest

from validator_contracts import (
    ACCEPTED,
    BENCHMARK_SHA256,
    FORBIDDEN_FIELD_NAMES,
    ContractValidationResult,
    ContractSchemaError,
    contract_validate,
    validate_contract_document,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "validator_contracts_oos_v1.json"


def document():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def contract(task_id):
    return next(item for item in document()["contracts"] if item["task_id"] == task_id)


class SchemaTests(unittest.TestCase):
    def test_frozen_document_is_exactly_40_unique_contracts(self):
        value = document()
        validate_contract_document(value)
        self.assertEqual(set(value), {"schema_version", "benchmark_sha256", "contracts"})
        self.assertEqual(len(value["contracts"]), 40)
        self.assertEqual(len({item["task_id"] for item in value["contracts"]}), 40)
        self.assertEqual(value["benchmark_sha256"], BENCHMARK_SHA256)

    def test_public_signature_and_immutable_result(self):
        self.assertEqual(
            tuple(inspect.signature(contract_validate).parameters),
            ("contract", "raw_output"),
        )
        result = contract_validate(contract("oos_transform_reverse"), "langis")
        self.assertIsInstance(result, ContractValidationResult)
        self.assertTrue(result.accepted)
        self.assertEqual(result.primary_reason, ACCEPTED)
        self.assertEqual(result.reasons, ())
        with self.assertRaises(AttributeError):
            result.accepted = False

    def test_forbidden_names_are_rejected_at_any_nesting_depth(self):
        for forbidden in sorted(FORBIDDEN_FIELD_NAMES):
            value = document()
            value["contracts"][0]["nested"] = {"list": [{forbidden: True}]}
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ContractSchemaError, "FORBIDDEN_FIELD"):
                    validate_contract_document(value)

    def test_missing_and_unexpected_fields_fail_closed(self):
        missing = copy.deepcopy(contract("oos_transform_reverse"))
        del missing["operation"]
        result = contract_validate(missing, "langis")
        self.assertEqual(result.primary_reason, "MALFORMED_CONTRACT")

        unexpected = copy.deepcopy(contract("oos_transform_reverse"))
        unexpected["unlisted"] = True
        result = contract_validate(unexpected, "langis")
        self.assertEqual(result.primary_reason, "UNEXPECTED_CONTRACT_FIELD")

        value = document()
        transform = next(
            item
            for item in value["contracts"]
            if item["task_id"] == "oos_transform_reverse"
        )
        transform.pop("operation")
        with self.assertRaisesRegex(ContractSchemaError, "MALFORMED_CONTRACT"):
            validate_contract_document(value)

    def test_invalid_types_unknown_types_and_contradictions_fail_closed(self):
        item = copy.deepcopy(contract("oos_extract_person"))
        item["explicit_types"]["age"] = "integer"
        self.assertEqual(
            contract_validate(item, '{"name":"anything","age":1}').primary_reason,
            "INVALID_CONTRACT_VALUE",
        )

        unknown = copy.deepcopy(contract("oos_transform_reverse"))
        unknown["contract_type"] = "unknown"
        self.assertEqual(
            contract_validate(unknown, "anything").primary_reason,
            "UNKNOWN_CONTRACT_TYPE",
        )

        unhashable = copy.deepcopy(contract("oos_transform_reverse"))
        unhashable["operation"] = []
        self.assertEqual(
            contract_validate(unhashable, "anything").primary_reason,
            "INVALID_CONTRACT_VALUE",
        )

    def test_contract_task_set_and_duplicate_ids_fail_closed(self):
        value = document()
        value["contracts"].pop()
        with self.assertRaises(ContractSchemaError):
            validate_contract_document(value)

        value = document()
        value["contracts"].append(copy.deepcopy(value["contracts"][0]))
        with self.assertRaises(ContractSchemaError):
            validate_contract_document(value)

        value = document()
        value["contracts"][1]["task_id"] = value["contracts"][0]["task_id"]
        with self.assertRaisesRegex(ContractSchemaError, "DUPLICATE_TASK_ID"):
            validate_contract_document(value)


class JsonTests(unittest.TestCase):
    def test_extract_checks_keys_and_types_but_not_values(self):
        item = contract("oos_extract_person")
        self.assertTrue(
            contract_validate(item, '{"name":"not the source","age":88}').accepted
        )
        self.assertEqual(
            contract_validate(item, '{"name":"Maya Chen","age":"29"}').primary_reason,
            "JSON_VALUE_TYPE_MISMATCH",
        )
        self.assertEqual(
            contract_validate(item, '{"name":"Maya Chen","wrong":29}').primary_reason,
            "KEY_SET_MISMATCH",
        )
        self.assertEqual(
            contract_validate(item, '["Maya Chen",29]').primary_reason,
            "NOT_A_JSON_OBJECT",
        )

    def test_meeting_time_and_train_departure_are_strings(self):
        meeting = contract("oos_extract_meeting")
        train = contract("oos_extract_train")
        self.assertTrue(
            contract_validate(
                meeting,
                '{"topic":"x","time":"14:30","room":"y"}',
            ).accepted
        )
        self.assertTrue(
            contract_validate(
                train,
                '{"origin":"Norwich","destination":"Cambridge","departure":"09:17"}',
            ).accepted
        )

    def test_extract_and_format_json_share_one_outer_fence_parser(self):
        extract = contract("oos_extract_person")
        formatted = contract("oos_json_contact")
        good_extract = '{"name":"x","age":1}'
        good_format = '{"first_name":"Leila","postcode":"SE18 6HQ"}'
        self.assertTrue(contract_validate(extract, good_extract).accepted)
        self.assertTrue(contract_validate(extract, f"```json\n{good_extract}\n```").accepted)
        self.assertTrue(contract_validate(formatted, good_format).accepted)
        self.assertTrue(contract_validate(formatted, f"```json\n{good_format}\n```").accepted)
        malformed = [
            f"```json\n{good_extract}",
            f"```json\n{good_extract}\n```\n```json\n{good_extract}\n```",
            f"prose\n```json\n{good_extract}\n```",
        ]
        for raw in malformed:
            with self.subTest(raw=raw):
                self.assertFalse(contract_validate(extract, raw).accepted)
                self.assertFalse(contract_validate(formatted, raw).accepted)

    def test_duplicate_keys_and_nonstandard_constants_are_rejected(self):
        item = contract("oos_json_contact")
        duplicate = '{"first_name":"Leila","first_name":"Other","postcode":"SE18 6HQ"}'
        for raw in (duplicate, '{"first_name":NaN,"postcode":"SE18 6HQ"}', '{"first_name":Infinity,"postcode":"SE18 6HQ"}'):
            with self.subTest(raw=raw):
                self.assertEqual(contract_validate(item, raw).primary_reason, "INVALID_JSON")

    def test_json_values_and_only_server_ambiguity(self):
        server = contract("oos_json_server")
        for port in (8443, "8443"):
            self.assertTrue(
                contract_validate(server, json.dumps({"host": "edge-7", "port": port})).accepted
            )
        contact = copy.deepcopy(contract("oos_json_contact"))
        contact["explicit_types"]["first_name"] = ["string", "number"]
        self.assertEqual(
            contract_validate(contact, '{"first_name":"Leila","postcode":"SE18 6HQ"}').primary_reason,
            "INVALID_CONTRACT_VALUE",
        )
        contact = copy.deepcopy(contract("oos_json_contact"))
        contact["supplied_field_values"]["first_name"] = ["Leila", "L"]
        self.assertEqual(
            contract_validate(contact, '{"first_name":"Leila","postcode":"SE18 6HQ"}').primary_reason,
            "INVALID_CONTRACT_VALUE",
        )

    def test_server_alternatives_cannot_move_or_change(self):
        server = copy.deepcopy(contract("oos_json_server"))
        server["explicit_types"]["host"] = ["string", "number"]
        self.assertEqual(
            contract_validate(server, '{"host":"edge-7","port":8443}').primary_reason,
            "INVALID_CONTRACT_VALUE",
        )
        server = copy.deepcopy(contract("oos_json_server"))
        server["supplied_field_values"]["port"] = 8443
        self.assertEqual(
            contract_validate(server, '{"host":"edge-7","port":8443}').primary_reason,
            "INVALID_CONTRACT_VALUE",
        )
        server = copy.deepcopy(contract("oos_json_server"))
        server["explicit_types"]["port"] = ["string", "number"]
        self.assertEqual(
            contract_validate(server, '{"host":"edge-7","port":8443}').primary_reason,
            "INVALID_CONTRACT_VALUE",
        )
        server = copy.deepcopy(contract("oos_json_server"))
        server["supplied_field_values"]["port"] = [8443, "08443"]
        self.assertEqual(
            contract_validate(server, '{"host":"edge-7","port":8443}').primary_reason,
            "INVALID_CONTRACT_VALUE",
        )


class TextAndTransformTests(unittest.TestCase):
    def test_bullets_reject_marker_order_spacing_and_line_defects(self):
        item = contract("oos_bullets_fruit")
        self.assertTrue(contract_validate(item, "- pear\n- plum\n- kiwi").accepted)
        for raw in (
            "* pear\n- plum\n- kiwi",
            "- plum\n- pear\n- kiwi",
            "-  pear\n- plum\n- kiwi",
            "- pear\n\n- plum\n- kiwi",
            "heading\n- pear\n- plum\n- kiwi",
            "- pear \n- plum\n- kiwi",
        ):
            self.assertFalse(contract_validate(item, raw).accepted)

    def test_labels_reject_key_separator_order_value_and_lines(self):
        item = contract("oos_labels_account")
        self.assertTrue(contract_validate(item, "account_id: AC-55\nstate: active").accepted)
        for raw in (
            "state: active\naccount_id: AC-55",
            "account_id=AC-55\nstate: active",
            "account_id: AC-56\nstate: active",
            "account_id: AC-55\nstate: active\n\n",
            "account_id: AC-55\nstate: active\nprose",
        ):
            self.assertFalse(contract_validate(item, raw).accepted)

    def test_all_transformations_are_recomputed_and_raw_exact(self):
        outputs = {
            "oos_transform_reverse": "langis",
            "oos_transform_uppercase": "EDGE NODE",
            "oos_transform_remove_spaces": "pairedsample",
            "oos_transform_underscores": "frozen_policy_check",
            "oos_transform_replace_o": "l0cal m0del",
        }
        for task_id, output in outputs.items():
            with self.subTest(task_id=task_id):
                self.assertTrue(contract_validate(contract(task_id), output).accepted)
                self.assertFalse(contract_validate(contract(task_id), output + "\n").accepted)

    def test_classification_accepts_outer_whitespace_but_not_other_changes(self):
        item = contract("oos_sentiment_positive_service")
        for raw in ("Positive", "Positive\n", "  Positive \r\n"):
            self.assertTrue(contract_validate(item, raw).accepted)
        for raw in (
            "positive", "Positive.", "**Positive**", "Result: Positive",
            "Positive\nNegative", "```Positive```", "Unknown",
        ):
            self.assertFalse(contract_validate(item, raw).accepted)
        self.assertTrue(contract_validate(item, "Negative\n").accepted)


if __name__ == "__main__":
    unittest.main()
