import json
import re
import tempfile
import time
import types
import unittest

import analyze_fast_path_timing_v1 as analysis
import fast_path_timing_bench_v1 as bench
from remote import RemoteResult
import run_fast_path_timing_v1 as runner
import sandbox


SETTINGS = {
    "race_models": ["m1", "m2"],
    "synthesis_model": "writer",
    "answer_max_tokens": 64,
    "synthesis_max_tokens": 256,
    "agreement_quorum": 2,
    "min_gate_examples": 2,
    "max_synthesis_attempts": 1,
    "sandbox_timeout_seconds": 2.0,
    "audit_sample_rate": 0.0,
    "audit_salt": "t",
}
DOUBLE = {
    "name": "double",
    "spec": "Return the input integer doubled.",
    "signature": "def solve(n: int) -> int:",
    "reference": "def solve(n):\n    return n * 2\n",
    "tests": [[[1], 2], [[3], 6]],
}


def prompt_args(prompt):
    return [json.loads(v) for v in re.findall(r"^Argument \d+ \(JSON\): (.*)$", prompt, re.M)]


def fake_remote(delay=0.0, fail=False):
    def call(prompt, config, api_key):
        if prompt.startswith("Write a Python function"):
            return RemoteResult(True, text=DOUBLE["reference"], model=config["model"])
        if fail:
            return RemoteResult(False, error="OPENROUTER_HTTP_500", model=config["model"])
        time.sleep(delay)
        value = prompt_args(prompt)[0] * 2
        return RemoteResult(True, text=f"ANSWER: {value}", model=config["model"], total_ms=1.0)
    return call


def tiny_bench(shapes=1):
    items = [{**DOUBLE, "name": f"double{i}", "spec": DOUBLE["spec"] + f" Variant {i}."}
             for i in range(shapes)]
    return types.SimpleNamespace(
        SHAPES=items,
        STREAM_SEED=1,
        STREAM_LENGTH=6,
        stream=lambda shape: [[n] for n in range(10, 16)],
        gold=lambda shape, inputs: [args[0] * 2 for args in inputs],
    )


class BenchTests(unittest.TestCase):
    def test_bench_self_verifies(self):
        bench.self_verify()
        self.assertEqual(len(bench.SHAPES), 30)

    def test_streams_are_distinct_and_seeded(self):
        shape = bench.SHAPES[0]
        inputs = bench.stream(shape)
        self.assertEqual(len({sandbox.canonical(a) for a in inputs}), bench.STREAM_LENGTH)
        self.assertNotEqual(inputs, bench.stream(shape, seed=1))


class RunnerTests(unittest.TestCase):
    def run_all(self, bench_module, remote_fn, arrival="drained"):
        rows = []
        status = runner.execute(
            bench_module.SHAPES, bench_module, {"model": "x"}, dict(SETTINGS),
            remote_fn, "k", 2, rows.append, arrival,
        )
        return status, rows

    def test_immediate_arrival_does_not_wait_for_learning(self):
        # One racer is slow, so agreement and synthesis lag behind the answers.
        def remote_fn(prompt, config, api_key):
            if config["model"] == "m2" and not prompt.startswith("Write"):
                time.sleep(0.25)
            return fake_remote()(prompt, config, api_key)

        _, drained = self.run_all(tiny_bench(), remote_fn)
        _, immediate = self.run_all(tiny_bench(), remote_fn, arrival="immediate")

        def code_count(rows):
            return sum(r.get("arm") == "C" and r.get("route") == "code" for r in rows)

        self.assertEqual(code_count(drained), 4)
        self.assertLess(code_count(immediate), 4)
        requests = [r for r in immediate if r["record_type"] == "request"]
        self.assertTrue(all(r["correct"] for r in requests))
        self.assertTrue(all(r["background_ms"] == 0.0 for r in requests))
        later = [r["gap_ms"] for r in requests if r["arm"] == "C" and r["index"] > 0]
        self.assertTrue(all(g is not None and g < 250 for g in later))
        # Learning still completes once the shape is closed.
        summary = next(r for r in immediate if r["record_type"] == "shape")
        self.assertTrue(summary["function_present_at_end"])

    def test_three_arms_per_request_and_promotion(self):
        status, rows = self.run_all(tiny_bench(), fake_remote(delay=0.05))
        self.assertEqual(status, "COMPLETED")
        requests = [r for r in rows if r["record_type"] == "request"]
        self.assertEqual(len(requests), 18)
        self.assertTrue(all(r["correct"] for r in requests))
        for index in range(6):
            arms = [r for r in requests if r["index"] == index]
            self.assertEqual(sorted(r["arm"] for r in arms), ["A", "B", "C"])
            self.assertEqual(sorted(r["position"] for r in arms), [0, 1, 2])
        # Arm B never synthesises; arm C is promoted after two agreed examples.
        self.assertEqual({r["route"] for r in requests if r["arm"] == "B"}, {"model"})
        c_routes = [r["route"] for r in requests if r["arm"] == "C"]
        self.assertEqual(c_routes, ["model", "model", "code", "code", "code", "code"])
        summary = next(r for r in rows if r["record_type"] == "shape")
        self.assertEqual(summary["promoted_at_index"], 1)
        self.assertIs(summary["function_gold_correct"], True)
        self.assertEqual((summary["examples"], summary["wrong_examples"]), (2, 0))
        code = [r["answer_ms"] for r in requests if r["arm"] == "C" and r["route"] == "code"]
        direct = [r["answer_ms"] for r in requests if r["arm"] == "A"]
        self.assertLess(max(code), min(direct) + 50)

    def test_arm_order_is_reproducible(self):
        orders = []
        for _ in range(2):
            _, rows = self.run_all(tiny_bench(), fake_remote())
            orders.append([(r["index"], r["arm"], r["position"]) for r in rows
                           if r["record_type"] == "request"])
        self.assertEqual(orders[0], orders[1])

    def test_early_stop_on_provider_failures(self):
        status, rows = self.run_all(tiny_bench(shapes=4), fake_remote(fail=True))
        self.assertEqual(status, "EARLY_STOP")
        self.assertEqual(rows[-1]["record_type"], "early_stop")
        self.assertEqual(len({r["shape"] for r in rows if r["record_type"] == "request"}), 3)

    def test_override_parsing(self):
        self.assertEqual(runner.parse_override("min_gate_examples=4"), ("min_gate_examples", 4))
        self.assertEqual(runner.parse_override('synthesis_model="a/b"'), ("synthesis_model", "a/b"))
        with self.assertRaises(ValueError):
            runner.parse_override("novalue")


