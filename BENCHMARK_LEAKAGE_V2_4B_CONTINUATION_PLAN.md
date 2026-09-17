# Benchmark Leakage Controls v2 — 4B Continuation Plan

Status: **FROZEN BEFORE 4B CONTINUATION**

Date frozen: 2026-09-17

This continuation covers only the missing `gemma3:4b` stratum after the
residency incident. It does not rerun the completed 270M or 1B strata.

## Inputs

- retained prior partial: `benchmark_leakage_v2_retry_runs.jsonl.partial`;
- required prior partial rows: 180, exactly 90 for each of `gemma3:270m` and
  `gemma3:1b`;
- fresh tasks: `benchmark_tasks_leakage_v2.json`;
- fresh oracle: `benchmark_oracle_leakage_v2.json`.

The prior partial is not a canonical result. Before combination, a validator
must authenticate every row's task, variant, condition, repetition, model
identity, provenance, and telemetry, and verify exactly 180 rows.

## 4B execution

- model: `gemma3:4b`;
- 3 repetitions per 20 variants and condition;
- 60 ordinary model rows and 120 ablation rows;
- temperature 0, maximum output tokens 256, no experiment-level retries;
- new output: `benchmark_leakage_v2_4b_runs.jsonl`.
- continuation wrapper: `run_benchmark_leakage_v2_4b.py`, SHA-256
  `773cc230598fc27561918c0cc211d541859a59ad9df7669222922a79787e3955`;

Read-only preflight must authenticate the installed 4B tag, digest, package
metadata, and residency. Because the incident found 4B non-resident, one
explicit warm-up request is authorized before the continuation. It uses the
non-benchmark prompt `Reply with the single word READY.`, records only separate
warm-up metadata and a raw-output hash in
`benchmark_leakage_v2_4b_warmup.json`, and contributes no row to benchmark
evidence or scoring. The benchmark starts only after a second read-only
residency check passes.

## Completion gate

Only after 4B produces exactly 180 rows may an analyzer combine the authenticated
270M, 1B, and 4B evidence. The original empty partial and the 180-row retry
partial remain preserved as incident evidence.
