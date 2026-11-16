import json
import re
from pathlib import Path
import tempfile
import time
import unittest

import fast_path
from fast_path import FastPathRequest, FastPathRequestError, FastPathRouter
from remote import RemoteResult


def prompt_args(prompt):
    return [json.loads(v) for v in re.findall(r"^Argument \d+ \(JSON\): (.*)$", prompt, re.M)]


SPEC = "Return the input integer doubled."
SIGNATURE = "def solve(n: int) -> int:"
GOOD = "def solve(n):\n    return n * 2\n"
# Agrees with GOOD on 0 and 2 only.
BAD = "def solve(n):\n    return n * n\n"


def request(args, examples=None):
    document = {
        "schema_version": "fast_path_request_v1",
        "task": {"spec": SPEC, "signature": SIGNATURE},
        "args": args,
    }
    if examples is not None:
        document["examples"] = examples
    return document


def examples(*numbers):
    return [{"args": [n], "expected": n * 2} for n in numbers]


class FakeRemote:
    """Answers by model name; the synthesis prompt gets queued sources."""

    def __init__(self, answers, sources=(), delays=None):
        self.answers, self.sources = answers, list(sources)
        self.delays = delays or {}
        self.calls = []
        self.probe_reply = None

    def __call__(self, prompt, config, api_key):
        model = config["model"]
        self.calls.append((model, prompt))
        if prompt.startswith("List boundary"):
            reply = self.probe_reply
            if reply is None:
                return RemoteResult(False, error="OPENROUTER_TIMEOUT", model=model)
            return RemoteResult(True, text=reply, model=model, total_ms=1.0)
        if prompt.startswith("Write a Python function"):
            if not self.sources:
                return RemoteResult(False, error="OPENROUTER_TIMEOUT", model=model)
            return RemoteResult(True, text=self.sources.pop(0), model=model, total_ms=1.0)
        time.sleep(self.delays.get(model, 0))
        answer = self.answers[model]
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            return RemoteResult(False, error="OPENROUTER_HTTP_500", model=model)
        if callable(answer):
            answer = answer(prompt_args(prompt))
        return RemoteResult(
            True, text=answer, model=model, total_ms=self.delays.get(model, 0) * 1000
        )

    def answer_calls(self):
        return [c for c in self.calls if not c[1].startswith("Write a Python function")]


def double(args):
    return json.dumps(args[0] * 2)


class FastPathTestCase(unittest.TestCase):
    def build(self, remote, models=("a", "b"), **overrides):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings = {
            "race_models": list(models),
            "synthesis_model": "writer",
            "answer_max_tokens": 128,
            "synthesis_max_tokens": 512,
            "agreement_quorum": 2,
            "min_gate_examples": 3,
            "max_synthesis_attempts": 2,
            "sandbox_timeout_seconds": 2.0,
            "audit_sample_rate": 0.0,
            "audit_salt": "t",
            **overrides,
        }
        root = Path(self.tmp.name)
        self.log = root / "runs.jsonl"
        return FastPathRouter(
            {"remote": {"model": "unused", "max_tokens": 64}, "fast_path": settings},
            root / "store",
            self.log,
            remote_fn=remote,
            api_key="k",
        )

    def records(self, kind):
        lines = self.log.read_text(encoding="utf-8").splitlines()
        return [r for r in map(json.loads, lines) if r["record_type"] == kind]


