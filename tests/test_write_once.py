import json
import time
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


LIST_DESCRIPTION = "Count the reviews whose text is positive and add n."
LIST_PROGRAM = {"readings": [{"id": "tone", "input": "reviews", "each": True, "field": "text",
                              "labels": ["up", "down"],
                              "spec": "Classify the review text as 'up' or 'down'."}],
                "code": "def solve(inputs, readings):\n    return inputs['n'] + readings['tone'].count('up')\n"}


class ListFake(Fake):
    def __call__(self, prompt, config, api_key):
        if prompt.startswith("Carry out the task"):
            self.calls.append(prompt[:20])
            i = job_inputs(prompt)
            value = i["n"] + sum("great" in r["text"] for r in i["reviews"])
            return RemoteResult(True, text=f"ANSWER: {value}", model=config["model"], total_ms=1.0)
        return super().__call__(prompt, config, api_key)


def list_request(n, texts):
    return {"schema_version": "fast_path_task_v1", "description": LIST_DESCRIPTION,
            "inputs": {"n": n, "reviews": [{"stars": 3, "text": t} for t in texts]}}


class ListReadingTests(WriteOnceTests):
    def test_each_reading_reads_every_item(self):
        fake = ListFake([LIST_PROGRAM])
        router = self.build(fake)
        texts = [["great", "awful"], ["great", "great", "meh"], ["bad"], ["great"]]
        results = []
        for n, t in enumerate(texts, start=1):
            results.append(router.handle(list_request(n, t)))
            router.drain()
        self.assertEqual([r["route"] for r in results], ["race", "race", "program", "program"])
        self.assertEqual(results[2]["value"], 3)
        self.assertEqual(results[3]["readings"], {"tone": ["up"]})
        self.assertEqual(results[3]["value"], 5)

    def test_each_reading_shape_is_checked(self):
        inputs = list_request(1, ["a"])["inputs"]
        no_each = {**LIST_PROGRAM, "readings": [{k: v for k, v in LIST_PROGRAM["readings"][0].items()
                                                 if k not in ("each", "field")}]}
        self.assertEqual(write_once.parse_program(json.dumps(no_each), inputs)[1], "PROGRAM_READINGS_INVALID")
        wrong_field = {**LIST_PROGRAM, "readings": [{**LIST_PROGRAM["readings"][0], "field": "stars"}]}
        self.assertEqual(write_once.parse_program(json.dumps(wrong_field), inputs)[1],
                         "PROGRAM_READINGS_INVALID")
        self.assertIsNotNone(write_once.parse_program(json.dumps(LIST_PROGRAM), inputs)[0])


class StoreAndEarlyTests(WriteOnceTests):
    def test_program_survives_a_new_router(self):
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fake = Fake([GOOD])
        fast = self.build(fake).router
        first = write_once.WriteOnceRouter(fast, Path(tmp.name) / "programs")
        for n in (1, 2):
            first.handle(request(n))
            first.drain()
        first.close()
        second = write_once.WriteOnceRouter(fast, Path(tmp.name) / "programs")
        self.addCleanup(second.close)
        self.assertEqual(second.handle(request(5))["route"], "program")

    def test_early_write_starts_on_first_sight_and_adopts_after_two_examples(self):
        fake = Fake([GOOD])
        router = self.build(fake, write_early=True)
        router.handle(request(1))
        router.drain()
        record = next(iter(router._records.values()))
        # Written before any second example exists; held as a candidate.
        self.assertIsNotNone(record["candidate"])
        self.assertIsNone(record["program"])
        router.handle(request(2))
        router.drain()
        self.assertIsNotNone(record["program"])
        self.assertTrue(record["attempts"][0]["early"])
        self.assertEqual(router.handle(request(3))["route"], "program")
        self.assertEqual(sum(c.startswith("Write a program") for c in fake.calls), 1)

    def test_failed_early_candidate_falls_back_to_a_normal_write(self):
        fake = Fake([WRONG, GOOD])
        router = self.build(fake, write_early=True)
        routes = []
        for n in range(1, 6):
            routes.append(router.handle(request(n))["route"])
            router.drain()
        record = next(iter(router._records.values()))
        self.assertEqual([a["outcome"] for a in record["attempts"]], ["REJECTED", "ADOPTED"])
        self.assertEqual(routes[-1], "program")


