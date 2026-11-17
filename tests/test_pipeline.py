import json
from pathlib import Path
import re
import tempfile
import time
import unittest

from fast_path import FastPathRouter
import pipeline
from pipeline import Job, JobError, Orchestrator
from remote import RemoteResult


def task(spec, signature):
    return {"spec": spec, "signature": signature}


DOUBLE = task("Return the input integer doubled.", "def solve(n: int) -> int:")
ADD = task("Return the sum of two integers.", "def solve(a: int, b: int) -> int:")
MOOD = task("Classify the mood of the text as 'up' or 'down'.", "def solve(text: str) -> str:")


def job(inputs=None, steps=None, output="total"):
    return {
        "schema_version": "fast_path_job_v1",
        "inputs": {"n": 4, "text": "fine"} if inputs is None else inputs,
        "steps": steps if steps is not None else [
            {"id": "twice", "kind": "function", "task": DOUBLE, "args": [{"ref": "n"}]},
            {"id": "mood", "kind": "judgement", "task": MOOD, "args": [{"ref": "text"}]},
            {"id": "total", "kind": "function", "task": ADD,
             "args": [{"ref": "twice"}, {"value": 10}]},
        ],
        "output": output,
    }


def prompt_args(prompt):
    return [json.loads(v) for v in re.findall(r"^Argument \d+ \(JSON\): (.*)$", prompt, re.M)]


class FakeRemote:
    def __init__(self, delay=0.0, fail_spec=None):
        self.delay, self.fail_spec, self.calls = delay, fail_spec, []

    def __call__(self, prompt, config, api_key):
        self.calls.append(prompt)
        model = config["model"]
        if prompt.startswith("Write a Python function"):
            source = ("def solve(a, b):\n    return a + b\n" if "sum of two" in prompt
                      else "def solve(n):\n    return n * 2\n")
            return RemoteResult(True, text=source, model=model)
        if self.fail_spec and self.fail_spec in prompt:
            return RemoteResult(False, error="OPENROUTER_HTTP_500", model=model)
        time.sleep(self.delay)
        args = prompt_args(prompt)
        if "mood" in prompt:
            value = "up"
        elif "sum of two" in prompt:
            value = args[0] + args[1]
        else:
            value = args[0] * 2
        return RemoteResult(True, text=f"ANSWER: {json.dumps(value)}", model=model, total_ms=1.0)


class PipelineTestCase(unittest.TestCase):
    def build(self, remote):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        settings = {
            "race_models": ["a", "b"], "synthesis_model": "writer",
            "answer_max_tokens": 64, "synthesis_max_tokens": 256,
            "agreement_quorum": 2, "min_gate_examples": 2, "max_synthesis_attempts": 1,
            "sandbox_timeout_seconds": 2.0, "audit_sample_rate": 0.0, "audit_salt": "t",
        }
        self.router = FastPathRouter(
            {"remote": {"model": "x"}, "fast_path": settings},
            root / "store", root / "runs.jsonl", remote_fn=remote, api_key="k",
        )
        self.log = root / "jobs.jsonl"
        orchestrator = Orchestrator(self.router, self.log)
        self.addCleanup(orchestrator.close)
        return orchestrator


class JobValidationTests(unittest.TestCase):
    def test_valid_job(self):
        parsed = Job.from_mapping(job())
        self.assertEqual([s.id for s in parsed.steps], ["twice", "mood", "total"])
        self.assertEqual(parsed.steps[2].needs, {"twice"})

    def test_malformed_jobs_are_rejected(self):
        good = job()["steps"]
        bad = [
            [],
            {**job(), "extra": 1},
            {**job(), "schema_version": "x"},
            job(inputs=[]),
            job(steps=[]),
            job(output="missing"),
            job(output="n"),
            job(steps=[{**good[0], "kind": "guess"}]),
            job(steps=[{**good[0], "id": "n"}]),
            job(steps=[good[0], good[0]]),
            job(steps=[{**good[0], "args": [{"ref": "later"}]}]),
            job(steps=[{**good[0], "args": [4]}]),
            job(steps=[{**good[0], "args": [{"ref": "n", "value": 1}]}]),
            job(steps=[{**good[0], "task": {"spec": "x"}}]),
            job(steps=[{**good[0], "task": task("x", "def other(n):")}]),
            job(steps=[good[2]]),
        ]
        for document in bad:
            with self.subTest(document=str(document)[:60]):
                with self.assertRaises(JobError):
                    Job.from_mapping(document)


class OrchestratorTests(PipelineTestCase):
    def test_values_flow_between_steps(self):
        orchestrator = self.build(FakeRemote())
        result = orchestrator.run(job())
        self.router.drain()
        self.assertEqual((result["value"], result["reason"]), (18, "JOB_COMPLETED"))
        self.assertEqual({s["id"]: s["value"] for s in result["steps"]},
                         {"twice": 8, "mood": "up", "total": 18})

    def test_independent_steps_run_concurrently(self):
        orchestrator = self.build(FakeRemote(delay=0.3))
        result = orchestrator.run(job())
        self.router.drain()
        steps = {s["id"]: s for s in result["steps"]}
        # twice and mood overlap; total waits for twice.
        self.assertLess(steps["mood"]["started_ms"], steps["twice"]["finished_ms"])
        self.assertGreaterEqual(steps["total"]["started_ms"], steps["twice"]["finished_ms"] - 1)
        self.assertLess(result["total_ms"], 850)

    def test_function_steps_are_promoted_and_judgement_steps_never_are(self):
        remote = FakeRemote()
        orchestrator = self.build(remote)
        for n in (1, 2, 3):
            orchestrator.run(job(inputs={"n": n, "text": f"text {n}"}))
            self.router.drain()
        before = len(remote.calls)
        result = orchestrator.run(job(inputs={"n": 50, "text": "new text"}))
        self.router.drain()
        routes = {s["id"]: s["route"] for s in result["steps"]}
        self.assertEqual(routes, {"twice": "code", "mood": "model", "total": "code"})
        self.assertEqual(result["value"], 110)
        # Only the judgement step called models: one call per race model.
        self.assertEqual(len(remote.calls) - before, 2)
        specs = {record["spec"] for record in self.router.store.shapes()}
        self.assertNotIn(MOOD["spec"], specs)

    def test_failed_step_stops_dependants_but_not_the_job_log(self):
        orchestrator = self.build(FakeRemote(fail_spec="doubled"))
        result = orchestrator.run(job())
        self.router.drain()
        self.assertEqual(
            (result["value"], result["reason"], result["failed_step"]),
            (None, "STEP_FAILED", "twice"),
        )
        self.assertEqual(result["not_started"], ["total"])
        self.assertIn("No answer", pipeline.render_job(result))

    def test_job_log_is_metadata_only(self):
        orchestrator = self.build(FakeRemote())
        orchestrator.run(job(inputs={"n": 4, "text": "secret-input"}))
        self.router.drain()
        text = self.log.read_text(encoding="utf-8")
        self.assertNotIn("secret", text)
        record = json.loads(text.splitlines()[0])
        self.assertEqual([s["id"] for s in record["steps"]][-1], "total")
        self.assertNotIn("value", record["steps"][0])


if __name__ == "__main__":
    unittest.main()
