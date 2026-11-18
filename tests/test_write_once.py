import json
from pathlib import Path
import tempfile
import types
import unittest

from fast_path import FastPathRouter
from remote import RemoteResult
import run_fast_path_planned_v1 as runner
import write_once
from tests.test_planner import job_inputs

DESCRIPTION = "Double n, add the length of text, and add 1 if the note's mood is up."
GOOD = {"readings": [{"id": "mood", "input": "note", "labels": ["up", "down"],
                      "spec": "Classify the mood of the text as 'up' or 'down'."}],
        "code": "def solve(inputs, readings):\n    return inputs['n'] * 2 + len(inputs['text']) + "
                "(1 if readings['mood'] == 'up' else 0)\n"}
WRONG = {"readings": [], "code": "def solve(inputs, readings):\n    return inputs['n']\n"}
SETTINGS = {
    "race_models": ["a", "b"], "synthesis_model": "w", "answer_max_tokens": 64,
    "synthesis_max_tokens": 64, "agreement_quorum": 2, "min_gate_examples": 2,
    "max_synthesis_attempts": 1, "sandbox_timeout_seconds": 2.0, "audit_sample_rate": 0.0,
    "audit_salt": "t", "planner_model": "planner", "planner_max_tokens": 512,
    "plan_examples": 2, "max_plan_attempts": 2, "plan_audit_rate": 0.0,
}


class Fake:
    def __init__(self, programs):
        self.programs = list(programs)
        self.calls = []

    def __call__(self, prompt, config, api_key):
        self.calls.append(prompt[:20])
        if prompt.startswith("Write a program"):
            if not self.programs:
                return RemoteResult(False, error="OPENROUTER_TIMEOUT", model=config["model"])
            return RemoteResult(True, text=json.dumps(self.programs.pop(0)), model=config["model"])
        if prompt.startswith("Carry out the task"):
            i = job_inputs(prompt)
            value = i["n"] * 2 + len(i["text"]) + (1 if "great" in i["note"] else 0)
            return RemoteResult(True, text=f"ANSWER: {value}", model=config["model"], total_ms=1.0)
        mood = "up" if "great" in prompt else "down"
        return RemoteResult(True, text=f'ANSWER: "{mood}"', model=config["model"], total_ms=1.0)


def request(n, note="great day"):
    return {"schema_version": "fast_path_task_v1", "description": DESCRIPTION,
            "inputs": {"n": n, "text": "ab" * n, "note": note}}


class WriteOnceTests(unittest.TestCase):
    def build(self, fake, **overrides):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fast = FastPathRouter({"remote": {"model": "x"}, "fast_path": {**SETTINGS, **overrides}},
                              Path(tmp.name) / "s", Path(tmp.name) / "r.jsonl",
                              remote_fn=fake, api_key="k")
        router = write_once.WriteOnceRouter(fast)
        self.addCleanup(fast.close)
        self.addCleanup(router.close)
        return router

    def test_races_then_adopts_and_serves_the_program(self):
        fake = Fake([GOOD])
        router = self.build(fake)
        routes = []
        for n, note in [(1, "great"), (2, "sad"), (3, "great"), (4, "sad")]:
            result = router.handle(request(n, note))
            routes.append(result["route"])
            router.drain()
            self.assertEqual(result["value"], n * 4 + (1 if note == "great" else 0))
        self.assertEqual(routes, ["race", "race", "program", "program"])
        summary = router.summary(next(iter(router._records)))
        self.assertTrue(summary["adopted"])
        self.assertEqual(summary["attempts"][0]["trial"], {"examples": 2, "passed": 2})

    def test_program_prompt_shows_no_answer(self):
        fake = Fake([GOOD])
        router = self.build(fake)
        for n in (1, 2):
            router.handle(request(n))
            router.drain()
        prompt = write_once.build_program_prompt(DESCRIPTION, request(1)["inputs"])
        self.assertNotIn("ANSWER", prompt.split("Inputs")[1].split("Split")[0])
        self.assertIn("readings", prompt)

    def test_wrong_program_is_rejected_and_attempts_are_bounded(self):
        fake = Fake([WRONG, WRONG, GOOD])
        router = self.build(fake)
        for n in range(1, 6):
            self.assertEqual(router.handle(request(n))["route"], "race")
            router.drain()
        summary = router.summary(next(iter(router._records)))
        self.assertEqual([a["outcome"] for a in summary["attempts"]], ["REJECTED", "REJECTED"])
        self.assertEqual(sum(c.startswith("Write a program") for c in fake.calls), 2)

    def test_parse_program_refusals(self):
        inputs = request(1)["inputs"]
        self.assertEqual(write_once.parse_program("nope", inputs)[1], "PROGRAM_NOT_JSON")
        bad_input = {**GOOD, "readings": [{**GOOD["readings"][0], "input": "n"}]}
        self.assertEqual(write_once.parse_program(json.dumps(bad_input), inputs)[1],
                         "PROGRAM_READINGS_INVALID")
        sneaky = {"readings": [], "code": "import os\ndef solve(inputs, readings):\n    return 1\n"}
        self.assertTrue(write_once.parse_program(json.dumps(sneaky), inputs)[1]
                        .startswith("PROGRAM_CODE_REJECTED"))
        self.assertIsNotNone(write_once.parse_program(json.dumps(GOOD), inputs)[0])


