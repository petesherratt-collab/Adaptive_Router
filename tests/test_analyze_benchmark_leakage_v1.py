import unittest

from analyze_benchmark_leakage_v1 import (
    analyze_null_baselines,
    build_construct_validity_report,
    oracle_correct,
)


class LeakageAnalysisTests(unittest.TestCase):
    def test_raw_and_normalized_correctness_are_separate(self):
        entry = {"expected": "positive", "match_mode": "classification"}
        self.assertEqual(oracle_correct(entry, " Positive\n"), (False, True))

    def test_structured_json_uses_object_order_insensitive_comparison(self):
        entry = {"expected": {"city": "Osaka", "zone": "urban"}, "match_mode": "structured_json"}
        self.assertEqual(oracle_correct(entry, '{"zone":"urban","city":"Osaka"}'), (False, True))

    def test_baseline_analysis_reports_variant_verdicts(self):
        tasks = [{"task_id": "t", "variant_id": "base", "prompt": "Input: positive"}]
        oracle = {"t__base": {"expected": "positive", "match_mode": "classification"}}
        rows, verdicts = analyze_null_baselines(tasks, oracle, {"input": lambda prompt: "positive"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(verdicts, {"t__base": "CV_NULL_BASELINE_PASSES"})

    def test_construct_report_keeps_missing_model_controls_pending(self):
        tasks = [
            {"task_id": "t", "variant_id": "base", "prompt": "Input: alpha"},
            {"task_id": "t", "variant_id": "mut1", "prompt": "Input: beta"},
        ]
        baseline = [
            {"task_id": "t", "variant_id": "base", "baseline_id": "empty", "oracle_correct": False},
            {"task_id": "t", "variant_id": "mut1", "baseline_id": "empty", "oracle_correct": False},
        ]
        report = build_construct_validity_report(tasks, baseline)
        self.assertEqual(report["t"]["final_status"], "CV_PENDING_MODEL_CONTROLS")

    def test_construct_report_detects_mutant_divergence(self):
        tasks = [
            {"task_id": "t", "variant_id": "base", "prompt": "Input: alpha"},
            {"task_id": "t", "variant_id": "mut1", "prompt": "Input: beta"},
        ]
        baseline = [
            {"task_id": "t", "variant_id": "base", "oracle_correct": False},
            {"task_id": "t", "variant_id": "mut1", "oracle_correct": False},
        ]
        model = [
            {"task_id": "t", "variant_id": "base", "oracle_correct_normalized": True},
            {"task_id": "t", "variant_id": "mut1", "oracle_correct_normalized": False},
        ]
        ablation = [
            {"task_id": "t", "variant_id": "base", "oracle_correct_normalized": False},
            {"task_id": "t", "variant_id": "mut1", "oracle_correct_normalized": False},
        ]
        report = build_construct_validity_report(tasks, baseline, model_rows=model, ablation_rows=ablation)
        self.assertEqual(report["t"]["mutation_status"], "CV_MUTANT_DIVERGENCE")
        self.assertEqual(report["t"]["final_status"], "CV_MUTANT_DIVERGENCE")


if __name__ == "__main__":
    unittest.main()
