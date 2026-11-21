import json
from pathlib import Path
import re
import tempfile
import time
import unittest

from fast_path import FastPathRouter
import planner
from planner import PlanningRouter, TaskRequest, TaskRequestError
from remote import RemoteResult


DESCRIPTION = "Double the number n, then add the number of characters in the text."
DOUBLE = "Return the input integer doubled."
LENGTH = "Return the number of characters in the text."
ADD = "Return the sum of two integers."
GOOD_PLAN = {
    "steps": [
        {"id": "twice", "kind": "function",
         "task": {"spec": DOUBLE, "signature": "def solve(n: int) -> int:"}, "args": [{"ref": "n"}]},
        {"id": "size", "kind": "function",
         "task": {"spec": LENGTH, "signature": "def solve(text: str) -> int:"}, "args": [{"ref": "text"}]},
        {"id": "total", "kind": "function",
         "task": {"spec": ADD, "signature": "def solve(a: int, b: int) -> int:"},
         "args": [{"ref": "twice"}, {"ref": "size"}]},
    ],
    "output": "total",
}
# Forgets to double: wrong on every example.
BAD_PLAN = {
    "steps": [GOOD_PLAN["steps"][1],
              {"id": "total", "kind": "function",
               "task": {"spec": ADD, "signature": "def solve(a: int, b: int) -> int:"},
               "args": [{"ref": "n"}, {"ref": "size"}]}],
    "output": "total",
}
SOURCES = {
    DOUBLE: "def solve(n):\n    return n * 2\n",
    LENGTH: "def solve(text):\n    return len(text)\n",
    ADD: "def solve(a, b):\n    return a + b\n",
}


def request(n, text):
    return {"schema_version": "fast_path_task_v1", "description": DESCRIPTION,
            "inputs": {"n": n, "text": text}}


def step_args(prompt):
    return [json.loads(v) for v in re.findall(r"^Argument \d+ \(JSON\): (.*)$", prompt, re.M)]


def job_inputs(prompt):
    return {k: json.loads(v) for k, v in re.findall(r"^- (\w+) \(JSON\): (.*)$", prompt, re.M)}


class FakeRemote:
    def __init__(self, plans=(), task_answer=None):
        self.plans = list(plans)
        self.task_answer = task_answer or (lambda model, i: i["n"] * 2 + len(i["text"]))
        self.calls = []

    def __call__(self, prompt, config, api_key):
        model = config["model"]
        self.calls.append((model, prompt))
        if prompt.startswith("Plan how to compute"):
            if not self.plans:
                return RemoteResult(False, error="OPENROUTER_TIMEOUT", model=model)
            return RemoteResult(True, text=json.dumps(self.plans.pop(0)), model=model)
        if prompt.startswith("Write a Python function"):
            spec = re.search(r"^Specification: (.*)$", prompt, re.M).group(1)
            return RemoteResult(True, text=SOURCES[spec], model=model)
        if prompt.startswith("Carry out the task"):
            value = self.task_answer(model, job_inputs(prompt))
            return RemoteResult(True, text=f"ANSWER: {json.dumps(value)}", model=model, total_ms=1.0)
        args = step_args(prompt)
        if DOUBLE in prompt:
            value = args[0] * 2
        elif LENGTH in prompt:
            value = len(args[0])
        else:
            value = args[0] + args[1]
        return RemoteResult(True, text=f"ANSWER: {json.dumps(value)}", model=model, total_ms=1.0)

    def count(self, prefix):
        return sum(p.startswith(prefix) for _, p in self.calls)


class PlannerTestCase(unittest.TestCase):
    def build(self, remote, **overrides):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        settings = {
            "race_models": ["a", "b"], "synthesis_model": "writer", "answer_max_tokens": 64,
            "synthesis_max_tokens": 256, "agreement_quorum": 2, "min_gate_examples": 2,
            "max_synthesis_attempts": 1, "sandbox_timeout_seconds": 2.0,
            "audit_sample_rate": 0.0, "audit_salt": "t",
            "planner_model": "planner", "planner_max_tokens": 512,
            "plan_examples": 2, "max_plan_attempts": 2, "plan_audit_rate": 0.0,
            **overrides,
        }
        fast = FastPathRouter({"remote": {"model": "x"}, "fast_path": settings},
                              root / "store", root / "runs.jsonl", remote_fn=remote, api_key="k")
        router = PlanningRouter(fast, root / "templates", root / "tasks.jsonl")
        # Cleanups run last-in first-out: the planning router drains first.
        self.addCleanup(fast.close)
        self.addCleanup(router.close)
        return router

    def record(self, router, n=1, text="ab"):
        return router.store.get(TaskRequest.from_mapping(request(n, text)).template)


