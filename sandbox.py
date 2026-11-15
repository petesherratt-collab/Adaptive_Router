"""Restricted execution of candidate ``solve`` functions.

A candidate is untrusted source text, usually written by a model. It is first
screened statically, then run in a separate Python process with stripped
builtins, a small module allowlist, resource limits and a wall-clock timeout.

This is defence in depth against accidents and casual misuse. It is not a
hardened security boundary: do not run adversarial code with it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import json
import subprocess
import sys
import time


ALLOWED_MODULES = (
    "math",
    "re",
    "string",
    "itertools",
    "functools",
    "collections",
    "heapq",
    "bisect",
)
ENTRY_POINT = "solve"
MAX_SOURCE_CHARS = 20_000

_BANNED_NODES = (
    ast.ClassDef,
    ast.AsyncFunctionDef,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Await,
    ast.Global,
    ast.With,
)
_TOP_LEVEL_NODES = (ast.FunctionDef, ast.Assign, ast.Import, ast.ImportFrom)


def check_source(source):
    """Return ``(ok, reason)`` for a candidate source string."""
    if not isinstance(source, str) or not source.strip():
        return False, "EMPTY_SOURCE"
    if len(source) > MAX_SOURCE_CHARS:
        return False, "SOURCE_TOO_LONG"
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return False, "SYNTAX_ERROR"

    body = list(tree.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not all(isinstance(node, _TOP_LEVEL_NODES) for node in body):
        return False, "TOP_LEVEL_STATEMENT"
    entry_points = [
        node
        for node in body
        if isinstance(node, ast.FunctionDef) and node.name == ENTRY_POINT
    ]
    if len(entry_points) != 1:
        return False, "ENTRY_POINT_MISSING"

    for node in ast.walk(tree):
        if isinstance(node, _BANNED_NODES):
            return False, "BANNED_CONSTRUCT"
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_MODULES:
                    return False, "MODULE_NOT_ALLOWED"
        if isinstance(node, ast.ImportFrom):
            if node.level or node.module not in ALLOWED_MODULES:
                return False, "MODULE_NOT_ALLOWED"
            if any(alias.name.startswith("_") or alias.name == "*" for alias in node.names):
                return False, "PRIVATE_NAME"
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return False, "PRIVATE_NAME"
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return False, "PRIVATE_NAME"
    return True, "OK"


# Runs inside the child process. Kept as text so the child needs no project
# files on its import path.
_RUNNER = r"""
import json, sys, types

payload = json.loads(sys.stdin.read())
status = {"network_isolated": False}
try:
    import os
    os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNET)
    status["network_isolated"] = True
except Exception:
    pass
try:
    import resource
    cpu = payload["cpu_seconds"]
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    memory = payload["memory_bytes"]
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
except Exception:
    pass

import builtins as _b
import importlib

ALLOWED = set(payload["allowed_modules"])
_proxies = {}

def _proxy(name):
    if name not in _proxies:
        module = importlib.import_module(name)
        public = getattr(module, "__all__", None) or [
            n for n in dir(module) if not n.startswith("_")
        ]
        _proxies[name] = types.SimpleNamespace(**{
            n: getattr(module, n)
            for n in public
            if hasattr(module, n)
            and not isinstance(getattr(module, n), types.ModuleType)
        })
    return _proxies[name]

def _import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name not in ALLOWED:
        raise ImportError(name)
    return _proxy(name)

for name in ALLOWED:
    _proxy(name)

NAMES = '''abs all any ascii bin bool chr dict divmod enumerate filter float
format frozenset hash hex int isinstance issubclass iter len list map max min
next oct ord pow range repr reversed round set slice sorted str sum tuple zip
ArithmeticError AssertionError AttributeError Exception IndexError KeyError
LookupError NotImplementedError OverflowError RecursionError RuntimeError
StopIteration TypeError ValueError ZeroDivisionError'''.split()
safe = {n: getattr(_b, n) for n in NAMES}
safe.update({"True": True, "False": False, "None": None, "__import__": _import})

namespace = {"__builtins__": safe, "__name__": "candidate"}
out = {"status": status, "results": []}
try:
    exec(compile(payload["source"], "<candidate>", "exec"), namespace)
    fn = namespace[payload["entry_point"]]
except BaseException as exc:
    out["load_error"] = type(exc).__name__
else:
    for args in payload["calls"]:
        try:
            value = fn(*args)
            json.dumps(value, allow_nan=False)
            out["results"].append({"ok": True, "value": value})
        except BaseException as exc:
            out["results"].append({"ok": False, "error": type(exc).__name__})
sys.stdout.write(json.dumps(out, allow_nan=False))
"""


@dataclass
class SandboxResult:
    ok: bool
    error: str | None = None
    results: list = field(default_factory=list)
    elapsed_ms: float = 0.0
    network_isolated: bool = False


def run_function(
    source,
    calls,
    timeout_seconds=2.0,
    cpu_seconds=2,
    memory_bytes=512 * 1024 * 1024,
):
    """Run ``solve(*args)`` for each ``args`` in ``calls``.

    ``ok`` is true when the child completed and reported one result per call.
    Each result is ``{"ok": True, "value": ...}`` or ``{"ok": False,
    "error": <exception type name>}``. Returned values have been through JSON,
    so tuples arrive as lists and non-JSON values count as errors.
    """
    started = time.perf_counter()
    accepted, reason = check_source(source)
    if not accepted:
        return SandboxResult(False, error=reason)
    payload = json.dumps(
        {
            "source": source,
            "entry_point": ENTRY_POINT,
            "calls": calls,
            "cpu_seconds": cpu_seconds,
            "memory_bytes": memory_bytes,
            "allowed_modules": list(ALLOWED_MODULES),
        }
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _RUNNER],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env={},
            cwd="/",
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(
            False,
            error="SANDBOX_TIMEOUT",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if completed.returncode != 0:
        return SandboxResult(False, error="SANDBOX_CRASHED", elapsed_ms=elapsed_ms)
    try:
        out = json.loads(completed.stdout)
    except ValueError:
        return SandboxResult(False, error="SANDBOX_OUTPUT_INVALID", elapsed_ms=elapsed_ms)
    isolated = bool(out.get("status", {}).get("network_isolated"))
    if "load_error" in out:
        return SandboxResult(
            False,
            error="LOAD_ERROR:" + out["load_error"],
            elapsed_ms=elapsed_ms,
            network_isolated=isolated,
        )
    results = out.get("results", [])
    if len(results) != len(calls):
        return SandboxResult(False, error="SANDBOX_OUTPUT_INVALID", elapsed_ms=elapsed_ms)
    return SandboxResult(
        True, results=results, elapsed_ms=elapsed_ms, network_isolated=isolated
    )


def canonical(value):
    """Strict canonical JSON text: ``True`` differs from ``1``, ``1`` from ``1.0``."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
