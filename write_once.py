"""Write the job once: the competitor the planning router has to beat.

A request is a plain-language task description plus named inputs, as for
``planner.PlanningRouter``. Per task template:

1. Until a program is adopted, each request is answered by racing the whole
   task across the roster; agreed answers become job examples, by the same
   rule the planner uses.
2. Once ``plan_examples`` examples exist, one model call (``planner_model``)
   writes the whole job from the description and one request's inputs (no
   answer is shown): a list of reading steps, each a short judgement over one
   input with a fixed label set, and one Python function
   ``solve(inputs, readings)`` that does everything else.
3. The program is run on the stored examples, its reading steps raced exactly
   as the planner races judgement steps. It is adopted only if it reproduces
   every agreed answer. At most ``max_plan_attempts`` programs are tried.

Afterwards each request races only the reading steps, in parallel, and runs the
code in the sandbox. A ``plan_audit_rate`` sample is checked against a fresh
whole-task race; an agreed mismatch drops the program. No model judges the
code: adoption is by execution, as everywhere else in this project.

This is what a programmer with a coding model would do. It learns nothing step
by step, so after adoption it should run at about the ceiling arm's speed.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import threading
import time
import uuid

import fast_path
import planner
import sandbox
from shadow import should_shadow

PROGRAM_ROUTE = "program"


def build_program_prompt(description, inputs):
    modules = ", ".join(sandbox.ALLOWED_MODULES)
    lines = [
        "Write a program that carries out the task below.",
        "",
        f"Task: {description}",
        "",
        "Inputs (names and one example of their values):",
    ]
    lines += [f"- {name} (JSON): {json.dumps(value)}" for name, value in inputs.items()]
    lines += [
        "",
        "Split the work in two:",
        "- \"readings\": the parts that need reading meaning from prose (tone, topic, intent, language, "
        "which place or thing a text refers to, and so on). Each reading takes exactly one input and "
        "returns one label from a fixed list. Use as few as possible, none if code can do everything.",
        "- \"code\": Python source defining solve(inputs, readings), where inputs is a dict of the "
        "inputs above and readings maps each reading's id to its label. It must return the task's final "
        "result in exactly the requested form and do everything else: parsing, arithmetic, counting, "
        "rounding, lookups and formatting.",
        "",
        f"Code rules: pure Python; you may import only {modules}; no classes, no file or network access, "
        "no names beginning with an underscore; helper functions are allowed.",
        "",
        "Reply with JSON only, no code fence: {\"readings\": [{\"id\": \"<letters, digits, underscores>\", "
        "\"input\": \"<input name>\", \"spec\": \"<precise instruction that names the exact labels>\", "
        "\"labels\": [\"...\"]}], \"code\": \"<python source>\"}",
    ]
    return "\n".join(lines)


def parse_program(text, inputs):
    """Return ``(program, None)`` or ``(None, reason)``."""
    try:
        value = fast_path.strict_json(fast_path._unfence(text))
    except (ValueError, TypeError, RecursionError):
        return None, "PROGRAM_NOT_JSON"
    if not isinstance(value, dict) or set(value) != {"readings", "code"}:
        return None, "PROGRAM_FIELDS_MISMATCH"
    if not isinstance(value["code"], str) or not value["code"].strip():
        return None, "PROGRAM_CODE_MISSING"
    readings, seen = value["readings"], set()
    if not isinstance(readings, list):
        return None, "PROGRAM_READINGS_INVALID"
    for reading in readings:
        if (not isinstance(reading, dict) or set(reading) != {"id", "input", "spec", "labels"}
                or not isinstance(reading["id"], str) or not reading["id"].isidentifier()
                or reading["id"] in seen or reading["input"] not in inputs
                or not isinstance(inputs[reading["input"]], str)
                or not isinstance(reading["spec"], str) or not reading["spec"].strip()
                or not isinstance(reading["labels"], list) or not reading["labels"]
                or not all(isinstance(label, str) for label in reading["labels"])):
            return None, "PROGRAM_READINGS_INVALID"
        seen.add(reading["id"])
    accepted, reason = sandbox.check_source(fast_path._unfence(value["code"]) + "\n")
    if not accepted:
        return None, f"PROGRAM_CODE_REJECTED:{reason}"
    return {"readings": readings, "code": fast_path._unfence(value["code"]) + "\n"}, None


class WriteOnceRouter:
    def __init__(self, router):
        self.router = router
        self.settings = router.settings
        self._records = {}
        self._lock = threading.RLock()
        self._background = ThreadPoolExecutor(max_workers=4)
        self._readers = ThreadPoolExecutor(max_workers=8)
        self._pending = []

    # ---- hot path -------------------------------------------------------

    def handle(self, request):
        if not isinstance(request, planner.TaskRequest):
            request = planner.TaskRequest.from_mapping(request)
        started = time.perf_counter()
        with self._lock:
            record = self._records.setdefault(request.template, {
                "description": request.description, "examples": [], "program": None,
                "attempts": [], "demotions": [], "disagreements": 0, "jobs": 0,
            })
            program = record["program"]
        if program is not None:
            ok, value, readings = self.run_program(program, request.inputs)
            if ok:
                with self._lock:
                    record["jobs"] += 1
                request_id = str(uuid.uuid4())
                if should_shadow(request_id, self.settings.get("plan_audit_rate", 0.0),
                                 self.settings.get("audit_salt", "")):
                    futures = self.router.start_prompt_race(
                        planner.build_task_prompt(request.description, request.inputs))
                    self._submit(self._audit, request, futures, value, program["sha256"])
                return self._finish(started, value, PROGRAM_ROUTE, None, readings)
        futures = self.router.start_prompt_race(planner.build_task_prompt(request.description, request.inputs))
        model, value = fast_path.FastPathRouter._first_valid(futures)
        self._submit(self._observe, request, futures)
        if model is None:
            return self._finish(started, None, planner.NO_ANSWER, None, None)
        return self._finish(started, value, planner.RACE_ROUTE, model, None)

    def _finish(self, started, value, route, model, readings):
        return {"value": value, "route": route, "model": model, "readings": readings,
                "total_ms": (time.perf_counter() - started) * 1000}

    def run_program(self, program, inputs):
        """Race every reading in parallel, then run the code. Returns
        ``(ok, value, readings)``."""
        def read(reading):
            result = self.router.handle({
                "schema_version": fast_path.SCHEMA_VERSION,
                "task": {"spec": reading["spec"], "signature": "def solve(text: str) -> str:"},
                "args": [inputs[reading["input"]]],
            }, learn=False)
            return reading["id"], result
        readings = {}
        for reading_id, result in self._readers.map(read, program["readings"]):
            if result["route"] == "none":
                return False, None, readings
            readings[reading_id] = result["value"]
        run = sandbox.run_function(program["code"], [[inputs, readings]],
                                   self.settings["sandbox_timeout_seconds"])
        if not (run.ok and run.results[0]["ok"]):
            return False, None, readings
        return True, run.results[0]["value"], readings

    # ---- background -----------------------------------------------------

    def _submit(self, fn, *args):
        self._pending.append(self._background.submit(self.router._in_background, fn, *args))

    def drain(self):
        while self._pending:
            self._pending.pop().result()
        self.router.drain()

    def close(self):
        self.drain()
        self._background.shutdown(wait=True)
        self._readers.shutdown(wait=True)

    def _observe(self, request, futures):
        agreed, value, distinct = planner.PlanningRouter._agreement(
            futures, self.settings["agreement_quorum"], self.settings.get("job_agreement_min"))
        with self._lock:
            record = self._records[request.template]
            if agreed:
                key = sandbox.canonical(request.inputs)
                if all(sandbox.canonical(e["inputs"]) != key for e in record["examples"]):
                    record["examples"].append({"inputs": request.inputs, "expected": value})
            elif distinct > 1:
                record["disagreements"] += 1
            ready = (record["program"] is None and not record.get("writing")
                     and len(record["examples"]) >= self.settings["plan_examples"]
                     and sum(a["outcome"] != "REMOTE_ERROR" for a in record["attempts"])
                     < self.settings["max_plan_attempts"])
            if ready:
                record["writing"] = True
                examples = list(record["examples"][: self.settings["plan_examples"]])
        if ready:
            try:
                attempt = self._write(request.description, examples)
                with self._lock:
                    record["attempts"].append({k: v for k, v in attempt.items() if k != "program"})
                    if attempt["outcome"] == "ADOPTED":
                        record["program"] = attempt["program"]
            finally:
                with self._lock:
                    record["writing"] = False

    def _write(self, description, examples):
        config = {**self.router.remote_config, "model": self.settings["planner_model"],
                  "max_tokens": self.settings["planner_max_tokens"]}
        inputs = examples[0]["inputs"]
        started = time.perf_counter()
        try:
            result = self.router.remote_fn(build_program_prompt(description, inputs), config,
                                           self.router.api_key)
        except Exception as exc:
            return {"outcome": "REMOTE_ERROR", "reason": type(exc).__name__}
        write_ms = (time.perf_counter() - started) * 1000
        if not result.success:
            return {"outcome": "REMOTE_ERROR", "reason": result.error, "write_ms": write_ms}
        program, reason = parse_program(result.text, inputs)
        if program is None:
            return {"outcome": "INVALID_PROGRAM", "reason": reason, "write_ms": write_ms,
                    "reply": result.text[:6000]}
        program["sha256"] = hashlib.sha256(program["code"].encode("utf-8")).hexdigest()
        passed = 0
        for example in examples:
            ok, value, _ = self.run_program(program, example["inputs"])
            passed += ok and sandbox.canonical(value) == sandbox.canonical(example["expected"])
        outcome = "ADOPTED" if passed == len(examples) else "REJECTED"
        return {"outcome": outcome, "write_ms": write_ms, "sha256": program["sha256"],
                "readings": len(program["readings"]), "code_lines": program["code"].count("\n"),
                "trial": {"examples": len(examples), "passed": passed}, "program": program,
                **({"rejected_program": program} if outcome == "REJECTED" else {})}

    def _audit(self, request, futures, served, sha):
        agreed, value, _ = planner.PlanningRouter._agreement(
            futures, self.settings["agreement_quorum"], self.settings.get("job_agreement_min"))
        if not agreed or sandbox.canonical(value) == sandbox.canonical(served):
            return
        with self._lock:
            record = self._records[request.template]
            if record["program"] is not None and record["program"]["sha256"] == sha:
                record["demotions"].append({"sha256": sha, "reason": "AUDIT_MISMATCH"})
                record["program"] = None

    def summary(self, template):
        with self._lock:
            record = self._records.get(template)
            if record is None:
                return None
            program = record["program"]
            return {"examples": len(record["examples"]), "disagreements": record["disagreements"],
                    "attempts": record["attempts"], "adopted": program is not None,
                    "program_jobs": record["jobs"], "demotions": record["demotions"],
                    "program": program}
