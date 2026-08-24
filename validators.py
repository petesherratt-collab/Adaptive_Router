from dataclasses import dataclass
import json
import re

PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"

@dataclass
class ValidationResult:
    name: str
    status: str
    detail: str | None = None


def _normalize_structured_json(output):
    if not isinstance(output, str):
        return output
    stripped = output.strip()
    match = re.fullmatch(
        r"```[ \t]*json[ \t]*\r?\n(?P<body>.*?)\r?\n```",
        stripped,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group("body").strip() if match else output


def repeated(text):
    words = re.findall(r"\w+", text.lower())
    return len(words) >= 12 and len(set(words)) <= max(2, len(words) // 8)


def validate(task_class, prompt, output):
    if task_class == "extract_structured":
        try: value = json.loads(_normalize_structured_json(output))
        except (ValueError, TypeError): return ValidationResult("json_structure_v1", FAIL, "INVALID_JSON")
        keys = re.findall(r"(?:required keys?|keys?)\s*[:=]\s*([\w, ]+)", prompt, re.I)
        required = [k.strip() for k in keys[0].split(",")] if keys else []
        if required and (not isinstance(value, dict) or any(k not in value for k in required)):
            return ValidationResult("json_structure_v1", FAIL, "MISSING_REQUIRED_KEYS")
        return ValidationResult("json_structure_v1", PASS)
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
            try: json.loads(output)
            except ValueError: return ValidationResult("format_json_v1", FAIL)
            return ValidationResult("format_json_v1", PASS)
        if "bullet" in low:
            return ValidationResult("format_bullets_v1", PASS if re.search(r"(?m)^\s*[-*]\s+", output) else FAIL)
        return ValidationResult("format_v1", NOT_APPLICABLE)
    return ValidationResult("unsupported", NOT_APPLICABLE)
