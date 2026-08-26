"""Analyze the frozen out-of-sample paired routing evidence."""

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import random
from statistics import median


ROOT = Path(__file__).resolve().parent

LOCAL_INPUT = ROOT / "benchmark_runs_oos_local_v1.jsonl"
REMOTE_INPUT = (
    ROOT / "benchmark_runs_oos_openrouter_luna_v1.jsonl"
)
CSV_OUTPUT = ROOT / "routing_analysis_oos_v1.csv"
JSON_OUTPUT = ROOT / "routing_analysis_oos_v1.json"

BENCHMARK_SHA256 = (
    "6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295"
)
RUNNER_REVISION = (
    "50387be90fca40cf6f3f9467106a09abdc9a3c71"
)
LOCAL_MODEL = "gemma3:270m"
REMOTE_MODEL = "openai/gpt-5.6-luna"

OBSERVATIONS = 200
TASKS = 40
REPS = 5
BOOTSTRAP_SAMPLES = 6000

# The preregistration required a fixed seed but omitted its numeric
# value. This date-derived seed was selected after data collection.
BOOTSTRAP_SEED = 20260826

POLICIES = (
    "always_local",
    "always_remote",
    "coarse_class",
    "fine_capability",
)

LOCAL_FINE_FAMILIES = frozenset({
    "structured_extraction",
    "sentiment",
    "json_format",
})

ANALYSIS_DEVIATIONS = (
    "OOS-specific analysis code was not committed before model execution.",
    "The preregistration required a fixed random seed but did not record "
    "its numeric value; seed 20260826 was selected after data collection.",
)


def load_jsonl(path):
    records = []

    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON on line {line_number}: {path}"
                ) from exc

            records.append(record)

    return records


def index_records(records, source_name):
    indexed = {}

    for record in records:
        key = (record.get("task_id"), record.get("rep"))

        if None in key:
            raise ValueError(
                f"{source_name} contains an incomplete key: {key}"
            )

        if key in indexed:
            raise ValueError(
                f"{source_name} contains a duplicate key: {key}"
            )

        indexed[key] = record

    return indexed


def validate_identity(records, source_name, provider, model):
    if len(records) != OBSERVATIONS:
        raise ValueError(
            f"{source_name} must contain exactly "
            f"{OBSERVATIONS} observations"
        )

    task_counts = Counter(
        record.get("task_id") for record in records
    )
    if len(task_counts) != TASKS:
        raise ValueError(
            f"{source_name} must contain exactly {TASKS} tasks"
        )
    if set(task_counts.values()) != {REPS}:
        raise ValueError(
            f"{source_name} must contain {REPS} repetitions per task"
        )

    checks = (
        (
            "benchmark SHA-256",
            {record.get("benchmark_sha256") for record in records},
            {BENCHMARK_SHA256},
        ),
        (
            "runner revision",
            {record.get("code_revision") for record in records},
            {RUNNER_REVISION},
        ),
        (
            "provider",
            {record.get("provider") for record in records},
            {provider},
        ),
        (
            "requested model",
            {record.get("requested_model") for record in records},
            {model},
        ),
    )

    for label, observed, expected in checks:
        if observed != expected:
            raise ValueError(
                f"{source_name} {label} mismatch: {observed}"
            )


def pair_records(local_records, remote_records):
    validate_identity(
        local_records,
        "local",
        "ollama",
        LOCAL_MODEL,
    )
    validate_identity(
        remote_records,
        "remote",
        "openrouter",
        REMOTE_MODEL,
    )

    local_index = index_records(local_records, "local")
    remote_index = index_records(remote_records, "remote")

    if set(local_index) != set(remote_index):
        raise ValueError("local and remote paired key sets differ")

    pairs = []

    for local in local_records:
        key = (local["task_id"], local["rep"])
        remote = remote_index[key]

        for field in (
            "task_class",
            "capability_family",
            "benchmark_sha256",
            "code_revision",
        ):
            if local.get(field) != remote.get(field):
                raise ValueError(
                    f"paired {field} mismatch for key: {key}"
                )

        pairs.append((local, remote))

    return pairs


def route(policy, record):
    if policy == "always_local":
        return "local"

    if policy == "always_remote":
        return "remote"

    if policy == "coarse_class":
        if record["task_class"] in {
            "extract_structured",
            "classification",
        }:
            return "local"
        return "remote"

    if policy == "fine_capability":
        if record["capability_family"] in LOCAL_FINE_FAMILIES:
            return "local"
        return "remote"

    raise ValueError(f"unsupported policy: {policy}")


def available_values(values):
    return [
        value
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
    ]


