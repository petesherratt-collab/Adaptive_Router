"""Multi-step jobs over the fast path.

A job is a caller-declared plan: named inputs, a list of steps and one output.
Each step is a single-step task whose arguments are literal values, job
inputs or the results of earlier steps. The orchestrator is plain code. It
makes no model call of its own: for every step it only decides, by lookup,
whether promoted code can answer or the step goes to the model race.

Steps come in two kinds:

* ``function``: the answer is fully determined by the specification. These
  learn, and may be promoted to code.
* ``judgement``: the answer needs a model's reading of the input. These are
  always raced and never stored, synthesised or promoted.

Steps whose arguments are all available run concurrently.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid

import fast_path


SCHEMA_VERSION = "fast_path_job_v1"
STEP_KINDS = ("function", "judgement")
JOB_COMPLETED, STEP_FAILED = "JOB_COMPLETED", "STEP_FAILED"


class JobError(ValueError):
    """The caller supplied a malformed job."""


def _argument(value, known):
    if not isinstance(value, dict) or len(value) != 1:
        raise JobError("INVALID_ARGUMENT")
    if "value" in value:
        return ("value", value["value"])
    if "ref" in value:
        if not isinstance(value["ref"], str) or value["ref"] not in known:
            raise JobError("UNKNOWN_REFERENCE")
        return ("ref", value["ref"])
    raise JobError("INVALID_ARGUMENT")


class Step:
    def __init__(self, step_id, kind, spec, signature, arguments):
        self.id, self.kind = step_id, kind
        self.spec, self.signature, self.arguments = spec, signature, arguments
        self.needs = {name for how, name in arguments if how == "ref"}


class Job:
    def __init__(self, inputs, steps, output):
        self.inputs, self.steps, self.output = inputs, steps, output

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value, dict) or set(value) != {
            "schema_version", "inputs", "steps", "output",
        }:
            raise JobError("JOB_FIELDS_MISMATCH")
        if value["schema_version"] != SCHEMA_VERSION:
            raise JobError("JOB_SCHEMA_MISMATCH")
        inputs = value["inputs"]
        if not isinstance(inputs, dict) or not all(isinstance(k, str) and k for k in inputs):
            raise JobError("INVALID_INPUTS")
        if not isinstance(value["steps"], list) or not value["steps"]:
            raise JobError("INVALID_STEPS")
        known, steps = set(inputs), []
        for raw in value["steps"]:
            if not isinstance(raw, dict) or set(raw) != {"id", "kind", "task", "args"}:
                raise JobError("STEP_FIELDS_MISMATCH")
            if not isinstance(raw["id"], str) or not raw["id"] or raw["id"] in known:
                raise JobError("INVALID_STEP_ID")
            if raw["kind"] not in STEP_KINDS:
                raise JobError("INVALID_STEP_KIND")
            if not isinstance(raw["args"], list):
                raise JobError("INVALID_ARGUMENT")
            # A step may refer only to inputs and earlier steps, so a job
            # cannot contain a cycle.
            arguments = [_argument(arg, known) for arg in raw["args"]]
            try:
                checked = fast_path.FastPathRequest.from_mapping(
                    {
                        "schema_version": fast_path.SCHEMA_VERSION,
                        "task": raw["task"],
                        "args": [],
                    }
                )
            except fast_path.FastPathRequestError as exc:
                raise JobError(f"INVALID_STEP_TASK:{exc}") from exc
            steps.append(
                Step(raw["id"], raw["kind"], checked.spec, checked.signature, arguments)
            )
            known.add(raw["id"])
        output = value["output"]
        if not isinstance(output, str) or output not in known - set(inputs):
            raise JobError("INVALID_OUTPUT")
        return cls(inputs, steps, output)


def load_job(path):
    try:
        document = fast_path.strict_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise JobError("JOB_UNREADABLE") from exc
    return Job.from_mapping(document)


class Orchestrator:
    def __init__(self, router, log_path="fast_path_jobs.jsonl", max_parallel_steps=8,
                 background=False):
        """``background=True`` runs every step's model calls on the router's
        background pool, for work nobody is waiting on."""
        self.router = router
        self.background = background
        self.log_path = Path(log_path)
        self._pool = ThreadPoolExecutor(max_workers=max_parallel_steps)
        self._log_lock = threading.Lock()

    def close(self):
        self._pool.shutdown(wait=True)

    def _run_step(self, step, values, job_started):
        if self.background:
            with self.router.background_context():
                return self._run_step_now(step, values, job_started)
        return self._run_step_now(step, values, job_started)

    def _run_step_now(self, step, values, job_started):
        started = time.perf_counter()
        args = [values[name] if how == "ref" else name for how, name in step.arguments]
        result = self.router.handle(
            {
                "schema_version": fast_path.SCHEMA_VERSION,
                "task": {"spec": step.spec, "signature": step.signature},
                "args": args,
            },
            learn=step.kind == "function",
        )
        finished = time.perf_counter()
        return {
            "id": step.id,
            "kind": step.kind,
            "route": result["route"],
            "model": result["model"],
            "value": result["value"],
            "ms": (finished - started) * 1000,
            "started_ms": (started - job_started) * 1000,
            "finished_ms": (finished - job_started) * 1000,
        }

    def run(self, job):
        if not isinstance(job, Job):
            job = Job.from_mapping(job)
        started = time.perf_counter()
        values = dict(job.inputs)
        waiting = list(job.steps)
        running, done, failed = {}, [], None
        while (waiting or running) and failed is None:
            ready = [s for s in waiting if s.needs <= set(values)]
            for step in ready:
                waiting.remove(step)
                running[self._pool.submit(self._run_step, step, values, started)] = step
            finished, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in finished:
                running.pop(future)
                outcome = future.result()
                done.append(outcome)
                if outcome["route"] == "none":
                    failed = outcome["id"]
                else:
                    values[outcome["id"]] = outcome["value"]
        # Steps already started are allowed to finish so nothing is abandoned.
        for future in list(running):
            done.append(future.result())
        total_ms = (time.perf_counter() - started) * 1000
        completed = failed is None
        result = {
            "value": values.get(job.output) if completed else None,
            "reason": JOB_COMPLETED if completed else STEP_FAILED,
            "failed_step": failed,
            "total_ms": total_ms,
            "steps": sorted(done, key=lambda s: s["started_ms"]),
            "not_started": [s.id for s in waiting],
        }
        self._log(result)
        return result

    def _log(self, result):
        record = {
            "record_type": "fast_path_job",
            "job_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": result["reason"],
            "failed_step": result["failed_step"],
            "total_ms": result["total_ms"],
            # Metadata only: step values are never logged.
            "steps": [
                {k: s[k] for k in ("id", "kind", "route", "model", "ms", "started_ms", "finished_ms")}
                for s in result["steps"]
            ],
        }
        with self._log_lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def build_job_prompt(job):
    """One prompt asking a model to carry out the whole plan in a single reply."""
    if not isinstance(job, Job):
        job = Job.from_mapping(job)
    lines = [
        "Carry out the procedure below and give its final result.",
        "",
        "Inputs:",
    ]
    lines += [f"- {name} (JSON): {json.dumps(value)}" for name, value in job.inputs.items()]
    lines += ["", "Steps, in order:"]
    for number, step in enumerate(job.steps, start=1):
        arguments = ", ".join(
            (f"input '{name}'" if name in job.inputs else f"the result of step '{name}'")
            if how == "ref" else f"the value {json.dumps(name)}"
            for how, name in step.arguments
        )
        lines.append(
            f"{number}. Step '{step.id}': {step.spec} "
            f"Signature: {step.signature} Arguments in order: {arguments}."
        )
    lines += [
        "",
        f"The final result is the result of step '{job.output}'.",
        "",
        "Reply with exactly one line: the word ANSWER, a colon, then the "
        "final result encoded as JSON. Examples of the form: "
        'ANSWER: "text"   ANSWER: 42   ANSWER: [1, 2]   ANSWER: null',
        "Give the bare final result. Do not wrap it in an object unless the "
        "result itself is an object, and write nothing after the ANSWER line.",
    ]
    return "\n".join(lines)


def render_job(result):
    lines = [f"[{result['reason']} | {result['total_ms']:.0f} ms]"]
    for step in result["steps"]:
        via = step["model"] or step["route"]
        lines.append(
            f"  {step['id']:<16} {step['kind']:<9} {step['route']:<5} {via:<32}"
            f" {step['ms']:>7.0f} ms  (start {step['started_ms']:.0f})"
        )
    lines.append("")
    lines.append(json.dumps(result["value"]) if result["reason"] == JOB_COMPLETED
                 else "No answer was returned.")
    return "\n".join(lines)
