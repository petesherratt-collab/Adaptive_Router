import json
from pathlib import Path
import re
import unittest

from build_oos_benchmark import build_document
from run_benchmark import evaluate_oracle


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark_oos_v1.json"

EXPECTED_FAMILY_COUNTS = {
    "structured_extraction": 10,
    "sentiment": 5,
    "json_format": 5,
    "priority": 5,
    "markdown_bullets": 5,
    "key_value_labels": 5,
    "transformation": 5,
}

LOCAL_FAMILIES = {
    "structured_extraction",
    "sentiment",
    "json_format",
}

EXPECTED_ROUND_ORDER = [
    "structured_extraction",
    "sentiment",
    "json_format",
    "priority",
    "markdown_bullets",
    "key_value_labels",
    "transformation",
    "structured_extraction",
]


class OutOfSampleBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(
            BENCHMARK.read_text(encoding="utf-8")
        )
        cls.tasks = cls.document["tasks"]

    def test_document_identity_and_count(self):
        self.assertEqual(self.document["version"], 3)
        self.assertEqual(
            self.document["suite_id"],
            "oos_validation_v1",
        )
        self.assertEqual(self.document["task_count"], 40)
        self.assertEqual(len(self.tasks), 40)

    def test_task_ids_are_unique_and_new(self):
        task_ids = [item["task_id"] for item in self.tasks]

        self.assertEqual(len(set(task_ids)), 40)
        self.assertTrue(
            all(task_id.startswith("oos_") for task_id in task_ids)
        )

    def test_prompts_are_unique(self):
        prompts = [item["prompt"] for item in self.tasks]

        self.assertEqual(len(set(prompts)), 40)
        self.assertTrue(all(prompt.strip() for prompt in prompts))

    def test_family_counts_are_exact(self):
        actual = {
            family: sum(
                item["capability_family"] == family
                for item in self.tasks
            )
            for family in EXPECTED_FAMILY_COUNTS
        }

        self.assertEqual(actual, EXPECTED_FAMILY_COUNTS)
        self.assertEqual(
            self.document["capability_family_counts"],
            EXPECTED_FAMILY_COUNTS,
        )

    def test_fine_policy_split_is_twenty_twenty(self):
        local = sum(
            item["capability_family"] in LOCAL_FAMILIES
            for item in self.tasks
        )

        self.assertEqual(local, 20)
        self.assertEqual(len(self.tasks) - local, 20)

    def test_fixed_round_order_interleaves_families(self):
        for start in range(0, 40, 8):
            actual = [
                item["capability_family"]
                for item in self.tasks[start:start + 8]
            ]
            self.assertEqual(actual, EXPECTED_ROUND_ORDER)

    def test_task_class_counts_are_exact(self):
        expected = {
            "extract_structured": 10,
            "classification": 10,
            "format": 15,
            "transform": 5,
        }
        actual = {
            task_class: sum(
                item["task_class"] == task_class
                for item in self.tasks
            )
            for task_class in expected
        }

        self.assertEqual(actual, expected)

    def test_builder_reproduces_committed_document(self):
        self.assertEqual(self.document, build_document())

    def test_declared_expected_output_passes_oracle(self):
        for item in self.tasks:
            with self.subTest(task_id=item["task_id"]):
                if item["normalization"] == "structured_json":
                    raw = json.dumps(
                        item["expected"],
                        ensure_ascii=False,
                    )
                else:
                    raw = str(item["expected"])

                normalized, correct, validator = evaluate_oracle(
                    item,
                    raw,
                )

                self.assertTrue(correct)
                self.assertEqual(validator["status"], "PASS")
                self.assertIsInstance(normalized, str)

    def test_clearly_wrong_output_fails_oracle(self):
        for item in self.tasks:
            with self.subTest(task_id=item["task_id"]):
                raw = (
                    '{"wrong":"value"}'
                    if item["normalization"] == "structured_json"
                    else "__definitely_wrong__"
                )

                _, correct, validator = evaluate_oracle(
                    item,
                    raw,
                )

                self.assertFalse(correct)
                self.assertEqual(validator["status"], "FAIL")

    def test_priority_prompts_contain_complete_rubric(self):
        priority_tasks = [
            item
            for item in self.tasks
            if item["capability_family"] == "priority"
        ]

        for item in priority_tasks:
            prompt = item["prompt"]

            with self.subTest(task_id=item["task_id"]):
                self.assertIn("within 24 hours", prompt)
                self.assertIn("within seven days", prompt)
                self.assertIn("more than seven days", prompt)
                self.assertIn(
                    item["expected"].capitalize(),
                    {"High", "Medium", "Low"},
                )

    def test_sentiment_prompts_contain_complete_rubric(self):
        sentiment_tasks = [
            item
            for item in self.tasks
            if item["capability_family"] == "sentiment"
        ]

        for item in sentiment_tasks:
            prompt = item["prompt"]

            with self.subTest(task_id=item["task_id"]):
                self.assertIn("clearly favourable", prompt)
                self.assertIn("clearly unfavourable", prompt)
                self.assertIn(
                    "factual statement without evaluation",
                    prompt,
                )

    def test_bullet_expected_outputs_have_exact_syntax(self):
        bullet_tasks = [
            item
            for item in self.tasks
            if item["capability_family"] == "markdown_bullets"
        ]

        for item in bullet_tasks:
            lines = item["expected"].splitlines()

            with self.subTest(task_id=item["task_id"]):
                self.assertGreaterEqual(len(lines), 2)
                self.assertTrue(
                    all(
                        line.startswith("- ")
                        and not line.startswith("-  ")
                        for line in lines
                    )
                )
                self.assertNotIn("\n\n", item["expected"])

    def test_label_expected_outputs_have_exact_syntax(self):
        label_tasks = [
            item
            for item in self.tasks
            if item["capability_family"] == "key_value_labels"
        ]

        pattern = re.compile(r"^[a-z][a-z0-9_]*: \S.*$")

        for item in label_tasks:
            lines = item["expected"].splitlines()

            with self.subTest(task_id=item["task_id"]):
                self.assertTrue(
                    all(pattern.fullmatch(line) for line in lines)
                )
                self.assertNotIn("\n\n", item["expected"])

    def test_json_keys_are_explicitly_named_in_prompt(self):
        json_tasks = [
            item
            for item in self.tasks
            if item["normalization"] == "structured_json"
        ]

        for item in json_tasks:
            for key in item["expected"]:
                with self.subTest(
                    task_id=item["task_id"],
                    key=key,
                ):
                    self.assertIn(key, item["prompt"])

    def test_extraction_prompts_require_source_preservation(self):
        extraction_tasks = [
            item
            for item in self.tasks
            if item["capability_family"]
            == "structured_extraction"
        ]

        for item in extraction_tasks:
            with self.subTest(task_id=item["task_id"]):
                self.assertIn(
                    "Preserve source spelling",
                    item["prompt"],
                )
                self.assertNotIn("Dr.", item["prompt"])

    def test_normalizations_match_task_families(self):
        structured_families = {
            "structured_extraction",
            "json_format",
        }

        for item in self.tasks:
            expected_normalization = (
                "structured_json"
                if item["capability_family"]
                in structured_families
                else "text"
            )

            with self.subTest(task_id=item["task_id"]):
                self.assertEqual(
                    item["normalization"],
                    expected_normalization,
                )


if __name__ == "__main__":
    unittest.main()
