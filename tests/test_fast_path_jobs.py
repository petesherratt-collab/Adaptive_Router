import json
import re
import types
import unittest

import analyze_fast_path_jobs_v1 as analysis
import fast_path_jobs_bench_v1 as bench
import pipeline
from remote import RemoteResult
import run_fast_path_jobs_v1 as runner
from run_fast_path_timing_v1 import BASELINE_MODEL, ProviderMonitor


SETTINGS = {
    "race_models": ["m1", "m2"], "synthesis_model": "writer", "answer_max_tokens": 64,
    "synthesis_max_tokens": 256, "agreement_quorum": 2, "min_gate_examples": 2,
    "max_synthesis_attempts": 1, "sandbox_timeout_seconds": 2.0,
    "audit_sample_rate": 0.0, "audit_salt": "t",
}
MOOD = "Classify the mood as 'up' or 'down'."
DOUBLE = "Return the input integer doubled."
SHAPE = {
    "name": "tiny",
    "steps": [
        {"id": "mood", "kind": "judgement", "spec": MOOD, "signature": "def solve(text: str) -> str:",
         "args": [{"ref": "text"}]},
        {"id": "twice", "kind": "function", "spec": DOUBLE, "signature": "def solve(n: int) -> int:",
         "reference": "def solve(n):\n    return n * 2\n", "tests": [[[1], 2], [[3], 6]],
         "args": [{"ref": "n"}]},
    ],
    "output": "twice",
}


def prompt_args(prompt):
    return [json.loads(v) for v in re.findall(r"^Argument \d+ \(JSON\): (.*)$", prompt, re.M)]


def fake_remote(whole_job_wrong_for=()):
    def call(prompt, config, api_key):
        model = config["model"]
        if prompt.startswith("Write a Python function"):
            return RemoteResult(True, text=SHAPE["steps"][1]["reference"], model=model)
        if prompt.startswith("Carry out the procedure"):
            n = json.loads(re.search(r"^- n \(JSON\): (.*)$", prompt, re.M).group(1))
            value = 0 if model in whole_job_wrong_for else n * 2
            return RemoteResult(True, text=f"ANSWER: {value}", model=model, total_ms=1.0)
        value = "up" if "mood" in prompt else prompt_args(prompt)[0] * 2
        return RemoteResult(True, text=f"ANSWER: {json.dumps(value)}", model=model, total_ms=1.0)
    return call


def tiny_bench(jobs=5):
    instances = [({"n": n, "text": f"t{n}"}, {"mood": "up"}) for n in range(10, 10 + jobs)]
    return types.SimpleNamespace(
        SHAPES=[SHAPE], STREAM_SEED=1, STREAM_LENGTH=jobs,
        stream=lambda shape: instances,
        gold=lambda shape, inst: [{**i, "mood": "up", "twice": i["n"] * 2} for i, _ in inst],
    )


class BenchTests(unittest.TestCase):
    def test_bench_self_verifies(self):
        bench.self_verify()
        self.assertEqual((len(bench.SHAPES), bench.STREAM_LENGTH), (12, 20))

    def test_gold_walks_the_plan(self):
        shape = next(s for s in bench.SHAPES if s["name"] == "dial_code")
        instances = [({"note": "Our office in Porto needs the delivery.", "local": "91234567"},
                      {"city": "Porto", "country": "Portugal"})]
        gold = bench.gold(shape, instances)[0]
        self.assertEqual((gold["dial"], gold["phone"]), ("+351", "+351 912 345 67"))

    def test_whole_job_prompt_names_every_step_and_no_reference(self):
        shape = next(s for s in bench.SHAPES if s["name"] == "ticket_sla")
        inputs, labels = bench.stream(shape)[0]
        prompt = pipeline.build_job_prompt(bench.job_document(shape, inputs))
        for step in shape["steps"]:
            self.assertIn(f"Step '{step['id']}'", prompt)
        self.assertIn("the result of step 'tone'", prompt)
        self.assertIn("The final result is the result of step 'line'", prompt)
        # No reference implementation text reaches the prompt.
        self.assertNotIn("    return", prompt)
        self.assertNotIn("import re", prompt)