class RequestTests(unittest.TestCase):
    def test_valid_request_has_stable_shape(self):
        one = FastPathRequest.from_mapping(request([1]))
        two = FastPathRequest.from_mapping(request([2], examples(1)))
        self.assertEqual(one.shape, two.shape)
        self.assertEqual(len(one.shape), 64)

    def test_malformed_requests_are_rejected(self):
        bad = [
            [],
            {**request([1]), "extra": 1},
            {**request([1]), "schema_version": "x"},
            {**request([1]), "task": {"spec": SPEC}},
            {**request([1]), "task": {"spec": " ", "signature": SIGNATURE}},
            {**request([1]), "task": {"spec": SPEC, "signature": "def other(n):"}},
            {**request([1]), "task": {"spec": SPEC, "signature": "def solve(n:"}},
            request("not a list"),
            request([1], [{"args": [1]}]),
            request([1], [{"args": 1, "expected": 2}]),
        ]
        for document in bad:
            with self.subTest(document=document):
                with self.assertRaises(FastPathRequestError):
                    FastPathRequest.from_mapping(document)

    def test_parse_answer(self):
        self.assertEqual(fast_path.parse_answer(' "a3" \n'), (True, "a3"))
        self.assertEqual(fast_path.parse_answer("```json\n[1, 2]\n```"), (True, [1, 2]))
        self.assertEqual(fast_path.parse_answer("null"), (True, None))
        self.assertEqual(fast_path.parse_answer("ANSWER: [1, 2]"), (True, [1, 2]))
        self.assertEqual(
            fast_path.parse_answer('16 -> 1+6=7\n\nANSWER: {"value": 1}\nANSWER: 7\n'),
            (True, 7),
        )
        # A marked line that is not JSON is unusable even if other text parses.
        self.assertEqual(fast_path.parse_answer("7\nANSWER: seven"), (False, None))
        # Prose followed by a bare value is not mined for an answer.
        self.assertEqual(fast_path.parse_answer("9+9=18, 1+8=9\n\n9"), (False, None))
        for text in ("The answer is 4", "NaN", '{"a": 1, "a": 2}', ""):
            with self.subTest(text=text):
                self.assertEqual(fast_path.parse_answer(text), (False, None))


class ExampleTests(unittest.TestCase):
    def record(self):
        return {"examples": [], "example_conflicts": 0}

    def test_duplicate_and_conflict_rules(self):
        record = self.record()
        self.assertEqual(fast_path.add_example(record, [1], 2, "model_agreement"), "added")
        self.assertEqual(fast_path.add_example(record, [1], 2, "model_agreement"), "duplicate")
        # Two model-agreement answers that contradict each other cancel out.
        self.assertEqual(fast_path.add_example(record, [1], 3, "model_agreement"), "conflict")
        self.assertEqual(record["examples"], [])
        # A caller example replaces a contradicting model-agreement example...
        fast_path.add_example(record, [1], 3, "model_agreement")
        self.assertEqual(fast_path.add_example(record, [1], 2, "caller"), "conflict")
        self.assertEqual(record["examples"][0]["expected"], 2)
        # ...and is never displaced by one.
        self.assertEqual(fast_path.add_example(record, [1], 9, "model_agreement"), "conflict")
        self.assertEqual(record["examples"][0], {"args": [1], "expected": 2, "source": "caller"})
        self.assertEqual(record["example_conflicts"], 3)

    def test_type_strict_arguments(self):
        record = self.record()
        fast_path.add_example(record, [1], 2, "caller")
        self.assertEqual(fast_path.add_example(record, [True], 2, "caller"), "added")


class GateTests(unittest.TestCase):
    def test_gate_outcomes(self):
        ex = examples(1, 2, 3)
        self.assertEqual(fast_path.gate(GOOD, ex, 3)[0], True)
        passed, detail = fast_path.gate(BAD, ex, 3)
        self.assertEqual((passed, detail["reason"], detail["passed"]), (False, "EXAMPLE_MISMATCH", 1))
        self.assertEqual(fast_path.gate(GOOD, ex, 4)[1]["reason"], "TOO_FEW_EXAMPLES")
        self.assertEqual(
            fast_path.gate("import os\n" + GOOD, ex, 3)[1],
            {"reason": "STATIC_REJECTED", "static": "MODULE_NOT_ALLOWED"},
        )
        self.assertEqual(
            fast_path.gate("def solve(n):\n    while True:\n        pass\n", ex, 3, 0.5)[0],
            False,
        )

    def test_gate_is_type_strict(self):
        source = "def solve(n):\n    return float(n * 2)\n"
        self.assertFalse(fast_path.gate(source, examples(1, 2, 3), 3)[0])


