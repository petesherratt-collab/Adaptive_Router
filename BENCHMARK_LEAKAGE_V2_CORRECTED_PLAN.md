# Benchmark Leakage Controls v2 — Corrected Full Run

Status: **FROZEN BEFORE MODEL EXECUTION**

Date frozen: 2026-09-17

This corrected run supersedes the count-mismatched launch and the incomplete
270M/1B residency retry. Earlier partials and unretained outputs remain
incident artifacts and are not inputs to this run.

## Scope

- 10 fresh task IDs;
- base and mutant variants for each: 20 variants;
- models in order: `gemma3:270m`, `gemma3:1b`, `gemma3:4b`;
- 3 repetitions per variant and condition;
- ordinary model plus input-removed and input-shuffled ablations;
- 540 rows total: 180 ordinary and 360 ablation;
- temperature 0, maximum output tokens 256, no experiment-level retries;
- router policy not invoked or modified.

## Authenticated inputs

| Artifact | SHA-256 |
|---|---|
| `benchmark_tasks_leakage_v2.json` | `f83126da7ca0203074297680d88bfe8b5d00c30306902e5481194ed57e13f6b7` |
| `benchmark_oracle_leakage_v2.json` | `70c20a3586669791498f9aa7b8e2eba56f18fb555fb53b7a369549ba63e2f86d` |
| `run_benchmark_leakage_v2_corrected.py` | `c36d0d7248bc4e849d8784572d327026339b0eb464788402e63852ae2700857d` |

The corrected bundle passed separated-suite validation, mutation-pair checks,
request-boundary checks, and null-baseline screening for all 20 variants.

## Evidence boundary

Canonical output is `benchmark_leakage_v2_corrected_runs.jsonl`, with a new
`.partial` path. Existing v2 partials are preserved and excluded. Each row
records model identity, config and plan hashes, raw and normalized output,
both oracle verdicts, reason code, telemetry, and condition metadata.

No execution begins until the pending hashes are filled and this plan and
wrapper are committed together.
