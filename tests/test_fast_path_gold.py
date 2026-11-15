from concurrent.futures import ThreadPoolExecutor
import json
import unittest

import fast_path_gold_items_v1 as bank
from remote import RemoteResult
import run_fast_path_gold as gold


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
    n = json.loads(prompt.split("positional): ")[1].split("\n")[0])[0]
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