def simulate(pairs, policy):
    selected_passes = 0
    local_calls = 0
    remote_calls = 0
    beneficial = 0
    unnecessary = 0
    harmful = 0
    missed = 0
    unrecoverable = 0
    selected_transport_failures = 0
    selected_times = []
    selected_remote_costs = []
    oracle_ceiling_passes = 0

    for local, remote in pairs:
        decision = route(policy, local)
        local_ok = bool(local.get("oracle_correct"))
        remote_ok = bool(remote.get("oracle_correct"))

        if local_ok or remote_ok:
            oracle_ceiling_passes += 1

        if decision == "local":
            selected = local
            selected_ok = local_ok
            local_calls += 1

            if not local_ok and remote_ok:
                missed += 1
            if not local_ok and not remote_ok:
                unrecoverable += 1

        elif decision == "remote":
            selected = remote
            selected_ok = remote_ok
            remote_calls += 1

            if not local_ok and remote_ok:
                beneficial += 1
            if local_ok:
                unnecessary += 1
            if local_ok and not remote_ok:
                harmful += 1

            cost = remote.get("cost")
            if (
                isinstance(cost, (int, float))
                and not isinstance(cost, bool)
            ):
                selected_remote_costs.append(cost)

        else:
            raise ValueError(f"unsupported route: {decision}")

        if selected_ok:
            selected_passes += 1
        if not selected.get("success"):
            selected_transport_failures += 1

        selected_times.append(selected.get("total_ms"))

    observations = len(pairs)
    times = available_values(selected_times)

    return {
        "policy": policy,
        "interpretation": "strict",
        "observations": observations,
        "selected_passes": selected_passes,
        "selected_pass_rate": (
            selected_passes / observations
            if observations
            else None
        ),
        "local_calls": local_calls,
        "remote_calls": remote_calls,
        "remote_call_rate": (
            remote_calls / observations
            if observations
            else None
        ),
        "beneficial_escalations": beneficial,
        "unnecessary_escalations": unnecessary,
        "harmful_escalations": harmful,
        "missed_escalations": missed,
        "unrecoverable_local_failures": unrecoverable,
        "selected_transport_failures": (
            selected_transport_failures
        ),
        "oracle_ceiling_passes": oracle_ceiling_passes,
        "oracle_ceiling_rate": (
            oracle_ceiling_passes / observations
            if observations
            else None
        ),
        "median_selected_total_ms": (
            median(times) if times else None
        ),
        "summed_selected_work_ms": sum(times),
        "reported_remote_cost": sum(
            selected_remote_costs
        ),
        "remote_calls_with_reported_cost": len(
            selected_remote_costs
        ),
    }


def group_pairs_by_task(pairs):
    grouped = {}

    for pair in pairs:
        task_id = pair[0]["task_id"]
        grouped.setdefault(task_id, []).append(pair)

    if len(grouped) != TASKS:
        raise ValueError(
            f"expected {TASKS} task clusters, got {len(grouped)}"
        )

    for task_id, cluster in grouped.items():
        reps = {local["rep"] for local, remote in cluster}
        if len(cluster) != REPS or reps != set(range(1, REPS + 1)):
            raise ValueError(
                f"incomplete repetition cluster: {task_id}"
            )

    return grouped


def percentile(values, probability):
    ordered = sorted(values)

    if not ordered:
        raise ValueError("cannot calculate an empty percentile")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between zero and one")

    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower
    return (
        ordered[lower] * (1 - fraction)
        + ordered[upper] * fraction
    )


def cluster_bootstrap(
    pairs,
    samples=BOOTSTRAP_SAMPLES,
    seed=BOOTSTRAP_SEED,
):
    if samples < 1:
        raise ValueError("samples must be at least one")

    grouped = group_pairs_by_task(pairs)
    task_ids = sorted(grouped)
    generator = random.Random(seed)
    differences = []

    for _ in range(samples):
        sampled_pairs = []

        for _ in range(len(task_ids)):
            task_id = generator.choice(task_ids)
            sampled_pairs.extend(grouped[task_id])

        fine = simulate(
            sampled_pairs,
            "fine_capability",
        )
        remote = simulate(
            sampled_pairs,
            "always_remote",
        )

        differences.append(
            fine["selected_pass_rate"]
            - remote["selected_pass_rate"]
        )

    return {
        "method": "paired task-cluster bootstrap",
        "resampling_unit": "task",
        "repetitions_retained_per_task": REPS,
        "samples": samples,
        "seed": seed,
        "estimate": (
            simulate(pairs, "fine_capability")[
                "selected_pass_rate"
            ]
            - simulate(pairs, "always_remote")[
                "selected_pass_rate"
            ]
        ),
        "percentile_95_interval": {
            "lower": percentile(differences, 0.025),
            "upper": percentile(differences, 0.975),
        },
    }