class RequestTests(unittest.TestCase):
    def test_template_depends_on_description_names_and_types(self):
        one = TaskRequest.from_mapping(request(1, "a")).template
        self.assertEqual(one, TaskRequest.from_mapping(request(9, "zzz")).template)
        self.assertNotEqual(one, TaskRequest.from_mapping(request("1", "a")).template)
        other = {**request(1, "a"), "description": DESCRIPTION + " "}
        self.assertNotEqual(one, TaskRequest.from_mapping(other).template)

    def test_malformed_requests(self):
        for bad in ([], {**request(1, "a"), "extra": 1}, {**request(1, "a"), "schema_version": "x"},
                    {**request(1, "a"), "description": " "}, {**request(1, "a"), "inputs": {}}):
            with self.subTest(bad=str(bad)[:50]):
                with self.assertRaises(TaskRequestError):
                    TaskRequest.from_mapping(bad)

    def test_parse_plan(self):
        inputs = {"n": 1, "text": "a"}
        document, reason = planner.parse_plan("```json\n" + json.dumps(GOOD_PLAN) + "\n```", inputs)
        self.assertIsNone(reason)
        self.assertEqual(document["inputs"], inputs)
        self.assertEqual(planner.parse_plan("not json", inputs), (None, "PLAN_NOT_JSON"))
        self.assertEqual(planner.parse_plan(json.dumps({**GOOD_PLAN, "x": 1}), inputs),
                         (None, "PLAN_FIELDS_MISMATCH"))
        forward = {"steps": list(reversed(GOOD_PLAN["steps"])), "output": "total"}
        self.assertTrue(planner.parse_plan(json.dumps(forward), inputs)[1].startswith("PLAN_INVALID"))

    def test_signature_slips_are_tidied(self):
        self.assertEqual(planner.normalise_signature("  def parse_rows(csv: str) -> list "),
                         "def solve(csv: str) -> list:")
        self.assertEqual(planner.normalise_signature("def solve(a: int):"), "def solve(a: int):")
        sloppy = json.loads(json.dumps(GOOD_PLAN))
        sloppy["steps"][0]["task"]["signature"] = "def double(n: int) -> int"
        document, reason = planner.parse_plan(json.dumps(sloppy), {"n": 1, "text": "a"})
        self.assertIsNone(reason)
        self.assertEqual(document["steps"][0]["task"]["signature"], "def solve(n: int) -> int:")
        self.assertEqual(planner.normalise_signature("lambda n: n")[:6], "lambda")

    def test_plan_prompt_shows_inputs_but_no_answer(self):
        prompt = planner.build_plan_prompt(DESCRIPTION, {"n": 4, "text": "hello"})
        self.assertIn('- n (JSON): 4', prompt)
        self.assertIn('"judgement"', prompt)
        self.assertNotIn("13", prompt)


