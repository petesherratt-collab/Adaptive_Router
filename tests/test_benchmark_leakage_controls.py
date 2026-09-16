import unittest

from benchmark_leakage_controls import (
    ablate_prompt,
    assert_no_expected_value_leakage,
    construct_validity,
    evaluate_null_baselines,
    extract_input_block,
    longest_capitalised_span,
    normalization_delta,
    mutation_verdict,
)


class LeakageControlTests(unittest.TestCase):
    def test_input_block_requires_explicit_marker(self):
        self.assertEqual(extract_input_block("Instruction only"), "")
        self.assertEqual(
            extract_input_block("Extract the name.\nSource: Ada Lovelace"),
            "Ada Lovelace",
        )

    def test_longest_capitalised_span_is_deterministic(self):
        prompt = "extract Grace Hopper from the report about New York City."
        self.assertEqual(longest_capitalised_span(prompt), "New York City")

    def test_null_baselines_use_the_supplied_oracle(self):
        tasks = [{"task_id": "t1", "variant_id": "base", "prompt": "Input: high"}]
        calls = []

        def oracle(task, raw_output):
            calls.append((task["task_id"], raw_output))
            return raw_output == "high"

        rows = evaluate_null_baselines(tasks, oracle, baselines={"input": lambda p: extract_input_block(p)})
        self.assertEqual(rows[0]["raw_output"], "high")
        self.assertTrue(rows[0]["oracle_correct"])
        self.assertEqual(calls, [("t1", "high")])
        self.assertEqual(construct_validity({"input": True}), "CV_NULL_BASELINE_PASSES")

    def test_construct_validity_is_ok_when_all_baselines_fail(self):
        self.assertEqual(construct_validity({"empty": False, "echo": False}), "CV_OK")

    def test_prompt_ablation_is_explicit_and_deterministic(self):
        prompt = "classify the item.\nInput: red blue green"
        self.assertEqual(ablate_prompt(prompt, "input_removed"), "classify the item.\nInput: [REMOVED]")
        self.assertEqual(ablate_prompt(prompt, "input_shuffled"), "classify the item.\nInput: green blue red")
        with self.assertRaises(ValueError):
            ablate_prompt("instruction only", "input_removed")

    def test_mutation_divergence_is_reported(self):
        self.assertEqual(mutation_verdict(True, True), "CV_OK")
        self.assertEqual(mutation_verdict(False, False), "CV_OK")
        self.assertEqual(mutation_verdict(True, False), "CV_MUTANT_DIVERGENCE")

    def test_expected_values_are_checked_outside_prompt_only(self):
        payload = {"task_id": "t1", "prompt": "say secret", "model": "test"}
        assert_no_expected_value_leakage(payload, ["secret"])
        with self.assertRaises(AssertionError):
            assert_no_expected_value_leakage({**payload, "expected": "secret"}, ["secret"])

    def test_normalization_delta_scores_both_paths(self):
        result = normalization_delta(
            " Positive\n",
            lambda value: value.strip().lower(),
            lambda value: value == "positive",
        )
        self.assertEqual(result["raw_output"], " Positive\n")
        self.assertEqual(result["normalized_output"], "positive")
        self.assertFalse(result["oracle_correct_raw"])
        self.assertTrue(result["oracle_correct_normalized"])
        self.assertTrue(result["normalization_changed_verdict"])


if __name__ == "__main__":
    unittest.main()
