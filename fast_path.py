"""Time-first fast path for repeated single-step tasks.

A request names a task shape (a natural-language spec plus a ``solve``
signature) and supplies arguments. The router answers in one of two ways:

* code: a previously promoted function for this shape runs in the sandbox;
* model: the request is raced across several remote models and the first
  parseable answer is returned.

Nothing slow sits in front of the answer. After the answer is returned, a
background step collects every racer's answer, turns unanimous agreement into
a stored example, and may ask a model to write a function for the shape. A
function is promoted only by execution against stored examples; no model
judges a candidate. Promotion is conformance with those examples, not proof of
correctness.
"""

from __future__ import annotations

import ast
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid

import remote
import sandbox
from shadow import should_shadow


SCHEMA_VERSION = "fast_path_request_v1"
(
    CODE_FAST_PATH,
    MODEL_RACE_WON,
    RACE_NO_VALID_ANSWER,
) = ("CODE_FAST_PATH", "MODEL_RACE_WON", "RACE_NO_VALID_ANSWER")
SOURCE_CALLER, SOURCE_AGREEMENT = "caller", "model_agreement"
_SIGNATURE = re.compile(r"^def solve\(.*\)(\s*->\s*.+)?:$")
_FENCE = re.compile(r"^```[A-Za-z0-9_-]*\n(.*?)\n?```$", re.DOTALL)


class FastPathRequestError(ValueError):
    """The caller supplied a malformed fast-path request."""


def _reject_constant(name):
    raise ValueError(name)


def _unique_object(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def strict_json(text):
    return json.loads(
        text, parse_constant=_reject_constant, object_pairs_hook=_unique_object
    )


def _unfence(text):
    stripped = text.strip()
    match = _FENCE.match(stripped)
    return match.group(1).strip() if match else stripped


_ANSWER_LINE = re.compile(r"^\s*ANSWER:(.*)$", re.MULTILINE)


def parse_answer(text):
    """Return ``(ok, value)`` for a model answer.

    The answer is the JSON value on the last ``ANSWER:`` line. A reply that is
    nothing but one JSON value is also accepted. Anything else is unusable;
    no value is ever dug out of surrounding prose.
    """
    marked = _ANSWER_LINE.findall(text)
    candidate = marked[-1].strip() if marked else _unfence(text)
    try:
        return True, strict_json(candidate)
    except (ValueError, TypeError, RecursionError):
        return False, None


def shape_key(spec, signature):
    payload = json.dumps([spec, signature], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _valid_examples(value):
    if not isinstance(value, list):
        raise FastPathRequestError("INVALID_EXAMPLES")
    examples = []
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"args", "expected"}
            or not isinstance(item["args"], list)
        ):
            raise FastPathRequestError("INVALID_EXAMPLES")
        examples.append({"args": item["args"], "expected": item["expected"]})
    return examples


class FastPathRequest:
    def __init__(self, spec, signature, args, examples):
        self.spec, self.signature = spec, signature
        self.args, self.examples = args, examples
        self.shape = shape_key(spec, signature)

    @classmethod
    def from_mapping(cls, value):
        if (
            not isinstance(value, dict)
            or not {"schema_version", "task", "args"} <= set(value)
            or not set(value) <= {"schema_version", "task", "args", "examples"}
        ):
            raise FastPathRequestError("REQUEST_FIELDS_MISMATCH")
        if value["schema_version"] != SCHEMA_VERSION:
            raise FastPathRequestError("REQUEST_SCHEMA_MISMATCH")
        task = value["task"]
        if not isinstance(task, dict) or set(task) != {"spec", "signature"}:
            raise FastPathRequestError("TASK_FIELDS_MISMATCH")
        spec, signature = task["spec"], task["signature"]
        if not isinstance(spec, str) or not spec.strip():
            raise FastPathRequestError("INVALID_SPEC")
        if not isinstance(signature, str) or not _SIGNATURE.match(signature):
            raise FastPathRequestError("INVALID_SIGNATURE")
        try:
            ast.parse(signature + "\n    pass\n")
        except SyntaxError as exc:
            raise FastPathRequestError("INVALID_SIGNATURE") from exc
        if not isinstance(value["args"], list):
            raise FastPathRequestError("INVALID_ARGS")
        return cls(spec, signature, value["args"], _valid_examples(value.get("examples", [])))


def load_fast_path_request(path):
    try:
        document = strict_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FastPathRequestError("REQUEST_UNREADABLE") from exc
    return FastPathRequest.from_mapping(document)