def request_row(shape, index, arm, ms, correct=True, route="model"):
    return {"record_type": "request", "shape": shape, "index": index, "arm": arm,
            "answer_ms": ms, "background_ms": 5.0, "route": route,
            "answered": True, "correct": correct}


def synthetic(c_ms, c_correct=True, shapes=6, status="COMPLETED"):
    kinds = {"header": [{"label": "t", "override": None}], "request": [], "shape": [],
             "footer": [{"status": status}]}
    for s in range(shapes):
        for i in range(4):
            kinds["request"].append(request_row(f"s{s}", i, "A", 1000.0))
            kinds["request"].append(request_row(f"s{s}", i, "B", 700.0))
            kinds["request"].append(
                request_row(f"s{s}", i, "C", c_ms, c_correct or i > 0, "code")
            )
        kinds["shape"].append({"shape": f"s{s}", "promoted_at_index": 1,
                               "function_gold_correct": True, "demotions": [],
                               "wrong_examples": 0})
    return kinds


class AnalysisTests(unittest.TestCase):
    def test_supported_when_both_criteria_hold(self):
        result = analysis.analyse(synthetic(20.0), replicates=200)
        self.assertEqual(result["decision"], "SUPPORTED")
        self.assertEqual(result["scope"], "DESCRIPTIVE_SENSITIVITY")
        self.assertEqual(result["median_first_code_index"], 0)
        self.assertAlmostEqual(result["time_ratio_c_over_a"], 0.02)
        self.assertEqual(result["correctness_c_minus_a"], 0.0)
        self.assertEqual(result["arms"]["B"]["median_ms"], 700.0)
        self.assertEqual(result["shapes_promoted"], 6)

    def test_not_supported_when_too_slow(self):
        result = analysis.analyse(synthetic(800.0), replicates=200)
        self.assertEqual((result["time_criterion_met"], result["decision"]),
                         (False, "NOT_SUPPORTED"))

    def test_not_supported_when_less_correct(self):
        result = analysis.analyse(synthetic(20.0, c_correct=False), replicates=200)
        self.assertEqual(result["correctness_c_minus_a"], -0.25)
        self.assertEqual((result["correctness_criterion_met"], result["decision"]),
                         (False, "NOT_SUPPORTED"))
        self.assertEqual(result["code_served_wrong"], 6)

    def test_incomplete_run_is_not_analysed(self):
        result = analysis.analyse(synthetic(20.0, status="EARLY_STOP"), replicates=10)
        self.assertEqual(result["decision"], "NOT_ANALYSED")
        self.assertNotIn("time_ratio_c_over_a", result)

    def test_bootstrap_is_seeded(self):
        grouped = analysis.by_shape(synthetic(20.0)["request"])
        self.assertEqual(analysis.bootstrap(grouped, 50), analysis.bootstrap(grouped, 50))

    def test_percentile(self):
        self.assertEqual(analysis.percentile([1, 2, 3, 4, 5], 0.5), 3)
        self.assertEqual(analysis.percentile([10, 20], 0.9), 19.0)


if __name__ == "__main__":
    unittest.main()