class RunnerTests(unittest.TestCase):
    def run_all(self, remote_fn, monitor=None):
        rows = []
        status = runner.execute(tiny_bench().SHAPES, tiny_bench(), {"model": "x"},
                                dict(SETTINGS), remote_fn, "k", 1, rows.append, monitor)
        return status, rows

    def test_four_arms_per_job_and_learning_only_in_arm_c(self):
        status, rows = self.run_all(fake_remote())
        self.assertEqual(status, "COMPLETED")
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertEqual(len(jobs), 20)
        self.assertTrue(all(r["correct"] for r in jobs))
        for index in range(5):
            self.assertEqual(sorted(r["arm"] for r in jobs if r["index"] == index),
                             ["A", "B", "C", "R"])
        b_routes = {s["route"] for r in jobs if r["arm"] == "B" for s in r["steps"]}
        self.assertEqual(b_routes, {"model"})
        c_function = [s["route"] for r in sorted(jobs, key=lambda r: r["index"])
                      if r["arm"] == "C" for s in r["steps"] if s["kind"] == "function"]
        self.assertEqual(c_function, ["model", "model", "code", "code", "code"])
        c_judgement = {s["route"] for r in jobs if r["arm"] == "C"
                       for s in r["steps"] if s["kind"] == "judgement"}
        self.assertEqual(c_judgement, {"model"})
        summary = next(r for r in rows if r["record_type"] == "shape")
        step = summary["function_steps"][0]
        self.assertEqual((step["promoted"], step["function_gold_correct"], step["wrong_examples"]),
                         (True, True, 0))
        self.assertEqual(summary["judgement_shapes_stored"], 0)
        self.assertIsNone(next(r for r in jobs if r["arm"] == "A")["steps"])

    def test_wrong_whole_job_answers_are_scored(self):
        _, rows = self.run_all(fake_remote(whole_job_wrong_for=(BASELINE_MODEL,)))
        jobs = [r for r in rows if r["record_type"] == "job"]
        self.assertEqual(sum(r["correct"] for r in jobs if r["arm"] == "A"), 0)
        self.assertEqual(sum(r["correct"] for r in jobs if r["arm"] == "R"), 5)

    def test_account_error_stops_the_run(self):
        monitor = ProviderMonitor(
            lambda p, c, k: RemoteResult(False, error="OPENROUTER_HTTP_402", model=c["model"])
        )
        status, rows = self.run_all(monitor, monitor)
        self.assertEqual(status, "PROVIDER_FAILURE_STOP")
        self.assertLess(next(r for r in rows if r["record_type"] == "shape")["jobs_completed"], 5)


def job_row(shape, index, arm, ms, correct=True, steps=None):
    return {"record_type": "job", "shape": shape, "index": index, "arm": arm, "answer_ms": ms,
            "background_ms": 0.0, "answered": True, "correct": correct, "steps": steps}


def synthetic(c_ms, c_correct=True, status="COMPLETED"):
    kinds = {"header": [{"label": "primary", "override": None}], "job": [], "shape": [],
             "footer": [{"status": status}]}
    for s in range(6):
        for i in range(4):
            ok = c_correct or i > 0
            steps = [
                {"id": "j", "kind": "judgement", "route": "model", "ms": 800.0,
                 "started_ms": 0.0, "correct": ok},
                {"id": "f", "kind": "function", "route": "code", "ms": 30.0,
                 "started_ms": 800.0, "correct": ok},
            ]
            kinds["job"] += [job_row(f"s{s}", i, "A", 2000.0), job_row(f"s{s}", i, "R", 1500.0),
                             job_row(f"s{s}", i, "B", 1700.0, steps=steps),
                             job_row(f"s{s}", i, "C", c_ms, ok, steps)]
        kinds["shape"].append({"shape": f"s{s}", "judgement_shapes_stored": 0, "function_steps": [
            {"id": "f", "promoted": True, "function_gold_correct": True, "demotions": [],
             "wrong_examples": 0}]})
    return kinds


class AnalysisTests(unittest.TestCase):
    def test_supported(self):
        result = analysis.analyse(synthetic(900.0), replicates=200)
        self.assertEqual((result["scope"], result["decision"]), ("PROSPECTIVE", "SUPPORTED"))
        self.assertAlmostEqual(result["primary_c_vs_a"]["time_ratio"], 0.45)
        self.assertAlmostEqual(result["secondary"]["c_vs_r"]["time_ratio"], 0.6)
        self.assertAlmostEqual(result["secondary"]["r_vs_a"]["time_ratio"], 0.75)
        self.assertEqual(result["steps_arm_c"]["function:code"]["steps"], 24)
        self.assertEqual(result["function_steps_promoted"], 6)
        self.assertEqual(result["jobs_fully_on_code_for_functions"], 24)

    def test_not_supported_when_slower_than_the_limit(self):
        result = analysis.analyse(synthetic(1600.0), replicates=200)
        self.assertEqual((result["time_criterion_met"], result["decision"]), (False, "NOT_SUPPORTED"))

    def test_errors_are_attributed_to_the_earliest_wrong_step(self):
        result = analysis.analyse(synthetic(900.0, c_correct=False), replicates=200)
        self.assertEqual(result["decision"], "NOT_SUPPORTED")
        self.assertEqual(result["first_error_arm_c"], {"judgement:model": 6})
        self.assertEqual(result["steps_arm_c"]["judgement:model"]["wrong"], 6)

    def test_incomplete_run_is_not_analysed(self):
        result = analysis.analyse(synthetic(900.0, status="PROVIDER_FAILURE_STOP"), replicates=10)
        self.assertEqual(result["decision"], "NOT_ANALYSED")


if __name__ == "__main__":
    unittest.main()
