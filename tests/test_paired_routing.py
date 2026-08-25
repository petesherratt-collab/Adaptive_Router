import csv
from pathlib import Path
import tempfile
import unittest

from simulate_paired_routing import (
    POLICIES,
    load_jsonl,
    pair_records,
    simulate,
    write_results,
)


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PATH = ROOT / "benchmark_runs_simzero_v2.jsonl"
REMOTE_PATH = ROOT / "benchmark_runs_openrouter_luna_v1.jsonl"


class PairedRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local_records = load_jsonl(LOCAL_PATH)
        cls.remote_records = load_jsonl(REMOTE_PATH)
        cls.pairs = pair_records(
            cls.local_records,
            cls.remote_records,
        )

    def test_pairs_all_frozen_observations(self):
        self.assertEqual(len(self.local_records), 150)
        self.assertEqual(len(self.remote_records), 150)
        self.assertEqual(len(self.pairs), 150)

        keys = {
            (local["task_id"], local["rep"])
            for local, remote in self.pairs
        }
        self.assertEqual(len(keys), 150)

    def test_key_mismatch_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "paired key mismatch",
        ):
            pair_records(
                self.local_records,
                self.remote_records[:-1],
            )

    def test_selected_pass_counts(self):
        expected = {
            ("strict", "always_local"): 66,
            ("strict", "always_remote"): 128,
            ("strict", "coarse_class"): 116,
            ("strict", "fine_capability"): 125,
            ("audited", "always_local"): 71,
            ("audited", "always_remote"): 143,
            ("audited", "coarse_class"): 131,
            ("audited", "fine_capability"): 140,
        }

        for key, expected_passes in expected.items():
            interpretation, policy = key

            with self.subTest(
                interpretation=interpretation,
                policy=policy,
            ):
                result = simulate(
                    self.pairs,
                    policy,
                    interpretation,
                )
                self.assertEqual(
                    result["selected_passes"],
                    expected_passes,
                )

    def test_fine_policy_strict_metrics(self):
        result = simulate(
            self.pairs,
            "fine_capability",
            "strict",
        )

        self.assertEqual(result["local_calls"], 75)
        self.assertEqual(result["remote_calls"], 75)
        self.assertEqual(result["beneficial_escalations"], 59)
        self.assertEqual(result["missed_escalations"], 3)
        self.assertEqual(result["unnecessary_escalations"], 1)
        self.assertEqual(result["harmful_escalations"], 0)
        self.assertEqual(result["selected_transport_failures"], 0)
        self.assertEqual(result["oracle_ceiling_passes"], 128)
        self.assertAlmostEqual(
            result["reported_remote_cost"],
            0.0024892,
        )
        self.assertAlmostEqual(
            result["median_selected_total_ms"],
            990.314192022197,
        )

    def test_fine_policy_audited_metrics(self):
        result = simulate(
            self.pairs,
            "fine_capability",
            "audited",
        )

        self.assertEqual(result["selected_passes"], 140)
        self.assertEqual(result["beneficial_escalations"], 69)
        self.assertEqual(result["missed_escalations"], 5)
        self.assertEqual(result["unnecessary_escalations"], 1)
        self.assertEqual(result["harmful_escalations"], 0)
        self.assertEqual(result["unrecoverable_local_failures"], 0)
        self.assertEqual(result["oracle_ceiling_passes"], 145)

    def test_always_remote_retains_transport_failures(self):
        result = simulate(
            self.pairs,
            "always_remote",
            "audited",
        )

        self.assertEqual(result["selected_transport_failures"], 2)
        self.assertEqual(result["harmful_escalations"], 2)
        self.assertEqual(
            result["remote_calls_with_reported_cost"],
            148,
        )
        self.assertAlmostEqual(
            result["reported_remote_cost"],
            0.005432,
        )

    def test_output_contains_measured_not_assumed_metrics(self):
        results = [
            simulate(self.pairs, policy, interpretation)
            for interpretation in ("strict", "audited")
            for policy in POLICIES
        ]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "paired.csv"
            write_results(results, output)
            self.assertNotIn(
                b"\r\n",
                output.read_bytes(),
            )


            with output.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 8)
        self.assertIn("reported_remote_cost", rows[0])
        self.assertIn("selected_passes", rows[0])
        self.assertNotIn(
            "remote_success_rate_assumption",
            rows[0],
        )


if __name__ == "__main__":
    unittest.main()
