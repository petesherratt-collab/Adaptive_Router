# Benchmark Leakage Controls v2 — Execution Incident

Date: 2026-09-17

The first invocation of the frozen v2 wrapper stopped before the first model
request. The injected generator callback referenced `result.success` before
the assignment expression had bound `result`, producing
`UnboundLocalError`.

Observed effects:

- provider calls: 0;
- canonical output: not created;
- retained partial path: `benchmark_leakage_v2_runs.jsonl.partial`, zero bytes;
- no model output or telemetry was written;
- the partial path is preserved and will not be resumed, deleted, or reused.

The wrapper was corrected by using an ordinary helper function that binds the
local result before inspecting its success state. The retry uses a new
canonical output path and requires a new frozen retry plan. This incident is an
implementation failure, not a model or benchmark result.