class RunnerArmsTests(unittest.TestCase):
    def test_selected_arms_with_write_once(self):
        instances = [({"n": n, "text": "ab" * n, "note": "great" if n % 2 else "sad"}, {})
                     for n in range(1, 6)]
        shape = {"name": "tiny", "description": DESCRIPTION, "output": "out"}
        bench = types.SimpleNamespace(
            SHAPES=[shape], stream=lambda s: instances,
            gold=lambda s, inst: [{"out": i["n"] * 4 + (1 if i["n"] % 2 else 0)} for i, _ in inst])
        rows = []
        status = runner.execute([shape], bench, {"model": "x"}, dict(SETTINGS), Fake([GOOD]), "k", 1,
                                rows.append, only=("R", "W"), write_arm=True)
        self.assertEqual(status, "COMPLETED")
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertEqual({r["arm"] for r in jobs}, {"R", "W"})
        self.assertTrue(all(r["correct"] for r in jobs))
        w = [r["route"] for r in sorted(jobs, key=lambda r: r["index"]) if r["arm"] == "W"]
        self.assertEqual(w, ["race", "race", "program", "program", "program"])
        summary = next(r for r in rows if r["record_type"] == "shape")
        self.assertEqual(set(summary["usage"]), {"R", "W"})
        self.assertTrue(summary["write_once"]["adopted"])

        import analyze_write_once_v1 as analysis
        kinds = {"header": [{"label": "t"}], "footer": [{"status": "COMPLETED"}],
                 "job": jobs, "shape": [summary]}
        result = analysis.analyse(kinds, replicates=50)
        self.assertEqual(result["first_program_job_index"], {"tiny": 2})
        self.assertEqual(result["w_routes"]["program"]["jobs"], 3)


if __name__ == "__main__":
    unittest.main()


EDGE_WRONG = {"readings": GOOD["readings"],
              "code": "def solve(inputs, readings):\n    if inputs['n'] == 0:\n        return -1\n"
                      "    return inputs['n'] * 2 + len(inputs['text']) + (1 if readings['mood'] == 'up' else 0)\n"}


class ProbeFake(Fake):
    def __call__(self, prompt, config, api_key):
        if prompt.startswith("List edge-case inputs for testing a program"):
            self.calls.append(prompt[:20])
            self.probe_prompt = prompt
            return RemoteResult(True, text=json.dumps([{"n": 0, "text": ""}, {"n": 1, "text": "a"},
                                                       {"n": "bad", "text": ""}]), model=config["model"])
        return super().__call__(prompt, config, api_key)


class ProbeTests(WriteOnceTests):
    def run_jobs(self, programs, probes=4):
        fake = ProbeFake(programs)
        router = self.build(fake, program_probes=probes, probe_model="p", probe_max_tokens=64)
        for n in range(1, 6):
            router.handle(request(n))
            router.drain()
        return fake, router.summary(next(iter(router._records)))

    def test_probe_rejects_a_program_wrong_only_on_an_edge(self):
        fake, summary = self.run_jobs([EDGE_WRONG, GOOD])
        first, second = summary["attempts"]
        self.assertEqual(first["outcome"], "REJECTED")
        self.assertEqual(first["trial"], {"examples": 2, "passed": 2})
        self.assertEqual((first["probes"]["proposed"], first["probes"]["failed"]), (2, 1))
        self.assertEqual(second["outcome"], "ADOPTED")
        self.assertTrue(summary["adopted"])
        # The prose input is held at the example's value and not shown as a probe key.
        self.assertNotIn('"note"', fake.probe_prompt.split("Reply with one JSON array")[1])

    def test_probes_off_by_default(self):
        fake = ProbeFake([EDGE_WRONG])
        router = self.build(fake)
        for n in range(1, 4):
            router.handle(request(n))
            router.drain()
        self.assertTrue(router.summary(next(iter(router._records)))["adopted"])
        self.assertFalse(any(c.startswith("List edge") for c in fake.calls))

    def test_parse_job_probes(self):
        inputs = request(1)["inputs"]
        got = write_once.parse_job_probes(json.dumps([{"n": 2, "text": "x"}, {"n": 2, "text": "x"},
                                                      {"n": 3}, {"n": 4, "text": 5}]),
                                          inputs, ["note"], 6)
        self.assertEqual(got, [{"n": 2, "text": "x", "note": inputs["note"]}])


class RunnerProbeArmTests(unittest.TestCase):
    def test_arm_p_runs_with_probes(self):
        instances = [({"n": n, "text": "ab" * n, "note": "great"}, {}) for n in range(1, 6)]
        shape = {"name": "tiny", "description": DESCRIPTION, "output": "out"}
        bench = types.SimpleNamespace(SHAPES=[shape], stream=lambda s: instances,
                                      gold=lambda s, inst: [{"out": i["n"] * 4 + 1} for i, _ in inst])
        rows = []
        runner.execute([shape], bench, {"model": "x"},
                       {**SETTINGS, "probe_model": "p", "probe_max_tokens": 64}, ProbeFake([EDGE_WRONG, GOOD]),
                       "k", 1, rows.append, only=("R", "P"), probes=4)
        summary = next(r for r in rows if r["record_type"] == "shape")
        self.assertEqual([a["outcome"] for a in summary["write_once_probed"]["attempts"]],
                         ["REJECTED", "ADOPTED"])
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertTrue(all(r["correct"] for r in jobs))
        self.assertEqual(set(summary["usage"]), {"R", "P"})
