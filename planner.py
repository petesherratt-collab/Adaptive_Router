"""Model-written plans for multi-step jobs.

A request gives a plain-language task description and named inputs. Requests
with the same description and the same input names and types share a
*template*. Per template the router works in two stages:

1. Until a plan is adopted, each request is answered by racing the whole task
   across the roster. Afterwards every racer's answer is collected, and
   unanimous answers become job examples (inputs plus agreed answer).
2. Once enough examples exist, a planner model is asked for a step plan from
   the description and the input names alone. It sees no agreed answers. The
   plan is then run through the step pipeline on the stored examples. Only if
   it reproduces every agreed answer is it adopted. Later requests run the
   adopted plan, whose function steps can in turn be promoted to code.

No model judges a plan: adoption is by execution against agreed answers, the
same rule the fast path applies to functions. A sample of planned answers is
audited by a fresh whole-task race; if the racers agree on something else, the
plan is dropped and the template goes back to stage 1.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import statistics
from pathlib import Path
import threading
import time
import uuid

import fast_path
import pipeline
import sandbox
from shadow import should_shadow


SCHEMA_VERSION = "fast_path_task_v1"
(PLAN_ROUTE, RACE_ROUTE, NO_ANSWER) = ("plan", "race", "none")
JSON_TYPE_NAMES = {bool: "boolean", int: "number", float: "number", str: "string",
                   list: "array", dict: "object", type(None): "null"}


class TaskRequestError(ValueError):
    """The caller supplied a malformed task request."""


class TaskRequest:
    def __init__(self, description, inputs):
        self.description, self.inputs = description, inputs
        self.template = template_key(description, inputs)

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value, dict) or set(value) != {"schema_version", "description", "inputs"}:
            raise TaskRequestError("REQUEST_FIELDS_MISMATCH")
        if value["schema_version"] != SCHEMA_VERSION:
            raise TaskRequestError("REQUEST_SCHEMA_MISMATCH")
        if not isinstance(value["description"], str) or not value["description"].strip():
            raise TaskRequestError("INVALID_DESCRIPTION")
        inputs = value["inputs"]
        if not isinstance(inputs, dict) or not inputs or not all(
            isinstance(k, str) and k for k in inputs
        ):
            raise TaskRequestError("INVALID_INPUTS")
        return cls(value["description"], inputs)


def template_key(description, inputs):
    shape = {name: JSON_TYPE_NAMES.get(type(v), "other") for name, v in sorted(inputs.items())}
    payload = json.dumps([description, shape], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_task_prompt(description, inputs):
    lines = ["Carry out the task below and give its final result.", "", f"Task: {description}", "", "Inputs:"]
    lines += [f"- {name} (JSON): {json.dumps(value)}" for name, value in inputs.items()]
    lines += [
        "",
        "Reply with exactly one line: the word ANSWER, a colon, then the final "
        "result encoded as JSON. Examples of the form: "
        'ANSWER: "text"   ANSWER: 42   ANSWER: [1, 2]   ANSWER: null',
        "Give the bare final result, and write nothing after the ANSWER line.",
    ]
    return "\n".join(lines)


def build_plan_prompt(description, inputs):
    """Ask for a step plan. ``inputs`` are one request's values, shown so the
    planner can see their formats; no answer is shown."""
    lines = [
        "Plan how to compute the result of the task below as a sequence of steps.",
        "",
        f"Task: {description}",
        "",
        "Inputs (names and one example of their values):",
    ]
    lines += [f"- {name} (JSON): {json.dumps(value)}" for name, value in inputs.items()]
    lines += [
        "",
        "Each step is one of two kinds:",
        "- \"function\": its result is fully determined by its arguments under a precise rule that ordinary "
        "code could implement, such as parsing, counting, arithmetic, sorting, lookups and formatting.",
        "- \"judgement\": its result needs reading meaning from prose, such as tone, topic, language, "
        "intent, or which name or place a sentence mentions.",
        "Use judgement steps only where code could not decide. Keep each judgement step to reading one "
        "input and returning a short label or name; do every calculation and all formatting in function steps.",
        "Make function steps small. Each should do one thing that a short function of about ten lines could "
        "do: parse an input into a list, compute one number, pick one item, or format the final text. Return a "
        "simple value (a number, a string or a list), not an object that bundles several results. Several small "
        "steps are better than one large one.",
        "",
        "Each step is an object with exactly these keys:",
        "- \"id\": a short name of letters, digits and underscores, different from the input names;",
        "- \"kind\": \"function\" or \"judgement\";",
        "- \"task\": {\"spec\": ..., \"signature\": ...}. The spec is a complete, precise rule: whoever "
        "carries out the step sees only its spec, signature and argument values, never the task above. "
        "The signature is a Python line such as \"def solve(text: str, limit: int) -> list:\". "
        "Arguments and results are JSON values;",
        "- \"args\": the arguments in signature order, each {\"ref\": \"<an input name or an earlier step id>\"} "
        "or {\"value\": <a JSON literal>}.",
        "Steps may refer only to inputs and earlier steps. The final step's result must be the task's final "
        "result in exactly the requested form.",
        "",
        "Reply with JSON only, no code fence: {\"steps\": [ ... ], \"output\": \"<id of the step whose result "
        "is the final result>\"}",
    ]
    return "\n".join(lines)


_FUNCTION_NAME = re.compile(r"^def\s+\w+\s*\(")


def normalise_signature(signature):
    """Tidy slips that do not change meaning: surrounding space, a missing
    final colon, and a function name other than ``solve``."""
    if not isinstance(signature, str):
        return signature
    text = signature.strip()
    text = _FUNCTION_NAME.sub("def solve(", text, count=1)
    if text.startswith("def solve(") and not text.endswith(":"):
        text += ":"
    return text


def _normalise_steps(steps):
    if not isinstance(steps, list):
        return steps
    tidy = []
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("task"), dict):
            task = {**step["task"], "signature": normalise_signature(step["task"].get("signature"))}
            step = {**step, "task": task}
        tidy.append(step)
    return tidy


def build_refine_prompt(description, inputs, document, fast, slow, jobs):
    """Ask for a finer plan, saying which function steps became code and which
    are still answered by language models after ``jobs`` uses."""
    plan = json.dumps({"steps": document["steps"], "output": document["output"]}, indent=1)
    return (
        build_plan_prompt(description, inputs)
        + "\n\nA plan for this task is already in use and gives correct results:\n"
        + plan
        + f"\n\nAfter {jobs} uses, these function steps run as verified code and are fast: "
        + (", ".join(fast) or "none")
        + ". These function steps are still answered by language models, which is slow: "
        + ", ".join(slow)
        + ". A step becomes code sooner when it is small and returns a simple value. Revise the plan: "
        "split each slow step into smaller function steps that each do one simple thing, keep the fast "
        "steps and the judgement steps as they are where you can, and keep the final result exactly the "
        "same. Reply with the whole revised plan in the same JSON form, JSON only."
    )


def parse_plan(text, inputs):
    """Return ``(job_document, None)`` or ``(None, reason)`` for a planner reply."""
    try:
        plan = fast_path.strict_json(fast_path._unfence(text))
    except (ValueError, TypeError, RecursionError):
        return None, "PLAN_NOT_JSON"
    if not isinstance(plan, dict) or set(plan) != {"steps", "output"}:
        return None, "PLAN_FIELDS_MISMATCH"
    plan = {**plan, "steps": _normalise_steps(plan["steps"])}
    document = {
        "schema_version": pipeline.SCHEMA_VERSION,
        "inputs": inputs,
        "steps": plan["steps"],
        "output": plan["output"],
    }
    try:
        pipeline.Job.from_mapping(document)
    except pipeline.JobError as exc:
        return None, f"PLAN_INVALID:{exc}"
    return document, None


def with_inputs(document, inputs):
    return {**document, "inputs": inputs}


class TemplateStore:
    """One JSON document per task template, written atomically."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self._lock = threading.RLock()
        self._cache = {}

    def lock(self):
        return self._lock

    def get(self, key):
        with self._lock:
            if key not in self._cache:
                try:
                    self._cache[key] = json.loads((self.directory / f"{key}.json").read_text("utf-8"))
                except (OSError, ValueError):
                    return None
            return self._cache[key]

    def ensure(self, request):
        with self._lock:
            record = self.get(request.template)
            if record is None:
                record = {
                    "template": request.template,
                    "description": request.description,
                    "input_names": sorted(request.inputs),
                    "examples": [],
                    "plan": None,
                    "plan_attempts": [],
                    "demotions": [],
                    "disagreements": 0,
                }
                self._cache[request.template] = record
                self.save(request.template)
            return record

    def save(self, key):
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{key}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._cache[key], indent=1), encoding="utf-8")
            os.replace(temporary, path)


