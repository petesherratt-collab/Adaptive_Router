# Runtime v0.3 Structural-JSON Shadow 1B Evaluation V1 Plan

Status: **FROZEN BEFORE IMPLEMENTATION AND PROVIDER EXECUTION**

Date frozen: 2026-09-09

## Objective and evidential boundary

Evaluate whether `gemma3:1b` can satisfy the precommitted safety, correctness,
cost-saving, and latency requirements for local authority on the released
runtime v0.3 structural-JSON workload family.

Runtime v0.3 remains remote-authoritative throughout this experiment. The local
1B answer is shadow evidence and is never returned to the user.

The sealed 270M V2 result and its retrospective error analysis motivate a model
change only. They are not training data, validation data, or permission to tune
rules against observed outcomes. This experiment uses 40 fresh tasks and makes
no causal claim that 1B is better than 270M because the two models are not
paired on the same fresh tasks. Its primary question is whether 1B independently
passes the frozen deployment screen.

The benchmark, model identity, experiment configuration, provider-outcome
policy, budgets, measures, and promotion rule are frozen before implementation
and before any generation request. Any post-start deviation must be retained
and disclosed.

## Frozen identities

| Item | Value |
|---|---|
| Runtime release | `v0.3.0` |
| Runtime commit | `f67273d04ef9b8a3964ed4371390808bf6ba8ffe` |
| Experiment base commit | `a3de1a7` |
| Local model | `gemma3:1b` |
| Local digest | `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc` |
| Local format | `gguf` |
| Local parameter size | `999.89M` |
| Local quantization | `Q4_K_M` |
| Local package size | `815319791` bytes |
| Remote model | `openai/gpt-5.6-luna` |
| Experiment config | `config_runtime_v0_3_shadow_json_1b_v1.json` |
| Config SHA-256 | `0285d0b79dba88c2f6714b1c9742910fd9508b24115e4defa3ee65df87a4192c` |
| Benchmark | `benchmark_runtime_v0_3_shadow_json_1b_v1.json` |
| Benchmark SHA-256 | `54fd3f5c253dbe0bf7b558c8cba807bfc341c48187df04a2815ec5153b1a60d1` |

The execution implementation revision and this plan's SHA-256 must be pinned
before provider calls. The model digest must be authenticated through Ollama's
local metadata API during preflight. The live `config.json` must not be
modified.

## Fresh suite

- 40 tasks × 3 repetitions = 120 ordered observations.
- All requests use `extract_structured` and `structured_json`.
- Four 10-task strata: `flat_scalar`, `record_selection`,
  `type_boundary`, and `nested_collection`.
- Every observation attempts one authoritative remote arm and one local 1B
  shadow arm for the same task and repetition.
- No task identifier, exact prompt, exact source block, or complete expected
  JSON object is reused from structural-JSON shadow V1 or V2.
- Prior outcome rows are not consulted when implementing or executing this
  suite.

## Execution boundary

Use only the frozen experiment configuration. It sets
`allow_user_visible_local=false`, shadow enabled, shadow execution enabled,
sample rate 1.0, and local model `gemma3:1b`. Do not modify live
`config.json`.

The router must return the remote result or its remote error. Injected
experiment providers may retain both raw arms in sealed evidence; ordinary
router telemetry must remain prompt- and output-text-free.

No repair, semantic judge, second local attempt, replacement task, or
experiment-level provider retry is permitted. The released runtime's bounded
remote retry policy remains unchanged.

## Provider outcomes and continuation

An arm is an authenticated attempt only when exactly one injected provider
logical call is captured and its result has valid typed metadata. A result with
`success=false` is a measured provider or service failure. Record it, score
the arm task-incorrect, retain its stable error code and attempt count, and
continue. Never substitute local shadow output for an authoritative remote
failure.

A successful or measured failed remote result must have `attempt_count` in
`1..2` and `retry_count == attempt_count - 1`. Zero attempts are a
preflight or instrumentation defect. A successful remote result must report
finite, non-negative, non-Boolean numeric cost. A failed remote result may
report the same valid cost or `null` when billing is unavailable. Each null
is separately reported and charged a frozen USD 0.001 reserve. Reported and
reserved cost remain distinct.

The completed suite requires exactly 120 captured remote logical calls, 120
captured local logical calls, and 120 telemetry rows. Reconciled remote HTTP
attempts are the sum of validated `attempt_count` values and must lie in
120..240.

Zero or multiple expected calls, missing or duplicate telemetry, malformed
metadata, request/task/order/identity/hash/budget mismatch, write failure, or
an uncaught exception are fatal instrumentation failures and halt execution.
Provider failures and instrumentation failures must never be conflated.

## Budgets and stop rules

| Quantity | Limit |
|---|---:|
| Remote logical calls | 120 |
| Remote HTTP attempts | 240 |
| Local logical calls | 120 |
| Known plus reserved remote cost | USD 0.03 |

