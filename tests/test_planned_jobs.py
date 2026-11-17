import types
import unittest

import analyze_fast_path_planned_v1 as analysis
import fast_path_planned_bench_v1 as bench
import run_fast_path_planned_v1 as runner
from tests.test_planner import DESCRIPTION, GOOD_PLAN, FakeRemote


SETTINGS = {
    "race_models": ["m1", "m2"], "synthesis_model": "writer", "answer_max_tokens": 64,
    "synthesis_max_tokens": 256, "agreement_quorum": 2, "min_gate_examples": 2,
    "max_synthesis_attempts": 1, "sandbox_timeout_seconds": 2.0, "audit_sample_rate": 0.0,
    "audit_salt": "t", "planner_model": "planner", "planner_max_tokens": 512,
    "plan_examples": 2, "max_plan_attempts": 1, "plan_audit_rate": 0.0,
}


def tiny_bench(jobs=6):
    instances = [({"n": n, "text": "a" * n}, {}) for n in range(1, jobs + 1)]
    return types.SimpleNamespace(
        SHAPES=[{"name": "tiny", "description": DESCRIPTION, "output": "out"}],
        stream=lambda shape: instances,
        gold=lambda shape, inst: [{"out": i["n"] * 3} for i, _ in inst],
    )


class BenchTests(unittest.TestCase):
    def test_descriptions_self_verify(self):
        bench.self_verify()
        self.assertEqual(len(bench.SHAPES), 7)


class RunnerTests(unittest.TestCase):
    def test_three_arms_and_plan_adoption(self):
        rows = []
        status = runner.execute(tiny_bench().SHAPES, tiny_bench(), {"model": "x"}, dict(SETTINGS),
                                FakeRemote(plans=[GOOD_PLAN]), "k", 1, rows.append)
        self.assertEqual(status, "COMPLETED")
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertEqual(len(jobs), 18)
        self.assertTrue(all(r["correct"] for r in jobs))
        c_routes = [r["route"] for r in sorted(jobs, key=lambda r: r["index"]) if r["arm"] == "C"]
        self.assertEqual(c_routes, ["race", "race", "plan", "plan", "plan", "plan"])
        later = [r for r in jobs if r["arm"] == "C" and r["index"] == 5][0]
        self.assertEqual({s["route"] for s in later["steps"]}, {"code"})
        summary = next(r for r in rows if r["record_type"] == "shape")
        self.assertTrue(summary["plan_adopted"])
        self.assertEqual((summary["examples"], summary["wrong_examples"]), (2, 0))
        self.assertEqual(sum(s["promoted"] for s in summary["plan_steps"]), 3)
        usage = summary["usage"]
        self.assertEqual(usage["A"]["calls"], 6)
        self.assertEqual(usage["R"]["calls"], 12)
        # Arm C pays for planning, trials and learning on top of its races.
        self.assertGreater(usage["C"]["calls"], usage["R"]["calls"])
        purposes = usage["C"]["by_purpose"]
        self.assertEqual(sum(p["calls"] for p in purposes.values()), usage["C"]["calls"])
        self.assertEqual(set(purposes), {"whole_task", "plan", "step_answer", "synthesis"})
        self.assertEqual(set(usage["R"]["by_purpose"]), {"whole_task"})

    def test_purpose_of_prompts(self):
        self.assertEqual(runner.purpose_of("Carry out the task below and"), "whole_task")
        self.assertEqual(runner.purpose_of("List boundary and edge-case inputs for"), "probe_proposal")
        self.assertEqual(runner.purpose_of("something else"), "other")

    def test_immediate_arrival_does_not_wait_for_background_work(self):
        rows = []
        runner.execute(tiny_bench().SHAPES, tiny_bench(), {"model": "x"}, dict(SETTINGS),
                       FakeRemote(plans=[GOOD_PLAN]), "k", 1, rows.append, None, "immediate")
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertTrue(all(r["background_ms"] == 0.0 for r in jobs))
        self.assertTrue(all(r["correct"] for r in jobs))
        self.assertTrue(next(r for r in rows if r["record_type"] == "shape")["plan_adopted"])


def job(shape, index, arm, ms, route="race", correct=True):
    return {"record_type": "job", "shape": shape, "index": index, "arm": arm, "answer_ms": ms,
            "answered": True, "correct": correct, "route": route, "steps": None}


