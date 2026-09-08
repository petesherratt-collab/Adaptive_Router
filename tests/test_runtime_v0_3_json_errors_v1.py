"""Tests for the frozen runtime v0.3 JSON error analysis V1."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import analyze_runtime_v0_3_json_errors_v1 as analysis
import runtime_v0_3_shadow_json_v2 as pv


ROOT = Path(__file__).resolve().parents[1]


class AuthenticatedAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = analysis.build_analysis(ROOT)

    def test_sealed_inputs_reconcile(self):
        report = self.report
        self.assertEqual(report["analysis_status"], "RETROSPECTIVE_ONLY")
        self.assertEqual(report["sealed_v2_decision"], "DO_NOT_PROMOTE")
        self.assertEqual(report["overall"]["observation_count"], 120)
        self.assertEqual(report["overall"]["task_count"], 40)
        self.assertEqual(report["overall"]["local_correct_count"], 16)
        self.assertEqual(report["overall"]["local_contract_pass_count"], 39)
        self.assertEqual(report["overall"]["local_accepted_error_count"], 23)
        self.assertEqual(len(report["row_classifications"]), 120)
        self.assertEqual(
            sum(report["overall"]["leaf_difference_counts"].values()),
            sum(
                len(row["differences"])
                for row in report["row_classifications"]
            ),
        )
        self.assertTrue(all(
            "expected_value" not in difference
            and "candidate_value" not in difference
            for row in report["row_classifications"]
            for difference in row["differences"]
        ))
        self.assertEqual(
            report["sealed_v2_correctness_overlap"]["overall"],
            {"both": 16, "local_only": 0, "neither": 15, "remote_only": 89},
        )

    def test_task_clusters_are_primary_units(self):
        report = self.report
        self.assertEqual(len(report["tasks"]), 40)
        self.assertEqual(
            report["task_pattern_summary"]["correctness_patterns"],
            {
                "mixed_correctness": 1,
                "unanimous_correct": 5,
                "unanimous_error": 34,
            },
        )
        self.assertTrue(all(task["retrospective_only"] for task in report["tasks"]))

    def test_subgroup_inventory_is_exhaustive(self):
        report = self.report
        self.assertEqual(len(report["subgroup_inventory"]), 42)
        self.assertEqual(
            report["subgroup_family_counts"],
            {
                "contract_pass": 1,
                "contract_pass_single_stratum": 4,
                "contract_pass_stratum_allowlist": 15,
                "contract_signature": 17,
                "preoutput_stratum": 4,
                "three_repetition_unanimity": 1,
            },
        )
        allowlists = [
            item for item in report["subgroup_inventory"]
            if item["family"] == "contract_pass_stratum_allowlist"
        ]
        self.assertEqual(len(allowlists), (1 << len(analysis.STRATA)) - 1)
        self.assertTrue(all(item["retrospective_only"] for item in allowlists))

    def test_actual_candidate_screen_fails(self):
        report = self.report
        self.assertEqual(report["candidate_screen"]["decision"], "NO_RULE_CANDIDATE")
        self.assertEqual(report["candidate_screen"]["candidate_rule_ids"], [])
        self.assertFalse(any(
            item["incorrect_accepted_rows"] == 0
            for item in report["subgroup_inventory"]
        ))
        self.assertEqual(report["interpretation"], ["MODEL_CHANGE_CANDIDATE"])

    def test_dry_run_creates_no_outputs(self):
        paths = analysis.output_paths(ROOT)
        before = {name: path.exists() for name, path in paths.items()}
        analysis.build_analysis(ROOT)
        after = {name: path.exists() for name, path in paths.items()}
        self.assertEqual(after, before)


class DifferenceClassificationTests(unittest.TestCase):
    def test_recursive_diff_reports_every_leaf_class_without_values(self):
        expected = {
            "a": 1,
            "b": [1, 2],
            "c": {"x": True},
            "d": "text",
            "f": None,
        }
        candidate = {
            "a": 2,
            "b": [1],
            "c": "wrong container",
            "d": 3,
            "e": None,
        }
        differences = analysis.recursive_differences(expected, candidate)
        self.assertEqual(
            {item["class"] for item in differences},
            {
                "missing_member",
                "unexpected_member",
                "container_type",
                "scalar_type",
                "array_length",
                "scalar_value",
            },
        )
        self.assertTrue(all("expected_value" not in item for item in differences))
        self.assertTrue(all("candidate_value" not in item for item in differences))

    def test_json_pointer_escaping_and_numeric_equivalence(self):
        self.assertEqual(
            analysis.recursive_differences({"a/b~c": 1}, {"a/b~c": 2})[0]["path"],
            "/a~1b~0c",
        )
        self.assertEqual(analysis.recursive_differences(1, 1.0), [])
        self.assertEqual(
            analysis.recursive_differences(True, 1)[0]["class"], "scalar_type"
        )

    def test_primary_precedence(self):
        differences = [
            {"class": "scalar_value"},
            {"class": "container_type"},
            {"class": "unexpected_member"},
        ]
        self.assertEqual(analysis.primary_class(differences), "member_set")
        self.assertEqual(
            analysis.primary_class([], provider_success=False), "provider_failure"
        )
        self.assertEqual(
            analysis.primary_class([], parse_error="INVALID_JSON"),
            "unparseable_candidate",
        )


class CandidateBoundaryTests(unittest.TestCase):
    @staticmethod
    def synthetic_rows(error_index=None):
        rows = []
        for task_number in range(10):
            for repetition in range(3):
                index = task_number * 3 + repetition
                rows.append({
                    "task_id": f"task_{task_number:02d}",
                    "correct": index != error_index,
                    "remote_correct": True,
                })
        return rows

    def test_candidate_screen_success_fixture(self):
        rule = analysis._rule(
            "synthetic", "contract_pass", "synthetic deployable rule",
            {"contract_status"}, lambda item: True,
        )
        result = analysis.evaluate_rule(rule, self.synthetic_rows())
        self.assertEqual(
            result["candidate_screen"], "CANDIDATE_FOR_FRESH_TEST_ONLY"
        )
        self.assertEqual(result["accepted_task_cluster_count"], 10)

    def test_candidate_screen_rejects_one_accepted_error(self):
        rule = analysis._rule(
            "synthetic", "contract_pass", "synthetic deployable rule",
            {"contract_status"}, lambda item: True,
        )
        result = analysis.evaluate_rule(rule, self.synthetic_rows(error_index=0))
        self.assertEqual(result["candidate_screen"], "NOT_A_CANDIDATE")

    def test_oracle_dependent_features_are_forbidden(self):
        for feature in sorted(analysis.FORBIDDEN_FEATURES):
            with self.subTest(feature=feature), self.assertRaises(pv.FrozenDesignError):
                analysis._rule(
                    "forbidden", "contract_pass", "forbidden",
                    {feature}, lambda item: True,
                )


class StateAndParsingTests(unittest.TestCase):
    def test_protocol_hash_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / analysis.PROTOCOL_NAME).write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(
                pv.FrozenDesignError, "ERROR_ANALYSIS_PROTOCOL_HASH_MISMATCH"
            ):
                analysis.authenticate_inputs(root)

    def test_duplicate_json_key_rejects(self):
        with self.assertRaises(pv.FrozenDesignError):
            pv.strict_json_loads('{"key":1,"key":2}')

    def test_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = analysis.output_paths(root)
            paths["json"].write_text("occupied\n", encoding="utf-8")
            with self.assertRaisesRegex(
                pv.StateError, "ERROR_ANALYSIS_OUTPUT_ALREADY_EXISTS"
            ):
                analysis.write_analysis(root)


if __name__ == "__main__":
    unittest.main()