class BatchFake(ListFake):
    """Answers a batched reading with one label per text; a per-item reading
    with one label."""
    def __init__(self, programs, split=False):
        super().__init__(programs)
        self.split = split  # model 'b' disagrees on everything
        self.broken = False  # every model but 'a' gives an unusable answer

    def __call__(self, prompt, config, api_key):
        if prompt.startswith("Work out what"):
            self.calls.append(("read", config["model"], "every text in the list" in prompt))
            if self.broken and config["model"] != "a":
                return RemoteResult(True, text="no idea", model=config["model"], total_ms=1.0)
            arg = json.loads(prompt.split("Argument 1 (JSON): ")[1].split("\n")[0])
            flip = self.split and config["model"] == "b"
            label = lambda t: ("down" if "great" in t else "up") if flip else ("up" if "great" in t else "down")
            value = [label(t) for t in arg] if isinstance(arg, list) else label(arg)
            return RemoteResult(True, text=f"ANSWER: {json.dumps(value)}", model=config["model"], total_ms=1.0)
        return super().__call__(prompt, config, api_key)


class ReadingFixTests(WriteOnceTests):
    def adopt(self, fake, **settings):
        router = self.build(fake, **settings)
        for n, t in enumerate([["great", "bad"], ["great"]], start=1):
            router.handle(list_request(n, t))
            router.drain()
        return router

    def test_batched_reading_is_one_race_per_list(self):
        fake = BatchFake([LIST_PROGRAM])
        router = self.adopt(fake, batch_readings=True)
        fake.calls.clear()
        result = router.handle(list_request(5, ["great", "meh", "great"]))
        router.drain()
        self.assertEqual((result["route"], result["value"]), ("program", 7))
        reads = [c for c in fake.calls if isinstance(c, tuple)]
        self.assertEqual(len(reads), 2)  # one per racer, not one per item
        self.assertTrue(all(batched for _, _, batched in reads))

    def test_a_batched_answer_of_the_wrong_length_is_not_used(self):
        router = self.build(BatchFake([]), batch_readings=True)
        reading = {**LIST_PROGRAM["readings"][0]}

        class Short(BatchFake):
            def __call__(self, prompt, config, api_key):
                if config["model"] == "a" and prompt.startswith("Work out what"):
                    return RemoteResult(True, text='ANSWER: ["up"]', model="a", total_ms=0.1)
                return super().__call__(prompt, config, api_key)
        router.router.remote_fn = Short([])
        ok, value, _ = router._reading_value(reading, ["great", "bad"])
        self.assertEqual((ok, value), (True, ["up", "down"]))

    def test_gate_flags_disagreement(self):
        fake = BatchFake([LIST_PROGRAM])
        router = self.adopt(fake, batch_readings=True, uncertainty_gate=True)
        fake.split = True  # only after adoption, so the trial is not affected
        result = router.handle(list_request(5, ["great"]))
        router.drain()
        self.assertEqual(result["route"], "program")
        self.assertTrue(result["uncertain"])
        calm = self.adopt(BatchFake([LIST_PROGRAM]), batch_readings=True, uncertainty_gate=True)
        self.assertFalse(calm.handle(list_request(6, ["great"]))["uncertain"])

    def test_race_route_flag(self):
        router = self.build(Fake([]), uncertainty_gate=True)
        self.assertFalse(router.handle(request(1))["uncertain"])

    def test_majority_decision_outvotes_a_dissenting_reader(self):
        fake = BatchFake([LIST_PROGRAM])
        router = self.adopt(fake, race_models=["a", "b", "c"], decision="majority")
        fake.split = True  # model b now reads every text the other way; a and c still agree
        result = router.handle(list_request(5, ["great", "bad"]))
        router.drain()
        self.assertEqual((result["route"], result["value"]), ("program", 6))  # 5 + one "up", as a and c read it
        self.assertTrue(result["uncertain"])  # b disagreed, so it is flagged
        fake.split = False
        self.assertFalse(router.handle(list_request(6, ["great"]))["uncertain"])

    def test_flagged_program_answer_is_served_from_the_fallback_race(self):
        fake = BatchFake([LIST_PROGRAM])
        router = self.adopt(fake, uncertainty_gate=True, flag_fallback="majority")
        calm = router.handle(list_request(4, ["great"]))
        router.drain()
        self.assertEqual((calm["route"], calm["uncertain"]), ("program", False))
        fake.split = True  # readers now disagree: the program's answer is flagged
        result = router.handle(list_request(5, ["great", "bad"]))
        router.drain()
        self.assertEqual(result["route"], write_once.FALLBACK_ROUTE)
        self.assertIn("program_value", result)
        self.assertEqual(result["value"], 6)  # the whole-task race's answer

    def test_flagged_answer_is_returned_for_review_without_a_retry(self):
        fake = BatchFake([LIST_PROGRAM])
        router = self.adopt(fake, uncertainty_gate=True, flag_fallback="review")
        fake.split = True
        before = len(fake.calls)
        result = router.handle(list_request(5, ["great", "bad"]))
        self.assertEqual((result["route"], result["uncertain"]), (write_once.REVIEW_ROUTE, True))
        self.assertIsNotNone(result["value"])  # the program's answer, provisional
        self.assertFalse(any(isinstance(c, str) and c.startswith("Carry out the task") for c in fake.calls[before:]))  # no whole-task race

    def test_majority_decision_on_the_whole_task_race(self):
        router = self.build(Fake([]), decision="majority")
        result = router.handle(request(1))
        self.assertEqual(result["route"], "race")
        self.assertFalse(result["uncertain"])

    def test_adaptive_width_narrows_after_agreement_and_widens_on_dispute(self):
        fake = BatchFake([LIST_PROGRAM])
        router = self.adopt(fake, race_models=["a", "b", "c"], batch_readings=True,
                            adaptive_width={"width": 2, "after": 2})
        for n in range(3, 6):
            router.handle(list_request(n, ["great"]))
            router.drain()
        fake.calls.clear()
        router.handle(list_request(9, ["great"]))
        router.drain()
        self.assertEqual(len([c for c in fake.calls if isinstance(c, tuple)]), 2)
        fake.broken = True  # whichever two race, they no longer agree: full width again
        router.handle(list_request(10, ["great"]))
        router.drain()
        fake.broken = False
        fake.calls.clear()
        router.handle(list_request(11, ["great"]))
        router.drain()
        self.assertEqual(len([c for c in fake.calls if isinstance(c, tuple)]), 3)


