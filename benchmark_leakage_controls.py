"""Deterministic construct-validity controls for future benchmark revisions."""

from collections.abc import Callable, Iterable, Mapping
import re


def extract_input_block(prompt: str) -> str:
    """Return text following a conservative ``Input:`` or ``Source:`` marker.

    Prompts without one of these explicit markers return an empty string rather
    than guessing which prose is task input.
    """
    if not isinstance(prompt, str):
        return ""
    matches = list(re.finditer(r"(?im)^(?:input|source):\s*", prompt))
    if not matches:
        return ""
    return prompt[matches[-1].end():].strip()


def longest_capitalised_span(prompt: str) -> str:
    """Return the longest adjacent Name-like span, or an empty string."""
    if not isinstance(prompt, str):
        return ""
    token = r"[A-Z][\w'’-]*"
    spans = re.findall(rf"{token}(?:\s+{token})*", prompt)
    return max(spans, key=lambda value: (len(value.split()), len(value)), default="")


def _longest_word(prompt: str) -> str:
    return max(prompt.split(), key=len, default="") if isinstance(prompt, str) else ""


def _first_line(prompt: str) -> str:
    return prompt.strip().splitlines()[0] if isinstance(prompt, str) and prompt.strip() else ""


def _last_line(prompt: str) -> str:
    return prompt.strip().splitlines()[-1] if isinstance(prompt, str) and prompt.strip() else ""


def null_baselines() -> Mapping[str, Callable[[str], str]]:
    """Return the frozen, model-free baseline strategies."""
    return {
        "empty": lambda prompt: "",
        "echo_prompt": lambda prompt: prompt,
        "echo_input_block": extract_input_block,
        "first_line": _first_line,
        "last_line": _last_line,
        "longest_capitalised_span": longest_capitalised_span,
        "longest_word": _longest_word,
        "constant_positive": lambda prompt: "positive",
        "constant_high": lambda prompt: "high",
    }


def evaluate_null_baselines(
    tasks: Iterable[Mapping],
    oracle_fn: Callable[[Mapping, str], bool],
    *,
    baselines: Mapping[str, Callable[[str], str]] | None = None,
) -> list[dict]:
    """Score every baseline through the supplied benchmark oracle."""
    strategies = baselines or null_baselines()
    rows = []
    for task in tasks:
        for baseline_id, baseline_fn in strategies.items():
            raw_output = baseline_fn(task["prompt"])
            rows.append({
                "task_id": task["task_id"],
                "variant_id": task.get("variant_id", "base"),
                "condition": "null_baseline",
                "baseline_id": baseline_id,
                "raw_output": raw_output,
                "oracle_correct": bool(oracle_fn(task, raw_output)),
            })
    return rows


def construct_validity(baseline_results: Mapping[str, bool]) -> str:
    """Return the task-level null-baseline verdict."""
    return "CV_NULL_BASELINE_PASSES" if any(baseline_results.values()) else "CV_OK"


def ablate_prompt(prompt: str, mode: str) -> str:
    """Remove or deterministically shuffle the marked input block."""
    if mode not in {"input_removed", "input_shuffled"}:
        raise ValueError("unsupported ablation mode")
    if not isinstance(prompt, str):
        return ""
    match = re.search(r"(?im)^(?P<marker>(?:input|source):\s*)(?P<body>.*)$", prompt)
    if not match:
        raise ValueError("prompt has no explicit input/source block")
    body = match.group("body")
    replacement = "[REMOVED]" if mode == "input_removed" else " ".join(reversed(body.split()))
    return prompt[:match.start("body")] + replacement + prompt[match.end("body"):]


def mutation_verdict(base_passed: bool, mutant_passed: bool) -> str:
    """Classify agreement between a base task and its surface mutation."""
    return "CV_OK" if base_passed == mutant_passed else "CV_MUTANT_DIVERGENCE"


def assert_no_expected_value_leakage(payload: Mapping, expected_values: Iterable[str]) -> None:
    """Reject oracle values appearing in serialized payload fields outside prompt."""
    import json

    payload_without_prompt = {key: value for key, value in payload.items() if key != "prompt"}
    serialized = json.dumps(payload_without_prompt, ensure_ascii=False, sort_keys=True)
    leaked = [value for value in expected_values if value and value in serialized]
    if leaked:
        raise AssertionError("oracle expected value leaked into request payload")


def normalization_delta(
    raw_output: str,
    normalize_fn: Callable[[str], str],
    oracle_fn: Callable[[str], bool],
) -> dict:
    """Score raw and normalized output independently and expose the delta."""
    normalized_output = normalize_fn(raw_output)
    raw_correct = bool(oracle_fn(raw_output))
    normalized_correct = bool(oracle_fn(normalized_output))
    return {
        "raw_output": raw_output,
        "normalized_output": normalized_output,
        "normalization_applied": normalized_output != raw_output,
        "normalization_changed_verdict": raw_correct != normalized_correct,
        "oracle_correct_raw": raw_correct,
        "oracle_correct_normalized": normalized_correct,
    }
