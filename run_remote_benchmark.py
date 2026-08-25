"""Run or safely resume the paired OpenRouter benchmark."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess

from dotenv import load_dotenv

from remote import generate
from run_benchmark import (
    DEFAULT_BENCHMARK,
    evaluate_oracle,
    load_benchmark,
    summarize_records,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "benchmark_runs_openrouter_luna_v1.jsonl"
DEFAULT_SUMMARY = ROOT / "benchmark_summary_openrouter_luna_v1.json"

MODEL = "openai/gpt-5.6-luna"
REPS = 5
MAX_REQUESTS = 150
MAX_COST_USD = 0.10

REMOTE_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "model": MODEL,
    "timeout_seconds": 90,
    "temperature": 0,
    "max_tokens": 256,
}


def file_sha256(path):
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def code_revision():
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def expected_keys(tasks, reps=REPS):
    return {
        (task["task_id"], rep)
        for task in tasks
        for rep in range(1, reps + 1)
    }


def load_existing(path, tasks, reps=REPS):
    path = Path(path)

    if not path.exists():
        return []

    records = []
    seen = set()
    allowed = expected_keys(tasks, reps)

    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON on existing output line {line_number}"
                ) from exc

            key = (record.get("task_id"), record.get("rep"))

            if key not in allowed:
                raise ValueError(
                    f"unexpected existing observation key: {key}"
                )

            if key in seen:
                raise ValueError(
                    f"duplicate existing observation key: {key}"
                )

            if record.get("requested_model") != MODEL:
                raise ValueError(
                    "existing observation uses another requested "
                    f"model: {key}"
                )

            seen.add(key)
            records.append(record)

    return records


def numeric_sum(records, field):
    return sum(
        value
        for record in records
        if isinstance(
            (value := record.get(field)),
            (int, float),
        )
        and not isinstance(value, bool)
    )


def run_remote(
    tasks,
    api_key,
    output_path=DEFAULT_OUTPUT,
    reps=REPS,
    max_cost_usd=MAX_COST_USD,
    generate_fn=generate,
):
    if reps < 1:
        raise ValueError("reps must be at least 1")

    if len(tasks) * reps > MAX_REQUESTS:
        raise ValueError(
            f"run would exceed {MAX_REQUESTS} requests"
        )

    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is not configured"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = load_existing(output_path, tasks, reps)
    completed = {
        (record["task_id"], record["rep"])
        for record in records
    }
    cumulative_cost = numeric_sum(records, "cost")

    if cumulative_cost >= max_cost_usd:
        raise RuntimeError(
            "existing run has reached the cost stop"
        )

    benchmark_hash = file_sha256(DEFAULT_BENCHMARK)
    revision = code_revision()

    with output_path.open("a", encoding="utf-8") as handle:
        for task in tasks:
            for rep in range(1, reps + 1):
                key = (task["task_id"], rep)

                if key in completed:
                    continue

                if cumulative_cost >= max_cost_usd:
                    raise RuntimeError(
                        "cost stop reached at "
                        f"${cumulative_cost:.8f}"
                    )

                result = generate_fn(
                    task["prompt"],
                    REMOTE_CONFIG,
                    api_key,
                )

                raw_output = (
                    result.text
                    if isinstance(result.text, str)
                    else ""
                )
                normalized, oracle_correct, validator = (
                    evaluate_oracle(task, raw_output)
                )

                record = {
                    "task_id": task["task_id"],
                    "rep": rep,
                    "task_class": task["task_class"],
                    "requested_model": MODEL,
                    "returned_model": result.model,
                    "request_parameters": {
                        "temperature": REMOTE_CONFIG[
                            "temperature"
                        ],
                        "max_tokens": REMOTE_CONFIG[
                            "max_tokens"
                        ],
                    },
                    "benchmark_sha256": benchmark_hash,
                    "code_revision": revision,
                    "raw_output": raw_output,
                    "normalized_output": normalized,
                    "oracle_correct": oracle_correct,
                    "validator": validator,
                    "validator_status": validator["status"],
                    "response_id": result.response_id,
                    "status_code": result.status_code,
                    "finish_reason": result.finish_reason,
                    "native_finish_reason": (
                        result.native_finish_reason
                    ),
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": (
                        result.completion_tokens
                    ),
                    "total_tokens": result.total_tokens,
                    "reasoning_tokens": result.reasoning_tokens,
                    "cached_tokens": result.cached_tokens,
                    "cache_write_tokens": (
                        result.cache_write_tokens
                    ),
                    "cost": result.cost,
                    "router_metadata": result.router_metadata,
                    "cache_status": result.cache_status,
                    "total_ms": result.total_ms,
                    "success": result.success,
                    "error": result.error,
                }

                handle.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())

                records.append(record)
                completed.add(key)

                if isinstance(result.cost, (int, float)):
                    cumulative_cost += result.cost

                print(
                    f"{len(completed):3}/"
                    f"{len(tasks) * reps} "
                    f"{task['task_id']} rep={rep} "
                    f"oracle={validator['status']} "
                    f"cost=${cumulative_cost:.8f}",
                    flush=True,
                )

    return records


def write_remote_summary(
    records,
    path=DEFAULT_SUMMARY,
):
    summary = summarize_records(records)

    summary.update({
        "requested_model": MODEL,
        "request_parameters": {
            "temperature": REMOTE_CONFIG["temperature"],
            "max_tokens": REMOTE_CONFIG["max_tokens"],
        },
        "successful_response_count": sum(
            bool(record.get("success"))
            for record in records
        ),
        "total_prompt_tokens": numeric_sum(
            records,
            "prompt_tokens",
        ),
        "total_completion_tokens": numeric_sum(
            records,
            "completion_tokens",
        ),
        "total_reasoning_tokens": numeric_sum(
            records,
            "reasoning_tokens",
        ),
        "total_cached_tokens": numeric_sum(
            records,
            "cached_tokens",
        ),
        "total_cache_write_tokens": numeric_sum(
            records,
            "cache_write_tokens",
        ),
        "total_tokens": numeric_sum(
            records,
            "total_tokens",
        ),
        "total_cost": numeric_sum(records, "cost"),
        "returned_models": dict(sorted(Counter(
            record.get("returned_model")
            for record in records
            if record.get("returned_model")
        ).items())),
        "finish_reasons": dict(sorted(Counter(
            record.get("finish_reason")
            for record in records
            if record.get("finish_reason")
        ).items())),
        "cache_statuses": dict(sorted(Counter(
            record.get("cache_status")
            for record in records
            if record.get("cache_status")
        ).items())),
    })

    Path(path).write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_SUMMARY,
    )
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=MAX_COST_USD,
    )
    args = parser.parse_args(argv)

    tasks = load_benchmark()["tasks"]
    planned = len(tasks) * REPS

    print(f"Model: {MODEL}")
    print(f"Tasks: {len(tasks)}")
    print(f"Repetitions: {REPS}")
    print(f"Maximum requests: {planned}")
    print(f"Cost stop: ${args.max_cost_usd:.2f}")
    print(f"Output: {args.output}")

    if not args.execute:
        print(
            "Dry run only; pass --execute "
            "to call OpenRouter."
        )
        return

    load_dotenv(ROOT / ".env")

    records = run_remote(
        tasks,
        os.getenv("OPENROUTER_API_KEY"),
        args.output,
        REPS,
        args.max_cost_usd,
    )

    if len(records) != planned:
        raise RuntimeError(
            f"incomplete run: expected {planned}, "
            f"found {len(records)}"
        )

    summary = write_remote_summary(
        records,
        args.summary_output,
    )

    print(f"Wrote {len(records)} observations")
    print(
        "Overall passes: "
        f"{summary['overall_pass_count']}/"
        f"{len(records)}"
    )
    print(
        f"Total cost: ${summary['total_cost']:.8f}"
    )
    print(f"Summary: {args.summary_output}")


if __name__ == "__main__":
    main()
