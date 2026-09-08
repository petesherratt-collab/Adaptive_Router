"""Retrospective, offline error analysis for runtime v0.3 JSON shadow V2."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
import os
from pathlib import Path
from statistics import median
from typing import Any

import analyze_runtime_v0_3_shadow_json_v2 as v2_analysis
import runtime_v0_3_shadow_json_v2 as pv


ROOT = Path(__file__).resolve().parent
PROTOCOL_NAME = "RUNTIME_V0_3_JSON_ERROR_ANALYSIS_V1_PLAN.md"
PROTOCOL_SHA256 = "3e0a9475c894469f5a8881b4e6063770628b1f789dd296130af61bfe3687aeef"
SCHEMA_VERSION = "runtime_v0_3_json_error_analysis_v1"
INPUT_HASHES = {
    pv.BENCHMARK_NAME: pv.BENCHMARK_SHA256,
    "runtime_v0_3_shadow_json_v2_runs.jsonl":
        "1b846bb04cbf335d8bce8b37e5d94cb509a4a06f9a476408023ee7cf80060702",
    "runtime_v0_3_shadow_json_v2_router_telemetry.jsonl":
        "333a073ab9c50aaa4aafed2f1bc09e65bff49fa7bf45960db016d50a1ae16ba6",
    "runtime_v0_3_shadow_json_v2_summary.json":
        "d2a1a1f1d007ebb226f1fadb3df63e7e8248d0ff7514414b35fdec5bfd5c2a6e",
    "runtime_v0_3_shadow_json_v2_analysis.json":
        "b4a93b8ecee9dc45d17dc281c903cd5a1629ef7f95edc42433562438e0393160",
}
OUTPUT_NAMES = {
    "json": "runtime_v0_3_json_error_analysis_v1.json",
    "csv": "runtime_v0_3_json_error_analysis_v1.csv",
    "markdown": "RUNTIME_V0_3_JSON_ERROR_ANALYSIS_V1.md",
}
STRATA = tuple(pv.STRATUM_COUNTS)
PRIMARY_PRECEDENCE = (
    "provider_failure",
    "unparseable_candidate",
    "member_set",
    "container_type",
    "scalar_type",
    "array_length",
    "scalar_value",
    "exact",
)
DEPLOYABLE_FAMILIES = {
    "contract_pass",
    "contract_pass_single_stratum",
    "contract_pass_stratum_allowlist",
    "preoutput_stratum",
    "contract_signature",
}
FORBIDDEN_FEATURES = {
    "task_id", "source_literal", "expected_value", "oracle_result",
    "remote_result", "error_class",
}


def output_paths(root=ROOT):
    root = Path(root)
    return {key: root / name for key, name in OUTPUT_NAMES.items()}


def _read_jsonl(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.endswith("\n") or any(not line for line in text.splitlines()):
        raise pv.FrozenDesignError("MALFORMED_OR_TRUNCATED_JSONL")
    return [pv.strict_json_loads(line) for line in text.splitlines()]


def authenticate_inputs(root=ROOT):
    root = Path(root)
    if pv.file_sha256(root / PROTOCOL_NAME) != PROTOCOL_SHA256:
        raise pv.FrozenDesignError("ERROR_ANALYSIS_PROTOCOL_HASH_MISMATCH")
    for name, expected in INPUT_HASHES.items():
        if pv.file_sha256(root / name) != expected:
            raise pv.FrozenDesignError("ERROR_ANALYSIS_INPUT_HASH_MISMATCH=" + name)

    _, tasks, inventory = pv.load_frozen_inputs(root)
    rows = _read_jsonl(root / "runtime_v0_3_shadow_json_v2_runs.jsonl")
    telemetry = _read_jsonl(
        root / "runtime_v0_3_shadow_json_v2_router_telemetry.jsonl"
    )
    summary = pv.strict_json_loads(
        (root / "runtime_v0_3_shadow_json_v2_summary.json").read_text(
            encoding="utf-8"
        )
    )
    sealed_analysis = pv.strict_json_loads(
        (root / "runtime_v0_3_shadow_json_v2_analysis.json").read_text(
            encoding="utf-8"
        )
    )
    revision = summary.get("implementation_revision")
    pv.validate_rows(rows, tasks, revision)
    recomputed = v2_analysis.analyze_rows(rows, tasks, revision)
    if sealed_analysis != recomputed:
        raise pv.FrozenDesignError("SEALED_ANALYSIS_RECOMPUTE_MISMATCH")
    if (
        len(telemetry) != pv.OBSERVATION_COUNT
        or [row["router_request_id"] for row in rows]
        != [record.get("request_id") for record in telemetry]
        or any(row["router_telemetry"] != record for row, record in zip(rows, telemetry))
        or summary.get("runs_sha256") != INPUT_HASHES[
            "runtime_v0_3_shadow_json_v2_runs.jsonl"
        ]
        or summary.get("router_telemetry_sha256") != INPUT_HASHES[
            "runtime_v0_3_shadow_json_v2_router_telemetry.jsonl"
        ]
        or summary.get("observation_count") != pv.OBSERVATION_COUNT
        or summary.get("runtime_correct_count")
        != sealed_analysis["overall"]["runtime_correct_count"]
        or summary.get("local_accepted_error_count")
        != sealed_analysis["overall"]["local_accepted_error_count"]
    ):
        raise pv.FrozenDesignError("ERROR_ANALYSIS_CROSS_FILE_MISMATCH")
    return rows, tasks, inventory, sealed_analysis


def _json_type(value):
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) in (int, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _pointer(path, token):
    escaped = str(token).replace("~", "~0").replace("/", "~1")
    return path + "/" + escaped


def recursive_differences(expected, candidate, path=""):
    """Return value-free recursive difference records."""
    expected_type = _json_type(expected)
    candidate_type = _json_type(candidate)
    if expected_type != candidate_type:
        containers = {"object", "array"}
        kind = (
            "container_type"
            if expected_type in containers or candidate_type in containers
            else "scalar_type"
        )
        return [{
            "class": kind,
            "path": path or "/",
            "expected_type": expected_type,
            "candidate_type": candidate_type,
        }]
    if isinstance(expected, dict):
        differences = []
        for key in sorted(set(expected) - set(candidate)):
            differences.append({
                "class": "missing_member",
                "path": _pointer(path, key),
                "expected_type": _json_type(expected[key]),
                "candidate_type": "missing",
            })
        for key in sorted(set(candidate) - set(expected)):
            differences.append({
                "class": "unexpected_member",
                "path": _pointer(path, key),
                "expected_type": "missing",
                "candidate_type": _json_type(candidate[key]),
            })
        for key in sorted(set(expected) & set(candidate)):
            differences.extend(
                recursive_differences(expected[key], candidate[key], _pointer(path, key))
            )
        return differences
    if isinstance(expected, list):
        differences = []
        if len(expected) != len(candidate):
            differences.append({
                "class": "array_length",
                "path": path or "/",
                "expected_type": "array",
                "candidate_type": "array",
            })
        for index, (left, right) in enumerate(zip(expected, candidate)):
            differences.extend(
                recursive_differences(left, right, _pointer(path, index))
            )
        return differences
    equal = (
        expected == candidate
        if expected_type != "number"
        else float(expected) == float(candidate)
    )
    if equal:
        return []
    return [{
        "class": "scalar_value",
        "path": path or "/",
        "expected_type": expected_type,
        "candidate_type": candidate_type,
    }]


def primary_class(differences, provider_success=True, parse_error=None):
    if not provider_success:
        return "provider_failure"
    if parse_error:
        return "unparseable_candidate"
    classes = {item["class"] for item in differences}
    if classes & {"missing_member", "unexpected_member"}:
        classes.add("member_set")
    for name in PRIMARY_PRECEDENCE:
        if name == "exact" or name in classes:
            return name
    raise AssertionError("unreachable")


def _canonical_candidate(row):
    oracle = row["local_oracle"]
    if not row["local"]["success"]:
        return "provider_failure:" + row["local"]["error"]
    if oracle.get("error"):
        return "parse_error:" + oracle["error"]
    return json.dumps(
        oracle.get("normalized"), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    )


def classify_rows(rows, inventory):
    classified = []
    for row in rows:
        task = inventory[row["task_id"]]
        local = row["local"]
        oracle = row["local_oracle"]
        parse_error = oracle.get("error")
        differences = []
        if local["success"] and not parse_error:
            differences = recursive_differences(
                task["oracle"]["expected_json"], oracle.get("normalized")
            )
        classified.append({
            "task_id": row["task_id"],
            "repetition": row["repetition"],
            "stratum": row["stratum"],
            "provider_success": local["success"],
            "contract_pass": row["local_contract"]["status"] == "PASS",
            "correct": bool(oracle["correct"]),
            "remote_correct": bool(row["remote_oracle"]["correct"]),
            "accepted_error": (
                row["local_contract"]["status"] == "PASS"
                and not oracle["correct"]
            ),
            "primary_class": primary_class(
                differences, local["success"], parse_error
            ),
            "differences": differences,
            "differing_path_count": len({item["path"] for item in differences}),
            "candidate_key": _canonical_candidate(row),
            "local_total_ms": float(local["total_ms"]),
            "tokens_per_second": local.get("tokens_per_second"),
        })
    return classified


def _scope(items):
    cross = Counter(
        ("PASS" if item["contract_pass"] else "FAIL",
         "CORRECT" if item["correct"] else "INCORRECT")
        for item in items
    )
    leaf = Counter(
        difference["class"]
        for item in items for difference in item["differences"]
    )
    primary = Counter(item["primary_class"] for item in items)
    paths = Counter(
        difference["path"]
        for item in items for difference in item["differences"]
    )
    rates = [
        float(item["tokens_per_second"])
        for item in items
        if type(item.get("tokens_per_second")) in (int, float)
        and not isinstance(item.get("tokens_per_second"), bool)
        and math.isfinite(item["tokens_per_second"])
    ]
    return {
        "observation_count": len(items),
        "task_count": len({item["task_id"] for item in items}),
        "local_provider_success_count": sum(item["provider_success"] for item in items),
        "local_contract_pass_count": sum(item["contract_pass"] for item in items),
        "local_correct_count": sum(item["correct"] for item in items),
        "local_accepted_error_count": sum(item["accepted_error"] for item in items),
        "contract_oracle_cross_tab": {
            f"{contract}_{oracle}": cross[(contract, oracle)]
            for contract in ("PASS", "FAIL")
            for oracle in ("CORRECT", "INCORRECT")
        },
        "leaf_difference_counts": dict(sorted(leaf.items())),
        "difference_path_counts": dict(sorted(paths.items())),
        "primary_class_counts": dict(sorted(primary.items())),
        "differing_path_counts": dict(sorted(Counter(
            item["differing_path_count"] for item in items
        ).items())),
        "median_local_total_ms": median(item["local_total_ms"] for item in items),
        "median_tokens_per_second": median(rates) if rates else None,
    }


def _declared_depth(explicit_types):
    return max(
        (2 if value in {"array", "object"} else 1)
        for value in explicit_types.values()
    )


def contract_signature(task):
    contract = task["runtime_request"]["contract"]
    counts = Counter(contract["explicit_types"].values())
    return {
        "top_level_key_count": len(contract["exact_keys"]),
        "declared_type_counts": dict(sorted(counts.items())),
        "maximum_declared_nesting_depth": _declared_depth(contract["explicit_types"]),
    }


def task_table(classified, inventory):
    grouped = defaultdict(list)
    for item in classified:
        grouped[item["task_id"]].append(item)
    result = []
    for task_id in [task["task_id"] for task in inventory.values()]:
        items = sorted(grouped[task_id], key=lambda item: item["repetition"])
        if len(items) != pv.REPETITIONS:
            raise pv.FrozenDesignError("ERROR_ANALYSIS_TASK_CLUSTER_SIZE")
        correct = sum(item["correct"] for item in items)
        passed = sum(item["contract_pass"] for item in items)
        result.append({
            "task_id": task_id,
            "stratum": items[0]["stratum"],
            "correct_repetitions": correct,
            "contract_pass_repetitions": passed,
            "accepted_error_repetitions": sum(item["accepted_error"] for item in items),
            "unique_candidate_count": len({item["candidate_key"] for item in items}),
            "correctness_pattern": (
                "unanimous_correct" if correct == 3
                else "unanimous_error" if correct == 0
                else "mixed_correctness"
            ),
            "contract_pattern": (
                "unanimous_pass" if passed == 3
                else "unanimous_fail" if passed == 0
                else "mixed_contract_status"
            ),
            "contract_signature": contract_signature(inventory[task_id]),
            "primary_classes": dict(sorted(Counter(
                item["primary_class"] for item in items
            ).items())),
            "retrospective_only": True,
        })
    return result


def task_pattern_summary(tasks):
    return {
        "correctness_patterns": dict(sorted(Counter(
            task["correctness_pattern"] for task in tasks
        ).items())),
        "contract_patterns": dict(sorted(Counter(
            task["contract_pattern"] for task in tasks
        ).items())),
        "candidate_uniqueness": dict(sorted(Counter(
            task["unique_candidate_count"] for task in tasks
        ).items())),
    }


def _rule(rule_id, family, label, features, predicate, deployable=True):
    if set(features) & FORBIDDEN_FEATURES:
        raise pv.FrozenDesignError("FORBIDDEN_ROUTER_FEATURE=" + rule_id)
    return {
        "rule_id": rule_id,
        "family": family,
        "label": label,
        "features": sorted(features),
        "deployable": deployable,
        "predicate": predicate,
    }


def build_rules(classified, tasks):
    rules = [_rule(
        "contract_pass", "contract_pass", "contract PASS",
        {"contract_status"}, lambda item: item["contract_pass"],
    )]
    for stratum in STRATA:
        rules.append(_rule(
            "contract_pass_single_stratum:" + stratum,
            "contract_pass_single_stratum",
            "contract PASS and stratum=" + stratum,
            {"contract_status", "stratum"},
            lambda item, stratum=stratum:
                item["contract_pass"] and item["stratum"] == stratum,
        ))
    for mask in range(1, 1 << len(STRATA)):
        allowed = tuple(
            name for index, name in enumerate(STRATA) if mask & (1 << index)
        )
        token = "+".join(allowed)
        rules.append(_rule(
            "contract_pass_allowlist:" + token,
            "contract_pass_stratum_allowlist",
            "contract PASS and stratum in " + token,
            {"contract_status", "stratum"},
            lambda item, allowed=frozenset(allowed):
                item["contract_pass"] and item["stratum"] in allowed,
        ))
    for stratum in STRATA:
        rules.append(_rule(
            "preoutput_stratum:" + stratum,
            "preoutput_stratum", "stratum=" + stratum,
            {"stratum"}, lambda item, stratum=stratum: item["stratum"] == stratum,
        ))

    signatures = {}
    for task in tasks:
        signature = contract_signature(task)
        token = json.dumps(signature, sort_keys=True, separators=(",", ":"))
        signatures[token] = signature
    task_signatures = {
        task["task_id"]: json.dumps(
            contract_signature(task), sort_keys=True, separators=(",", ":")
        ) for task in tasks
    }
    for index, token in enumerate(sorted(signatures), start=1):
        rules.append(_rule(
            f"contract_signature:{index:02d}", "contract_signature", token,
            {"contract_signature"},
            lambda item, token=token: task_signatures[item["task_id"]] == token,
        ))

    grouped = defaultdict(list)
    for item in classified:
        grouped[item["task_id"]].append(item)
    unanimous = {
        task_id for task_id, items in grouped.items()
        if len(items) == 3
        and all(item["contract_pass"] for item in items)
        and len({item["candidate_key"] for item in items}) == 1
    }
    rules.append(_rule(
        "three_rep_unanimous_pass_and_value",
        "three_repetition_unanimity",
        "three local calls all PASS with identical canonical candidate",
        {"contract_status", "candidate_replication"},
        lambda item: item["task_id"] in unanimous,
        deployable=False,
    ))
    return rules


def evaluate_rule(rule, classified):
    accepted = [item for item in classified if rule["predicate"](item)]
    accepted_tasks = {item["task_id"] for item in accepted}
    error_tasks = {
        item["task_id"] for item in accepted if not item["correct"]
    }
    errors = sum(not item["correct"] for item in accepted)
    counterfactual = sum(
        item["correct"] if rule["predicate"](item) else item["remote_correct"]
        for item in classified
    )
    runtime_correct = sum(item["remote_correct"] for item in classified)
    upper = (
        v2_analysis.clopper_pearson_upper(errors, len(accepted))
        if accepted else 1.0
    )
    eligible = (
        rule["deployable"]
        and rule["family"] in DEPLOYABLE_FAMILIES
        and not set(rule["features"]) & FORBIDDEN_FEATURES
        and len(accepted_tasks) >= 10
        and errors == 0
        and counterfactual >= runtime_correct
    )
    return {
        "rule_id": rule["rule_id"],
        "family": rule["family"],
        "label": rule["label"],
        "features": rule["features"],
        "deployable": rule["deployable"],
        "accepted_row_count": len(accepted),
        "accepted_task_cluster_count": len(accepted_tasks),
        "correct_accepted_rows": len(accepted) - errors,
        "incorrect_accepted_rows": errors,
        "tasks_with_accepted_error": len(error_tasks),
        "accepted_error_rate": errors / len(accepted) if accepted else None,
        "accepted_error_upper_95": upper,
        "remote_logical_calls_avoided": len(accepted),
        "counterfactual_correct_count": counterfactual,
        "runtime_correct_count": runtime_correct,
        "candidate_screen": (
            "CANDIDATE_FOR_FRESH_TEST_ONLY" if eligible
            else "NOT_A_CANDIDATE"
        ),
        "retrospective_only": True,
    }


def analyze(rows, tasks, inventory, sealed_analysis):
    classified = classify_rows(rows, inventory)
    task_rows = task_table(classified, inventory)
    rules = build_rules(classified, tasks)
    subgroup_rows = [evaluate_rule(rule, classified) for rule in rules]
    candidates = [
        item["rule_id"] for item in subgroup_rows
        if item["candidate_screen"] == "CANDIDATE_FOR_FRESH_TEST_ONLY"
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "analysis_status": "RETROSPECTIVE_ONLY",
        "protocol_sha256": PROTOCOL_SHA256,
        "authenticated_inputs": dict(INPUT_HASHES),
        "sealed_v2_decision": sealed_analysis["promotion"]["decision"],
        "sealed_v2_correctness_overlap": {
            "overall": sealed_analysis["overall"]["overlap"],
            "by_stratum": {
                stratum: sealed_analysis["by_stratum"][stratum]["overlap"]
                for stratum in STRATA
            },
        },
        "overall": _scope(classified),
        "by_stratum": {
            stratum: _scope([
                item for item in classified if item["stratum"] == stratum
            ]) for stratum in STRATA
        },
        "task_pattern_summary": task_pattern_summary(task_rows),
        "row_classifications": [{
            key: item[key] for key in (
                "task_id",
                "repetition",
                "stratum",
                "provider_success",
                "contract_pass",
                "correct",
                "accepted_error",
                "primary_class",
                "differing_path_count",
                "differences",
            )
        } for item in classified],
        "tasks": task_rows,
        "subgroup_inventory": subgroup_rows,
        "subgroup_family_counts": dict(sorted(Counter(
            item["family"] for item in subgroup_rows
        ).items())),
        "candidate_screen": {
            "decision": (
                "CANDIDATE_FOR_FRESH_TEST_ONLY" if candidates
                else "NO_RULE_CANDIDATE"
            ),
            "candidate_rule_ids": candidates,
        },
        "interpretation": [
            "MODEL_CHANGE_CANDIDATE",
        ],
        "prohibited_claims": [
            "V2 validates a successor policy",
            "contract PASS establishes semantic correctness",
            "retrospective subgroups authorize local serving",
        ],
    }
    if (
        report["overall"]["observation_count"] != 120
        or report["overall"]["task_count"] != 40
        or len(task_rows) != 40
        or len(rules) != len(subgroup_rows)
        or report["overall"]["local_accepted_error_count"]
        != sealed_analysis["overall"]["local_accepted_error_count"]
        or report["overall"]["local_correct_count"]
        != sealed_analysis["overall"]["local_correct_count"]
    ):
        raise pv.FrozenDesignError("ERROR_ANALYSIS_RECONCILIATION_FAILED")
    return report


def build_analysis(root=ROOT):
    rows, tasks, inventory, sealed = authenticate_inputs(root)
    return analyze(rows, tasks, inventory, sealed)


def _csv_safe(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def csv_rows(report):
    rows = []
    for task in report["tasks"]:
        rows.append({
            "record_type": "task",
            "record_id": task["task_id"],
            "family_or_stratum": task["stratum"],
            "accepted_rows": "",
            "accepted_tasks": "",
            "correct_rows": task["correct_repetitions"],
            "incorrect_rows": 3 - task["correct_repetitions"],
            "accepted_errors": task["accepted_error_repetitions"],
            "accepted_error_rate": "",
            "accepted_error_upper_95": "",
            "counterfactual_correct": "",
            "candidate_screen": "",
            "detail": {
                "contract_pattern": task["contract_pattern"],
                "correctness_pattern": task["correctness_pattern"],
                "unique_candidate_count": task["unique_candidate_count"],
                "contract_signature": task["contract_signature"],
            },
            "retrospective_only": True,
        })
    for item in report["subgroup_inventory"]:
        rows.append({
            "record_type": "subgroup",
            "record_id": item["rule_id"],
            "family_or_stratum": item["family"],
            "accepted_rows": item["accepted_row_count"],
            "accepted_tasks": item["accepted_task_cluster_count"],
            "correct_rows": item["correct_accepted_rows"],
            "incorrect_rows": item["incorrect_accepted_rows"],
            "accepted_errors": item["incorrect_accepted_rows"],
            "accepted_error_rate": item["accepted_error_rate"],
            "accepted_error_upper_95": item["accepted_error_upper_95"],
            "counterfactual_correct": item["counterfactual_correct_count"],
            "candidate_screen": item["candidate_screen"],
            "detail": {"label": item["label"], "features": item["features"]},
            "retrospective_only": True,
        })
    return [{key: _csv_safe(value) for key, value in row.items()} for row in rows]


def markdown_report(report):
    overall = report["overall"]
    task_patterns = report["task_pattern_summary"]
    lines = [
        "# Runtime v0.3 structural-JSON error analysis V1",
        "",
        "**Status:** RETROSPECTIVE ONLY  ",
        f"**Candidate screen:** {report['candidate_screen']['decision']}  ",
        f"**Sealed V2 decision:** {report['sealed_v2_decision']}",
        "",
        "## Observations",
        "",
        f"The local provider completed all {overall['observation_count']} observations "
        f"across {overall['task_count']} task clusters. It was oracle-correct on "
        f"{overall['local_correct_count']}/120 rows. The structural contract passed "
        f"{overall['local_contract_pass_count']} rows, including "
        f"{overall['local_accepted_error_count']} semantic errors.",
        "",
        "| Stratum | Correct | Contract PASS | Accepted errors |",
        "|---|---:|---:|---:|",
    ]
    for stratum in STRATA:
        value = report["by_stratum"][stratum]
        lines.append(
            f"| {stratum} | {value['local_correct_count']}/30 | "
            f"{value['local_contract_pass_count']}/30 | "
            f"{value['local_accepted_error_count']} |"
        )
    lines.extend([
        "",
        "## Deterministic derivations",
        "",
        "Primary error classes count each row once. Leaf-difference counts may count "
        "more than one path per row.",
        "",
        "```json",
        json.dumps({
            "primary_class_counts": overall["primary_class_counts"],
            "leaf_difference_counts": overall["leaf_difference_counts"],
            "task_patterns": task_patterns,
        }, indent=2, sort_keys=True),
        "```",
        "",
        "Every predeclared subgroup is present in the JSON and CSV outputs. No "
        "deployable subgroup passed the frozen candidate screen.",
        "",
        "## Candidate hypotheses",
        "",
        "- **MODEL_CHANGE_CANDIDATE:** Gemma 3 270M is inadequate for this "
        "structural-JSON distribution. V2 does not validate any replacement model.",
        "No validator-change candidate is established: this analysis does not "
        "specify and test an oracle-free deterministic check that both rejects an "
        "accepted error and retains a correct local PASS.",
        "",
        "Neither hypothesis changes the shipped remote-authoritative policy.",
        "",
        "## Prohibited claims",
        "",
        "- This retrospective analysis does not validate a successor router.",
        "- Contract PASS does not establish semantic correctness.",
        "- Favorable V2 subgroups do not authorize local serving.",
        "",
        "## Gotchas",
        "",
        "The dataset contains 120 rows but only 40 task clusters. Three repetitions "
        "do not create 120 independent tasks. Exhaustively printing subgroup results "
        "limits cherry-picking but does not remove post-selection bias.",
        "",
        "A fast local arm is not automatically useful: rejected local calls add "
        "latency before fallback, while accepted semantic errors remove correctness.",
        "",
    ])
    return "\n".join(lines)


def _write_text_atomic(path, text):
    partial, handle = pv.open_partial(path)
    try:
        handle.write(text.rstrip("\n") + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    pv.publish_partial(partial, path)


def write_analysis(root=ROOT):
    paths = output_paths(root)
    if any(path.exists() or Path(str(path) + ".partial").exists()
           for path in paths.values()):
        raise pv.StateError("ERROR_ANALYSIS_OUTPUT_ALREADY_EXISTS")
    report = build_analysis(root)
    pv.atomic_write_json(paths["json"], report)
    rows = csv_rows(report)
    partial, handle = pv.open_partial(paths["csv"])
    try:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    pv.publish_partial(partial, paths["csv"])
    _write_text_atomic(paths["markdown"], markdown_report(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    report = write_analysis() if args.write else build_analysis()
    print(json.dumps({
        "status": "PASS",
        "analysis_status": report["analysis_status"],
        "observation_count": report["overall"]["observation_count"],
        "task_count": report["overall"]["task_count"],
        "local_correct_count": report["overall"]["local_correct_count"],
        "local_contract_pass_count": report["overall"]["local_contract_pass_count"],
        "local_accepted_error_count": report["overall"]["local_accepted_error_count"],
        "subgroup_count": len(report["subgroup_inventory"]),
        "candidate_screen": report["candidate_screen"]["decision"],
        "provider_network_requests": 0,
        "repository_outputs_created": 3 if args.write else 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