class PlanningTests(PlannerTestCase):
    def test_race_then_plan_adopted_then_served_by_plan(self):
        remote = FakeRemote(plans=[GOOD_PLAN])
        router = self.build(remote)
        first = router.handle(request(3, "abcd"))
        self.assertEqual((first["value"], first["route"]), (10, "race"))
        router.drain()
        self.assertIsNone(self.record(router)["plan"])
        router.handle(request(5, "xy"))
        router.drain()
        record = self.record(router)
        self.assertEqual([a["outcome"] for a in record["plan_attempts"]], ["ADOPTED"])
        self.assertEqual(record["plan_attempts"][0]["trial"], {"examples": 2, "passed": 2})
        self.assertEqual(record["plan_attempts"][0]["function_steps"], 3)
        third = router.handle(request(7, "hello"))
        router.drain()
        self.assertEqual((third["value"], third["route"]), (19, "plan"))
        self.assertEqual({s["id"] for s in third["steps"]}, {"twice", "size", "total"})
        self.assertEqual(remote.count("Plan how to compute"), 1)

    def test_planner_never_sees_agreed_answers(self):
        remote = FakeRemote(plans=[GOOD_PLAN])
        router = self.build(remote)
        router.handle(request(100, "abc"))
        router.drain()
        router.handle(request(200, "de"))
        router.drain()
        prompt = next(p for _, p in remote.calls if p.startswith("Plan how to compute"))
        self.assertNotIn("203", prompt)
        self.assertNotIn("402", prompt)

    def test_wrong_plan_is_rejected_and_attempts_are_bounded(self):
        remote = FakeRemote(plans=[BAD_PLAN, BAD_PLAN, GOOD_PLAN])
        router = self.build(remote)
        for n in range(1, 6):
            served = router.handle(request(n, "ab"))
            router.drain()
            self.assertEqual(served["route"], "race")
        record = self.record(router)
        self.assertEqual([a["outcome"] for a in record["plan_attempts"]], ["REJECTED", "REJECTED"])
        self.assertIsNone(record["plan"])
        self.assertEqual(remote.count("Plan how to compute"), 2)

    def test_invalid_plans_are_kept_and_failures_recorded(self):
        bad = {"steps": [], "output": "x"}
        remote = FakeRemote(plans=[bad, bad])
        router = self.build(remote, max_plan_attempts=3)
        for n in (1, 2, 3):
            router.handle(request(n, "ab"))
            router.drain()
        attempts = self.record(router)["plan_attempts"]
        self.assertEqual([a["outcome"] for a in attempts[:2]], ["INVALID_PLAN", "REMOTE_ERROR"])
        self.assertEqual(len(attempts[0]["refused"]), 2)
        self.assertIn('"steps": []', attempts[0]["refused"][0]["reply"])

    def test_refused_plan_is_retried_with_its_reason(self):
        broken = json.loads(json.dumps(GOOD_PLAN))
        broken["steps"][0]["task"]["signature"] = "solve n"
        remote = FakeRemote(plans=[broken, GOOD_PLAN])
        router = self.build(remote)
        for n in (1, 2):
            router.handle(request(n, "ab"))
            router.drain()
        attempt = self.record(router)["plan_attempts"][0]
        self.assertEqual(attempt["outcome"], "ADOPTED")
        self.assertEqual(attempt["refused"][0]["reason"],
                         "PLAN_INVALID:INVALID_STEP_TASK:INVALID_SIGNATURE")
        retry = [p for _, p in remote.calls if p.startswith("Plan how to compute")][1]
        self.assertIn("refused by the plan checker with this reason: PLAN_INVALID", retry)

    def test_rejected_plan_text_is_kept(self):
        remote = FakeRemote(plans=[BAD_PLAN])
        router = self.build(remote, max_plan_attempts=1)
        for n in (1, 2):
            router.handle(request(n, "ab"))
            router.drain()
        attempt = self.record(router)["plan_attempts"][0]
        self.assertEqual(attempt["outcome"], "REJECTED")
        self.assertEqual(attempt["rejected_plan"]["output"], "total")

    def test_disagreement_forms_no_example(self):
        remote = FakeRemote(plans=[GOOD_PLAN],
                            task_answer=lambda model, i: 0 if model == "b" else i["n"] * 2 + len(i["text"]))
        router = self.build(remote)
        for n in (1, 2, 3):
            router.handle(request(n, "ab"))
            router.drain()
        record = self.record(router)
        self.assertEqual((record["examples"], record["disagreements"]), ([], 3))
        self.assertEqual(remote.count("Plan how to compute"), 0)

    def test_audit_mismatch_drops_the_plan(self):
        state = {"wrong": False}
        remote = FakeRemote(plans=[GOOD_PLAN], task_answer=lambda model, i: (
            -1 if state["wrong"] else i["n"] * 2 + len(i["text"])))
        router = self.build(remote, plan_audit_rate=1.0)
        for n in (1, 2):
            router.handle(request(n, "ab"))
            router.drain()
        self.assertIsNotNone(self.record(router)["plan"])
        state["wrong"] = True
        served = router.handle(request(9, "ab"))
        router.drain()
        self.assertEqual(served["route"], "plan")
        record = self.record(router)
        self.assertIsNone(record["plan"])
        self.assertEqual(record["demotions"][0]["reason"], "AUDIT_MISMATCH")

    def test_failed_plan_run_falls_back_to_the_race(self):
        remote = FakeRemote(plans=[GOOD_PLAN])
        router = self.build(remote)
        for n in (1, 2):
            router.handle(request(n, "ab"))
            router.drain()
        original = remote.__call__

        def broken(prompt, config, api_key):
            if "characters in the text" in prompt and not prompt.startswith("Carry out"):
                return RemoteResult(False, error="OPENROUTER_HTTP_500", model=config["model"])
            return original(prompt, config, api_key)
        router.router.remote_fn = broken
        router.router.store.get(router.router.store.shapes()[0]["shape"])  # store warm
        for record in router.router.store.shapes():
            record["function"] = None
        served = router.handle(request(30, "xyz"))
        router.drain()
        self.assertEqual((served["route"], served["value"]), ("race", 63))