class TimedFake(BatchFake):
    """BatchFake with a delay on whole-task answers or on readings, to decide who finishes first."""
    def __init__(self, programs, race_delay=0.0, read_delay=0.0):
        super().__init__(programs)
        self.race_delay, self.read_delay = race_delay, read_delay

    def __call__(self, prompt, config, api_key):
        if prompt.startswith("Carry out the task"):
            time.sleep(self.race_delay)
        elif prompt.startswith("Work out what"):
            time.sleep(self.read_delay)
        return super().__call__(prompt, config, api_key)


class AlongsideTests(ReadingFixTests):
    def test_program_wins_when_the_race_is_slow(self):
        fake = TimedFake([LIST_PROGRAM])
        router = self.adopt(fake, uncertainty_gate=True, race_alongside=True)
        fake.race_delay = 0.3
        result = router.handle(list_request(5, ["great", "bad"]))
        router.drain()
        self.assertEqual((result["route"], result["value"], result["uncertain"]), ("program", 6, False))
        self.assertLess(result["total_ms"], 300)

    def test_race_wins_when_the_readings_are_slow(self):
        fake = TimedFake([LIST_PROGRAM])
        router = self.adopt(fake, uncertainty_gate=True, race_alongside=True)
        fake.read_delay = 0.3
        result = router.handle(list_request(5, ["great", "bad"]))
        self.assertEqual((result["route"], result["value"], result["uncertain"]), ("race", 6, False))
        self.assertLess(result["total_ms"], 300)
        router.drain()

    def test_flagged_program_waits_for_race_agreement(self):
        fake = TimedFake([LIST_PROGRAM])
        router = self.adopt(fake, uncertainty_gate=True, race_alongside=True)
        fake.split = True  # program's readings disagree: flagged, so the race decides
        fake.race_delay = 0.1
        result = router.handle(list_request(5, ["great", "bad"]))
        router.drain()
        self.assertEqual((result["route"], result["value"], result["uncertain"]), ("race", 6, False))


