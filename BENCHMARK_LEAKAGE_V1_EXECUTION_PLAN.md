# Benchmark Leakage Controls v1 — Execution Plan

Status: **FROZEN BEFORE MODEL EXECUTION**

Date frozen: 2026-09-16

This plan applies the controls in `BENCHMARK_LEAKAGE_CONTROLS_V1_PLAN.md` to
the fresh separated 10-variant bundle. It does not modify the frozen V2
benchmark or reuse its evidence.

## Frozen inputs

- Tasks: `benchmark_tasks_leakage_v1.json`
- Oracle: `benchmark_oracle_leakage_v1.json`
- Control implementation: `benchmark_leakage_controls.py`
- Preflight: `benchmark_leakage_preflight.py`
- Runner: `benchmark_leakage_runner.py`
- Execution wrapper: `run_benchmark_leakage_v1.py`
- Baseline report: `benchmark_leakage_v1_null_baseline_report.json`

The task and oracle files are separate. Task data contains no `expected`
field. Every task ID has a `base` and `mut1` variant. Current offline review
marks all 10 variants `CV_OK` against the implemented null baselines.

Authenticated input and implementation hashes at freeze:

| Artifact | SHA-256 |
|---|---|
| `benchmark_tasks_leakage_v1.json` | `5ab3acf293e24d586f7c174221d7e1c89cfe3a92bea3f0d9b53d0e93d15a9da5` |
| `benchmark_oracle_leakage_v1.json` | `a2593bd02f0a39762368346af68c24c8702267fa5e3b900fb40256e4549b8875` |
| `benchmark_leakage_controls.py` | `671502409e1c5042e804c31014e586a77fca32fe219759d1e5d9ae5425b72a54` |
| `benchmark_leakage_preflight.py` | `6e0990beb0b490d37f753ea5b3194b1e69f82cdc6a0f7b47999c3caf37fd34f5` |
| `analyze_benchmark_leakage_v1.py` | `2070275a0ee2881957e19a8ca567b3135ece7a7ed88218531d7b43bc2d418c79` |
| `benchmark_leakage_runner.py` | `457c29b3459ee461d7638aedafe2076e95e92d48c1484bdaa47b1bedc7dc2624` |
| `run_benchmark_leakage_v1.py` | `0fde692a8a4a2e4a2d26d8cde40a96e045139d890fd7c8f1890e9d7626c9dd71` |
| `benchmark_leakage_v1_null_baseline_report.json` | `c9a4af2d4928a77daa77cac14ee945bd72a2f2641614e307fb36aabf2dd8e374` |

## Frozen execution parameters

These values are copied from the repository's existing local configuration and
were explicitly reviewed before freeze:

| Parameter | Proposed value |
|---|---|
| Provider | Ollama local |
| Model | `gemma3:270m` |
| Repetitions | 3 per task variant and condition |
| Temperature | 0 |
| Maximum output tokens | 256 |
| Conditions | `model`, `ablation` |
| Ablation modes | `input_removed`, `input_shuffled` |
| Retries | 0 at experiment level |
| Router policy | not invoked or modified |

This produces 30 ordinary model observations and 60 ablation observations.
Null baselines remain offline and are not counted as model observations.
Canonical evidence will be written once to `benchmark_leakage_v1_runs.jsonl`;
the wrapper refuses an existing canonical or partial path.

Before freeze, preflight must authenticate the installed model tag and digest,
record residency, confirm the output paths are absent, and bind the execution
to the final plan and input hashes.

## Review result

The freeze review passed: all 10 variants are `CV_OK`, all 10 oracle keys match
the task variants, all mutation pairs validate, 20 ablation conditions are
deterministically generated, request-boundary leakage checks pass, and 22/22
focused tests pass. No provider call was made during review.

## Required pre-execution checks

1. Authenticate the installed model tag and digest, and record residency.
2. Revalidate this plan's commit and the frozen task/oracle/control hashes.
3. Run the separated-suite, variant, request-boundary, and mutation-pair
   preflights.
4. Run all null baselines through the shared oracle and normalization path.
5. Confirm no task has `CV_NULL_BASELINE_PASSES`.
6. Confirm the model runner records raw and normalized verdicts independently.
7. Confirm ablation and mutant results will be reported separately from
   capability scores.
8. Confirm immutable output paths and a no-overwrite policy.

## Execution gate

No model request may be issued unless every required pre-execution check passes
and this document is present in a committed change.
The execution commit must be recorded in every result row. A preflight failure
must create no canonical result file.

## Interpretation gate

Model passes are not sufficient for a capability claim. A task is eligible for
capability scoring only when:

- all null baselines fail;
- all ablation variants fail;
- mutation results are reported, with divergence flagged;
- raw and normalized correctness are both available; and
- contract conformance, operational survival, and oracle correctness remain
  separate metrics.

Any task failing a control is excluded or flagged according to the frozen
protocol. It is not repaired after seeing model output.
