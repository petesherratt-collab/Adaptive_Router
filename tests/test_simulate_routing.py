import json
import unittest
from pathlib import Path

from simulate_routing import local_correct, route, simulate


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "benchmark_runs_simzero_v2.jsonl"


def load_rows():
    with RUNS.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class RoutingPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_rows()

    def test_frozen_observation_count(self):
        self.assertEqual(len(self.rows), 150)

    def test_coarse_policy_uses_task_class_only(self):
        routes = [route("coarse_class", row) for row in self.rows]
        self.assertEqual(routes.count("local"), 75)
        self.assertEqual(routes.count("remote"), 75)

    def test_fine_policy_uses_capability_families(self):
        routes = [route("fine_capability", row) for row in self.rows]
        self.assertEqual(routes.count("local"), 75)
        self.assertEqual(routes.count("remote"), 75)

        event_failure = next(
            row for row in self.rows if row["task_id"] == "extract_event_2"
        )
        priority = next(
            row for row in self.rows if row["task_id"] == "classify_priority"
        )

        self.assertEqual(route("fine_capability", event_failure), "local")
        self.assertEqual(route("fine_capability", priority), "remote")

    def test_audited_override_is_narrow(self):
        person = next(
            row for row in self.rows if row["task_id"] == "extract_person_2"
        )
        event = next(
            row for row in self.rows if row["task_id"] == "extract_event_2"
        )

        self.assertFalse(local_correct(person, "strict"))
        self.assertTrue(local_correct(person, "audited"))
        self.assertFalse(local_correct(event, "strict"))
        self.assertFalse(local_correct(event, "audited"))

    def test_empirical_policy_counts(self):
        expected = {
            ("strict", "always_local"): (150, 0, 66, 84, 0),
            ("strict", "always_remote"): (0, 150, 0, 0, 66),
            ("strict", "coarse_class"): (75, 75, 51, 24, 15),
            ("strict", "fine_capability"): (75, 75, 65, 10, 1),
            ("audited", "always_local"): (150, 0, 71, 79, 0),
            ("audited", "always_remote"): (0, 150, 0, 0, 71),
            ("audited", "coarse_class"): (75, 75, 56, 19, 15),
            ("audited", "fine_capability"): (75, 75, 70, 5, 1),
        }

        for (interpretation, policy), counts in expected.items():
            with self.subTest(interpretation=interpretation, policy=policy):
                result = simulate(self.rows, policy, interpretation, 1.0)
                actual = (
                    result["local_calls"],
                    result["remote_calls"],
                    result["local_passes"],
                    result["missed_escalations"],
                    result["unnecessary_escalations"],
                )
                self.assertEqual(actual, counts)

    def test_counterfactual_remote_success_is_labelled(self):
        result = simulate(
            self.rows,
            "fine_capability",
            "strict",
            0.80,
        )

        self.assertEqual(result["remote_success_rate_assumption"], 0.80)
        self.assertEqual(result["expected_remote_passes"], 60.0)
        self.assertEqual(result["expected_total_passes"], 125.0)
        self.assertAlmostEqual(result["expected_success_rate"], 125 / 150)


if __name__ == "__main__":
    unittest.main()

