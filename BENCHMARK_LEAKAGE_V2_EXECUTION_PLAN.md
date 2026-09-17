# Benchmark Leakage Controls v2 — Three-Model Execution Plan

Status: **FROZEN BEFORE MODEL EXECUTION**

Date frozen: 2026-09-17

This plan covers the fresh v2 expansion bundle and leaves all v1 evidence
immutable. It is frozen only after review, final runner authentication, and a
committed change.

## Frozen inputs under review

| Artifact | SHA-256 |
|---|---|
| `benchmark_tasks_leakage_v2.json` | `3b134115bb29eb760fe079e7d703f87cf12e7ae7dceebb0bfa3d75b471e29c2d` |
| `benchmark_oracle_leakage_v2.json` | `ba11fa14956b161c9ecb2f9b1c826a5ec8bc97466b63eb5db622138497e4dd95` |
| `benchmark_leakage_controls.py` | `671502409e1c5042e804c31014e586a77fca32fe219759d1e5d9ae5425b72a54` |
| `benchmark_leakage_preflight.py` | `6e0990beb0b490d37f753ea5b3194b1e69f82cdc6a0f7b47999c3caf37fd34f5` |
| `benchmark_leakage_runner.py` | `f552d253120d794af9842b87c8d6cefc7e521af0451c36c6dbc68d100df7752e2` |
| `run_benchmark_leakage_v2.py` | `9a6272a4e97ced6072378e442960e69d5940e95d03ccfa3be7ec57d66e84bf68` |

Offline review confirms 20 variants, 20 ablation conditions, valid mutation
pairs, matching task/oracle keys, and `CV_OK` for every variant against the
current null baselines.

## Frozen execution parameters

| Parameter | Value |
|---|---|
| Provider | Ollama local |
| Model order | `gemma3:270m`, `gemma3:1b`, `gemma3:4b` |
| Repetitions | 3 per variant and condition |
| Temperature | 0 |
| Maximum output tokens | 256 |
| Conditions | ordinary model, input-removed ablation, input-shuffled ablation |
| Experiment-level retries | 0 |
| Router policy | not invoked or modified |

Per model this is 60 ordinary observations and 120 ablation observations. The
full run is 180 ordinary model observations and 360 ablation observations.

Canonical evidence will be written once to `benchmark_leakage_v2_runs.jsonl`;
the wrapper refuses existing canonical or partial paths and writes a partial
file until all three model strata reconcile.

## Model identities to authenticate before execution

| Model | Digest | Parameters | Quantization | Package bytes |
|---|---|---:|---|---:|
| `gemma3:270m` | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` | 268.10M | Q8_0 | 291554930 |
| `gemma3:1b` | `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc` | 999.89M | Q4_K_M | 815319791 |
| `gemma3:4b` | `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` | 4.3B | Q4_K_M | 3338801804 |

The installed tag, digest, package metadata, and residency must be checked
read-only immediately before the first request for each model. A mismatch
blocks execution.

## Output and ordering rules

Canonical outputs must be new v2 paths and must refuse existing canonical or
partial files. Model order is fixed as listed above. Each row must include
model tag/digest, config hash, implementation revision, condition, variant,
repetition, raw and normalized output, both oracle verdicts, reason code,
telemetry, and residency/cache metadata.

No model request is permitted until this plan is present in a committed change.
Any provider or
instrumentation failure is retained as a diagnosed result or fails closed; no
silent retry, prompt repair, task replacement, or evidence overwrite is
allowed.

## Analysis boundary

Null-baseline, ablation, mutation, normalization, model-correctness, and any
operational metrics must be reported separately. Classification remains a
semantic-oracle question, not merely permitted-label conformance. No result
supports semantic correctness, routing promotion, or generalization beyond
this frozen suite.