def family_results(pairs):
    families = sorted({
        local["capability_family"]
        for local, remote in pairs
    })
    results = {}

    for family in families:
        selected = [
            pair
            for pair in pairs
            if pair[0]["capability_family"] == family
        ]
        local_passes = sum(
            bool(local.get("oracle_correct"))
            for local, remote in selected
        )
        remote_passes = sum(
            bool(remote.get("oracle_correct"))
            for local, remote in selected
        )

        results[family] = {
            "observations": len(selected),
            "local_passes": local_passes,
            "local_pass_rate": (
                local_passes / len(selected)
            ),
            "remote_passes": remote_passes,
            "remote_pass_rate": (
                remote_passes / len(selected)
            ),
        }

    return results


def task_results(pairs):
    grouped = group_pairs_by_task(pairs)
    results = {}

    for task_id, selected in sorted(grouped.items()):
        local_passes = sum(
            bool(local.get("oracle_correct"))
            for local, remote in selected
        )
        remote_passes = sum(
            bool(remote.get("oracle_correct"))
            for local, remote in selected
        )

        results[task_id] = {
            "capability_family": selected[0][0][
                "capability_family"
            ],
            "observations": len(selected),
            "local_passes": local_passes,
            "local_pass_rate": local_passes / len(selected),
            "remote_passes": remote_passes,
            "remote_pass_rate": remote_passes / len(selected),
        }

    return results


def analyze(pairs):
    policies = [
        simulate(pairs, policy)
        for policy in POLICIES
    ]
    by_policy = {
        result["policy"]: result
        for result in policies
    }

    fine = by_policy["fine_capability"]
    remote = by_policy["always_remote"]
    gap = (
        fine["selected_pass_rate"]
        - remote["selected_pass_rate"]
    )

    criterion = {
        "required_remote_calls": 100,
        "minimum_allowed_success_gap": -0.05,
        "observed_remote_calls": fine["remote_calls"],
        "observed_success_gap": gap,
        "remote_call_condition_passed": (
            fine["remote_calls"] == 100
        ),
        "success_gap_condition_passed": gap >= -0.05,
    }
    criterion["overall_passed"] = (
        criterion["remote_call_condition_passed"]
        and criterion["success_gap_condition_passed"]
    )

    return {
        "analysis_id": "oos_validation_v1_strict",
        "interpretation": "strict",
        "benchmark_sha256": BENCHMARK_SHA256,
        "runner_revision": RUNNER_REVISION,
        "analysis_deviations": list(ANALYSIS_DEVIATIONS),
        "policies": policies,
        "per_family": family_results(pairs),
        "per_task": task_results(pairs),
        "primary_criterion": criterion,
        "bootstrap": cluster_bootstrap(pairs),
    }


def write_csv(results, path):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(results[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(results)


def write_json(result, path):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")

    path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="calculate and write the frozen strict analysis",
    )
    args = parser.parse_args(argv)

    print(f"Local evidence: {LOCAL_INPUT}")
    print(f"Remote evidence: {REMOTE_INPUT}")
    print(f"Bootstrap samples: {BOOTSTRAP_SAMPLES}")
    print(f"Bootstrap seed: {BOOTSTRAP_SEED}")
    print(f"CSV output: {CSV_OUTPUT}")
    print(f"JSON output: {JSON_OUTPUT}")

    if not args.write:
        print("Dry run only; no analysis outputs were created.")
        return

    if CSV_OUTPUT.exists() or JSON_OUTPUT.exists():
        raise FileExistsError(
            "analysis output already exists"
        )

    local = load_jsonl(LOCAL_INPUT)
    remote = load_jsonl(REMOTE_INPUT)
    pairs = pair_records(local, remote)
    result = analyze(pairs)

    write_csv(result["policies"], CSV_OUTPUT)
    write_json(result, JSON_OUTPUT)

    print(f"Paired observations: {len(pairs)}")

    for policy in result["policies"]:
        print(
            f"{policy['policy']:18} "
            f"pass={policy['selected_passes']:3}/"
            f"{policy['observations']} "
            f"remote={policy['remote_calls']:3} "
            f"cost=${policy['reported_remote_cost']:.8f}"
        )

    criterion = result["primary_criterion"]
    interval = result["bootstrap"][
        "percentile_95_interval"
    ]

    print(
        "Fine-minus-remote gap: "
        f"{criterion['observed_success_gap']:+.1%}"
    )
    print(
        "Bootstrap 95% interval: "
        f"[{interval['lower']:+.1%}, "
        f"{interval['upper']:+.1%}]"
    )
    print(
        "Primary criterion: "
        f"{'PASS' if criterion['overall_passed'] else 'FAIL'}"
    )


if __name__ == "__main__":
    main()
