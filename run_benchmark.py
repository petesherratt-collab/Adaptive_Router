"""Run the fixed deterministic benchmark directly against an Ollama model."""

import argparse
import json
from pathlib import Path

from local import LocalResult, generate, model_residency
from validators import FAIL, PASS, _normalize_structured_json


ROOT = Path(__file__).resolve().parent
DEFAULT_BENCHMARK = ROOT / "benchmark.json"
DEFAULT_OUTPUT = ROOT / "benchmark_runs.jsonl"
ORACLE_NAME = "benchmark_oracle_v1"
EXPECTED_TASK_COUNT = 10
EXPECTED_TASK_CLASSES = frozenset({
    "extract_structured",
    "classification",
    "format",
    "transform",
})


def load_benchmark(path=DEFAULT_BENCHMARK):
    """Load and minimally validate the benchmark definition."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("benchmark must contain a non-empty tasks list")
    task_ids = [task.get("task_id") for task in tasks]
    if any(not task_id for task_id in task_ids) or len(set(task_ids)) != len(task_ids):
        raise ValueError("benchmark task_id values must be present and unique")
    if len(tasks) != EXPECTED_TASK_COUNT:
        raise ValueError(f"benchmark must contain exactly {EXPECTED_TASK_COUNT} tasks")
    task_classes = {task.get("task_class") for task in tasks}
    if task_classes != EXPECTED_TASK_CLASSES:
        raise ValueError("benchmark must cover the four required task classes exactly")
    required = {"task_id", "task_class", "normalization", "prompt", "expected"}
    for task in tasks:
        if not required.issubset(task):
            missing = ", ".join(sorted(required - set(task)))
            raise ValueError(f"benchmark task {task.get('task_id', '<unknown>')} missing: {missing}")
        if task["normalization"] not in {"structured_json", "text"}:
            raise ValueError(f"unsupported normalization: {task['normalization']}")
    return data


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_output(task, raw_output):
    """Apply only the task's declared deterministic output normalization."""
    if not isinstance(raw_output, str):
        raw_output = ""
    if task["normalization"] == "text":
        # Boundary whitespace is transport/presentation noise; content is exact.
        return raw_output.strip()
    if task["normalization"] == "structured_json":
        candidate = _normalize_structured_json(raw_output)
        try:
            return _canonical_json(json.loads(candidate))
        except (TypeError, ValueError):
            # Keep malformed output visible in the record while making the
            # oracle fail closed.
            return candidate.strip() if isinstance(candidate, str) else ""
    raise ValueError(f"unsupported normalization: {task['normalization']}")


def expected_output(task):
    if task["normalization"] == "structured_json":
        return _canonical_json(task["expected"])
    return str(task["expected"]).strip()


def evaluate_oracle(task, raw_output):
    """Return the normalized output and an explicit deterministic oracle result."""
    normalized = normalize_output(task, raw_output)
    expected = expected_output(task)
    correct = normalized == expected
    detail = None if correct else "EXPECTED_MISMATCH"
    if task["normalization"] == "structured_json":
        try:
            json.loads(_normalize_structured_json(raw_output))
        except (TypeError, ValueError):
            detail = "INVALID_JSON"
    validator = {
        "name": ORACLE_NAME,
        "status": PASS if correct else FAIL,
        "detail": detail,
    }
    return normalized, correct, validator


def _failed_result(exc):
    return LocalResult(False, error=type(exc).__name__)


def run_benchmark(tasks, model_config, reps=3, output_path=DEFAULT_OUTPUT,
                  generate_fn=generate, residency_fn=model_residency):
    """Run every task ``reps`` times and write exactly one record per run."""
    if reps < 1:
        raise ValueError("reps must be at least 1")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with output_path.open("w", encoding="utf-8") as handle:
        for task in tasks:
            for rep in range(1, reps + 1):
                try:
                    residency = residency_fn(model_config)
                except Exception:
                    residency = {"resident": None, "size_bytes": None}
                try:
                    result = generate_fn(task["prompt"], model_config)
                except Exception as exc:
                    result = _failed_result(exc)
                raw_output = result.text if isinstance(result.text, str) else ""
                normalized, oracle_correct, validator = evaluate_oracle(task, raw_output)
                record = {
                    "task_id": task["task_id"],
                    "rep": rep,
                    "model": model_config["model"],
                    "task_class": task["task_class"],
                    "raw_output": raw_output,
                    "normalized_output": normalized,
                    "oracle_correct": oracle_correct,
                    "validator": validator,
                    "validator_status": validator["status"],
                    "ttft_ms": result.ttft_ms,
                    "total_ms": result.total_ms,
                    "tokens_per_second": result.tokens_per_second,
                    "model_residency": residency,
                    "success": result.success,
                    "error": result.error,
                }
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                records.append(record)
    return records


def _positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Ollama model name; defaults to config.json local.model")
    parser.add_argument("--reps", type=_positive_int, default=3,
                        help="number of runs per task (default: 3)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="JSONL output path (default: benchmark_runs.jsonl)")
    args = parser.parse_args(argv)

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    model_config = dict(config["local"])
    if args.model:
        model_config["model"] = args.model
    tasks = load_benchmark()["tasks"]
    records = run_benchmark(tasks, model_config, args.reps, args.output)
    print(f"Wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