class RaceTests(FastPathTestCase):
    def test_first_valid_answer_wins_without_waiting_for_slow_model(self):
        remote = FakeRemote({"a": double, "b": double}, delays={"a": 0.6, "b": 0.0})
        router = self.build(remote)
        result = router.handle(request([5]))
        self.assertEqual((result["value"], result["route"], result["model"]), (10, "model", "b"))
        self.assertLess(result["total_ms"], 400)
        router.drain()

    def test_unparseable_and_failed_racers_are_skipped(self):
        remote = FakeRemote(
            {"a": "The answer is 10", "b": None, "c": RuntimeError("x"), "d": double},
            delays={"d": 0.1},
        )
        router = self.build(remote, models=("a", "b", "c", "d"))
        result = router.handle(request([5]))
        self.assertEqual((result["value"], result["model"]), (10, "d"))
        router.drain()

    def test_no_valid_answer(self):
        router = self.build(FakeRemote({"a": None, "b": "nope"}))
        result = router.handle(request([5]))
        self.assertEqual(
            (result["route"], result["reason"], result["text"]),
            ("none", "RACE_NO_VALID_ANSWER", ""),
        )
        router.drain()

    def test_telemetry_carries_no_arguments_or_answers(self):
        router = self.build(FakeRemote({"a": '"secret-answer"', "b": '"secret-answer"'}))
        router.handle(request(["secret-argument"]))
        router.drain()
        text = self.log.read_text(encoding="utf-8")
        self.assertNotIn("secret", text)
        self.assertNotIn(SPEC, text)