if __name__ == "__main__":
    unittest.main()


REFINED_PLAN = json.loads(json.dumps(GOOD_PLAN).replace('"twice"', '"doubled"'))


class MajorityTests(PlannerTestCase):
    def three_racers(self, **overrides):
        # Racer "c" always dissents.
        remote = FakeRemote(plans=[GOOD_PLAN], task_answer=lambda model, i: (
            -1 if model == "c" else i["n"] * 2 + len(i["text"])))
        return remote, self.build(remote, race_models=["a", "b", "c"], **overrides)

    def test_unanimity_blocks_examples_when_one_racer_dissents(self):
        remote, router = self.three_racers()
        for n in (1, 2, 3):
            router.handle(request(n, "ab"))
            router.drain()
        self.assertEqual(self.record(router)["examples"], [])
        self.assertEqual(remote.count("Plan how to compute"), 0)

    def test_majority_rule_forms_examples_and_plans(self):
        remote, router = self.three_racers(job_agreement_min=2)
        for n in (1, 2):
            router.handle(request(n, "ab"))
            router.drain()
        record = self.record(router)
        self.assertEqual([e["expected"] for e in record["examples"]], [4, 6])
        self.assertIsNotNone(record["plan"])

    def test_majority_needs_a_clear_lead(self):
        from concurrent.futures import Future

        def done(value):
            future = Future()
            future.set_result({"valid": True, "value": value})
            return future
        tie = [done(1), done(1), done(2), done(2)]
        self.assertEqual(PlanningRouter._agreement(tie, 2, 2)[0], False)
        lead = [done(1), done(1), done(1), done(2)]
        self.assertEqual(PlanningRouter._agreement(lead, 2, 3)[:2], (True, 1))
        self.assertEqual(PlanningRouter._agreement(lead, 2, 4)[0], False)
        self.assertEqual(PlanningRouter._agreement(lead, 2)[0], False)


class ShadowTests(PlannerTestCase):
    def slow_remote(self, plans, task_delay=0.3, step_delay=0.15, task_answer=None):
        remote = FakeRemote(plans=plans, task_answer=task_answer)
        original = remote.__call__

        def call(prompt, config, api_key):
            if prompt.startswith("Carry out the task"):
                time.sleep(task_delay)
            elif not prompt.startswith(("Plan how", "Write a Python", "List boundary")):
                time.sleep(step_delay)
            return original(prompt, config, api_key)
        return remote, call

    def test_plan_serves_only_once_its_shadow_runs_beat_the_race(self):
        remote, call = self.slow_remote([GOOD_PLAN])
        router = self.build(call, plan_shadow=True, plan_live_window=2, plan_live_ratio=0.75)
        routes = []
        for n in range(1, 9):
            routes.append(router.handle(request(n, "a" * n))["route"])
            router.drain()
        record = self.record(router)
        self.assertEqual(record["plan"]["mode"], "live")
        self.assertEqual(routes[:3], ["race", "race", "race"])
        self.assertEqual(routes[-1], "plan")
        switch = routes.index("plan")
        # It went live only after shadow runs, and after the steps became code.
        self.assertGreaterEqual(record["plan"]["live_after_shadow_runs"], 2)
        self.assertTrue(all(r["function"] for r in router.router.store.shapes()))
        self.assertTrue(all(r == "race" for r in routes[:switch]))

    def test_slow_plan_stays_in_shadow(self):
        remote, call = self.slow_remote([GOOD_PLAN], task_delay=0.0)
        router = self.build(call, plan_shadow=True, synthesis_enabled=False)
        routes = []
        for n in range(1, 6):
            routes.append(router.handle(request(n, "ab"))["route"])
            router.drain()
        self.assertEqual(set(routes), {"race"})
        self.assertEqual(self.record(router)["plan"]["mode"], "shadow")

    def test_shadow_mismatch_drops_the_plan(self):
        state = {"wrong": False}
        remote, call = self.slow_remote([GOOD_PLAN], task_delay=0.0, step_delay=0.0, task_answer=(
            lambda model, i: -1 if state["wrong"] else i["n"] * 2 + len(i["text"])))
        router = self.build(call, plan_shadow=True)
        for n in (1, 2):
            router.handle(request(n, "ab"))
            router.drain()
        self.assertEqual(self.record(router)["plan"]["mode"], "shadow")
        state["wrong"] = True
        router.handle(request(3, "ab"))
        router.drain()
        record = self.record(router)
        self.assertIsNone(record["plan"])
        self.assertEqual(record["demotions"][0]["reason"], "SHADOW_MISMATCH")


