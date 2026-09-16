# Benchmark Leakage Controls v1 — Pre-Execution Review

Date: 2026-09-16
Status: **NOT READY FOR MODEL EXECUTION**

This is a review of the offline control implementation and fresh separated
bundle. No model or network call was made.

## Authenticated artifacts

| Artifact | SHA-256 |
|---|---|
| `BENCHMARK_LEAKAGE_CONTROLS_V1_PLAN.md` | `d3e8f5c459b813c7c4f1a92cee57e2da5ec185548feca5dd11d835bc08506960` |
| `benchmark_tasks_leakage_v1.json` | `5ab3acf293e24d586f7c174221d7e1c89cfe3a92bea3f0d9b53d0e93d15a9da5` |
| `benchmark_oracle_leakage_v1.json` | `a2593bd02f0a39762368346af68c24c8702267fa5e3b900fb40256e4549b8875` |
| `benchmark_leakage_controls.py` | `671502409e1c5042e804c31014e586a77fca32fe219759d1e5d9ae5425b72a54` |
| `benchmark_leakage_preflight.py` | `6e0990beb0b490d37f753ea5b3194b1e69f82cdc6a0f7b47999c3caf37fd34f5` |
| `analyze_benchmark_leakage_v1.py` | `2070275a0ee2881957e19a8ca567b3135ece7a7ed88218531d7b43bc2d418c79` |
| `benchmark_leakage_runner.py` | `715339d9835cd9129bc5856a3e278ce3cce24ecb18d4cde40fc492e5ae4a1410` |

## Structural checks

- 10 task variants and 10 matching oracle keys: **PASS**.
- Five task IDs, each with `base` and `mut1`: **PASS**.
- Mutation pairs preserve task class and change prompt content: **PASS**.
- Request payloads contain only model, task identity, variant identity, and
  prompt: **PASS**.
- Twelve scalar string leaves from oracle expected values checked for leakage
  outside prompt fields: **PASS**.
- Twenty deterministic ablation conditions generated: **PASS**.
- Focused regression tests: **22/22 PASS**.
- Whitespace validation: **PASS**.

## Null-baseline finding and redesign

The initial offline report identified three variants that were passable by a
trivial baseline:

| Task variant | Baseline | Status |
|---|---|---|
| `classify_sentiment__base` | `constant_positive` | `CV_NULL_BASELINE_PASSES` |
| `extract_person__base` | `longest_capitalised_span` | `CV_NULL_BASELINE_PASSES` |
| `extract_person__mut1` | `longest_capitalised_span` | `CV_NULL_BASELINE_PASSES` |

Those variants were redesigned before any model execution: the sentiment base
was changed to a neutral case, and both person prompts gained longer
capitalized distractor spans. The updated offline report now marks **all 10
variants `CV_OK`** against the implemented baselines. This is a design-stage
resolution, not evidence of model capability.

## Remaining blockers

The bundle remains not ready for model execution because:

1. No model condition has been run.
2. No ablation condition has been run against a model; all ablated outputs are
   therefore pending.
3. No model-based base/mutant agreement or divergence is available.
4. The 10-variant bundle is a control pilot, not yet a replacement for a full
   benchmark suite.

No model execution should begin until the exclusions/redesign decision,
repetition count, model identity, execution budget, and immutable output paths
are frozen and hashed.