class AnalysisTests(unittest.TestCase):
    def kinds(self, c_ms):
        kinds = {"header": [{"label": "t"}], "footer": [{"status": "COMPLETED"}], "job": [],
                 "shape": [{"shape": f"s{s}", "plan_adopted": True, "plan_attempts": [{"outcome": "ADOPTED"}],
                            "plan_steps": [{"kind": "function", "promoted": True}], "plan_demotions": [],
                            "wrong_examples": 0} for s in range(5)]}
        for s in range(5):
            for i in range(4):
                kinds["job"] += [job(f"s{s}", i, "A", 3000.0), job(f"s{s}", i, "R", 2000.0),
                                 job(f"s{s}", i, "C", c_ms if i >= 2 else 2000.0,
                                     "plan" if i >= 2 else "race")]
        return kinds

    def test_supported_against_the_race(self):
        result = analysis.analyse(self.kinds(800.0), replicates=200)
        self.assertEqual(result["decision"], "SUPPORTED")
        self.assertEqual(result["first_plan_job_index"]["s0"], 2)
        self.assertEqual(result["arm_c_routes"]["plan"]["jobs"], 10)
        self.assertEqual(result["median_after_plan_ms"]["C"], 800.0)
        self.assertEqual(result["plan_attempt_outcomes"], {"ADOPTED": 5})

    def test_not_supported_when_no_faster(self):
        self.assertEqual(analysis.analyse(self.kinds(2500.0), replicates=200)["decision"], "NOT_SUPPORTED")


if __name__ == "__main__":
    unittest.main()


class FreshBenchTests(unittest.TestCase):
    def test_fresh_bench_self_verifies(self):
        import fast_path_planned_bench_v2 as fresh

        fresh.self_verify()
        self.assertEqual(len(fresh.SHAPES), 7)
        self.assertEqual(fresh.SHAPES[0]["output"], "result")


class CeilingTests(unittest.TestCase):
    def ceiling_bench(self):
        mood = {"up": 1, "down": -1}
        instances = [({"n": n, "text": "a" * n, "note": "great"}, {"mood": "up"}) for n in range(1, 6)]
        shape = {"name": "tiny", "description": DESCRIPTION + " Also read the mood of the note.",
                 "output": "out",
                 "reference": lambda inputs, labels: inputs["n"] * 3 + mood[labels["mood"]]}
        bench = types.SimpleNamespace(
            SHAPES=[shape], stream=lambda shape: instances,
            gold=lambda shape, inst: [{"out": i["n"] * 3 + 1} for i, _ in inst])
        reading = {"tiny": {"field": "note", "label": "mood", "signature": "def solve(text: str) -> str:",
                            "spec": "Classify the mood of the text as 'up' or 'down'."}}
        return bench, reading

    def remote(self, mood_answer):
        fake = FakeRemote(plans=[GOOD_PLAN], task_answer=lambda model, i: i["n"] * 3 + 1)

        def call(prompt, config, api_key):
            if "mood of the text" in prompt:
                from remote import RemoteResult
                return RemoteResult(True, text=f'ANSWER: "{mood_answer}"', model=config["model"], total_ms=1.0)
            return fake(prompt, config, api_key)
        return call

    def run(self, mood_answer):
        bench, reading = self.ceiling_bench()
        rows = []
        runner.execute(bench.SHAPES, bench, {"model": "x"}, dict(SETTINGS), self.remote(mood_answer),
                       "k", 1, rows.append, None, "drained", reading)
        return rows

    def test_ceiling_arm_races_the_reading_step_and_runs_reference_code(self):
        rows = self.run("up")
        d = [r for r in rows if r["record_type"] == "job" and r["arm"] == "D"]
        self.assertEqual(len(d), 5)
        self.assertTrue(all(r["correct"] and r["reading_correct"] for r in d))
        usage = next(r for r in rows if r["record_type"] == "shape")["usage"]
        # One race of two models per job for the reading step, nothing else.
        self.assertEqual(usage["D"]["calls"], 10)

    def test_wrong_or_unusable_reading_makes_the_job_wrong(self):
        for answer in ("down", "sideways"):
            with self.subTest(answer=answer):
                d = [r for r in self.run(answer) if r["record_type"] == "job" and r["arm"] == "D"]
                self.assertTrue(all(r["answered"] and not r["correct"] and not r["reading_correct"] for r in d))

    def test_analysis_reports_the_ceiling(self):
        rows = self.run("up")
        kinds = {"header": [{"label": "t"}], "footer": [{"status": "COMPLETED"}]}
        for row in rows:
            kinds.setdefault(row["record_type"], []).append(row)
        result = analysis.analyse(kinds, replicates=50)
        self.assertEqual((result["ceiling"]["reading_correct"], result["ceiling"]["jobs"]), (5, 5))
        self.assertIn("D", result["arms"])
        self.assertIn("C", result["ceiling"]["first_three_jobs_median_ms"])


class ShippedCeilingTests(unittest.TestCase):
    def test_reading_steps_cover_every_fresh_shape(self):
        import fast_path_ceiling_v1 as ceiling
        import fast_path_planned_bench_v2 as fresh

        self.assertEqual(set(ceiling.READING), {s["name"] for s in fresh.SHAPES})
        for shape in fresh.SHAPES:
            reading = ceiling.READING[shape["name"]]
            inputs, labels = fresh.stream(shape)[0]
            self.assertIn(reading["field"], inputs)
            self.assertIn(reading["label"], labels)
            self.assertEqual(shape["reference"](inputs, labels), fresh.gold(shape, [(inputs, labels)])[0]["result"])