class LearningTests(FastPathTestCase):
    def shape(self, router):
        return router.store.shapes()[0]

    def test_agreement_becomes_an_example_and_disagreement_does_not(self):
        router = self.build(FakeRemote({"a": double, "b": double}))
        router.handle(request([1]))
        router.drain()
        self.assertEqual(
            self.shape(router)["examples"],
            [{"args": [1], "expected": 2, "source": "model_agreement"}],
        )

        router = self.build(FakeRemote({"a": double, "b": "7"}))
        router.handle(request([1]))
        router.drain()
        self.assertEqual(self.shape(router)["examples"], [])
        self.assertEqual(self.shape(router)["disagreements"], 1)

    def test_single_valid_answer_is_below_quorum(self):
        router = self.build(FakeRemote({"a": double, "b": None}))
        router.handle(request([1]))
        router.drain()
        self.assertEqual(self.shape(router)["examples"], [])
        self.assertEqual(self.shape(router)["disagreements"], 0)

    def test_promotion_then_code_route_makes_no_model_call(self):
        remote = FakeRemote({"a": double, "b": double}, sources=["```python\n" + GOOD + "```"])
        router = self.build(remote)
        first = router.handle(request([10], examples(1, 2, 3)))
        self.assertEqual(first["route"], "model")
        router.drain()
        function = self.shape(router)["function"]
        self.assertEqual(function["source"], GOOD)
        self.assertEqual(function["gate"]["reason"], "PASS")

        before = len(remote.calls)
        second = router.handle(request([21]))
        router.drain()
        self.assertEqual((second["value"], second["route"]), (42, "code"))
        self.assertEqual(second["reason"], "CODE_FAST_PATH")
        self.assertEqual(len(remote.calls), before)

    def test_synthesiser_never_sees_examples(self):
        remote = FakeRemote({"a": double, "b": double}, sources=[GOOD])
        router = self.build(remote)
        router.handle(request([10], examples(111, 222, 333)))
        router.drain()
        prompt = next(p for _, p in remote.calls if p.startswith("Write a Python function"))
        for token in ("111", "222", "333", "444", "666"):
            self.assertNotIn(token, prompt)

    def test_answer_prompt_lists_each_argument(self):
        prompt = fast_path.build_answer_prompt(SPEC, SIGNATURE, [[1, 2], "x"])
        self.assertIn("Argument 1 (JSON): [1, 2]\nArgument 2 (JSON): \"x\"", prompt)
        self.assertIn("no arguments", fast_path.build_answer_prompt(SPEC, SIGNATURE, []))

    def test_wrong_function_is_rejected_and_attempts_are_bounded(self):
        remote = FakeRemote({"a": double, "b": double}, sources=[BAD, BAD, GOOD])
        router = self.build(remote)
        for n in (10, 11, 12, 13):
            router.handle(request([n], examples(1, 2, 3)))
            router.drain()
        shape = self.shape(router)
        self.assertIsNone(shape["function"])
        self.assertEqual(
            [a["outcome"] for a in shape["synthesis_attempts"]], ["REJECTED", "REJECTED"]
        )
        self.assertEqual(len(remote.sources), 1)

    def test_no_synthesis_below_minimum_examples(self):
        remote = FakeRemote({"a": double, "b": "0"}, sources=[GOOD])
        router = self.build(remote)
        router.handle(request([10], examples(1, 2)))
        router.drain()
        self.assertEqual(self.shape(router)["synthesis_attempts"], [])

    def test_synthesis_remote_failure_is_recorded(self):
        router = self.build(FakeRemote({"a": double, "b": double}))
        router.handle(request([10], examples(1, 2, 3)))
        router.drain()
        self.assertEqual(self.shape(router)["synthesis_attempts"][0]["outcome"], "REMOTE_ERROR")
        # A provider failure does not use up one of the bounded attempts.
        router.remote_fn.sources.append(GOOD)
        router.handle(request([11]))
        router.drain()
        self.assertIsNotNone(self.shape(router)["function"])

    def test_runtime_failure_demotes_and_falls_back_to_models(self):
        fragile = "def solve(n):\n    return [0, 2, 4, 6][n]\n"
        remote = FakeRemote({"a": double, "b": double}, sources=[fragile])
        router = self.build(remote, max_synthesis_attempts=1)
        router.handle(request([0], examples(1, 2, 3)))
        router.drain()
        self.assertIsNotNone(self.shape(router)["function"])
        result = router.handle(request([50]))
        router.drain()
        self.assertEqual((result["value"], result["route"]), (100, "model"))
        shape = self.shape(router)
        self.assertIsNone(shape["function"])
        self.assertEqual(shape["demotions"][0]["reason"], "RUNTIME_FAILURE")

    def test_audit_disagreement_demotes_a_wrong_function(self):
        # BAD reproduces the only examples available (0 and 2), so it is promoted.
        remote = FakeRemote({"a": double, "b": double}, sources=[BAD])
        router = self.build(
            remote, min_gate_examples=2, max_synthesis_attempts=1, audit_sample_rate=1.0
        )
        router.handle(request([0], examples(0, 2)))
        router.drain()
        self.assertIsNotNone(self.shape(router)["function"])

        served = router.handle(request([5]))
        self.assertEqual((served["value"], served["route"]), (25, "code"))
        router.drain()
        shape = self.shape(router)
        self.assertIsNone(shape["function"])
        self.assertEqual(shape["demotions"][0]["reason"], "EXAMPLE_MISMATCH")
        self.assertTrue(self.records("fast_path_request")[-1]["decision"]["audited"])

    def probing_router(self, remote, **overrides):
        settings = {
            "min_gate_examples": 2, "max_synthesis_attempts": 1,
            "probe_enabled": True, "probe_model": "prober", "max_probes": 4,
            "probe_max_tokens": 128, **overrides,
        }
        return self.build(remote, **settings)

    def test_probes_block_a_function_that_fits_the_arrived_examples(self):
        # BAD reproduces the arrived examples (0 and 2) but not the probes.
        remote = FakeRemote({"a": double, "b": double}, sources=[BAD])
        remote.probe_reply = "```json\n[[3], [5], [3], [1, 2], \"x\", [7], [9], [11]]\n```"
        router = self.probing_router(remote)
        router.handle(request([0], examples(0, 2)))
        router.drain()
        shape = self.shape(router)
        self.assertIsNone(shape["function"])
        self.assertEqual(shape["synthesis_attempts"][0]["outcome"], "REJECTED")
        # Duplicates and wrong-arity entries are dropped; the cap is four.
        self.assertEqual(
            shape["probes"],
            {"model": "prober", "error": None, "proposed": 4, "agreed": 4,
             "disagreed": 0, "added": 4, "conflicts": 0},
        )
        sources = {e["source"] for e in shape["examples"]}
        self.assertEqual(sources, {"caller", "probe_agreement"})

    def test_probes_do_not_block_a_correct_function(self):
        remote = FakeRemote({"a": double, "b": double}, sources=[GOOD])
        remote.probe_reply = "[[0], [1], [-1], [1000]]"
        router = self.probing_router(remote)
        router.handle(request([10], examples(1, 2)))
        router.drain()
        self.assertEqual(self.shape(router)["function"]["gate"]["examples"], 6)

    def test_disputed_probe_is_not_stored(self):
        remote = FakeRemote(
            {"a": double, "b": lambda args: "0" if args[0] == 5 else double(args)},
            sources=[GOOD],
        )
        remote.probe_reply = "[[5], [6]]"
        router = self.probing_router(remote)
        router.handle(request([10], examples(1, 2)))
        router.drain()
        shape = self.shape(router)
        self.assertEqual((shape["probes"]["agreed"], shape["probes"]["disagreed"]), (1, 1))
        self.assertNotIn([5], [e["args"] for e in shape["examples"]])
        self.assertIsNotNone(shape["function"])

    def test_probe_failure_does_not_stop_synthesis_and_is_not_repeated(self):
        for reply, error, calls in (
            (None, "OPENROUTER_TIMEOUT", 1),
            ("not json", "PROBE_REPLY_INVALID", 2),
        ):
            with self.subTest(error=error):
                remote = FakeRemote({"a": double, "b": double}, sources=[BAD, GOOD])
                remote.probe_reply = reply
                router = self.probing_router(remote, max_synthesis_attempts=2)
                router.handle(request([10], examples(1, 3)))
                router.drain()
                router.handle(request([11]))
                router.drain()
                shape = self.shape(router)
                self.assertEqual(shape["probes"]["error"], error)
                self.assertIsNotNone(shape["function"])
                probes = [c for c in remote.calls if c[1].startswith("List boundary")]
                self.assertEqual(len(probes), calls)

    def test_probe_proposer_sees_no_examples(self):
        remote = FakeRemote({"a": double, "b": double}, sources=[GOOD])
        remote.probe_reply = "[[0]]"
        router = self.probing_router(remote)
        router.handle(request([10], examples(111, 222)))
        router.drain()
        prompt = next(p for _, p in remote.calls if p.startswith("List boundary"))
        for token in ("111", "222", "444"):
            self.assertNotIn(token, prompt)

    def test_store_survives_restart(self):
        remote = FakeRemote({"a": double, "b": double}, sources=[GOOD])
        router = self.build(remote)
        router.handle(request([10], examples(1, 2, 3)))
        router.drain()
        reopened = FastPathRouter(
            {"remote": {"model": "unused"}, "fast_path": router.settings},
            router.store.directory,
            self.log,
            remote_fn=FakeRemote({}),
            api_key="k",
        )
        self.assertEqual(reopened.handle(request([4]))["route"], "code")
        self.assertIn("code ", fast_path.render_status(reopened.store))


if __name__ == "__main__":
    unittest.main()
