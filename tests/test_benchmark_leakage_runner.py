import unittest

from benchmark_leakage_runner import run_ablation_conditions, run_conditions


class LeakageRunnerTests(unittest.TestCase):
    def test_model_result_records_raw_and_normalized_verdicts(self):
        tasks = [{"task_id": "t", "variant_id": "base", "task_class": "classification", "prompt": "Input: positive"}]
        oracle = {"t__base": {"expected": "positive", "match_mode": "classification"}}
        rows = run_conditions(tasks, oracle, lambda prompt, model: " Positive\n", "stub")
        self.assertEqual(rows[0]["reason_code"], "PASS_VIA_NORMALIZATION")
        self.assertFalse(rows[0]["oracle_correct_raw"])
        self.assertTrue(rows[0]["oracle_correct_normalized"])
        self.assertTrue(rows[0]["normalization_changed_verdict"])

    def test_empty_output_has_explicit_failure_reason(self):
        tasks = [{"task_id": "t", "variant_id": "base", "task_class": "format", "prompt": "Input: x"}]
        oracle = {"t__base": {"expected": "x", "match_mode": "text"}}
        rows = run_conditions(tasks, oracle, lambda prompt, model: "", "stub")
        self.assertEqual(rows[0]["reason_code"], "FAIL_EMPTY_OUTPUT")
        self.assertEqual(rows[0]["status"], "FAIL")

    def test_provider_failure_is_not_misclassified_as_empty_output(self):
        tasks = [{"task_id": "t", "variant_id": "base", "task_class": "format", "prompt": "Input: x"}]
        oracle = {"t__base": {"expected": "x", "match_mode": "text"}}
        rows = run_conditions(
            tasks, oracle,
            lambda prompt, model: {"raw_output": "", "telemetry": {"success": False, "error": "LOCAL_TIMEOUT"}},
            "stub",
        )
        self.assertEqual(rows[0]["reason_code"], "PROVIDER_FAILURE")

    def test_run_metadata_is_copied_to_each_row(self):
        tasks = [{"task_id": "t", "variant_id": "base", "task_class": "format", "prompt": "Input: x"}]
        oracle = {"t__base": {"expected": "x", "match_mode": "text"}}
        metadata = {"config_sha256": "abc", "model_digest": "digest"}
        rows = run_conditions(tasks, oracle, lambda prompt, model: "x", "stub", run_metadata=metadata)
        self.assertEqual(rows[0]["run_metadata"], metadata)

    def test_generator_metadata_is_preserved(self):
        tasks = [{"task_id": "t", "variant_id": "base", "task_class": "format", "prompt": "Input: x"}]
        oracle = {"t__base": {"expected": "x", "match_mode": "text"}}
        rows = run_conditions(
            tasks, oracle,
            lambda prompt, model: {"raw_output": "x", "telemetry": {"total_ms": 1.5}},
            "stub",
        )
        self.assertEqual(rows[0]["telemetry"], {"total_ms": 1.5})

    def test_ablation_uses_same_callback_without_provider_discovery(self):
        tasks = [{"task_id": "t", "variant_id": "base", "task_class": "format", "prompt": "do task\nInput: alpha beta"}]
        oracle = {"t__base": {"expected": "alpha", "match_mode": "text"}}
        prompts = []
        rows = run_ablation_conditions(tasks, oracle, lambda prompt, model: prompts.append(prompt) or "wrong", "stub")
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(prompts), 2)
        self.assertEqual({row["ablation_mode"] for row in rows}, {"input_removed", "input_shuffled"})


if __name__ == "__main__":
    unittest.main()
