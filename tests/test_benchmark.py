import json
import tempfile
import unittest
from pathlib import Path

from local import LocalResult
from run_benchmark import evaluate_oracle, load_benchmark, run_benchmark
from validators import FAIL, PASS


class BenchmarkOracleTests(unittest.TestCase):
    def test_benchmark_has_ten_tasks_across_required_classes(self):
        tasks = load_benchmark()["tasks"]
        self.assertEqual(len(tasks), 10)
        self.assertEqual(
            {task["task_class"] for task in tasks},
            {"extract_structured", "classification", "format", "transform"},
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

    def test_text_oracle_is_exact_after_boundary_whitespace_only(self):
        task = {
            "task_id": "label",
            "task_class": "classification",
            "normalization": "text",
            "prompt": "classify",
            "expected": "positive",
        }
        self.assertTrue(evaluate_oracle(task, "\npositive\n")[1])
        self.assertFalse(evaluate_oracle(task, "Positive")[1])


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
            "model_residency",
        }
        for line in lines:
            record = json.loads(line)
            self.assertTrue(required.issubset(record))
            self.assertEqual(record["model"], "test-model")
            self.assertEqual(record["validator_status"], PASS)
            self.assertTrue(record["oracle_correct"])
            self.assertEqual(record["model_residency"]["resident"], True)


if __name__ == "__main__":
    unittest.main()
