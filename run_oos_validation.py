"""Run or safely resume the frozen out-of-sample paired validation."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import subprocess

from dotenv import load_dotenv

from local import LocalResult, generate as generate_local, model_residency
from remote import generate as generate_remote
from run_benchmark import evaluate_oracle


ROOT = Path(__file__).resolve().parent

BENCHMARK = ROOT / "benchmark_oos_v1.json"
BENCHMARK_SHA256 = (
    "6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295"
)
SUITE_ID = "oos_validation_v1"
TASK_COUNT = 40
REPS = 5
OBSERVATION_COUNT = TASK_COUNT * REPS

LOCAL_MODEL = "gemma3:270m"
REMOTE_MODEL = "openai/gpt-5.6-luna"
MAX_COST_USD = 0.10

LOCAL_OUTPUT = ROOT / "benchmark_runs_oos_local_v1.jsonl"
LOCAL_SUMMARY = ROOT / "benchmark_summary_oos_local_v1.json"
REMOTE_OUTPUT = ROOT / "benchmark_runs_oos_openrouter_luna_v1.jsonl"
REMOTE_SUMMARY = ROOT / "benchmark_summary_oos_openrouter_luna_v1.json"

EXPECTED_FAMILY_COUNTS = {
    "structured_extraction": 10,
    "sentiment": 5,
    "json_format": 5,
    "priority": 5,
    "markdown_bullets": 5,
    "key_value_labels": 5,
    "transformation": 5,
}

REMOTE_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "model": REMOTE_MODEL,
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


def load_suite(path=BENCHMARK):
    path = Path(path)

    if file_sha256(path) != BENCHMARK_SHA256:
        raise ValueError("frozen benchmark SHA-256 mismatch")

    document = json.loads(path.read_text(encoding="utf-8"))

    if document.get("suite_id") != SUITE_ID:
        raise ValueError("unexpected suite_id")

    tasks = document.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != TASK_COUNT:
        raise ValueError(f"suite must contain exactly {TASK_COUNT} tasks")

    task_ids = [task.get("task_id") for task in tasks]
    if any(not task_id for task_id in task_ids):
        raise ValueError("every task must have a task_id")
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("duplicate task_id")

    required = {
        "task_id",
        "task_class",
        "capability_family",
        "normalization",
        "prompt",
        "expected",
    }
    for task in tasks:
        missing = required - set(task)
        if missing:
            raise ValueError(
                f"task {task.get('task_id')} missing fields: "
                f"{', '.join(sorted(missing))}"
            )

    family_counts = Counter(
        task["capability_family"] for task in tasks
    )
    if dict(family_counts) != EXPECTED_FAMILY_COUNTS:
        raise ValueError(
            "capability-family counts differ from preregistration"
        )

    return document


def expected_keys(tasks):
    return {
        (task["task_id"], rep)
        for task in tasks
        for rep in range(1, REPS + 1)
    }


def load_existing(path, tasks, provider, requested_model, revision):
    path = Path(path)
    if not path.exists():
        return []

    allowed = expected_keys(tasks)
    task_by_id = {task["task_id"]: task for task in tasks}
    records = []
    seen = set()

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
            if record.get("provider") != provider:
                raise ValueError(
                    f"existing observation uses wrong provider: {key}"
                )
            if record.get("requested_model") != requested_model:
                raise ValueError(
                    f"existing observation uses wrong model: {key}"
                )
            if record.get("benchmark_sha256") != BENCHMARK_SHA256:
                raise ValueError(
                    f"existing observation uses wrong benchmark: {key}"
                )
            if record.get("code_revision") != revision:
                raise ValueError(
                    f"existing observation uses another code revision: {key}"
                )

            task = task_by_id[key[0]]
            if (
                record.get("task_class") != task["task_class"]
                or record.get("capability_family")
                != task["capability_family"]
            ):
                raise ValueError(
                    f"existing observation metadata mismatch: {key}"
                )

            seen.add(key)
            records.append(record)

    return records


def append_record(handle, record):
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


def median_available(records, field):
    values = [
        value
        for record in records
        if isinstance(
            (value := record.get(field)),
            (int, float),
        )
        and not isinstance(value, bool)
    ]
    return median(values) if values else None


def summary_bucket(records):
    count = len(records)
    passes = sum(
        bool(record.get("oracle_correct"))
        for record in records
    )
    return {
        "observation_count": count,
        "pass_count": passes,
        "pass_rate": passes / count if count else None,
    }


def make_summary(records, provider, requested_model):
    records = list(records)
    per_task = {}
    per_class = {}
    per_family = {}

    for record in records:
        per_task.setdefault(record["task_id"], []).append(record)
        per_class.setdefault(record["task_class"], []).append(record)
        per_family.setdefault(
            record["capability_family"], []
        ).append(record)

    summary = {
        **summary_bucket(records),
        "suite_id": SUITE_ID,
        "benchmark_sha256": BENCHMARK_SHA256,
        "provider": provider,
        "requested_model": requested_model,
        "successful_response_count": sum(
            bool(record.get("success")) for record in records
        ),
        "empty_output_count": sum(
            record.get("raw_output") == "" for record in records
        ),
        "median_total_ms": median_available(records, "total_ms"),
        "per_task": {
            key: summary_bucket(value)
            for key, value in sorted(per_task.items())
        },
        "per_class": {
            key: summary_bucket(value)
            for key, value in sorted(per_class.items())
        },
        "per_family": {
            key: summary_bucket(value)
            for key, value in sorted(per_family.items())
        },
    }

    if provider == "ollama":
        summary.update({
            "median_ttft_ms": median_available(
                records, "ttft_ms"
            ),
            "median_tokens_per_second": median_available(
                records, "tokens_per_second"
            ),
        })
    else:
        summary.update({
            "request_parameters": {
                "temperature": REMOTE_CONFIG["temperature"],
                "max_tokens": REMOTE_CONFIG["max_tokens"],
            },
            "total_prompt_tokens": numeric_sum(
                records, "prompt_tokens"
            ),
            "total_completion_tokens": numeric_sum(
                records, "completion_tokens"
            ),
            "total_reasoning_tokens": numeric_sum(
                records, "reasoning_tokens"
            ),
            "total_cached_tokens": numeric_sum(
                records, "cached_tokens"
            ),
            "total_cache_write_tokens": numeric_sum(
                records, "cache_write_tokens"
            ),
            "total_tokens": numeric_sum(records, "total_tokens"),
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

    return summary

def finish_summary(
    records,
    summary_path,
    provider,
    requested_model,
):
    summary_path = Path(summary_path)

    if len(records) != OBSERVATION_COUNT:
        raise RuntimeError(
            f"incomplete run: expected {OBSERVATION_COUNT}, "
            f"found {len(records)}"
        )

    expected = make_summary(
        records,
        provider,
        requested_model,
    )

    if summary_path.exists():
        try:
            existing = json.loads(
                summary_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "existing summary is not valid JSON"
            ) from exc

        if existing != expected:
            raise ValueError(
                "existing summary does not match evidence"
            )

        print(
            f"Verified existing summary; left untouched: "
            f"{summary_path}"
        )
        return existing

    summary_path.write_text(
        json.dumps(
            expected,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return expected


def run_local(
    tasks,
    model_config,
    output_path=LOCAL_OUTPUT,
    summary_path=LOCAL_SUMMARY,
    generate_fn=generate_local,
    residency_fn=model_residency,
):
    revision = code_revision()
    if not revision:
        raise RuntimeError("unable to identify Git revision")
    if model_config.get("model") != LOCAL_MODEL:
        raise ValueError("local model differs from preregistration")

    records = load_existing(
        output_path,
        tasks,
        "ollama",
        LOCAL_MODEL,
        revision,
    )
    completed = {
        (record["task_id"], record["rep"])
        for record in records
    }

    if Path(summary_path).exists() and len(records) != OBSERVATION_COUNT:
        raise RuntimeError(
            "summary exists for an incomplete local run"
        )

    with Path(output_path).open("a", encoding="utf-8") as handle:
        for task in tasks:
            for rep in range(1, REPS + 1):
                key = (task["task_id"], rep)
                if key in completed:
                    continue

                try:
                    residency = residency_fn(model_config)
                except Exception:
                    residency = {
                        "resident": None,
                        "size_bytes": None,
                    }

                try:
                    result = generate_fn(
                        task["prompt"],
                        model_config,
                    )
                except Exception as exc:
                    result = LocalResult(
                        False,
                        error=type(exc).__name__,
                    )

                raw_output = (
                    result.text
                    if isinstance(result.text, str)
                    else ""
                )
                normalized, correct, validator = evaluate_oracle(
                    task, raw_output
                )

                record = {
                    "task_id": task["task_id"],
                    "rep": rep,
                    "task_class": task["task_class"],
                    "capability_family": task[
                        "capability_family"
                    ],
                    "provider": "ollama",
                    "requested_model": LOCAL_MODEL,
                    "returned_model": LOCAL_MODEL,
                    "benchmark_sha256": BENCHMARK_SHA256,
                    "code_revision": revision,
                    "raw_output": raw_output,
                    "normalized_output": normalized,
                    "oracle_correct": correct,
                    "validator": validator,
                    "validator_status": validator["status"],
                    "ttft_ms": result.ttft_ms,
                    "total_ms": result.total_ms,
                    "tokens_per_second": (
                        result.tokens_per_second
                    ),
                    "model_residency": residency,
                    "success": result.success,
                    "error": result.error,
                }
                append_record(handle, record)
                records.append(record)
                completed.add(key)

                print(
                    f"local {len(completed):3}/"
                    f"{OBSERVATION_COUNT} "
                    f"{task['task_id']} rep={rep} "
                    f"oracle={validator['status']}",
                    flush=True,
                )

    return finish_summary(
        records,
        summary_path,
        "ollama",
        LOCAL_MODEL,
    )


def run_remote(
    tasks,
    api_key,
    output_path=REMOTE_OUTPUT,
    summary_path=REMOTE_SUMMARY,
    generate_fn=generate_remote,
):
    revision = code_revision()
    if not revision:
        raise RuntimeError("unable to identify Git revision")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured")

    records = load_existing(
        output_path,
        tasks,
        "openrouter",
        REMOTE_MODEL,
        revision,
    )
    completed = {
        (record["task_id"], record["rep"])
        for record in records
    }
    cumulative_cost = numeric_sum(records, "cost")

    if Path(summary_path).exists() and len(records) != OBSERVATION_COUNT:
        raise RuntimeError(
            "summary exists for an incomplete remote run"
        )
    if (
        len(records) != OBSERVATION_COUNT
        and cumulative_cost >= MAX_COST_USD
    ):
        raise RuntimeError("existing run has reached the cost stop")

    with Path(output_path).open("a", encoding="utf-8") as handle:
        for task in tasks:
            for rep in range(1, REPS + 1):
                key = (task["task_id"], rep)
                if key in completed:
                    continue
                if cumulative_cost >= MAX_COST_USD:
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
                normalized, correct, validator = evaluate_oracle(
                    task, raw_output
                )

                record = {
                    "task_id": task["task_id"],
                    "rep": rep,
                    "task_class": task["task_class"],
                    "capability_family": task[
                        "capability_family"
                    ],
                    "provider": "openrouter",
                    "requested_model": REMOTE_MODEL,
                    "returned_model": result.model,
                    "request_parameters": {
                        "temperature": REMOTE_CONFIG[
                            "temperature"
                        ],
                        "max_tokens": REMOTE_CONFIG[
                            "max_tokens"
                        ],
                    },
                    "benchmark_sha256": BENCHMARK_SHA256,
                    "code_revision": revision,
                    "raw_output": raw_output,
                    "normalized_output": normalized,
                    "oracle_correct": correct,
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
                append_record(handle, record)
                records.append(record)
                completed.add(key)

                if isinstance(result.cost, (int, float)):
                    cumulative_cost += result.cost

                print(
                    f"remote {len(completed):3}/"
                    f"{OBSERVATION_COUNT} "
                    f"{task['task_id']} rep={rep} "
                    f"oracle={validator['status']} "
                    f"cost=${cumulative_cost:.8f}",
                    flush=True,
                )

    return finish_summary(
        records,
        summary_path,
        "openrouter",
        REMOTE_MODEL,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--execute-local", action="store_true")
    group.add_argument("--execute-remote", action="store_true")
    args = parser.parse_args(argv)

    document = load_suite()
    tasks = document["tasks"]

    print(f"Suite: {SUITE_ID}")
    print(f"Benchmark SHA-256: {BENCHMARK_SHA256}")
    print(f"Tasks: {len(tasks)}")
    print(f"Repetitions: {REPS}")
    print(f"Observations per model: {OBSERVATION_COUNT}")
    print(f"Local output: {LOCAL_OUTPUT}")
    print(f"Remote output: {REMOTE_OUTPUT}")

    if not args.execute_local and not args.execute_remote:
        print("Dry run only; no model calls were made.")
        return

    config = json.loads(
        (ROOT / "config.json").read_text(encoding="utf-8")
    )

    if args.execute_local:
        summary = run_local(tasks, dict(config["local"]))
        print(
            "Local passes: "
            f"{summary['pass_count']}/"
            f"{summary['observation_count']}"
        )
        print(f"Local summary: {LOCAL_SUMMARY}")
        return

    load_dotenv(ROOT / ".env")
    summary = run_remote(
        tasks,
        os.getenv("OPENROUTER_API_KEY"),
    )
    print(
        "Remote passes: "
        f"{summary['pass_count']}/"
        f"{summary['observation_count']}"
    )
    print(f"Remote cost: ${summary['total_cost']:.8f}")
    print(f"Remote summary: {REMOTE_SUMMARY}")


if __name__ == "__main__":
    main()