class IsolationTests(PlannerTestCase):
    def test_learning_runs_on_background_threads_and_answers_on_live_ones(self):
        import threading
        threads = {"task": set(), "step": set()}
        remote = FakeRemote(plans=[GOOD_PLAN])

        def call(prompt, config, api_key):
            name = threading.current_thread().name.split("_")[0]
            if prompt.startswith("Carry out the task"):
                threads["task"].add(name)
            elif not prompt.startswith(("Plan how", "Write a Python", "List boundary")):
                threads["step"].add(name)
            return remote(prompt, config, api_key)
        router = self.build(call, plan_shadow=True, plan_live_ratio=0.0)
        for n in range(1, 5):
            router.handle(request(n, "a" * n))
            router.drain()
        # Whole-task answers are live; every step run (trials, shadow runs) is learning.
        self.assertEqual(threads["task"], {"live-model"})
        self.assertEqual(threads["step"], {"background-model"})

    def test_only_one_shadow_run_per_task_at_a_time(self):
        remote = FakeRemote(plans=[GOOD_PLAN])

        def call(prompt, config, api_key):
            if not prompt.startswith(("Carry out", "Plan how", "Write a Python", "List boundary")):
                time.sleep(0.2)
            return remote(prompt, config, api_key)
        router = self.build(call, plan_shadow=True, plan_live_ratio=0.0, synthesis_enabled=False)
        for n in (1, 2):
            router.handle(request(n, "ab"))
            router.drain()
        for n in range(3, 8):
            router.handle(request(n, "ab"))
        router.drain()
        self.assertGreaterEqual(router.shadow_skipped, 3)
        self.assertLessEqual(len(self.record(router)["plan"]["shadow_ms"]), 2)


