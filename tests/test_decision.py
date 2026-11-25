"""Decision rules (first / majority) and the agreed-answer cache."""
from concurrent.futures import Future
import json
import unittest

import fast_path
from tests.test_fast_path import FakeRemote, FastPathTestCase, request


def done(model, value, ms, valid=True):
    f = Future()
    f.set_result({"model": model, "success": True, "valid": valid, "value": value, "error": None, "total_ms": ms})
    return f


class DecideTests(unittest.TestCase):
    def test_majority_beats_a_fast_outlier(self):
        d = fast_path.decide([done("fast", "sell", 1), done("b", "irrelevant", 5), done("c", "irrelevant", 6),
                              done("d", "irrelevant", 7)], "majority")
        self.assertEqual(d["value"], "irrelevant")
        self.assertFalse(d["agreed"])
        self.assertTrue(d["uncertain"])
        self.assertEqual(d["votes"], {'"irrelevant"': 3, '"sell"': 1})

    def test_unanimous_majority_is_agreed(self):
        d = fast_path.decide([done("a", 4, 3), done("b", 4, 2)], "majority")
        self.assertEqual((d["value"], d["model"], d["agreed"], d["uncertain"]), (4, "b", True, False))

    def test_tie_goes_to_on_tie_or_fastest_and_is_uncertain(self):
        race = lambda: [done("a", "buy", 9), done("b", "sell", 2)]
        self.assertEqual(fast_path.decide(race(), "majority", on_tie="irrelevant")["value"], "irrelevant")
        d = fast_path.decide(race(), "majority")
        self.assertEqual((d["value"], d["uncertain"]), ("sell", True))

    def test_first_and_check_and_nothing_valid(self):
        d = fast_path.decide([done("a", "x", 1), done("b", 7, 2)], "first", check=lambda v: isinstance(v, int))
        self.assertEqual((d["ok"], d["value"], d["agreed"]), (True, 7, None))
        self.assertFalse(fast_path.decide([done("a", None, 1, valid=False)], "majority")["ok"])
        with self.assertRaises(ValueError):
            fast_path.decide([], "vote")


class AgreementTests(unittest.TestCase):
    def test_returns_on_the_second_matching_answer(self):
        d = fast_path.decide([done("a", 5, 1), done("b", 6, 2), done("c", 5, 3)], "agreement")  # only 5 can reach two
        self.assertEqual((d["value"], d["agreed"], d["uncertain"]), (5, True, False))
        self.assertIn(d["model"], ("a", "c"))  # one of the two that agreed; finished futures have no order

    def test_no_two_agree_falls_back_to_majority_flagged(self):
        d = fast_path.decide([done("a", 1, 1), done("b", 2, 2), done("c", None, 3, valid=False)], "agreement")
        self.assertTrue(d["ok"] and d["uncertain"])
        self.assertIn(d["value"], (1, 2))


class CacheTests(FastPathTestCase):
    def test_agreed_answer_is_served_without_a_race(self):
        remote = FakeRemote({"a": "ANSWER: 6", "b": "ANSWER: 6"})
        router = self.build(remote, answer_cache=True)
        first = router.handle(request([3]))
        router.drain()
        calls = len(remote.answer_calls())
        second = router.handle(request([3]))
        router.close()
        self.assertEqual(first["route"], "model")
        self.assertEqual((second["route"], second["reason"], second["value"]), ("cache", fast_path.ANSWER_CACHED, 6))
        self.assertEqual(len(remote.answer_calls()), calls)  # no new model calls

    def test_cache_is_off_by_default_and_skipped_without_learning(self):
        remote = FakeRemote({"a": "ANSWER: 6", "b": "ANSWER: 6"})
        router = self.build(remote)
        router.handle(request([3])); router.drain()
        self.assertEqual(router.handle(request([3]))["route"], "model")
        router.close()
        cached = self.build(FakeRemote({"a": "ANSWER: 6", "b": "ANSWER: 6"}), answer_cache=True)
        cached.handle(request([3])); cached.drain()
        self.assertEqual(cached.handle(request([3]), learn=False)["route"], "model")
        cached.close()

    def test_disagreed_answer_is_not_cached(self):
        remote = FakeRemote({"a": "ANSWER: 6", "b": "ANSWER: 7"})
        router = self.build(remote, answer_cache=True)
        router.handle(request([3])); router.drain()
        self.assertEqual(router.handle(request([3]))["route"], "model")
        router.close()


class RaceDecidedTests(FastPathTestCase):
    def test_race_prompt_decided_majority(self):
        remote = FakeRemote({"a": "ANSWER: 1", "b": "ANSWER: 2", "c": "ANSWER: 2"})
        router = self.build(remote, models=("a", "b", "c"))
        d = router.race_prompt_decided(fast_path.build_answer_prompt("s", "def solve(n):", [1]), "majority")
        router.close()
        self.assertEqual((d["value"], d["uncertain"]), (2, True))


if __name__ == "__main__":
    unittest.main()


SUBTLE_SOURCE = "def solve(n):\n    return n * 2 if n <= 3 else n * 2 + 1\n"  # right on 1..3, wrong after
GOOD_SOURCE = "def solve(n):\n    return n * 2\n"


class SingleStepProbationTests(FastPathTestCase):
    def run_stream(self, probation):
        from tests.test_fast_path import double
        remote = FakeRemote({"a": double, "b": double}, sources=[SUBTLE_SOURCE, GOOD_SOURCE])
        router = self.build(remote, probation_jobs=probation)
        results = []
        for n in range(1, 10):
            results.append(router.handle(request([n])))
            router.drain()
        record = router.store.get(fast_path.FastPathRequest.from_mapping(request([1])).shape)
        router.close()
        return results, record

    def test_probation_catches_a_function_wrong_after_promotion(self):
        results, record = self.run_stream(10)
        wrong = [n for n, r in enumerate(results, start=1) if r["value"] != n * 2]
        self.assertEqual(len(wrong), 1)  # served once by the planted function, then caught
        self.assertEqual(record["demotions"][0]["reason"], "EXAMPLE_MISMATCH")
        self.assertEqual(record["audits"]["mismatches"], 1)

    def test_without_probation_the_planted_function_keeps_serving(self):
        results, record = self.run_stream(0)
        wrong = [n for n, r in enumerate(results, start=1) if r["value"] != n * 2]
        self.assertGreaterEqual(len(wrong), 4)
        self.assertEqual(record["demotions"], [])
