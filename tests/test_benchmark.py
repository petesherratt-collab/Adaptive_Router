import json
import tempfile
import unittest
from pathlib import Path

from local import LocalResult
from run_benchmark import (
    evaluate_oracle,
    load_benchmark,
    run_benchmark,
    summarize_records,
)
from validators import FAIL, PASS


class BenchmarkOracleTests(unittest.TestCase):
    def test_benchmark_has_thirty_tasks_with_required_class_shape(self):
        tasks = load_benchmark()["tasks"]
        self.assertEqual(len(tasks), 30)
        self.assertEqual(
            {
                task_class: sum(task["task_class"] == task_class for task in tasks)
                for task_class in {
                    "extract_structured", "classification", "format", "transform"
                }
            },
            {
                "extract_structured": 9,
                "classification": 6,
                "format": 9,
                "transform": 6,
            },
        )

    def test_structured_oracle_reuses_fenced_json_normalization(self):
        task = {
            "task_id": "person",
            "task_class": "extract_structured",
            "normalization": "structured_json",
            "prompt": "extract",
            "expected": {"name": "A", "age": 2},
        }
        normalized, correct, validator = evaluate_oracle(
            task, '  ```JSON\n{"age":2,"name":"A"}\n```  '
        )
        self.assertEqual(normalized, '{"age":2,"name":"A"}')
        self.assertTrue(correct)
        self.assertEqual(validator["status"], PASS)

        _, correct, validator = evaluate_oracle(task, 'Here is JSON: {"name":"A","age":2}')
        self.assertFalse(correct)
        self.assertEqual(validator["status"], FAIL)
        self.assertEqual(validator["detail"], "INVALID_JSON")

    def test_valid_but_wrong_structured_value_fails(self):
        task = {
            "task_id": "person",
            "task_class": "extract_structured",
            "normalization": "structured_json",
            "prompt": "extract",
            "expected": {"name": "A", "age": 2},
        }
        normalized, correct, validator = evaluate_oracle(
            task, '{"name":"B","age":2}'
        )
        self.assertEqual(normalized, '{"age":2,"name":"B"}')
        self.assertFalse(correct)
        self.assertEqual(validator["status"], FAIL)
        self.assertEqual(validator["detail"], "EXPECTED_MISMATCH")

    def test_classification_oracle_normalizes_case_and_boundary_whitespace(self):
        task = {
            "task_id": "label",
            "task_class": "classification",
            "normalization": "text",
            "prompt": "classify",
            "expected": "positive",
        }
        self.assertTrue(evaluate_oracle(task, "\npositive\n")[1])
        self.assertTrue(evaluate_oracle(task, "Positive")[1])

    def test_classification_normalizes_complete_output_without_extracting_label(self):
        task = {
            "task_id": "label",
            "task_class": "classification",
            "normalization": "text",
            "prompt": "classify",
            "expected": "positive",
        }
        normalized, correct, _ = evaluate_oracle(
            task, "  POSITIVE with confidence 0.99  "
        )
        self.assertEqual(normalized, "positive with confidence 0.99")
        self.assertFalse(correct)

    def test_nonclassification_text_normalization_remains_case_sensitive(self):
        task = {
            "task_id": "reverse",
            "task_class": "transform",
            "normalization": "text",
            "prompt": "transform",
            "expected": "result",
        }
        self.assertEqual(evaluate_oracle(task, " RESULT ")[0], "RESULT")

    def test_format_prompts_state_required_syntax(self):
        tasks = {task["task_id"]: task for task in load_benchmark()["tasks"]}
        self.assertIn(
            'exactly the lowercase keys "city" and "country"',
            tasks["format_json"]["prompt"],
        )
        self.assertIn(
            '"-" as the Markdown bullet marker',
            tasks["format_bullets"]["prompt"],
        )


class BenchmarkRecordTests(unittest.TestCase):
    def test_jsonl_has_one_record_per_task_rep_and_required_fields(self):
        tasks = load_benchmark()["tasks"][:2]
        outputs = {task["prompt"]: task["expected"] for task in tasks}

        def fake_generate(prompt, config):
            expected = outputs[prompt]
            raw = json.dumps(expected) if isinstance(expected, dict) else str(expected)
            return LocalResult(True, raw, 12.5, 34.5, 5.0)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            records = run_benchmark(
                tasks,
                {"model": "test-model"},
                reps=2,
                output_path=output,
                generate_fn=fake_generate,
                residency_fn=lambda config: {"resident": True, "size_bytes": 123},
            )
            lines = output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(records), 4)
        self.assertEqual(len(lines), 4)
        required = {
            "task_id", "rep", "model", "task_class", "raw_output",
            "normalized_output", "oracle_correct", "validator",
            "validator_status", "ttft_ms", "total_ms", "tokens_per_second",
            "model_residency", "success", "error",
        }
        for line in lines:
            record = json.loads(line)
            self.assertTrue(required.issubset(record))
            self.assertEqual(record["model"], "test-model")
            self.assertEqual(record["validator_status"], PASS)
            self.assertTrue(record["oracle_correct"])
            self.assertEqual(record["model_residency"]["resident"], True)


class BenchmarkSummaryTests(unittest.TestCase):
    def test_summary_aggregates_pass_rates_medians_and_empty_outputs(self):
        records = [
            {
                "task_id": "format_a",
                "task_class": "format",
                "oracle_correct": True,
                "raw_output": "ok",
                "ttft_ms": 10.0,
                "total_ms": 20.0,
                "tokens_per_second": 5.0,
            },
            {
                "task_id": "format_a",
                "task_class": "format",
                "oracle_correct": False,
                "raw_output": "",
                "ttft_ms": 30.0,
                "total_ms": 40.0,
                "tokens_per_second": None,
            },
            {
                "task_id": "classify_a",
                "task_class": "classification",
                "oracle_correct": True,
                "raw_output": "positive",
                "ttft_ms": None,
                "total_ms": 60.0,
                "tokens_per_second": 10.0,
            },
        ]

        summary = summarize_records(records)

        self.assertEqual(summary["observation_count"], 3)
        self.assertEqual(summary["overall_pass_count"], 2)
        self.assertAlmostEqual(summary["overall_pass_rate"], 2 / 3)
        self.assertEqual(summary["per_task"]["format_a"]["pass_count"], 1)
        self.assertAlmostEqual(summary["per_class"]["format"]["pass_rate"], 0.5)
        self.assertAlmostEqual(summary["per_class"]["classification"]["pass_rate"], 1.0)
        self.assertEqual(summary["median_ttft_ms"], 20.0)
        self.assertEqual(summary["median_total_ms"], 40.0)
        self.assertEqual(summary["median_tokens_per_second"], 7.5)
        self.assertEqual(summary["empty_output_count"], 1)


if __name__ == "__main__":
    unittest.main()