def build_answer_prompt(spec, signature, args):
    if args:
        arguments = "\n".join(
            f"Argument {index} (JSON): {json.dumps(value)}"
            for index, value in enumerate(args, start=1)
        )
    else:
        arguments = "The function takes no arguments."
    return (
        "Work out what the function described below returns for the given "
        "arguments.\n\n"
        f"Specification: {spec}\n"
        f"Signature: {signature}\n"
        f"{arguments}\n\n"
        "Reply with exactly one line: the word ANSWER, a colon, then the "
        "return value encoded as JSON. Examples of the form: "
        'ANSWER: "text"   ANSWER: 42   ANSWER: [1, 2]   ANSWER: null\n'
        "Give the bare return value. Do not wrap it in an object, do not "
        "repeat the arguments, and write nothing after the ANSWER line."
    )


def build_synthesis_prompt(spec, signature):
    modules = ", ".join(sandbox.ALLOWED_MODULES)
    return (
        "Write a Python function that implements this specification.\n\n"
        f"Specification: {spec}\n"
        f"Signature: {signature}\n\n"
        "Rules: the function must be named solve and be pure. Arguments and "
        "the return value are JSON values. You may define helper functions. "
        f"You may import only: {modules}. No classes, no file or network "
        "access, no names beginning with an underscore.\n"
        "Reply with the Python source only."
    )


