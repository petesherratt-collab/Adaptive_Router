import json
import tempfile
import unittest
from pathlib import Path

from runtime_contracts import (
    RuntimeContractError,
    RuntimeRequest,
    contract_route,
    execute_deterministic,
    load_runtime_request,
    validate_runtime_output,
)


def request(task_class, contract, prompt="Do the requested task."):
    return RuntimeRequest.from_mapping(
        {
            "schema_version": "runtime_request_v1",
            "task_class": task_class,
            "prompt": prompt,
            "contract": contract,
        }
    )


class RuntimeContractTests(unittest.TestCase):
    def test_rejects_unknown_request_fields(self):
        with self.assertRaisesRegex(RuntimeContractError, "REQUEST_FIELDS_MISMATCH"):
            RuntimeRequest.from_mapping(
                {
                    "schema_version": "runtime_request_v1",
                    "task_class": "format",
                    "prompt": "Format this.",
                    "contract": {
                        "contract_type": "bullet_format",
                        "line_count": 1,
                        "marker": "-",
                        "separator": " ",
                    },
                    "expected": "forbidden",
                }
            )

    def test_request_loader_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(
                '{"schema_version":"runtime_request_v1",'
                '"task_class":"format","task_class":"format",'
                '"prompt":"Format this.","contract":{'
                '"contract_type":"bullet_format","line_count":1,'
                '"marker":"-","separator":" "}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeContractError, "DUPLICATE_JSON_KEY"):
                load_runtime_request(path)

    def test_task_and_contract_must_agree(self):
        with self.assertRaisesRegex(RuntimeContractError, "TASK_CONTRACT_MISMATCH"):
            request(
                "classification",
                {
                    "contract_type": "bullet_format",
                    "line_count": 1,
                    "marker": "-",
                    "separator": " ",
                },
            )

    def test_structured_json_checks_exact_keys_and_types(self):
        contract = request(
            "extract_structured",
            {
                "contract_type": "structured_json",
                "exact_keys": ["name", "count", "enabled"],
                "explicit_types": {
                    "name": "string",
                    "count": "number",
                    "enabled": "boolean",
                },
            },
        ).contract
        self.assertEqual(
            validate_runtime_output(
                contract, '{"name":"Ada","count":2,"enabled":true}'
            ).status,
            "PASS",
        )
        self.assertEqual(
            validate_runtime_output(
                contract, '{"name":"Ada","count":"2","enabled":true}'
            ).detail,
            "JSON_VALUE_TYPE_MISMATCH",
        )
        self.assertEqual(
            validate_runtime_output(
                contract, '{"name":"Ada","count":2,"enabled":true,"extra":1}'
            ).detail,
            "KEY_SET_MISMATCH",
        )

    def test_json_contract_allows_one_complete_outer_fence(self):
        contract = request(
            "extract_structured",
            {
                "contract_type": "structured_json",
                "exact_keys": ["name", "count"],
                "explicit_types": {"name": "string", "count": "number"},
            },
        ).contract
        output = "```json\n{\\"name\\":\\"Ada\\",\\"count\\":2}\n```"
        self.assertEqual(validate_runtime_output(contract, output).status, "PASS")

    def test_json_contract_rejects_surrounding_or_incomplete_fence(self):
        contract = request(
            "format",
            {
                "contract_type": "json_format",
                "exact_keys": ["count"],
                "explicit_types": {"count": "number"},
            },
        ).contract
        for output in (
            "Here it is:\n```json\n{\\"count\\":2}\n```",
            "```json\n{\\"count\\":2}",
            "```json\n```\n{\\"count\\":2}\n```",
        ):
            with self.subTest(output=output):
                self.assertEqual(
                    validate_runtime_output(contract, output).status, "FAIL"
                )

    def test_boolean_does_not_satisfy_number_type(self):
        contract = request(
            "format",
            {
                "contract_type": "json_format",
                "exact_keys": ["count"],
                "explicit_types": {"count": "number"},
            },
        ).contract
        self.assertEqual(
            validate_runtime_output(contract, '{"count":true}').status, "FAIL"
        )

    def test_bullet_contract_checks_every_line(self):
        contract = request(
            "format",
            {
                "contract_type": "bullet_format",
                "line_count": 2,
                "marker": "-",
                "separator": " ",
            },
        ).contract
        self.assertEqual(
            validate_runtime_output(contract, "- alpha\n- beta").status, "PASS"
        )
        self.assertEqual(
            validate_runtime_output(contract, "- alpha\nbeta").status, "FAIL"
        )

    def test_label_contract_requires_exactly_one_separator_per_line(self):
        contract = request(
            "format",
            {
                "contract_type": "label_format",
                "line_count": 2,
                "separator": " :: ",
            },
        ).contract
        self.assertEqual(
            validate_runtime_output(contract, "a :: b\nc :: d").status, "PASS"
        )
        self.assertEqual(
            validate_runtime_output(contract, "a :: b :: c\nd :: e").status,
            "FAIL",
        )

    def test_classification_contract_is_remote_only(self):
        contract = request(
            "classification",
            {
                "contract_type": "classification_labels",
                "permitted_labels": ["positive", "negative", "neutral"],
            },
        ).contract
        self.assertEqual(contract_route(contract), "remote")
        self.assertEqual(
            validate_runtime_output(contract, "positive").detail,
            "CONTRACT_NOT_LOCAL",
        )

    def test_deterministic_executor_bypasses_models(self):
        contract = request(
            "deterministic",
            {
                "contract_type": "deterministic_executor",
                "source_literal": "north-star-5",
                "operation": "remove_hyphens",
            },
        ).contract
        self.assertEqual(contract_route(contract), "deterministic")
        self.assertEqual(execute_deterministic(contract), "northstar5")

    def test_all_frozen_executor_operations_are_available(self):
        cases = {
            "rotate_left_one": ("lantern", "anternl"),
            "rotate_right_two": ("sapphire", "resapphi"),
            "remove_vowels": ("sequoia", "sq"),
            "replace_letter_e_with_7": ("velvet", "v7lv7t"),
            "collapse_whitespace_runs": ("cinder   quay", "cinder quay"),
            "swap_ascii_case": ("Rill7Zone", "rILL7zONE"),
            "remove_hyphens": ("north-star-5", "northstar5"),
            "sort_codepoints_ascending": ("b4Aa", "4Aab"),
            "duplicate_final_character": ("plum", "plumm"),
            "alphabetize_words": ("zeta alpha", "alpha zeta"),
        }
        for operation, (source, expected) in cases.items():
            with self.subTest(operation=operation):
                contract = request(
                    "deterministic",
                    {
                        "contract_type": "deterministic_executor",
                        "source_literal": source,
                        "operation": operation,
                    },
                ).contract
                self.assertEqual(execute_deterministic(contract), expected)


if __name__ == "__main__":
    unittest.main()
