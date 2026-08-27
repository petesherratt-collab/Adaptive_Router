"""Regression tests for the live-router validator scope defect.

Discovered 2026-08-27. The frozen out-of-sample evidence
(`benchmark_runs_oos_local_v1.jsonl`) recorded 10 structured-extraction
strict failures. Replaying those exact outputs through the live router's
`json_structure_v1` showed it returned PASS on all 10, because the
required-key regex failed to parse `Required keys exactly: ...` and the
validator silently degraded to "is this JSON" while still reporting PASS.

The prompts and outputs below are copied verbatim from the frozen suite and
frozen evidence. Nothing in this module reads or modifies the frozen files.

These tests lock in three properties:

1. a declared-but-unparsable key specification fails closed;
2. an applicable pass records exactly which keys were checked;
3. value-type defects are NOT claimed as caught, because this validator has
   no explicit schema and must not infer a guarantee it cannot establish.
"""

import unittest

from validators import (
    FAIL,
    MISSING_REQUIRED_KEYS,
    NO_KEY_SPECIFICATION,
    PASS,
    REQUIRED_KEYS_UNPARSED,
    SYNTAX_ONLY,
    required_keys,
    validate,
)

# Frozen suite: oos_validation_v1, benchmark SHA-256
# 6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295
WEATHER_PROMPT = (
    "Extract one JSON object from the source record. Required keys exactly: "
    "city, temperature_c, condition. Preserve source spelling, "
    "capitalization, underscores, and punctuation in string values. "
    "Represent numeric values as JSON numbers. Do not infer unstated values. "
    "Output only JSON. Source: Weather record: city Glasgow; temperature 11 "
    "degrees Celsius; condition rain."
)
DEVICE_PROMPT = (
    "Extract one JSON object from the source record. Required keys exactly: "
    "asset_id, operating_system, version. Preserve source spelling, "
    "capitalization, underscores, and punctuation in string values. "
    "Represent numeric values as JSON numbers. Do not infer unstated values. "
    "Output only JSON. Source: Device record: asset ID LT-882; operating "
    "system Fedora; version 42."
)
SERVER_PROMPT = (
    "Format the supplied fields as one JSON object. Use exactly these "
    "lowercase keys: host, port. Use the supplied values without "
    "modification. Include no additional keys or prose. Source: Host is "
    "edge-7 and port is 8443."
)

# Verbatim Gemma 3 270M outputs from the frozen local evidence.
WEATHER_OUTPUT = (
    '```json\n{\n  "city": "Glasgow",\n  "temperature": 11,\n'
    '  "condition": "rain"\n}\n```'
)
DEVICE_OUTPUT = (
    '```json\n{\n    "asset_id": "LT-882",\n'
    '    "operating_system": "Fedora",\n    "version": "42"\n}\n```'
)
SERVER_OUTPUT = '```json\n{\n  "host": "edge-7",\n  "port": "8443"\n}\n```'


class RequiredKeyParsingTests(unittest.TestCase):
    def test_frozen_prompt_phrasings_parse(self):
        for prompt, expected in (
            (WEATHER_PROMPT, ["city", "temperature_c", "condition"]),
            (DEVICE_PROMPT, ["asset_id", "operating_system", "version"]),
            (SERVER_PROMPT, ["host", "port"]),
            ("extract JSON required keys: name, age", ["name", "age"]),
        ):
            with self.subTest(prompt=prompt[:40]):
                declared, keys = required_keys(prompt)
                self.assertTrue(declared)
                self.assertEqual(keys, expected)

    def test_prompt_without_key_mention_is_not_declared(self):
        declared, keys = required_keys("extract JSON")
        self.assertFalse(declared)
        self.assertEqual(keys, [])


class FailClosedTests(unittest.TestCase):
    def test_declared_but_unparsable_keys_fail_closed(self):
        # Keys are declared in prose the extractor cannot parse. The old
        # behaviour was PASS on any parseable JSON; it must now escalate.
        prompt = "Extract JSON. The required keys are listed in the schema above."
        result = validate("extract_structured", prompt, '{"anything":1}')
        self.assertEqual(result.status, FAIL)
        self.assertEqual(result.detail, REQUIRED_KEYS_UNPARSED)
        self.assertEqual(result.checked_keys, ())

    def test_wrong_key_name_fails(self):
        # Frozen oos_extract_weather: emitted `temperature`, required
        # `temperature_c`. Failed the oracle 5/5 and passed the old validator.
        result = validate("extract_structured", WEATHER_PROMPT, WEATHER_OUTPUT)
        self.assertEqual(result.status, FAIL)
        self.assertTrue(result.detail.startswith(MISSING_REQUIRED_KEYS))
        self.assertIn("temperature_c", result.detail)
        self.assertEqual(
            result.checked_keys, ("city", "temperature_c", "condition")
        )

    def test_non_object_json_fails_when_keys_required(self):
        result = validate("extract_structured", WEATHER_PROMPT, "[1, 2, 3]")
        self.assertEqual(result.status, FAIL)
        self.assertEqual(result.detail, "NOT_A_JSON_OBJECT")