class RunnerFlaggedArmTests(unittest.TestCase):
    def test_arms_f_and_m_run_and_are_analysed(self):
        instances = [({"n": n, "reviews": [{"stars": 3, "text": t} for t in texts]}, {})
                     for n, texts in enumerate([["great", "bad"], ["great"], ["meh", "great"], ["bad"]], 1)]
        shape = {"name": "tiny", "description": LIST_DESCRIPTION, "output": "out"}
        gold = [{"out": i["n"] + sum("great" in r["text"] for r in i["reviews"])} for i, _ in instances]
        bench = types.SimpleNamespace(SHAPES=[shape], stream=lambda s: instances, gold=lambda s, inst: gold)
        rows = []
        runner.execute([shape], bench, {"model": "x"}, {**SETTINGS, "probe_model": "p", "probe_max_tokens": 64},
                       BatchFake([LIST_PROGRAM]), "k", 1, rows.append, only=("R", "P", "F", "M"), probes=4,
                       flagged=True)
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertEqual({r["arm"] for r in jobs}, {"R", "P", "F", "M"})
        self.assertTrue(all(r["correct"] for r in jobs))
        summary = next(r for r in rows if r["record_type"] == "shape")
        self.assertIn("write_once_fallback", summary)
        self.assertIn("write_once_majority", summary)
        import analyze_write_once_v1 as analysis
        result = analysis.analyse({"header": [{"label": "t"}], "footer": [{"status": "COMPLETED"}],
                                   "job": jobs, "shape": [summary]}, replicates=50, primary_arm="F")
        self.assertEqual(result["fallback"]["fallback"]["jobs"], 0)  # nobody disagreed
        self.assertIsNotNone(result["m_vs_p"])


class RunnerAlongsideArmTests(unittest.TestCase):
    def test_arm_s_runs_and_is_analysed(self):
        instances = [({"n": n, "reviews": [{"stars": 3, "text": t} for t in texts]}, {})
                     for n, texts in enumerate([["great", "bad"], ["great"], ["meh", "great"], ["bad"]], 1)]
        shape = {"name": "tiny", "description": LIST_DESCRIPTION, "output": "out"}
        gold = [{"out": i["n"] + sum("great" in r["text"] for r in i["reviews"])} for i, _ in instances]
        bench = types.SimpleNamespace(SHAPES=[shape], stream=lambda s: instances, gold=lambda s, inst: gold)
        rows = []
        runner.execute([shape], bench, {"model": "x"}, {**SETTINGS, "probe_model": "p", "probe_max_tokens": 64},
                       BatchFake([LIST_PROGRAM]), "k", 1, rows.append, only=("R", "S"), probes=4, alongside=True)
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertEqual({r["arm"] for r in jobs}, {"R", "S"})
        self.assertTrue(all(r["correct"] for r in jobs))
        summary = next(r for r in rows if r["record_type"] == "shape")
        self.assertIn("write_once_alongside", summary)
        import analyze_write_once_v1 as analysis
        result = analysis.analyse({"header": [{"label": "t"}], "footer": [{"status": "COMPLETED"}],
                                   "job": jobs, "shape": [summary]}, replicates=50, primary_arm="S")
        self.assertIsNotNone(result["s_vs_r"])


