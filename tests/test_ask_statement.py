import csv
import json
from pathlib import Path
import tempfile
import unittest

import ask_statement
from remote import RemoteResult

CODE = ("def solve(rows):\n    spent = -sum(r['amount'] for r in rows if r['merchant'] == 'Morrisons' and r['amount'] < 0)\n"
        "    return f'Morrisons: £{spent:.2f}'\n")


class Fake:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt, config, api_key):
        self.prompts.append(prompt)
        return RemoteResult(True, text=self.replies.pop(0), model=config["model"], cost=0.001)


def statement(directory):
    path = Path(directory) / "s.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["ID", "Created", "Title", "Subtitle", "Amount", "Currency", "Categories"])
        w.writerow(["1", "02/01/26, 10:00", "Morrisons", "", "-12.50", "GBP", "groceries"])
        w.writerow(["2", "01/01/26, 09:00", "Morrisons", "", "-7.25", "GBP", "groceries"])
        w.writerow(["3", "03/01/26, 19:00", "Wetherspoon", "", "-4.10", "GBP", "eating_out"])
    return path


class AskStatementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rows = ask_statement.load_statement(statement(self.tmp.name))

    def asker(self, fake):
        return ask_statement.Asker(self.rows, remote_fn=fake, api_key="k",
                                   cache_path=Path(self.tmp.name) / "cache.json")

    def test_loads_and_sorts_rows(self):
        self.assertEqual([r["date"] for r in self.rows], ["2026-01-01", "2026-01-02", "2026-01-03"])
        self.assertEqual(self.rows[0]["amount"], -7.25)

    def test_answer_is_computed_locally_and_then_cached(self):
        fake = Fake([json.dumps({"assumptions": "Morrisons only.", "code": CODE})])
        asker = self.asker(fake)
        first = asker.ask("How much at Morrisons?")
        self.assertEqual(first["answer"], "Morrisons: £19.75")
        self.assertFalse(first["cached"])
        self.assertIn("'Wetherspoon': 1 transactions", fake.prompts[0])
        second = self.asker(Fake([])).ask("  how much at   MORRISONS? ")
        self.assertTrue(second["cached"])
        self.assertEqual((second["answer"], second["model_calls"]), ("Morrisons: £19.75", 0))

    def test_failing_code_is_retried_with_the_error(self):
        broken = "def solve(rows):\n    return rows[99]\n"
        fake = Fake([json.dumps({"assumptions": "x", "code": broken}),
                     json.dumps({"assumptions": "Morrisons only.", "code": CODE})])
        result = self.asker(fake).ask("Morrisons?")
        self.assertEqual(result["answer"], "Morrisons: £19.75")
        self.assertIn("IndexError", fake.prompts[1])
        self.assertEqual(result["model_calls"], 2)

    def test_unsafe_code_is_refused(self):
        bad = json.dumps({"assumptions": "x", "code": "import os\ndef solve(rows):\n    return 'x'\n"})
        result = self.asker(Fake([bad, bad])).ask("Anything?")
        self.assertIsNone(result["answer"])
        self.assertTrue(result["error"].startswith("CODE_REJECTED"))
