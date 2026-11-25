"""Write the job once: the multi-step path.

A request is a plain-language task description plus named inputs
(``fast_path_task_v1``, as for ``planner.PlanningRouter``). Per task template:

1. Until a program is adopted, each request is answered by racing the whole
   task across the roster; agreed answers become job examples, by the same
   rule the planner uses.
2. Once ``plan_examples`` examples exist, one model call (``planner_model``)
   writes the whole job from the description and one request's inputs (no
   answer is shown): a list of reading steps, each a short judgement with a
   fixed label set, and one Python function ``solve(inputs, readings)`` that
   does everything else. A reading is over one text input, or over every item
   of a list of texts (or of a text field of a list of objects), giving one
   label or a list of labels.
3. The program is run on the stored examples, its readings raced exactly as
   the planner races judgement steps. With ``program_probes`` set, it must
   also reproduce the race's agreed answers on up to that many edge-case jobs
   proposed by ``probe_model``. It is adopted only if it reproduces every
   agreed answer. At most ``max_plan_attempts`` programs are tried.

With ``write_early`` set, the first program is written (and probed) as soon as
a template is first seen, in parallel with the race; it is tried against the
examples the moment they exist. This shortens the start-up under live traffic.

Afterwards each request races only the readings, in parallel, and runs the
code in the sandbox. A ``plan_audit_rate`` sample is checked against a fresh
whole-task race; an agreed mismatch drops the program. No model judges the
code: adoption is by execution, as everywhere else in this project. With a
``store_dir``, templates and programs are kept on disk between processes.

This superseded the planning router as the multi-step path after the
write-once experiments of 2026-11-18 (README, "Write the job once").
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid

import fast_path
import planner
import sandbox
from shadow import should_shadow

PROGRAM_ROUTE = "program"
READING_KEYS = {"id", "input", "spec", "labels"}
READING_OPTIONAL = {"each", "field"}


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
        "returns one label from a fixed list. Use as few as possible, none if code can do everything. "
        "If the input is a list of texts, add \"each\": true, and if it is a list of objects whose text "
        "is under one key, add \"each\": true and \"field\": \"<that key>\": the reading is then made "
        "on every item and gives a list of labels in item order.",
        "- \"code\": Python source defining solve(inputs, readings), where inputs is a dict of the "
        "inputs above and readings maps each reading's id to its label (or list of labels). It must "
        "return the task's final result in exactly the requested form and do everything else: parsing, "
        "arithmetic, counting, rounding, lookups and formatting.",
        "",
        f"Code rules: pure Python; you may import only {modules}; no classes, no file or network access, "
        "no names beginning with an underscore; helper functions are allowed.",
        "",
        "Reply with JSON only, no code fence: {\"readings\": [{\"id\": \"<letters, digits, underscores>\", "
        "\"input\": \"<input name>\", \"spec\": \"<precise instruction that names the exact labels>\", "
        "\"labels\": [\"...\"]}], \"code\": \"<python source>\"}",
    ]
    return "\n".join(lines)


def _texts(reading, inputs):
    """The texts a reading is made on: one string, or a list for ``each``."""
    value = inputs[reading["input"]]
    if not reading.get("each"):
        return value if isinstance(value, str) else None
    if not isinstance(value, list):
        return None
    field = reading.get("field")
    items = [item.get(field) if (field and isinstance(item, dict)) else item for item in value]
    return items if all(isinstance(item, str) for item in items) else None


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
        if (not isinstance(reading, dict) or not READING_KEYS <= set(reading)
                or set(reading) - READING_KEYS - READING_OPTIONAL
                or not isinstance(reading["id"], str) or not reading["id"].isidentifier()
                or reading["id"] in seen or reading["input"] not in inputs
                or not isinstance(reading["spec"], str) or not reading["spec"].strip()
                or not isinstance(reading["labels"], list) or not reading["labels"]
                or not all(isinstance(label, str) for label in reading["labels"])
                or ("field" in reading and not isinstance(reading["field"], str))
                or _texts(reading, inputs) is None):
            return None, "PROGRAM_READINGS_INVALID"
        seen.add(reading["id"])
    accepted, reason = sandbox.check_source(fast_path._unfence(value["code"]) + "\n")
    if not accepted:
        return None, f"PROGRAM_CODE_REJECTED:{reason}"
    return {"readings": readings, "code": fast_path._unfence(value["code"]) + "\n"}, None


def build_job_probe_prompt(description, inputs, fixed, limit):
    lines = [
        "List edge-case inputs for testing a program that carries out the task below.",
        "",
        f"Task: {description}",
        "",
        "One example of the inputs:",
    ]
    lines += [f"- {name} (JSON): {json.dumps(value)}" for name, value in inputs.items()
              if name not in fixed]
    lines += [
        "",
        f"Give up to {limit} different input sets, each valid under the task's description and in the "
        "same format as the example. Each should test a case a careless program could get wrong: "
        "rounding at exactly half, ties, empty or single-item lists, values exactly on a threshold the "
        "task mentions, zero amounts, and any special case the task names. Keep each set small.",
        "",
        "Reply with one JSON array of objects, each with exactly the keys "
        + ", ".join(json.dumps(n) for n in inputs if n not in fixed) + ". Reply with the JSON only.",
    ]
    return "\n".join(lines)


def parse_job_probes(text, inputs, fixed, limit):
    """Valid, distinct probe input sets of the example's shape, prose inputs
    filled in from the example."""
    try:
        value = fast_path.strict_json(fast_path._unfence(text))
    except (ValueError, TypeError, RecursionError):
        return []
    if not isinstance(value, list):
        return []
    wanted = {n for n in inputs if n not in fixed}
    kinds = {n: planner.JSON_TYPE_NAMES.get(type(v)) for n, v in inputs.items()}
    probes, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or set(item) != wanted:
            continue
        if any(planner.JSON_TYPE_NAMES.get(type(item[n])) != kinds[n] for n in wanted):
            continue
        probe = {n: (inputs[n] if n in fixed else item[n]) for n in inputs}
        key = sandbox.canonical(probe)
        if key not in seen:
            seen.add(key)
            probes.append(probe)
    return probes[:limit]


def _new_record(request):
    return {"template": request.template, "description": request.description,
            "input_names": sorted(request.inputs), "examples": [], "program": None,
            "candidate": None, "attempts": [], "demotions": [], "disagreements": 0, "jobs": 0}


class WriteOnceRouter:
    def __init__(self, router, store_dir=None):
        self.router = router
        self.settings = router.settings
        self.store_dir = Path(store_dir) if store_dir else None
        self._records = {}
        self._busy = {}  # template -> "writing" | "early"; not persisted
        self._width = {}  # reading key -> agreement streak and wins (adaptive_width)
        self._lock = threading.RLock()
        self._background = ThreadPoolExecutor(max_workers=4)
        self._readers = ThreadPoolExecutor(max_workers=8)
        self._items = ThreadPoolExecutor(max_workers=32)
        self._pending = []

    # ---- store ----------------------------------------------------------

    def _record(self, request):
        with self._lock:
            record = self._records.get(request.template)
            if record is None and self.store_dir is not None:
                path = self.store_dir / f"{request.template}.json"
                try:
                    record = json.loads(path.read_text("utf-8"))
                except (OSError, ValueError):
                    record = None
            created = record is None
            if created:
                record = _new_record(request)
            self._records[request.template] = record
            if created:
                self._save(request.template)
            return record, created

    def _save(self, template):
        if self.store_dir is None:
            return
        with self._lock:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            path = self.store_dir / f"{template}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._records[template], indent=1), encoding="utf-8")
            os.replace(temporary, path)

    # ---- hot path -------------------------------------------------------

    def handle(self, request):
        if not isinstance(request, planner.TaskRequest):
            request = planner.TaskRequest.from_mapping(request)
        started = time.perf_counter()
        record, created = self._record(request)
        with self._lock:
            program = record["program"]
        if created and program is None and self.settings.get("write_early"):
            with self._lock:
                self._busy[request.template] = "early"
            self._submit(self._early, request)
        if program is not None:
            ok, value, readings, uncertain = self.run_program_flagged(program, request.inputs)
            if ok:
                with self._lock:
                    record["jobs"] += 1
                request_id = str(uuid.uuid4())
                if should_shadow(request_id, self.settings.get("plan_audit_rate", 0.0),
                                 self.settings.get("audit_salt", "")):
                    futures = self.router.start_prompt_race(
                        planner.build_task_prompt(request.description, request.inputs))
                    self._submit(self._audit, request, futures, value, program["sha256"])
                return self._finish(started, value, PROGRAM_ROUTE, None, readings, uncertain)
        futures = self.router.start_prompt_race(planner.build_task_prompt(request.description, request.inputs))
        model, value, uncertain = self._race_answer(futures)
        self._submit(self._observe, request, futures)
        if model is None:
            return self._finish(started, None, planner.NO_ANSWER, None, None)
        return self._finish(started, value, planner.RACE_ROUTE, model, None, uncertain)

    def _race_answer(self, futures):
        """First valid whole-task answer; with ``uncertainty_gate``, also wait
        for a second and flag the answer if they differ. With
        ``decision: "majority"``, wait for every racer and take the majority."""
        if self.settings.get("decision") == "majority":
            d = fast_path.decide(futures, "majority")
            return d["model"] if d["ok"] else None, d["value"], d["uncertain"]
        if not self.settings.get("uncertainty_gate"):
            model, value = fast_path.FastPathRouter._first_valid(futures)
            return model, value, False
        first = None
        for future in as_completed(futures):
            answer = future.result()
            if not answer["valid"]:
                continue
            if first is None:
                first = answer
                continue
            return first["model"], first["value"], sandbox.canonical(answer["value"]) != sandbox.canonical(first["value"])
        if first is None:
            return None, None, False
        return first["model"], first["value"], True

    def _finish(self, started, value, route, model, readings, uncertain=False):
        return {"value": value, "route": route, "model": model, "readings": readings,
                "uncertain": uncertain, "total_ms": (time.perf_counter() - started) * 1000}

    def _read(self, spec, text):
        return self.router.handle({
            "schema_version": fast_path.SCHEMA_VERSION,
            "task": {"spec": spec, "signature": "def solve(text: str) -> str:"},
            "args": [text],
        }, learn=False)

    # Readings with the optional fixes of 2026-11-19: ``batch_readings`` (one
    # race reads every item of a list), ``uncertainty_gate`` (wait for a
    # second answer and flag disagreement) and ``adaptive_width`` (race fewer
    # models on a reading that keeps agreeing).

    def _width_models(self, key):
        models = list(self.settings["race_models"])
        width = self.settings.get("adaptive_width")
        if not width:
            return models
        with self._lock:
            stats = self._width.setdefault(key, {"streak": 0, "wins": {}})
            if stats["streak"] < width["after"]:
                return models
            ranked = sorted(models, key=lambda m: (-stats["wins"].get(m, 0), models.index(m)))
        return ranked[: max(2, width["width"])]

    def _note_width(self, key, futures, winner):
        """Background: wait for every racer, then update the agreement streak
        and win counts that ``_width_models`` uses."""
        answers = [f.result() for f in futures]
        valid = [a for a in answers if a["valid"]]
        agreed = len(valid) >= 2 and len({sandbox.canonical(a["value"]) for a in valid}) == 1
        with self._lock:
            stats = self._width.setdefault(key, {"streak": 0, "wins": {}})
            stats["streak"] = stats["streak"] + 1 if agreed else 0
            if winner:
                stats["wins"][winner] = stats["wins"].get(winner, 0) + 1

    def _race_reading(self, spec, signature, arg, check):
        """Race one reading. Returns ``(ok, value, uncertain)``. An answer
        counts only if ``check`` accepts it."""
        key = hashlib.sha256(json.dumps([spec, signature]).encode()).hexdigest()
        prompt = fast_path.build_answer_prompt(spec, signature, [arg])
        models = self._width_models(key)
        futures = {self.router._pool().submit(self.router._ask, m, prompt): m for m in models}
        if self.settings.get("decision") == "majority":
            d = fast_path.decide(futures, "majority", check)
            if self.settings.get("adaptive_width"):
                self._submit(self._note_width, key, list(futures), d["model"])
            return (True, d["value"], d["uncertain"]) if d["ok"] else (False, None, False)
        gate = self.settings.get("uncertainty_gate")
        first = second = None
        winner = None
        for future in as_completed(futures):
            answer = future.result()
            if not (answer["valid"] and check(answer["value"])):
                continue
            if first is None:
                first, winner = answer["value"], answer["model"]
                if not gate:
                    break
            else:
                second = answer["value"]
                break
        if self.settings.get("adaptive_width"):
            self._submit(self._note_width, key, list(futures), winner)
        if first is None:
            return False, None, False
        uncertain = bool(gate) and (second is None or sandbox.canonical(second) != sandbox.canonical(first))
        return True, first, uncertain

    def _reading_value(self, reading, texts):
        """``(ok, value, uncertain)`` for one reading of a program."""
        labels = set(reading["labels"])
        fixes = any(self.settings.get(k) for k in ("batch_readings", "uncertainty_gate", "adaptive_width")) \
            or self.settings.get("decision") == "majority"
        if not reading.get("each"):
            if not fixes:
                result = self._read(reading["spec"], texts)
                return result["route"] != "none", result["value"], False
            return self._race_reading(reading["spec"], "def solve(text: str) -> str:", texts,
                                      lambda v: isinstance(v, str))
        if self.settings.get("batch_readings"):
            spec = (reading["spec"] + " Apply this to every text in the list, in order, and return a list "
                    "with exactly one label per text.")
            return self._race_reading(
                spec, "def solve(texts: list) -> list:", texts,
                lambda v: isinstance(v, list) and len(v) == len(texts) and all(x in labels for x in v))
        if not fixes:
            results = list(self._items.map(lambda t: self._read(reading["spec"], t), texts))
            if any(r["route"] == "none" for r in results):
                return False, None, False
            return True, [r["value"] for r in results], False
        results = list(self._items.map(
            lambda t: self._race_reading(reading["spec"], "def solve(text: str) -> str:", t,
                                         lambda v: isinstance(v, str)), texts))
        if not all(ok for ok, _, _ in results):
            return False, None, False
        return True, [v for _, v, _ in results], any(u for _, _, u in results)

    def run_program(self, program, inputs, background=False):
        """Race every reading in parallel, then run the code. Returns
        ``(ok, value, readings)``; see ``run_program_flagged``."""
        ok, value, readings, _ = self.run_program_flagged(program, inputs, background)
        return ok, value, readings

    def run_program_flagged(self, program, inputs, background=False):
        """As ``run_program``, plus whether any reading was uncertain (racers
        disagreed, with ``uncertainty_gate``). ``background=True`` (trials and
        probes) puts the races on the background pool."""
        def read(reading):
            texts = _texts(reading, inputs)
            if texts is None:
                return reading["id"], (False, None, False)
            if background:
                with self.router.background_context():
                    return reading["id"], self._reading_value(reading, texts)
            return reading["id"], self._reading_value(reading, texts)

        readings, uncertain = {}, False
        for reading_id, (ok, value, flag) in self._readers.map(read, program["readings"]):
            if not ok:
                return False, None, readings, uncertain
            readings[reading_id] = value
            uncertain = uncertain or flag
        run = sandbox.run_function(program["code"], [[inputs, readings]],
                                   self.settings["sandbox_timeout_seconds"])
        if not (run.ok and run.results[0]["ok"]):
            return False, None, readings, uncertain
        return True, run.results[0]["value"], readings, uncertain

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
        self._items.shutdown(wait=True)

    def _attempts_left(self, record):
        used = sum(a["outcome"] != "REMOTE_ERROR" for a in record["attempts"])
        return used < self.settings["max_plan_attempts"]

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
            self._save(request.template)
            ready = (record["program"] is None and request.template not in self._busy
                     and len(record["examples"]) >= self.settings["plan_examples"]
                     and self._attempts_left(record))
            if not ready:
                return
            self._busy[request.template] = "writing"
            examples = list(record["examples"][: self.settings["plan_examples"]])
            candidate, record["candidate"] = record["candidate"], None
        try:
            if candidate is not None:
                attempt = self._judge_candidate(candidate, examples)
            else:
                attempt = self._write(request.description, examples)
            self._record_attempt(request.template, attempt)
        finally:
            with self._lock:
                self._busy.pop(request.template, None)

    def _record_attempt(self, template, attempt):
        with self._lock:
            record = self._records[template]
            record["attempts"].append({k: v for k, v in attempt.items() if k != "program"})
            if attempt["outcome"] == "ADOPTED":
                record["program"] = attempt["program"]
            self._save(template)

    def _early(self, request):
        """Write and probe the first program at once, without examples. It is
        tried against the examples when they exist (in ``_observe``)."""
        try:
            attempt = self._compose(request.description, request.inputs)
            if attempt.get("program") is not None and self.settings.get("program_probes", 0):
                attempt["probes"] = self._probe(request.description, request.inputs, attempt["program"])
            attempt["early"] = True
            with self._lock:
                record = self._records[request.template]
                if attempt.get("program") is None or (attempt.get("probes") or {}).get("failed"):
                    if (attempt.get("probes") or {}).get("failed"):
                        attempt.update({"outcome": "REJECTED", "rejected_program": attempt["program"]})
                    record["attempts"].append({k: v for k, v in attempt.items() if k != "program"})
                else:
                    record["candidate"] = attempt
                self._save(request.template)
        finally:
            with self._lock:
                self._busy.pop(request.template, None)
            # Examples may already be waiting for this candidate.
            self._try_candidate(request)

    def _try_candidate(self, request):
        with self._lock:
            record = self._records[request.template]
            if (record["program"] is not None or record["candidate"] is None
                    or request.template in self._busy
                    or len(record["examples"]) < self.settings["plan_examples"]):
                return
            self._busy[request.template] = "writing"
            examples = list(record["examples"][: self.settings["plan_examples"]])
            candidate, record["candidate"] = record["candidate"], None
        try:
            self._record_attempt(request.template, self._judge_candidate(candidate, examples))
        finally:
            with self._lock:
                self._busy.pop(request.template, None)

    def _judge_candidate(self, candidate, examples):
        passed = self._trial(candidate["program"], examples)
        outcome = "ADOPTED" if passed == len(examples) else "REJECTED"
        return {**candidate, "outcome": outcome, "trial": {"examples": len(examples), "passed": passed},
                **({"rejected_program": candidate["program"]} if outcome == "REJECTED" else {})}

    def _compose(self, description, inputs):
        """One model call for a program. Returns an attempt dict with a
        ``program`` or a failure outcome."""
        config = {**self.router.remote_config, "model": self.settings["planner_model"],
                  "max_tokens": self.settings["planner_max_tokens"]}
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
        return {"outcome": "WRITTEN", "write_ms": write_ms, "sha256": program["sha256"],
                "readings": len(program["readings"]), "code_lines": program["code"].count("\n"),
                "probes": None, "program": program}

    def _trial(self, program, examples):
        passed = 0
        for example in examples:
            ok, value, _ = self.run_program(program, example["inputs"], background=True)
            passed += ok and sandbox.canonical(value) == sandbox.canonical(example["expected"])
        return passed

    def _write(self, description, examples):
        attempt = self._compose(description, examples[0]["inputs"])
        program = attempt.get("program")
        if program is None:
            return attempt
        passed = self._trial(program, examples)
        outcome = "ADOPTED" if passed == len(examples) else "REJECTED"
        if outcome == "ADOPTED" and self.settings.get("program_probes", 0):
            attempt["probes"] = self._probe(description, examples[0]["inputs"], program)
            if attempt["probes"]["failed"]:
                outcome = "REJECTED"
        attempt.update({"outcome": outcome, "trial": {"examples": len(examples), "passed": passed}})
        if outcome == "REJECTED":
            attempt["rejected_program"] = program
        return attempt

    def _probe(self, description, inputs, program):
        """Edge-case jobs: the probe model proposes inputs (prose inputs held
        at the example's values), the whole-task race answers them, and the
        program must reproduce every agreed answer. No model judges the
        program; the probes only add agreed examples."""
        limit = self.settings["program_probes"]
        fixed = sorted({r["input"] for r in program["readings"]})
        summary = {"proposed": 0, "agreed": 0, "failed": 0, "error": None, "failures": []}
        if not [n for n in inputs if n not in fixed]:
            summary["error"] = "NO_PROBE_INPUTS"
            return summary
        config = {**self.router.remote_config, "model": self.settings["probe_model"],
                  "max_tokens": self.settings["probe_max_tokens"]}
        try:
            result = self.router.remote_fn(build_job_probe_prompt(description, inputs, fixed, limit),
                                           config, self.router.api_key)
        except Exception as exc:
            summary["error"] = type(exc).__name__
            return summary
        if not result.success:
            summary["error"] = result.error
            return summary
        probes = parse_job_probes(result.text, inputs, fixed, limit)
        summary["proposed"] = len(probes)
        races = [self.router.start_prompt_race(planner.build_task_prompt(description, p)) for p in probes]
        for probe, futures in zip(probes, races):
            agreed, value, _ = planner.PlanningRouter._agreement(
                futures, self.settings["agreement_quorum"], self.settings.get("job_agreement_min"))
            if not agreed:
                continue
            summary["agreed"] += 1
            ok, got, _ = self.run_program(program, probe, background=True)
            if not (ok and sandbox.canonical(got) == sandbox.canonical(value)):
                summary["failed"] += 1
                summary["failures"].append({"inputs": probe, "expected": value, "got": got})
        return summary

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
                self._save(request.template)

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
