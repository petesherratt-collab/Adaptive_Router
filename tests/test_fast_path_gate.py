import json
from pathlib import Path
import unittest

import evaluate_fast_path_gate as gate_eval


ROOT = Path(__file__).resolve().parents[1]


class GateEvaluationTests(unittest.TestCase):
    def test_vendored_bank_matches_pin(self):
        self.assertTrue(gate_eval.verify_pin(gate_eval.DEFAULT_BANK))

    def test_subset_counting(self):
        items = [
            {
                "name": "double",
                "reference": "def solve(n):\n    return n * 2\n",
                "buggy": "def solve(n):\n    return n * n\n",
                "tests": [((0,), 0), ((2,), 4), ((3,), 6)],
            }
        ]
        result = gate_eval.evaluate(items)
        by_k = result["items"][0]["by_k"]
        # The buggy variant passes tests 0 and 1 only.
        self.assertEqual(by_k["1"], {"subsets": 3, "buggy_accepted": 2, "reference_rejected": 0})
        self.assertEqual(by_k["2"], {"subsets": 3, "buggy_accepted": 1, "reference_rejected": 0})
        self.assertEqual(by_k["3"], {"subsets": 1, "buggy_accepted": 0, "reference_rejected": 0})
        self.assertAlmostEqual(
            result["by_example_count"]["1"]["mean_false_accept_rate"], 2 / 3
        )

    def test_statically_rejected_candidate_never_passes(self):
        items = [
            {
                "name": "x",
                "reference": "import os\ndef solve(n):\n    return n\n",
                "buggy": "def solve(n):\n    return 0\n",
                "tests": [((1,), 1), ((2,), 2)],
            }
        ]
        row = gate_eval.evaluate(items)["items"][0]
        self.assertEqual(row["reference_static"], "MODULE_NOT_ALLOWED")
        self.assertEqual(row["by_k"]["1"]["reference_rejected"], 2)

    def test_committed_dev_result_reproduces(self):
        committed = json.loads(
            (ROOT / "fast_path_gate_dev_v1.json").read_text(encoding="utf-8")
        )
        result = gate_eval.evaluate(gate_eval.load_items(gate_eval.DEFAULT_BANK))
        self.assertEqual(result["items"], committed["items"])
        self.assertEqual(result["by_example_count"], committed["by_example_count"])
        self.assertEqual(
            committed["bank"]["sha256"], gate_eval.sha256_file(gate_eval.DEFAULT_BANK)
        )


if __name__ == "__main__":
    unittest.main()
