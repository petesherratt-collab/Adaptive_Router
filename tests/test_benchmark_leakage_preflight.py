import json
import tempfile
import unittest
from pathlib import Path

from benchmark_leakage_preflight import (
    build_request_payload,
    build_ablation_conditions,
    load_separated_suite,
    run_null_baseline_preflight,
    validate_variant_inventory,
    validate_request_boundary,
    validate_mutation_pairs,
)


class LeakagePreflightTests(unittest.TestCase):
    def suite_files(self, tasks, oracle):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        tasks_path = root / "tasks.json"
        oracle_path = root / "oracle.json"
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
        oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
        return directory, tasks_path, oracle_path

    def test_separated_suite_and_request_boundary(self):
        tasks = [{"task_id": "t1", "task_class": "classification", "prompt": "Input: green", "variant_id": "base"}]
        oracle = {"t1__base": {"expected": "positive", "match_mode": "text"}}
        directory, tasks_path, oracle_path = self.suite_files(tasks, oracle)
        with directory:
            loaded_tasks, loaded_oracle = load_separated_suite(tasks_path, oracle_path)
            self.assertEqual(build_request_payload(loaded_tasks[0], "test"), {
                "model": "test", "task_id": "t1", "variant_id": "base", "prompt": "Input: green"
            })
            self.assertEqual(validate_request_boundary(loaded_tasks, loaded_oracle)["task_count"], 1)

    def test_expected_field_in_task_data_is_rejected(self):
        tasks = [{"task_id": "t1", "task_class": "format", "prompt": "x", "variant_id": "base", "expected": "x"}]
        directory, tasks_path, oracle_path = self.suite_files(tasks, {"t1__base": {}})
        with directory, self.assertRaises(ValueError):
            load_separated_suite(tasks_path, oracle_path)

    def test_null_baseline_preflight_returns_rows_and_task_groups(self):
        tasks = [{"task_id": "t1", "task_class": "classification", "prompt": "Input: positive", "variant_id": "base"}]
        rows, by_task = run_null_baseline_preflight(tasks, lambda task, output: output == "positive", {"input": lambda prompt: "positive"})
        self.assertEqual(len(rows), 1)
        self.assertTrue(by_task["t1"]["input"])

    def test_variant_inventory_requires_base_and_mutant(self):
        tasks = [
            {"task_id": "t1", "variant_id": "base"},
            {"task_id": "t1", "variant_id": "mut1"},
        ]
        self.assertEqual(validate_variant_inventory(tasks), {"t1": ["base", "mut1"]})
        with self.assertRaises(ValueError):
            validate_variant_inventory([{"task_id": "t2", "variant_id": "base"}])

    def test_ablation_conditions_are_deterministic_and_model_free(self):
        tasks = [{"task_id": "t1", "variant_id": "base", "task_class": "format", "prompt": "do task\nInput: alpha beta"}]
        conditions = build_ablation_conditions(tasks)
        self.assertEqual([c["ablation_mode"] for c in conditions], ["input_removed", "input_shuffled"])
        self.assertEqual(conditions[0]["prompt"], "do task\nInput: [REMOVED]")
        self.assertEqual(conditions[1]["prompt"], "do task\nInput: beta alpha")

    def test_mutation_pairs_preserve_class_and_change_prompt(self):
        tasks = [
            {"task_id": "t1", "variant_id": "base", "task_class": "format", "prompt": "Input: alpha"},
            {"task_id": "t1", "variant_id": "mut1", "task_class": "format", "prompt": "Input: beta"},
        ]
        self.assertTrue(validate_mutation_pairs(tasks))
        with self.assertRaises(ValueError):
            validate_mutation_pairs([*tasks[:1], {**tasks[1], "prompt": "Input: alpha"}])


if __name__ == "__main__":
    unittest.main()
