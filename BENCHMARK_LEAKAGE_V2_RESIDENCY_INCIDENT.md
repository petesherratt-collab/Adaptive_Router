# Benchmark Leakage Controls v2 — Residency Incident

Date: 2026-09-17

The corrected v2 retry authenticated and completed the `gemma3:270m` and
`gemma3:1b` strata, writing 180 valid partial rows: 90 per model, comprising
60 ordinary model rows and 120 ablation rows per model.

Before the first `gemma3:4b` request, read-only residency authentication
failed because the model was not resident. The wrapper failed closed.

Observed effects:

- 270M and 1B provider calls completed and are retained only in
  `benchmark_leakage_v2_retry_runs.jsonl.partial`;
- 4B provider calls: 0;
- canonical retry output: not created;
- partial evidence: 180 rows, 255K bytes at incident time;
- no rows were overwritten, resumed, or deleted.

This is an operational/preflight failure, not a model result. The partial file
must remain immutable and be authenticated before any later analysis or
combination. A continuation must use a new plan and output path.

The first invocation of the 4B continuation wrapper also stopped before any
provider request because its request-boundary preflight omitted the required
oracle argument. No warm-up record or 4B output was created. The call was
corrected in place before retrying the already-frozen continuation; this is a
second implementation-only preflight defect, not evidence.

The corrected 4B continuation then executed 90 provider observations for the
five-task bundle, but stopped before publication because the wrapper asserted
the planned 180-row count while the bundle actually contained only 10
variants. Those 90 outputs were held in memory and were not written to an
evidence file. This is a design-count and execution-wrapper incident, not
model evidence. The v2 bundle is being expanded with five additional fresh
task IDs to reach the intended 20 variants, and a new corrected output path
and plan are required.
