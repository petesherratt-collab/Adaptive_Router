from pathlib import Path
import tempfile
import unittest

from fast_path import FastPathRouter
from remote import RemoteResult

SPEC = "Return the number of characters in the text, counting spaces."
BUGGY = "def solve(text):\n    return len(text.replace(' ', ''))\n"
FIXED = "def solve(text):\n    return len(text)\n"


class Fake:
    def __init__(self):
        self.repair_prompts = []

    def __call__(self, prompt, config, api_key):
        if prompt.startswith("Write a Python function"):
            if "previous implementation gave wrong results" in prompt:
                self.repair_prompts.append(prompt)
                return RemoteResult(True, text=FIXED, model=config["model"])
            return RemoteResult(True, text=BUGGY, model=config["model"])
        text = prompt.split("Argument 1 (JSON): ")[1].split("\n")[0].strip('"')
        return RemoteResult(True, text=f"ANSWER: {len(text)}", model=config["model"], total_ms=1.0)


class RepairTests(unittest.TestCase):
    def run_router(self, **overrides):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        settings = {"race_models": ["a", "b"], "synthesis_model": "w", "answer_max_tokens": 64,
                    "synthesis_max_tokens": 64, "agreement_quorum": 2, "min_gate_examples": 3,
                    "max_synthesis_attempts": 1, "sandbox_timeout_seconds": 2.0,
                    "audit_sample_rate": 0.0, "audit_salt": "t", **overrides}
        fake = Fake()
        router = FastPathRouter({"remote": {"model": "x"}, "fast_path": settings},
                                Path(tmp.name) / "s", Path(tmp.name) / "r.jsonl",
                                remote_fn=fake, api_key="k")
        self.addCleanup(router.close)
        for text in ["a b", "cd", "e f g", "hij", "k l"]:
            router.handle({"schema_version": "fast_path_request_v1",
                           "task": {"spec": SPEC, "signature": "def solve(text: str) -> int:"},
                           "args": [text]})
            router.drain()
        return router, fake, router.store.shapes()[0]

    def test_off_by_default(self):
        _, fake, record = self.run_router()
        self.assertIsNone(record["function"])
        self.assertEqual(fake.repair_prompts, [])
        self.assertEqual(record["synthesis_attempts"][0]["gate"]["reason"], "EXAMPLE_MISMATCH")
        self.assertIn("rejected_source", record["synthesis_attempts"][0])

    def test_repair_shows_two_failures_and_must_pass_every_example(self):
        _, fake, record = self.run_router(repair_attempts=1)
        self.assertIsNotNone(record["function"])
        self.assertEqual(len(fake.repair_prompts), 1)
        self.assertEqual(fake.repair_prompts[0].count("- arguments"), 2)
        last = record["synthesis_attempts"][-1]
        self.assertEqual((last["outcome"], last["repair"]["examples_shown"]), ("PROMOTED", 2))
        self.assertEqual(last["gate"]["passed"], last["gate"]["examples"])


if __name__ == "__main__":
    unittest.main()