Reserve maximum-attempt and cost headroom before each observation. A completed
cost-crossing observation is retained, after which execution halts before the
next observation. Provider failures consume logical-call, attempt, latency,
reported-cost, and reserved-cost budgets exactly as frozen.

## Oracle separation

The runtime validator sees only the request contract and candidate text. It
checks JSON parseability, exact top-level keys, and declared top-level types. It
never sees expected values or oracle results.

After both arms and telemetry are captured, analysis applies an independent
recursive exact-JSON oracle. Object order and insignificant whitespace are
ignored. Array order, strings, booleans, nulls, structure, and value types are
significant. Numbers compare by numeric value; booleans never satisfy numbers.
Validator PASS means conformance, not correctness. An unsuccessful provider arm
has no candidate and is task-incorrect.

## Latency definitions

Report paired local-provider, authoritative remote-provider, actual runtime
request, and counterfactual request latency.

Counterfactual request latency is calculated per observation:

- local provider latency when local succeeds and its contract passes;
- local plus remote provider latency when local fails or its contract rejects,
  because real local-first fallback waits for local completion before remote.

Every required latency must be finite, non-negative, non-Boolean numeric
metadata. Missing or invalid latency is fatal reconciliation failure.

## Frozen measures

Report overall and by stratum:

- runtime, local, and remote end-to-end task success;
- local and remote provider-success counts and stable error-code counts;
- oracle correctness conditional on provider success, with denominators;
- contract passes, accepted errors, and correct rejections;
- paired both/local-only/remote-only/neither outcomes;
- counterfactual task success if a local contract PASS replaced remote;
- local-provider, remote-provider, actual runtime request, and deployable
  counterfactual request median latency;
- remote logical calls avoided, remote HTTP attempts, known cost, reserved
  failure cost, and total budgeted cost;
- arm, telemetry, row, task/repetition, hash, and identity reconciliation.

Overall primary denominators are 120; each stratum denominator is 30.
Conditional rates must print their denominators.

Use a fixed-seed task-cluster bootstrap with 10,000 draws. Each draw samples 40
task identifiers with replacement and includes all three repetitions. Report
percentile 95% intervals and undefined draws for paired task-success difference
and remote calls avoided.

For promotion, calculate the exact one-sided 95% Clopper-Pearson upper bound on
accepted-error rate, denominator local contract passes.

## Precommitted promotion rule

Report `PROMOTION_CANDIDATE` only if all conditions hold:

1. all 120 ordered observations, paired logical calls, and telemetry records
   authenticate, with 120..240 reconciled remote HTTP attempts;
2. local accepted errors = 0;
3. local contract passes ≥ 60;
4. the accepted-error upper 95% bound ≤ 0.05;
5. counterfactual end-to-end task success ≥ actual runtime task success;
6. counterfactual execution avoids ≥ 60 remote logical calls;
7. counterfactual request median latency ≤ actual runtime request median
   latency;
8. no instrumentation, identity, budget, execution, or analysis failure occurs.

Measured provider failures remain incorrect outcomes and may prevent promotion;
they do not alone make complete instrumentation incomplete. Otherwise report
`DO_NOT_PROMOTE`.

Promotion would authorize only a later reviewed product change for this exact
structural-JSON family. It does not change configuration, validate general 1B
capability, validate retrospective subgroups, or support a 1B-versus-270M
causal claim.

## Canonical state and outputs

Successful execution outputs:

- `runtime_v0_3_shadow_json_1b_v1_runs.jsonl`
- `runtime_v0_3_shadow_json_1b_v1_router_telemetry.jsonl`
- `runtime_v0_3_shadow_json_1b_v1_summary.json`

Successful analysis outputs:

- `runtime_v0_3_shadow_json_1b_v1_analysis.json`
- `runtime_v0_3_shadow_json_1b_v1_analysis.csv`

Fatal execution retains the run and telemetry `.partial` files and atomically
writes `runtime_v0_3_shadow_json_1b_v1_failure.json` after handles close. The
manifest contains stable failure code, stage, row counts, current task and
repetition when known, budget snapshot, partial hashes, frozen identities, and
implementation revision, but no prompt or output text.

Execution refuses to start if any canonical, partial, failure-manifest, or
analysis-output path exists. It never overwrites, resumes, renames, or deletes
evidence. Analysis requires the three successful execution inputs, exactly 120
rows, no partials, no failure manifest, and no pre-existing analysis outputs.

Dry-run and preflight make zero generation requests and create no repository
outputs. Writers are atomic, LF-only, and refuse overwrite.

Before execution, committed code and tests must authenticate frozen hashes and
identities; reject duplicate keys, unknown fields, and oracle leakage;
revalidate every runtime request; prove remote-authoritative routing and
text-free telemetry; reconcile captured arms and telemetry; cover measured
provider failures, null-cost reserves, attempt counts, failure manifests,
pairing, oracle independence, bootstrap determinism, exact-bound fixtures,
freshness checks, and sealed state transitions; run focused tests and the full
suite; and record any incident in `BUILD_HISTORY.md`.
