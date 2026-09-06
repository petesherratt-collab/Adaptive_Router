# Runtime v0.3 Structural-JSON Shadow Evaluation V1 Plan

Status: **FROZEN BEFORE EXECUTION**

Date frozen: 2026-09-06

## Objective and boundary

Measure whether the released runtime v0.3 local model can safely replace the remote answer for a narrowly defined structural-JSON workload. Runtime v0.3 remains remote-authoritative throughout this experiment: local output is shadow evidence and is never returned.

The benchmark, oracle, execution policy, budget, measures, and promotion rule are frozen before any benchmark provider call. The 40 tasks are fresh and were not used in earlier router experiments. No outcome may be inspected before the execution package is committed. Any post-start deviation is retained and disclosed.

## Frozen identities

| Item | Value |
|---|---|
| Runtime release | `v0.3.0` |
| Runtime commit | `f67273d04ef9b8a3964ed4371390808bf6ba8ffe` |
| Local model | `gemma3:270m` |
| Local digest | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` |
| Remote model | `openai/gpt-5.6-luna` |
| Config SHA-256 | `36df214e322b8148614e0ac8289ddb77779e326e06d91e3780ea39b87bd01657` |
| Benchmark SHA-256 | `76378d8bdeba1facb3f43f41186b2e31f091d8baea7550f10c54d42803ed0f93` |

The execution implementation revision and plan SHA-256 must be pinned before provider calls.

## Suite

- 40 tasks × 3 repetitions = 120 paired observations.
- All requests use `extract_structured` and `structured_json`.
- Four 10-task strata: `flat_scalar`, `record_selection`, `type_boundary`, and `nested_collection`.
- Every observation captures an authoritative remote arm and local shadow arm for the same task and repetition.

## Execution boundary

Use an experiment-only config copy with `allow_user_visible_local=false`, shadow enabled, execution enabled, and sample rate 1.0. Do not modify live `config.json`. The router must return the remote result. Injected experiment providers may retain both raw arms in sealed evidence; ordinary router telemetry must remain text-free. No repair, semantic judge, second local attempt, or policy retry is permitted. The released bounded remote retry remains active.

## Budget and stop rules

| Quantity | Limit |
|---|---:|
| Remote logical calls | 120 |
| Remote HTTP attempts | 240 |
| Local logical calls | 120 |
| Reported remote cost | USD 0.03 |

Reserve maximum-attempt headroom before each observation. Retain a completed cost-crossing observation, then stop. Missing arms, provider errors, malformed telemetry, identity/hash mismatch, or budget exhaustion make the run incomplete and block promotion.

## Oracle separation

The runtime validator sees only contract and candidate text. It checks parseability, exact top-level keys, and declared top-level types; it never sees expected values or oracle results.

After both arms and telemetry are sealed, analysis applies an independent recursive exact-JSON oracle. Object order and insignificant JSON whitespace are ignored. Array order, strings, booleans, nulls, structure, and value types are significant. Numbers compare by numeric value; booleans never satisfy numbers. Validator PASS means conformance, not correctness.

## Frozen measures

Report local and remote correctness and contract passes; local accepted errors and correct rejections; paired both/local-only/remote-only/neither; counterfactual correctness if a local contract PASS replaced remote; actual remote, paired local, and counterfactual selected-path median latency; avoided remote calls; remote attempts/cost; and every result by stratum. All denominators are 120.

Use a fixed-seed task-cluster bootstrap with 10,000 draws: sample 40 task IDs with replacement and include all three repetitions. Report percentile 95% intervals for paired correctness difference and remote calls avoided, plus undefined draws.

For promotion, calculate the exact one-sided 95% Clopper-Pearson upper bound on accepted-error rate, denominator local contract passes.

## Precommitted promotion rule

Report `PROMOTION_CANDIDATE` only if:

1. all 120 observations and both arms are authenticated;
2. local accepted errors = 0;
3. local contract passes ≥ 60;
4. accepted-error upper bound ≤ 0.05;
5. counterfactual correctness ≥ remote correctness;
6. counterfactual avoids ≥ 60 remote logical calls;
7. counterfactual selected-path median latency ≤ remote median latency;
8. no instrumentation, identity, budget, execution, or analysis failure occurred.

Otherwise report `DO_NOT_PROMOTE`. Promotion only permits a later reviewed product change for this exact structural-JSON family; it neither changes config nor supports a broader local-capability claim.

## Canonical outputs and implementation gate

The runner must refuse execution if any canonical or partial output exists. Canonical outputs are:

- `runtime_v0_3_shadow_json_v1_runs.jsonl`
- `runtime_v0_3_shadow_json_v1_router_telemetry.jsonl`
- `runtime_v0_3_shadow_json_v1_summary.json`
- `runtime_v0_3_shadow_json_v1_analysis.json`
- `runtime_v0_3_shadow_json_v1_analysis.csv`

Dry-run and preflight make zero provider generation requests and create no repository outputs. Writers are atomic, LF-only, and refuse overwrite.

Before execution, committed code and tests must authenticate all frozen identities; reject duplicate keys, unknown fields, and oracle leakage; revalidate requests; prove remote-authoritative routing and text-free telemetry; cross-check captured arms and telemetry; test budgets, pairing, oracle independence, bootstrap determinism, exact-bound fixtures, and state transitions; run focused tests and the full suite; and record any instrumentation failure in `BUILD_HISTORY.md`.