class PlanningRouter:
    def __init__(self, router, store_dir="fast_path_templates", log_path="fast_path_tasks.jsonl"):
        self.router = router
        self.settings = router.settings
        self.store = TemplateStore(store_dir)
        self.orchestrator = pipeline.Orchestrator(router, Path(log_path).with_suffix(".jobs.jsonl"))
        self.log_path = Path(log_path)
        self._background = ThreadPoolExecutor(max_workers=4)
        self._pending = []
        self._planning = set()
        self._log_lock = threading.Lock()

    # ---- hot path -------------------------------------------------------

    def handle(self, request):
        if not isinstance(request, TaskRequest):
            request = TaskRequest.from_mapping(request)
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        with self.store.lock():
            plan = self.store.ensure(request)["plan"]
        steps = None
        if plan is not None and plan.get("mode", "live") == "live":
            result = self.orchestrator.run(with_inputs(plan["document"], request.inputs))
            steps = result["steps"]
            if result["reason"] == pipeline.JOB_COMPLETED:
                with self.store.lock():
                    current = self.store.get(request.template)["plan"]
                    if current is not None and current["sha256"] == plan["sha256"]:
                        current["jobs"] = current.get("jobs", 0) + 1
                        self.store.save(request.template)
                self._submit(self._maybe_refine, request.template)
                if should_shadow(request_id, self.settings.get("plan_audit_rate", 0.0),
                                 self.settings.get("audit_salt", "")):
                    futures = self.router.start_prompt_race(
                        build_task_prompt(request.description, request.inputs))
                    self._submit(self._audit, request, futures, result["value"], plan["sha256"])
                return self._finish(request, request_id, started, result["value"], PLAN_ROUTE, None, steps)
        futures = self.router.start_prompt_race(build_task_prompt(request.description, request.inputs))
        model, value = fast_path.FastPathRouter._first_valid(futures)
        race_ms = (time.perf_counter() - started) * 1000
        with self.store.lock():
            record = self.store.get(request.template)
            if model is not None:
                record["race_ms"] = (record.get("race_ms", []) + [race_ms])[-20:]
        self._submit(self._observe, request, futures)
        if plan is not None:
            self._submit(self._shadow, request, futures, plan["sha256"])
        if model is None:
            return self._finish(request, request_id, started, None, NO_ANSWER, None, steps)
        return self._finish(request, request_id, started, value, RACE_ROUTE, model, steps)

    def _finish(self, request, request_id, started, value, route, model, steps):
        total_ms = (time.perf_counter() - started) * 1000
        self._log({
            "record_type": "task_request", "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "template": request.template, "route": route, "model": model, "total_ms": total_ms,
        })
        return {"value": value, "route": route, "model": model, "total_ms": total_ms,
                "template": request.template, "steps": steps}

    # ---- background -----------------------------------------------------

    def _submit(self, fn, *args):
        self._pending.append(self._background.submit(fn, *args))

    def drain(self):
        while self._pending:
            self._pending.pop().result()
        self.router.drain()

    def close(self):
        self.drain()
        self._background.shutdown(wait=True)
        self.orchestrator.close()

    @staticmethod
    def _agreement(futures, quorum, minimum=None):
        """Return ``(agreed, value, distinct answers)``.

        By default every valid answer must be identical, with at least
        ``quorum`` of them. With ``minimum`` set, an answer given by at least
        ``minimum`` racers, and by more racers than any other answer, counts
        as agreed even if others dissent.
        """
        answers = [f.result() for f in futures]
        valid = [a for a in answers if a["valid"]]
        counts = {}
        for answer in valid:
            key = sandbox.canonical(answer["value"])
            counts.setdefault(key, [0, answer["value"]])[0] += 1
        if len(valid) >= quorum and len(counts) == 1:
            return True, valid[0]["value"], 1
        if minimum and counts:
            ranked = sorted(counts.values(), key=lambda c: -c[0])
            if ranked[0][0] >= minimum and (len(ranked) == 1 or ranked[0][0] > ranked[1][0]):
                return True, ranked[0][1], len(counts)
        return False, None, len(counts)

    def _observe(self, request, futures):
        agreed, value, distinct = self._agreement(futures, self.settings["agreement_quorum"],
                                                   self.settings.get("job_agreement_min"))
        with self.store.lock():
            record = self.store.get(request.template)
            if agreed:
                key = sandbox.canonical(request.inputs)
                if all(sandbox.canonical(e["inputs"]) != key for e in record["examples"]):
                    record["examples"].append({"inputs": request.inputs, "expected": value})
            elif distinct > 1:
                record["disagreements"] += 1
            self.store.save(request.template)
        self._maybe_plan(request.template)

    def _new_plan(self, document, sha, **extra):
        mode = "shadow" if self.settings.get("plan_shadow", False) else "live"
        return {"document": document, "sha256": sha, "mode": mode, "jobs": 0, "shadow_ms": [],
                "adopted_at": datetime.now(timezone.utc).isoformat(), **extra}

    def _shadow(self, request, futures, plan_sha):
        """Run a shadow plan on a live job's inputs, off the answer path.

        Its function steps learn as they would on live traffic. Its answer is
        checked against the race: if the racers agree on something else, the
        plan is dropped. Once its recent runs are clearly faster than the
        race, the plan goes live.
        """
        with self.store.lock():
            plan = self.store.get(request.template)["plan"]
            if plan is None or plan["sha256"] != plan_sha:
                return
            document = plan["document"]
        started = time.perf_counter()
        result = self.orchestrator.run(with_inputs(document, request.inputs))
        shadow_ms = (time.perf_counter() - started) * 1000
        agreed, value, _ = self._agreement(futures, self.settings["agreement_quorum"],
                                           self.settings.get("job_agreement_min"))
        completed = result["reason"] == pipeline.JOB_COMPLETED
        with self.store.lock():
            record = self.store.get(request.template)
            plan = record["plan"]
            if plan is None or plan["sha256"] != plan_sha:
                return
            if agreed and (not completed or sandbox.canonical(result["value"]) != sandbox.canonical(value)):
                record["demotions"].append({"sha256": plan_sha, "reason": "SHADOW_MISMATCH"})
                record["plan"] = None
                self.store.save(request.template)
                self._log({"record_type": "plan_demotion", "template": request.template,
                           "reason": "SHADOW_MISMATCH"})
                return
            plan["jobs"] = plan.get("jobs", 0) + 1
            plan["shadow_ms"] = (plan.get("shadow_ms", []) + [shadow_ms])[-20:]
            window = self.settings.get("plan_live_window", 2)
            recent, races = plan["shadow_ms"][-window:], record.get("race_ms", [])
            if (plan["mode"] == "shadow" and len(recent) >= window and races
                    and max(recent) < self.settings.get("plan_live_ratio", 0.75) * statistics.median(races)):
                plan["mode"] = "live"
                plan["live_after_shadow_runs"] = len(plan["shadow_ms"])
                self._log({"record_type": "plan_live", "template": request.template,
                           "shadow_runs": len(plan["shadow_ms"])})
            self.store.save(request.template)
        self._maybe_refine(request.template)

    def _audit(self, request, futures, served, plan_sha):
        agreed, value, _ = self._agreement(futures, self.settings["agreement_quorum"],
                                                   self.settings.get("job_agreement_min"))
        if not agreed or sandbox.canonical(value) == sandbox.canonical(served):
            return
        with self.store.lock():
            record = self.store.get(request.template)
            if record["plan"] is None or record["plan"]["sha256"] != plan_sha:
                return
            record["demotions"].append({"sha256": plan_sha, "reason": "AUDIT_MISMATCH"})
            record["plan"] = None
            key = sandbox.canonical(request.inputs)
            if all(sandbox.canonical(e["inputs"]) != key for e in record["examples"]):
                record["examples"].append({"inputs": request.inputs, "expected": value})
            self.store.save(request.template)
        self._log({"record_type": "plan_demotion", "template": request.template})

    def _maybe_plan(self, template):
        with self.store.lock():
            record = self.store.get(template)
            if (
                record["plan"] is not None
                or template in self._planning
                or len(record["examples"]) < self.settings["plan_examples"]
                or sum(a["outcome"] != "REMOTE_ERROR" for a in record["plan_attempts"]
                       if a.get("kind") != "refine")
                >= self.settings["max_plan_attempts"]
            ):
                return
            self._planning.add(template)
            description = record["description"]
            examples = list(record["examples"])
        try:
            attempt = self._plan(description, examples)
            with self.store.lock():
                record = self.store.get(template)
                record["plan_attempts"].append({k: v for k, v in attempt.items() if k != "document"})
                if attempt["outcome"] == "ADOPTED":
                    record["plan"] = self._new_plan(attempt["document"], attempt["sha256"])
                self.store.save(template)
            self._log({"record_type": "plan_attempt", "template": template,
                       **{k: v for k, v in attempt.items() if k != "document"}})
        finally:
            with self.store.lock():
                self._planning.discard(template)

    def _step_speeds(self, document):
        """Split a plan's function steps into those promoted to code and the rest."""
        fast, slow = [], []
        for step in document["steps"]:
            if step["kind"] != "function":
                continue
            stored = self.router.store.get(
                fast_path.shape_key(step["task"]["spec"], step["task"]["signature"]))
            (fast if stored and stored["function"] else slow).append(step["id"])
        return fast, slow

    def _maybe_refine(self, template):
        """Feedback on speed: after ``refine_after_jobs`` uses, ask the planner
        to split the function steps that are still answered by models. The
        revised plan must pass the same trial before it replaces the old one."""
        with self.store.lock():
            record = self.store.get(template)
            plan = record["plan"]
            if (
                plan is None
                or template in self._planning
                or plan.get("jobs", 0) < self.settings.get("refine_after_jobs", 0)
                or not self.settings.get("max_refinements", 0)
                or sum(a.get("kind") == "refine" and a["outcome"] != "REMOTE_ERROR"
                       for a in record["plan_attempts"]) >= self.settings["max_refinements"]
            ):
                return
            fast, slow = self._step_speeds(plan["document"])
            if not slow:
                return
            self._planning.add(template)
            description, examples = record["description"], list(record["examples"])
            old_sha, jobs = plan["sha256"], plan.get("jobs", 0)
        try:
            prompt = build_refine_prompt(description, examples[0]["inputs"], plan["document"],
                                         fast, slow, jobs)
            attempt = self._plan(description, examples, prompt)
            attempt.update({"kind": "refine", "refines": old_sha, "slow_steps": slow,
                            "fast_steps": fast, "after_jobs": jobs})
            with self.store.lock():
                record = self.store.get(template)
                record["plan_attempts"].append({k: v for k, v in attempt.items() if k != "document"})
                current = record["plan"]
                if (attempt["outcome"] == "ADOPTED" and current is not None
                        and current["sha256"] == old_sha):
                    record["plan"] = self._new_plan(attempt["document"], attempt["sha256"],
                                                    refined_from=old_sha)
                self.store.save(template)
            self._log({"record_type": "plan_refinement", "template": template,
                       **{k: v for k, v in attempt.items() if k != "document"}})
        finally:
            with self.store.lock():
                self._planning.discard(template)

    def propose_plan(self, description, inputs, prompt=None):
        """Ask the planner model for a plan.

        Returns ``(document, reason, ms, refused)``. A reply the validator
        refuses is sent back once with the reason; ``refused`` keeps each
        refused reply and its reason. A provider failure is not retried.
        """
        config = {
            **self.router.remote_config,
            "model": self.settings["planner_model"],
            "max_tokens": self.settings["planner_max_tokens"],
        }
        first = prompt or build_plan_prompt(description, inputs)
        prompt = first
        started, refused = time.perf_counter(), []
        for _ in range(1 + self.settings.get("plan_retries", 1)):
            try:
                result = self.router.remote_fn(prompt, config, self.router.api_key)
            except Exception as exc:
                return None, type(exc).__name__, (time.perf_counter() - started) * 1000, refused
            if not result.success:
                return None, result.error, (time.perf_counter() - started) * 1000, refused
            document, reason = parse_plan(result.text, inputs)
            if document is not None:
                return document, None, (time.perf_counter() - started) * 1000, refused
            refused.append({"reason": reason, "reply": result.text[:6000]})
            prompt = (
                first
                + "\n\nYour previous reply was refused by the plan checker with this reason: "
                + reason
                + ". Reply again with the whole corrected plan, JSON only."
            )
        return None, refused[-1]["reason"], (time.perf_counter() - started) * 1000, refused

    def _plan(self, description, examples, prompt=None):
        checked = examples[: self.settings["plan_examples"]]
        document, reason, ms, refused = self.propose_plan(description, checked[0]["inputs"], prompt)
        attempt = {"model": self.settings["planner_model"], "plan_ms": ms, "refused": refused}
        if document is None:
            outcome = "REMOTE_ERROR" if reason and reason.startswith("OPENROUTER") else "INVALID_PLAN"
            return {**attempt, "outcome": outcome, "reason": reason}
        sha = hashlib.sha256(json.dumps(document["steps"], sort_keys=True).encode()).hexdigest()
        kinds = [s["kind"] for s in document["steps"]]
        attempt.update({"sha256": sha, "steps": len(kinds),
                        "function_steps": kinds.count("function"),
                        "judgement_steps": kinds.count("judgement")})
        # The trial runs the plan through the pipeline, which also lets its
        # function steps start learning.
        passed = 0
        for example in checked:
            result = self.orchestrator.run(with_inputs(document, example["inputs"]))
            self.router.drain()
            if (result["reason"] == pipeline.JOB_COMPLETED
                    and sandbox.canonical(result["value"]) == sandbox.canonical(example["expected"])):
                passed += 1
        outcome = "ADOPTED" if passed == len(checked) else "REJECTED"
        attempt.update({"outcome": outcome, "trial": {"examples": len(checked), "passed": passed},
                        "document": document})
        if outcome == "REJECTED":
            attempt["rejected_plan"] = {"steps": document["steps"], "output": document["output"]}
        return attempt

    def _log(self, record):
        with self._log_lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
