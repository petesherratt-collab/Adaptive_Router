# Benchmark Leakage Controls v2 — Retry Plan

Status: **FROZEN BEFORE MODEL EXECUTION**

Date frozen: 2026-09-17

This retry supersedes the failed launch recorded in
`BENCHMARK_LEAKAGE_V2_EXECUTION_INCIDENT.md`. It uses the same reviewed fresh
20-variant bundle and three-model scope, but a corrected wrapper and a new
canonical output path. The retained empty partial from the failed launch is
not an input and is not modified.

## Scope and parameters

- Models, in order: `gemma3:270m`, `gemma3:1b`, `gemma3:4b`;
- 3 repetitions per variant and condition;
- 20 variants, ordinary model plus input-removed and input-shuffled ablations;
- 540 total rows: 180 ordinary and 360 ablation;
- temperature 0, maximum output tokens 256, no experiment-level retries;
- router policy not invoked or modified.

## Authenticated inputs

| Artifact | SHA-256 |
|---|---|
| `benchmark_tasks_leakage_v2.json` | `3b134115bb29eb760fe079e7d703f87cf12e7ae7dceebb0bfa3d75b471e29c2d` |
| `benchmark_oracle_leakage_v2.json` | `ba11fa14956b161c9ecb2f9b1c826a5ec8bc97466b63eb5db622138497e4dd95` |
| `benchmark_leakage_runner.py` | `f552d253120d794af9842b87c8d6cefc7e521af0451c36c6dbc68d100df7752e2` |
| `run_benchmark_leakage_v2.py` | `7993c0c114520a23257955f86059f4caeef6acc61ca578af20f4b0b60efcfded` |

The corrected wrapper must be committed and its final hash inserted before
execution. The retry output is `benchmark_leakage_v2_retry_runs.jsonl`; both it
and its `.partial` path must be absent before the first request.

## Gate

Before execution, rerun all focused tests, authenticate all three model tags,
digests, package metadata, and residency, and confirm the original failed
partial remains preserved separately. Any failure blocks execution. A complete
retry must reconcile exactly 540 rows before atomic publication.