class RefinementTests(PlannerTestCase):
    def build_refining(self, plans, **overrides):
        remote = FakeRemote(plans=plans)
        settings = {"synthesis_enabled": False, "refine_after_jobs": 2, "max_refinements": 1,
                    **overrides}
        return remote, self.build(remote, **settings)

    def run_jobs(self, router, count, start=1):
        served = []
        for n in range(start, start + count):
            served.append(router.handle(request(n, "a" * n)))
            router.drain()
        return served

    def test_slow_steps_are_reported_and_a_passing_revision_replaces_the_plan(self):
        remote, router = self.build_refining([GOOD_PLAN, REFINED_PLAN])
        served = self.run_jobs(router, 5)
        self.assertEqual([s["route"] for s in served], ["race", "race", "plan", "plan", "plan"])
        record = self.record(router)
        refine = [a for a in record["plan_attempts"] if a.get("kind") == "refine"]
        self.assertEqual(len(refine), 1)
        self.assertEqual((refine[0]["outcome"], refine[0]["after_jobs"]), ("ADOPTED", 2))
        self.assertEqual(refine[0]["slow_steps"], ["twice", "size", "total"])
        self.assertEqual(record["plan"]["refined_from"], record["plan_attempts"][0]["sha256"])
        self.assertIn("doubled", {s["id"] for s in served[-1]["steps"]})
        prompt = [p for _, p in remote.calls if p.startswith("Plan how to compute")][1]
        self.assertIn("still answered by language models, which is slow: twice, size, total", prompt)
        self.assertIn("run as verified code and are fast: none", prompt)

    def test_failing_revision_keeps_the_old_plan_and_refinement_is_bounded(self):
        remote, router = self.build_refining([GOOD_PLAN, BAD_PLAN, REFINED_PLAN])
        self.run_jobs(router, 7)
        record = self.record(router)
        refine = [a for a in record["plan_attempts"] if a.get("kind") == "refine"]
        self.assertEqual([a["outcome"] for a in refine], ["REJECTED"])
        self.assertEqual(record["plan"]["sha256"], record["plan_attempts"][0]["sha256"])
        self.assertEqual(remote.count("Plan how to compute"), 2)

    def test_no_refinement_when_every_function_step_is_code(self):
        remote, router = self.build_refining([GOOD_PLAN, REFINED_PLAN], synthesis_enabled=True)
        self.run_jobs(router, 8)
        record = self.record(router)
        self.assertFalse(any(a.get("kind") == "refine" for a in record["plan_attempts"]))

    def test_refinement_is_off_by_default(self):
        remote, router = self.build_refining([GOOD_PLAN, REFINED_PLAN], max_refinements=0)
        self.run_jobs(router, 5)
        self.assertEqual(remote.count("Plan how to compute"), 1)

    def test_planner_is_steered_to_small_steps(self):
        prompt = planner.build_plan_prompt(DESCRIPTION, {"n": 1, "text": "a"})
        self.assertIn("Make function steps small", prompt)
        self.assertIn("not an object that bundles several results", prompt)


class LearningRosterTests(PlannerTestCase):
    def models_by_purpose(self, remote):
        seen = {}
        for model, prompt in remote.calls:
            purpose = "task" if prompt.startswith("Carry out the task") else (
                "step" if prompt.startswith("Work out what") else "other")
            seen.setdefault(purpose, set()).add(model)
        return seen

    def test_background_learning_uses_the_learning_roster(self):
        remote = FakeRemote(plans=[GOOD_PLAN])
        router = self.build(remote, race_models=["a", "b", "c"], learning_models=["a", "b"],
                            plan_shadow=True, plan_live_ratio=0.0)
        for n in range(1, 6):
            router.handle(request(n, "a" * n))
            router.drain()
        seen = self.models_by_purpose(remote)
        self.assertEqual(seen["task"], {"a", "b", "c"})
        # Plan trials and shadow runs learn on two models only.
        self.assertEqual(seen["step"], {"a", "b"})
        self.assertTrue(all(r["function"] for r in router.router.store.shapes()))

    def test_live_steps_and_judgements_keep_the_full_roster(self):
        remote = FakeRemote()
        router = self.build(remote, race_models=["a", "b", "c"], learning_models=["a", "b"])
        fast = router.router
        step = {"schema_version": "fast_path_request_v1",
                "task": {"spec": DOUBLE, "signature": "def solve(n: int) -> int:"}, "args": [3]}
        fast.handle(step)
        fast.drain()
        live = {m for m, p in remote.calls if p.startswith("Work out what")}
        self.assertEqual(live, {"a", "b", "c"})
        remote.calls.clear()
        with fast.background_context():
            fast.handle({**step, "args": [4]}, learn=False)
        self.assertEqual({m for m, _ in remote.calls}, {"a", "b", "c"})
        remote.calls.clear()
        with fast.background_context():
            fast.handle({**step, "args": [5]})
        fast.drain()
        self.assertEqual({m for m, _ in remote.calls if m != "writer"}, {"a", "b"})

    def test_without_a_learning_roster_nothing_changes(self):
        remote = FakeRemote(plans=[GOOD_PLAN])
        router = self.build(remote, race_models=["a", "b", "c"], plan_shadow=True,
                            plan_live_ratio=0.0)
        for n in range(1, 4):
            router.handle(request(n, "a" * n))
            router.drain()
        self.assertEqual(self.models_by_purpose(remote)["step"], {"a", "b", "c"})