class ShapeStore:
    """One JSON document per task shape, written atomically."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self._lock = threading.RLock()
        self._cache = {}

    def _path(self, shape):
        return self.directory / f"{shape}.json"

    def get(self, shape):
        with self._lock:
            if shape not in self._cache:
                try:
                    self._cache[shape] = json.loads(
                        self._path(shape).read_text(encoding="utf-8")
                    )
                except (OSError, ValueError):
                    return None
            return self._cache[shape]

    def ensure(self, request):
        with self._lock:
            record = self.get(request.shape)
            if record is None:
                record = {
                    "shape": request.shape,
                    "spec": request.spec,
                    "signature": request.signature,
                    "examples": [],
                    "function": None,
                    "synthesis_attempts": [],
                    "demotions": [],
                    "disagreements": 0,
                    "example_conflicts": 0,
                }
                self._cache[request.shape] = record
                self.save(request.shape)
            return record

    def save(self, shape):
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self._path(shape).with_suffix(".tmp")
            temporary.write_text(
                json.dumps(self._cache[shape], indent=1), encoding="utf-8"
            )
            os.replace(temporary, self._path(shape))

    def shapes(self):
        with self._lock:
            names = {path.stem for path in self.directory.glob("*.json")}
            return [self.get(name) for name in sorted(names | set(self._cache))]

    def lock(self):
        return self._lock


def add_example(record, args, expected, source):
    """Add one example. Return ``"added"``, ``"duplicate"`` or ``"conflict"``.

    Caller-supplied examples win. A model-agreement example that contradicts a
    stored model-agreement example removes it and is not stored either.
    """
    key = sandbox.canonical(args)
    for index, existing in enumerate(record["examples"]):
        if sandbox.canonical(existing["args"]) != key:
            continue
        if sandbox.canonical(existing["expected"]) == sandbox.canonical(expected):
            if source == SOURCE_CALLER:
                existing["source"] = SOURCE_CALLER
            return "duplicate"
        record["example_conflicts"] += 1
        if source == SOURCE_CALLER:
            record["examples"][index] = {
                "args": args, "expected": expected, "source": source
            }
        elif existing["source"] != SOURCE_CALLER:
            del record["examples"][index]
        return "conflict"
    record["examples"].append({"args": args, "expected": expected, "source": source})
    return "added"


def gate(source, examples, minimum_examples, timeout_seconds=2.0):
    """Decide by execution alone whether ``source`` reproduces ``examples``.

    Returns ``(passed, detail)``. No model is consulted and the candidate's
    author never sees the examples.
    """
    accepted, reason = sandbox.check_source(source)
    if not accepted:
        return False, {"reason": "STATIC_REJECTED", "static": reason}
    if len(examples) < minimum_examples:
        return False, {"reason": "TOO_FEW_EXAMPLES", "examples": len(examples)}
    run = sandbox.run_function(
        source, [example["args"] for example in examples], timeout_seconds
    )
    if not run.ok:
        return False, {"reason": "EXECUTION_FAILED", "error": run.error}
    passed = sum(
        1
        for example, result in zip(examples, run.results)
        if result["ok"]
        and sandbox.canonical(result["value"]) == sandbox.canonical(example["expected"])
    )
    detail = {
        "reason": "PASS" if passed == len(examples) else "EXAMPLE_MISMATCH",
        "examples": len(examples),
        "passed": passed,
    }
    return passed == len(examples), detail


class FastPathRouter:
    def __init__(
        self,
        config,
        store_dir="fast_path_store",
        log_path="fast_path_runs.jsonl",
        remote_fn=remote.generate,
        api_key=None,
    ):
        self.remote_config = config["remote"]
        self.settings = config["fast_path"]
        if not self.settings["race_models"]:
            raise ValueError("fast_path.race_models must not be empty")
        self.store = ShapeStore(store_dir)
        self.log_path = Path(log_path)
        self.remote_fn = remote_fn
        self.api_key = (
            api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        )
        self._models = ThreadPoolExecutor(
            max_workers=max(4, 4 * len(self.settings["race_models"]))
        )
        self._background = ThreadPoolExecutor(max_workers=4)
        self._pending = []
        self._synthesising = set()
        self._log_lock = threading.Lock()

    # ---- hot path -------------------------------------------------------

    def handle(self, request):
        if not isinstance(request, FastPathRequest):
            request = FastPathRequest.from_mapping(request)
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        with self.store.lock():
            record = self.store.ensure(request)
            changed = [
                add_example(record, e["args"], e["expected"], SOURCE_CALLER)
                for e in request.examples
            ]
            if any(outcome != "duplicate" for outcome in changed):
                self.store.save(request.shape)
            function = record["function"]

        log = {
            "record_type": "fast_path_request",
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "shape": request.shape,
            "code": {"attempted": False},
        }
        if function is not None:
            run = sandbox.run_function(
                function["source"],
                [request.args],
                self.settings["sandbox_timeout_seconds"],
            )
            succeeded = run.ok and run.results[0]["ok"]
            log["code"] = {
                "attempted": True,
                "ok": succeeded,
                "ms": run.elapsed_ms,
                "function_sha256": function["sha256"],
            }
            if succeeded:
                value = run.results[0]["value"]
                audited = should_shadow(
                    request_id,
                    self.settings["audit_sample_rate"],
                    self.settings["audit_salt"],
                )
                if audited:
                    futures = self._start_race(request)
                    self._submit(self._observe, request, futures, request_id)
                return self._finish(
                    log, started, value, "code", CODE_FAST_PATH, audited=audited
                )
            self._demote(request.shape, "RUNTIME_FAILURE")

        futures = self._start_race(request)
        winner, value = self._first_valid(futures)
        self._submit(self._observe, request, futures, request_id)
        if winner is None:
            return self._finish(log, started, None, "none", RACE_NO_VALID_ANSWER)
        return self._finish(log, started, value, "model", MODEL_RACE_WON, model=winner)

    def _finish(self, log, started, value, route, reason, model=None, audited=False):
        total_ms = (time.perf_counter() - started) * 1000
        log["decision"] = {
            "route": route,
            "reason": reason,
            "model": model,
            "audited": audited,
            "total_ms": total_ms,
        }
        self._log(log)
        return {
            "value": value,
            "text": "" if route == "none" else json.dumps(value),
            "route": route,
            "reason": reason,
            "model": model,
            "shape": log["shape"],
            "total_ms": total_ms,
        }

    def _start_race(self, request):
        prompt = build_answer_prompt(request.spec, request.signature, request.args)
        return {
            self._models.submit(self._ask, model, prompt): model
            for model in self.settings["race_models"]
        }

    def _ask(self, model, prompt):
        try:
            result = self.remote_fn(
                prompt,
                {
                    **self.remote_config,
                    "model": model,
                    "max_tokens": self.settings["answer_max_tokens"],
                },
                self.api_key,
            )
        except Exception as exc:  # a racer must never take the request down
            return {"model": model, "success": False, "valid": False,
                    "error": type(exc).__name__, "total_ms": None}
        valid, value = parse_answer(result.text) if result.success else (False, None)
        return {
            "model": model,
            "success": result.success,
            "valid": valid,
            "value": value,
            "error": result.error,
            "total_ms": result.total_ms,
        }

    @staticmethod
    def _first_valid(futures):
        remaining = set(futures)
        while remaining:
            done, remaining = wait(remaining, return_when=FIRST_COMPLETED)
            valid = [f.result() for f in done if f.result()["valid"]]
            if valid:
                # Ties inside one wake-up go to the faster reported call.
                best = min(valid, key=lambda r: r["total_ms"] or 0)
                return best["model"], best["value"]
        return None, None

    # ---- background -----------------------------------------------------

    def _submit(self, fn, *args):
        self._pending.append(self._background.submit(fn, *args))

    def drain(self):
        """Wait for background observation and synthesis to finish."""
        while self._pending:
            self._pending.pop().result()

    def close(self):
        """Finish background work and release worker threads."""
        self.drain()
        self._models.shutdown(wait=True)
        self._background.shutdown(wait=True)

    def _observe(self, request, futures, request_id):
        answers = [future.result() for future in futures]
        valid = [a for a in answers if a["valid"]]
        distinct = {sandbox.canonical(a["value"]) for a in valid}
        agreed = len(valid) >= self.settings["agreement_quorum"] and len(distinct) == 1
        with self.store.lock():
            record = self.store.get(request.shape)
            outcome = None
            if agreed:
                outcome = add_example(
                    record, request.args, valid[0]["value"], SOURCE_AGREEMENT
                )
            elif len(distinct) > 1:
                record["disagreements"] += 1
            self.store.save(request.shape)
            function = record["function"]
        self._log(
            {
                "record_type": "fast_path_observation",
                "request_id": request_id,
                "shape": request.shape,
                "models": [
                    {k: a.get(k) for k in ("model", "success", "valid", "error", "total_ms")}
                    for a in answers
                ],
                "distinct_valid_answers": len(distinct),
                "agreed": agreed,
                "example": outcome,
            }
        )
        if function is not None:
            if agreed:
                self._recheck(request.shape, function)
            return
        self._maybe_synthesise(request.shape)

    def _recheck(self, shape, function):
        with self.store.lock():
            examples = list(self.store.get(shape)["examples"])
        passed, _ = gate(
            function["source"], examples, 1, self.settings["sandbox_timeout_seconds"]
        )
        if not passed:
            self._demote(shape, "EXAMPLE_MISMATCH")
            self._maybe_synthesise(shape)

    def _demote(self, shape, reason):
        with self.store.lock():
            record = self.store.get(shape)
            if record["function"] is None:
                return
            record["demotions"].append(
                {"sha256": record["function"]["sha256"], "reason": reason}
            )
            record["function"] = None
            self.store.save(shape)
        self._log({"record_type": "fast_path_demotion", "shape": shape, "reason": reason})

    def _maybe_synthesise(self, shape):
        with self.store.lock():
            record = self.store.get(shape)
            if (
                not self.settings.get("synthesis_enabled", True)
                or record["function"] is not None
                or shape in self._synthesising
                or len(record["examples"]) < self.settings["min_gate_examples"]
                or sum(
                    attempt["outcome"] != "REMOTE_ERROR"
                    for attempt in record["synthesis_attempts"]
                )
                >= self.settings["max_synthesis_attempts"]
            ):
                return
            self._synthesising.add(shape)
            spec, signature = record["spec"], record["signature"]
        try:
            attempt = self._synthesise(shape, spec, signature)
        finally:
            with self.store.lock():
                self._synthesising.discard(shape)
        self._log({"record_type": "fast_path_synthesis", "shape": shape, **attempt})

    def _synthesise(self, shape, spec, signature):
        model = self.settings["synthesis_model"]
        config = {
            **self.remote_config,
            "model": model,
            "max_tokens": self.settings["synthesis_max_tokens"],
        }
        started = time.perf_counter()
        try:
            result = self.remote_fn(
                build_synthesis_prompt(spec, signature), config, self.api_key
            )
        except Exception as exc:
            result = remote.RemoteResult(False, error=type(exc).__name__)
        attempt = {"model": model, "outcome": "REMOTE_ERROR", "error": result.error}
        source = None
        if result.success:
            source = _unfence(result.text) + "\n"
        with self.store.lock():
            record = self.store.get(shape)
            if source is not None:
                passed, detail = gate(
                    source,
                    list(record["examples"]),
                    self.settings["min_gate_examples"],
                    self.settings["sandbox_timeout_seconds"],
                )
                attempt = {
                    "model": model,
                    "outcome": "PROMOTED" if passed else "REJECTED",
                    "gate": detail,
                }
                if passed:
                    record["function"] = {
                        "source": source,
                        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                        "model": model,
                        "promoted_at": datetime.now(timezone.utc).isoformat(),
                        "gate": detail,
                    }
            attempt["ms"] = (time.perf_counter() - started) * 1000
            record["synthesis_attempts"].append(attempt)
            self.store.save(shape)
        return attempt

    def _log(self, record):
        with self._log_lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def render_status(store):
    lines = []
    for record in store.shapes():
        function = record["function"]
        state = f"code {function['sha256'][:12]}" if function else "model race"
        lines.append(
            f"{record['shape'][:12]}  {state:<18}  examples={len(record['examples'])}"
            f"  attempts={len(record['synthesis_attempts'])}"
            f"  demotions={len(record['demotions'])}"
            f"  disagreements={record['disagreements']}"
            f"  {record['signature']}"
        )
    return "\n".join(lines) or "No task shapes recorded."
