import unittest
from validators import validate, PASS, FAIL, NOT_APPLICABLE

class ValidatorTests(unittest.TestCase):
    def test_valid_raw_json_passes(self):
        self.assertEqual(
            validate("extract_structured", "extract JSON required keys: name, age", '{"name":"A","age":2}').status,
            PASS,
        )

    def test_valid_fenced_json_passes(self):
        output = '  ```JSON\n{"name":"A","age":2}\n```  '
        self.assertEqual(
            validate("extract_structured", "extract JSON required keys: name, age", output).status,
            PASS,
        )

    def test_malformed_json_inside_fence_fails(self):
        output = '```json\n{"name":"A","age":}\n```'
        result = validate("extract_structured", "extract JSON", output)
        self.assertEqual(result.status, FAIL)
        self.assertEqual(result.detail, "INVALID_JSON")

    def test_prose_plus_json_fails(self):
        output = 'Here is the JSON: {"name":"A","age":2}'
        self.assertEqual(validate("extract_structured", "extract JSON", output).status, FAIL)

    def test_incomplete_or_multiple_fences_fail(self):
        outputs = (
            '```json\n{"name":"A","age":2}',
            '```json\n{"name":"A","age":2}\n```\n```json\n{"name":"B","age":3}\n```',
        )
        for output in outputs:
            with self.subTest(output=output):
                self.assertEqual(validate("extract_structured", "extract JSON", output).status, FAIL)
    def test_rewrite(self):
        self.assertEqual(validate("rewrite", "rewrite: This is a clumsy sentence that needs improvement.", "This sentence reads much more clearly now.").status, PASS)
        self.assertEqual(validate("rewrite", "rewrite x", "").status, FAIL)
    def test_summary(self):
        self.assertEqual(validate("summarise_short", "summarise " + "source "*30, "brief summary").status, PASS)
        self.assertEqual(validate("summarise_short", "summarise short", "a very long output that is not shorter").status, FAIL)
    def test_format_and_na(self):
        self.assertEqual(validate("format", "format as bullets", "- one\n- two").status, PASS)
        self.assertEqual(validate("format", "format neatly", "anything").status, NOT_APPLICABLE)
