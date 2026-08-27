"""Deterministic, task-specific validators used by the live router.

Scope discipline
----------------

These validators gate live routing decisions. They are deliberately weaker
than the benchmark oracle in `run_benchmark.py` / `run_oos_validation.py`,
which compares output against frozen expected values.

A validator here may establish only:

- syntax validity (does the output parse as JSON);
- schema conformity limited to required-key presence;
- coarse output shape.

It may not establish semantic correctness, and it never checks value types
unless an explicit deterministic schema is supplied. Every applicable result
therefore records what was actually checked, so a run log can never be read
as a stronger guarantee than the validator made. See BUILD_HISTORY.md,
2026-08-27.
"""

from dataclasses import dataclass
import json
import re

PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"

INVALID_JSON = "INVALID_JSON"
REQUIRED_KEYS_UNPARSED = "REQUIRED_KEYS_UNPARSED"
MISSING_REQUIRED_KEYS = "MISSING_REQUIRED_KEYS"
NOT_A_JSON_OBJECT = "NOT_A_JSON_OBJECT"
NO_KEY_SPECIFICATION = "NO_KEY_SPECIFICATION"
SYNTAX_ONLY = "SYNTAX_ONLY"

# A prompt that mentions keys at all is treated as declaring a key
# specification. KEY_LIST must then succeed or the validator fails closed.
KEY_DECLARATION = re.compile(r"\bkeys?\b", re.IGNORECASE)
KEY_LIST = re.compile(
    r"\bkeys?\b[^:=\n]{0,40}[:=]\s*"
    r"(?P<keys>[A-Za-z0-9_]+(?:\s*,\s*[A-Za-z0-9_]+)*)",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    name: str
    status: str
    detail: str | None = None
    checked_keys: tuple[str, ...] = ()
    value_types_checked: bool = False


def _strip_one_json_fence(output):
    """Remove exactly one complete outer ```json fence, or return unchanged.

    Applied identically to `extract_structured` and JSON `format` validation.
    This is narrow mechanical normalization, not semantic repair: an
    unterminated fence, a second fence, or surrounding prose is left intact
    and will fail JSON parsing.
    """
    if not isinstance(output, str):
        return output
    stripped = output.strip()
    match = re.fullmatch(
        r"```[ \t]*json[ \t]*\r?\n(?P<body>.*?)\r?\n```",
        stripped,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group("body").strip() if match else output


# The frozen benchmark harness imports this name. It is retained as an alias
# with byte-identical behaviour so that replaying frozen evidence through
# `run_benchmark.py` is unaffected by this change.
_normalize_structured_json = _strip_one_json_fence


def required_keys(prompt):
    """Return (declared, keys).

    `declared` is True when the prompt appears to specify required keys.
    `keys` is the parsed list, which may be empty even when `declared` is
    True. That combination is the fail-closed case.
    """
    if not isinstance(prompt, str) or not KEY_DECLARATION.search(prompt):
        return False, []
    match = KEY_LIST.search(prompt)
    if not match:
        return True, []
    return True, [key.strip() for key in match.group("keys").split(",") if key.strip()]


def _check_required_keys(name, prompt, value):
    """Key-presence check only. Value types are never inferred here."""
    declared, keys = required_keys(prompt)

    if declared and not keys:
        # The prompt specifies keys but they could not be parsed. Passing
        # here would silently degrade the check to "is this JSON" while
        # still reporting PASS, so fail closed and escalate instead.
        return ValidationResult(name, FAIL, REQUIRED_KEYS_UNPARSED)

    if not keys:
        return ValidationResult(name, PASS, NO_KEY_SPECIFICATION)

    if not isinstance(value, dict):
        return ValidationResult(name, FAIL, NOT_A_JSON_OBJECT, tuple(keys))

    missing = [key for key in keys if key not in value]
    if missing:
        return ValidationResult(
            name,
            FAIL,
            f"{MISSING_REQUIRED_KEYS}={','.join(missing)}",
            tuple(keys),
        )

    return ValidationResult(
        name,
        PASS,
        f"CHECKED_KEYS={','.join(keys)}",
        tuple(keys),
    )


def repeated(text):
    words = re.findall(r"\w+", text.lower())
    return len(words) >= 12 and len(set(words)) <= max(2, len(words) // 8)


def validate(task_class, prompt, output):
    if task_class == "extract_structured":
        try:
            value = json.loads(_strip_one_json_fence(output))
        except (ValueError, TypeError):
            return ValidationResult("json_structure_v1", FAIL, INVALID_JSON)
        return _check_required_keys("json_structure_v1", prompt, value)
    if task_class == "rewrite":
        if not output.strip() or len(output) < 10 or len(output) > max(100, len(prompt) * 3) or repeated(output):
            return ValidationResult("rewrite_shape_v1", FAIL)
        return ValidationResult("rewrite_shape_v1", PASS)
    if task_class == "summarise_short":
        if not output.strip() or len(output) >= len(prompt) or len(output) > 2000 or repeated(output):
            return ValidationResult("summary_basic_v1", FAIL)
        return ValidationResult("summary_basic_v1", PASS)
    if task_class == "format":
        low = prompt.lower()
        if "json" in low:
            try:
                json.loads(_strip_one_json_fence(output))
            except (ValueError, TypeError):
                return ValidationResult("format_json_v1", FAIL, INVALID_JSON)
            return ValidationResult("format_json_v1", PASS, SYNTAX_ONLY)
        if "bullet" in low:
            return ValidationResult("format_bullets_v1", PASS if re.search(r"(?m)^\s*[-*]\s+", output) else FAIL)
        return ValidationResult("format_v1", NOT_APPLICABLE)
    return ValidationResult("unsupported", NOT_APPLICABLE)