class RunnerAgreementArmTests(unittest.TestCase):
    def test_arm_g_races_to_agreement_and_is_analysed(self):
        instances = [({"n": n, "reviews": [{"stars": 3, "text": t} for t in texts]}, {})
                     for n, texts in enumerate([["great", "bad"], ["great"], ["meh", "great"], ["bad"]], 1)]
        shape = {"name": "tiny", "description": LIST_DESCRIPTION, "output": "out"}
        gold = [{"out": i["n"] + sum("great" in r["text"] for r in i["reviews"])} for i, _ in instances]
        bench = types.SimpleNamespace(SHAPES=[shape], stream=lambda s: instances, gold=lambda s, inst: gold)
        rows = []
        runner.execute([shape], bench, {"model": "x"}, {**SETTINGS, "probe_model": "p", "probe_max_tokens": 64},
                       BatchFake([LIST_PROGRAM]), "k", 1, rows.append, only=("R", "G"), agreement=True)
        jobs = [r for r in rows if r["record_type"] == "job"]
        g = [r for r in jobs if r["arm"] == "G"]
        self.assertEqual(len(g), 4)
        self.assertTrue(all(r["correct"] and r["route"] == "race_agreed" and r["uncertain"] is False for r in g))
        import analyze_write_once_v1 as analysis
        summary = next(r for r in rows if r["record_type"] == "shape")
        result = analysis.analyse({"header": [{"label": "t"}], "footer": [{"status": "COMPLETED"}],
                                   "job": jobs, "shape": [summary]}, replicates=50, primary_arm="G")
        self.assertIsNotNone(result["g_vs_r"])


class RunnerFixedArmTests(unittest.TestCase):
    def test_arm_b_runs_with_the_reading_fixes(self):
        instances = [({"n": n, "reviews": [{"stars": 3, "text": t} for t in texts]}, {})
                     for n, texts in enumerate([["great", "bad"], ["great"], ["meh", "great"], ["bad"]], 1)]
        shape = {"name": "tiny", "description": LIST_DESCRIPTION, "output": "out"}
        gold = [{"out": i["n"] + sum("great" in r["text"] for r in i["reviews"])} for i, _ in instances]
        bench = types.SimpleNamespace(SHAPES=[shape], stream=lambda s: instances, gold=lambda s, inst: gold)
        rows = []
        runner.execute([shape], bench, {"model": "x"}, {**SETTINGS, "probe_model": "p", "probe_max_tokens": 64},
                       BatchFake([LIST_PROGRAM]), "k", 1, rows.append, only=("R", "B"), probes=4, fixes=True)
        jobs = [r for r in rows if r["record_type"] == "job"]
        b = sorted((r for r in jobs if r["arm"] == "B"), key=lambda r: r["index"])
        self.assertTrue(all(r["correct"] for r in jobs))
        self.assertEqual([r["route"] for r in b], ["race", "race", "program", "program"])
        self.assertTrue(all(r["uncertain"] is False for r in b))
        import analyze_write_once_v1 as analysis
        summary = next(r for r in rows if r["record_type"] == "shape")
        result = analysis.analyse({"header": [{"label": "t"}], "footer": [{"status": "COMPLETED"}],
                                   "job": jobs, "shape": [summary]}, replicates=50, primary_arm="B")
        self.assertEqual(result["uncertainty"]["B"]["unflagged"], {"jobs": 4, "correct": 4})
