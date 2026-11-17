from concurrent.futures import ThreadPoolExecutor
import json
import re
import unittest

import fast_path_gold_items_v1 as bank
from remote import RemoteResult
import run_fast_path_gold as gold


def prompt_args(prompt):
    return [json.loads(v) for v in re.findall(r"^Argument \d+ \(JSON\): (.*)$", prompt, re.M)]


ITEM = {
    "name": "double",
    "spec": "Return the input integer doubled.",
    "signature": "def solve(n: int) -> int:",
    "tests": [[[0], 0], [[2], 4], [[3], 6]],
}


def fake_remote(prompt, config, api_key):
    model = config["model"]
    if prompt.startswith("Write a Python function"):
        return RemoteResult(True, text="def solve(n):\n    return n * n\n", model=model)
    n = prompt_args(prompt)[0]
    if model == "down":
        return RemoteResult(False, error="OPENROUTER_TIMEOUT", model=model)
    if model == "prose":
        return RemoteResult(True, text="It is " + str(n * 2), model=model)
    value = n * 2 if model == "right" else n * n
    return RemoteResult(True, text=json.dumps(value), model=model, total_ms=1.0)


class GoldBankTests(unittest.TestCase):
    def test_bank_self_verifies(self):
        bank.self_verify()
        self.assertGreaterEqual(len(bank.ITEMS), 28)


class GoldRunTests(unittest.TestCase):
    def rows(self, models):
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = gold.answer_rows(ITEM, models, {}, fake_remote, "k", pool)
        rows.append(gold.synthesis_row(ITEM, "writer", {}, 256, fake_remote, "k"))
        return rows

    def test_summary_counts(self):
        summary = gold.summarise(self.rows(["right", "square", "squarer", "prose", "down"]))
        self.assertEqual(
            summary["per_model"]["right"],
            {"observations": 3, "task_clusters": 1, "wrong_or_invalid": 0, "invalid": 0},
        )
        self.assertEqual(summary["per_model"]["square"]["wrong_or_invalid"], 1)
        self.assertEqual(summary["per_model"]["prose"]["invalid"], 3)
        self.assertEqual(summary["per_model"]["down"]["wrong_or_invalid"], 3)
        # Two models sharing the same fault agree on the wrong answer for n = 3.
        self.assertEqual(
            summary["pairwise_agreement"]["square + squarer"],
            {"cases": 3, "agreed": 3, "agreed_and_wrong": 1},
        )
        self.assertEqual(
            summary["pairwise_agreement"]["right + square"],
            {"cases": 3, "agreed": 2, "agreed_and_wrong": 0},
        )
        self.assertEqual(
            summary["synthesis"],
            {"items": 1, "provider_failures": 0, "statically_rejected": 0,
             "gold_correct": 0, "gold_wrong": 1},
        )

    def test_synthesis_row_records_pass_vector(self):
        row = self.rows(["right"])[-1]
        self.assertEqual((row["static"], row["passed"]), ("OK", [True, True, False]))


if __name__ == "__main__":
    unittest.main()


class ProbeEvaluationTests(unittest.TestCase):
    def test_pass_vectors_and_summary(self):
        import evaluate_fast_path_probes as probes

        examples = [{"args": [0], "expected": 0}, {"args": [3], "expected": 6}]
        self.assertEqual(probes.passes("def solve(n):\n    return n * 2\n", examples), [True, True])
        self.assertEqual(probes.passes("def solve(n):\n    return n * n\n", examples), [True, False])
        self.assertEqual(probes.passes("import os\ndef solve(n):\n    return 0\n", examples), [False, False])
        self.assertEqual(probes.passes("def solve(n):\n    return 0\n", []), [])
        rows = [
            {"record_type": "item", "item": "a", "proposed": 3, "agreed": 2, "disagreed": 1,
             "reference_rejected": False, "buggy_rejected": True},
            {"record_type": "item", "item": "b", "proposed": 2, "agreed": 0, "disagreed": 0,
             "reference_rejected": False, "buggy_rejected": False},
            {"record_type": "item", "item": "c", "proposed": 2, "agreed": 2, "disagreed": 0,
             "reference_rejected": True, "buggy_rejected": True},
        ]
        summary = probes.summarise(rows)
        self.assertEqual((summary["buggy_rejected"], summary["buggy_accepted"]), (2, 1))
        self.assertEqual(summary["reference_rejected_items"], ["c"])
        self.assertEqual(summary["buggy_accepted_items"], ["b"])
        self.assertEqual(summary["items_with_probe_examples"], 2)

    def test_recorded_case_is_wrong_only_at_zero(self):
        import json as _json
        from pathlib import Path
        import evaluate_fast_path_probes as probes

        case = _json.loads(
            (Path(__file__).resolve().parents[1] / "fast_path_probe_case_number_to_words.json")
            .read_text(encoding="utf-8")
        )[0]
        examples = [{"args": [0], "expected": "zero"}, {"args": [21], "expected": "twenty-one"}]
        self.assertEqual(probes.passes(case["buggy"], examples), [False, True])
        self.assertEqual(probes.passes(case["reference"], examples), [True, True])