class CheckedKeyDisclosureTests(unittest.TestCase):
    def test_applicable_pass_records_checked_keys(self):
        result = validate(
            "extract_structured",
            WEATHER_PROMPT,
            '{"city":"Glasgow","temperature_c":11,"condition":"rain"}',
        )
        self.assertEqual(result.status, PASS)
        self.assertEqual(
            result.checked_keys, ("city", "temperature_c", "condition")
        )
        self.assertEqual(
            result.detail, "CHECKED_KEYS=city,temperature_c,condition"
        )

    def test_pass_without_key_specification_is_labelled(self):
        result = validate("extract_structured", "extract JSON", '{"a":1}')
        self.assertEqual(result.status, PASS)
        self.assertEqual(result.detail, NO_KEY_SPECIFICATION)
        self.assertEqual(result.checked_keys, ())


class ValueTypeScopeTests(unittest.TestCase):
    """This validator has no explicit schema and must not claim value types.

    These tests deliberately assert a known limitation rather than a fix.
    Both outputs below are genuine strict-oracle failures in the frozen
    evidence (string "42" and string "8443" where JSON numbers were
    required). The validator passes them on key presence / syntax alone.
    The point is that it never reports having checked value types, so a
    PASS here cannot be mistaken for semantic correctness.
    """

    def test_string_typed_number_passes_key_check_but_claims_no_types(self):
        # Frozen oos_extract_device: `"version": "42"`, failed the oracle 5/5.
        result = validate("extract_structured", DEVICE_PROMPT, DEVICE_OUTPUT)
        self.assertEqual(result.status, PASS)
        self.assertEqual(
            result.checked_keys, ("asset_id", "operating_system", "version")
        )
        self.assertFalse(result.value_types_checked)

    def test_format_json_reports_syntax_only(self):
        # Frozen oos_json_server: `"port": "8443"`, failed the oracle 4/5.
        result = validate("format", SERVER_PROMPT, SERVER_OUTPUT)
        self.assertEqual(result.status, PASS)
        self.assertEqual(result.detail, SYNTAX_ONLY)
        self.assertFalse(result.value_types_checked)

    def test_no_validator_ever_claims_value_types_were_checked(self):
        for task_class, prompt, output in (
            ("extract_structured", WEATHER_PROMPT, WEATHER_OUTPUT),
            ("extract_structured", DEVICE_PROMPT, DEVICE_OUTPUT),
            ("format", SERVER_PROMPT, SERVER_OUTPUT),
            ("format", "format as bullets", "- one\n- two"),
            ("rewrite", "rewrite: a clumsy sentence here", "A clearer one."),
        ):
            with self.subTest(task_class=task_class):
                self.assertFalse(
                    validate(task_class, prompt, output).value_types_checked
                )


class FenceNormalizationParityTests(unittest.TestCase):
    """One outer JSON fence is stripped identically on both JSON paths.

    Before this change `format_json_v1` did not strip fences, so fenced
    output failed to parse. That produced a correct rejection of
    oos_json_server for the wrong reason: the fence broke the parse, not the
    string-typed port. Removing the accident makes the real limitation
    visible instead of hiding it behind a coincidence.
    """

    FENCED = '```json\n{"host":"edge-7","port":8443}\n```'

    def test_both_paths_strip_one_fence(self):
        self.assertEqual(
            validate("extract_structured", "extract JSON", self.FENCED).status,
            PASS,
        )
        self.assertEqual(
            validate("format", "format as JSON", self.FENCED).status, PASS,
        )

    def test_both_paths_reject_unterminated_fence(self):
        broken = '```json\n{"host":"edge-7"}'
        self.assertEqual(
            validate("extract_structured", "extract JSON", broken).status, FAIL
        )
        self.assertEqual(
            validate("format", "format as JSON", broken).status, FAIL
        )

    def test_both_paths_reject_prose_around_json(self):
        prose = 'Here is the JSON: {"host":"edge-7"}'
        self.assertEqual(
            validate("extract_structured", "extract JSON", prose).status, FAIL
        )
        self.assertEqual(
            validate("format", "format as JSON", prose).status, FAIL
        )


if __name__ == "__main__":
    unittest.main()
