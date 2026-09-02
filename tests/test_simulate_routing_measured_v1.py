import json
import tempfile
import unittest
from pathlib import Path

from simulate_routing_measured_v1 import (
    INTERPRETATIONS,
    build_analysis,
    interpreted_correct,
    pair_rows,
    policy_rows,
    route,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "benchmark_runs_simzero_v2.jsonl"
REMOTE = ROOT / "benchmark_runs_openrouter_luna_v1.jsonl"


class MeasuredRoutingReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = build_analysis(LOCAL, REMOTE)

    def test_source_identity_and_pair_count(self):
        source = self.analysis["source_identity"]
        self.assertEqual(source["paired_observations"], 150)
        self.assertEqual(
            source["local_sha256"],
            "5637130c56894a0263c534bb87c5037901f0e535df28e658f68d5e85c03f7f6e",
        )
        self.assertEqual(
            source["remote_sha256"],
            "341d203f34f3789e489329030895970e719483334e42d2ac144080516e3c0405",
        )

    def test_overlap_counts_are_frozen(self):
        expected = {
            "strict": (66, 0, 62, 22, 128),
            "audited": (69, 2, 74, 5, 145),
        }
        for interpretation, values in expected.items():
            with self.subTest(interpretation=interpretation):
                overlap = self.analysis["interpretations"][interpretation]["overlap"]
                actual = (
                    overlap["both_correct"],
                    overlap["local_only"],
                    overlap["remote_only"],
                    overlap["neither"],
                    overlap["oracle_selector_passes"],
                )
                self.assertEqual(actual, values)

    def test_policy_counts_are_measured(self):
        expected = {
            ("strict", "always_local"): (66, 0, 0),
            ("strict", "always_remote"): (128, 150, 2),
            ("strict", "coarse_class"): (116, 75, 0),
            ("strict", "fine_capability"): (125, 75, 0),
            ("audited", "always_local"): (71, 0, 0),
            ("audited", "always_remote"): (143, 150, 2),
            ("audited", "coarse_class"): (131, 75, 0),
            ("audited", "fine_capability"): (140, 75, 0),
        }
        for interpretation in INTERPRETATIONS:
            for row in self.analysis["interpretations"][interpretation]["policies"]:
                key = (interpretation, row["policy"])
                actual = (
                    row["passes"],
                    row["remote_calls"],
                    row["remote_transport_failures"],
                )
                self.assertEqual(actual, expected[key])

    def test_fine_policy_measured_cost_and_latency(self):
        row = next(
            row
            for row in self.analysis["interpretations"]["strict"]["policies"]
            if row["policy"] == "fine_capability"
        )
        self.assertAlmostEqual(row["reported_remote_cost_usd"], 0.0024892)
        self.assertAlmostEqual(row["median_selected_total_ms"], 990.314192022197)
        self.assertEqual(row["pass_delta_vs_always_remote"], -3)
        self.assertEqual(row["remote_calls_saved_vs_always_remote"], 75)

    def test_route_does_not_read_outcomes(self):
        row = {
            "task_id": "format_json_contact",
            "task_class": "format",
            "oracle_correct": False,
            "success": False,
        }
        before = route("fine_capability", row)
        row["oracle_correct"] = True
        row["success"] = True
        self.assertEqual(route("fine_capability", row), before)

    def test_audited_adjustments_are_narrow(self):
        false_row = {"oracle_correct": False, "task_id": "extract_person_2"}
        self.assertFalse(interpreted_correct("local", false_row, "strict"))
        self.assertTrue(interpreted_correct("local", false_row, "audited"))
        self.assertFalse(interpreted_correct("remote", false_row, "audited"))

        false_row["task_id"] = "format_labels_ticket"
        self.assertTrue(interpreted_correct("remote", false_row, "audited"))
        self.assertFalse(interpreted_correct("local", false_row, "audited"))

        false_row["task_id"] = "classify_priority_medium"
        self.assertFalse(interpreted_correct("remote", false_row, "audited"))

    def test_pairing_rejects_missing_and_duplicate_keys(self):
        local = [{"task_id": "a", "rep": 1, "task_class": "format"}]
        remote = [{"task_id": "b", "rep": 1, "task_class": "format"}]
        with self.assertRaisesRegex(ValueError, "Paired key mismatch"):
            pair_rows(local, remote)
        with self.assertRaisesRegex(ValueError, "Duplicate local"):
            pair_rows(local + local, local)

    def test_csv_rows_cover_each_policy_and_interpretation(self):
        rows = policy_rows(self.analysis)
        self.assertEqual(len(rows), 8)
        self.assertEqual(
            {(row["interpretation"], row["policy"]) for row in rows},
            {
                (interpretation, policy)
                for interpretation in INTERPRETATIONS
                for policy in (
                    "always_local",
                    "always_remote",
                    "coarse_class",
                    "fine_capability",
                )
            },
        )

    def test_writer_is_deterministic_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "result.json"
            csv_path = root / "result.csv"
            write_outputs(self.analysis, json_path, csv_path)
            first_json = json_path.read_bytes()
            first_csv = csv_path.read_bytes()
            parsed = json.loads(first_json)
            self.assertEqual(parsed["analysis"], "measured_paired_routing_replay_v1")
            self.assertNotIn(b"\r\n", first_json)
            self.assertNotIn(b"\r\n", first_csv)
            with self.assertRaises(FileExistsError):
                write_outputs(self.analysis, json_path, csv_path)


if __name__ == "__main__":
    unittest.main()
