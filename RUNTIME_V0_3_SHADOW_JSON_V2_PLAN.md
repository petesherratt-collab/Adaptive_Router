# Runtime v0.3 Structural-JSON Shadow Evaluation V2 Plan

Status: **FROZEN BEFORE IMPLEMENTATION AND PROVIDER EXECUTION**

Date frozen: 2026-09-08

## Objective and succession boundary

Measure whether the released runtime v0.3 local model can safely replace the
remote answer for a narrowly defined structural-JSON workload. Runtime v0.3
remains remote-authoritative throughout this experiment: local output is shadow
evidence and is never returned.

V2 succeeds the incomplete V1 run recorded in
`RUNTIME_V0_3_SHADOW_JSON_V1_EXECUTION_INCIDENT.md`. V1 halted when an HTTP-200
remote response failed runtime response validation at observation 48. V2 uses
40 fresh tasks. It does not resume V1, reuse V1 tasks, alter V1 evidence, or
silently treat provider failure as missing data.

The benchmark, oracle, provider-outcome policy, execution budget, measures, and
promotion rule are frozen before implementation and before any V2 provider
call. Any post-start deviation must be retained and disclosed.

## Frozen identities

| Item | Value |
|---|---|
| Runtime release | `v0.3.0` |
| Runtime commit | `f67273d04ef9b8a3964ed4371390808bf6ba8ffe` |
| V2 base commit | `198ecebd3a27c70fc8fdf9e1dab1b11adf1cac2b` |
| Local model | `gemma3:270m` |
| Local digest | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` |
| Remote model | `openai/gpt-5.6-luna` |
| Config SHA-256 | `36df214e322b8148614e0ac8289ddb77779e326e06d91e3780ea39b87bd01657` |
| Benchmark SHA-256 | `b160537b15f25941227d9381c0bee625f2af8ed385463b1608a6568f1079e278` |

The execution implementation revision and plan SHA-256 must be pinned before
provider calls.

## Suite

- 40 tasks × 3 repetitions = 120 observations.
- All requests use `extract_structured` and `structured_json`.
- Four 10-task strata: `flat_scalar`, `record_selection`, `type_boundary`, and
  `nested_collection`.
- Every observation attempts one authoritative remote arm and one local shadow
  arm for the same task and repetition.
- No task, source literal, expected JSON value, or task identifier is reused
  from V1.

## Execution boundary

Use an experiment-only config copy with `allow_user_visible_local=false`,
shadow enabled, execution enabled, and sample rate 1.0. Do not modify live
`config.json`. The router must return the remote result or its remote error.
Injected experiment providers may retain both raw arms in sealed evidence;
ordinary router telemetry must remain text-free.

No repair, semantic judge, second local attempt, replacement task, or
experiment-level provider retry is permitted. The released runtime's bounded
remote retry policy remains unchanged.

## Provider outcomes and continuation rule

V2 separates **attempted provider failure** from **missing or corrupt
instrumentation**.

An arm is an authenticated attempt when exactly one injected provider call was
captured and its result has valid typed metadata. A result with `success=false`
is a measured provider/service failure, not a missing arm. Record it, score its
task outcome as incorrect, retain its stable error code and attempt count, and
continue to the next observation. Do not substitute the local shadow for a
failed authoritative remote result.

The following remain fatal instrumentation failures: zero or multiple calls for
an expected arm; missing or multiple telemetry records; malformed result or
telemetry fields; request, task, decision, identity, hash, order, or budget
mismatch; write failure; and any uncaught exception. These halt execution.

Remote and local provider failures must be reported separately by stable error
code. Report both end-to-end task success, where a failed provider result is
incorrect, and oracle correctness conditional on provider success. Do not use
the conditional measure for promotion.

## Budget and stop rules

| Quantity | Limit |
|---|---:|
| Remote logical calls | 120 |
| Remote HTTP attempts | 240 |
| Local logical calls | 120 |
| Reported remote cost | USD 0.03 |

Reserve maximum-attempt headroom before each observation. Retain a completed
cost-crossing observation, then halt before the next call. Provider failures
consume logical-call, attempt, latency, and reported-cost budgets exactly as
recorded.

## Oracle separation

The runtime validator sees only contract and candidate text. It checks
parseability, exact top-level keys, and declared top-level types; it never sees
expected values or oracle results.

After provider calls and telemetry are captured, analysis applies an independent
recursive exact-JSON oracle. Object order and insignificant JSON whitespace are
ignored. Array order, strings, booleans, nulls, structure, and value types are
significant. Numbers compare by numeric value; booleans never satisfy numbers.
Validator PASS means conformance, not correctness. An unsuccessful provider arm
has no candidate text and is task-incorrect.

## Frozen measures

Report, overall and by stratum:

- runtime, local, and remote end-to-end task success;
- local and remote provider-success counts and stable error-code counts;
- oracle correctness conditional on provider success;
- contract passes, local accepted errors, and correct rejections;
- paired both/local-only/remote-only/neither task outcomes;
- counterfactual task success if a local contract PASS replaced a successful or
  failed remote result;
- authoritative remote-provider, paired local-provider, actual end-to-end
  runtime, and counterfactual selected-path median latency;
- avoided remote calls, remote attempts, and reported remote cost; and
- attempted-arm, telemetry, row, and task/repetition reconciliation.

All primary task-success denominators are 120. Conditional provider-correctness
denominators must be printed explicitly.

Use a fixed-seed task-cluster bootstrap with 10,000 draws: sample 40 task IDs
with replacement and include all three repetitions. Report percentile 95%
intervals for paired task-success difference and remote calls avoided, plus
undefined draws.

For promotion, calculate the exact one-sided 95% Clopper-Pearson upper bound on
accepted-error rate, denominator local contract passes.

## Precommitted promotion rule

Report `PROMOTION_CANDIDATE` only if:

1. all 120 ordered observations, 120 remote attempts, 120 local attempts, and
   120 telemetry records authenticate;
2. local accepted errors = 0;
3. local contract passes ≥ 60;
4. the accepted-error upper bound ≤ 0.05;
5. counterfactual end-to-end task success ≥ actual runtime task success;
6. counterfactual avoids ≥ 60 remote logical calls;
7. counterfactual selected-path median latency ≤ authoritative remote-provider
   median latency;
8. no instrumentation, identity, budget, execution, or analysis failure
   occurred.

Recorded provider failures do not by themselves make the instrument incomplete;
they count as incorrect task outcomes and can prevent criteria 5 or 7 from
passing. Otherwise report `DO_NOT_PROMOTE`.

Promotion only permits a later reviewed product change for this exact
structural-JSON family. It neither changes configuration nor supports a broader
local-capability claim.

## Canonical outputs and failure manifest

Successful execution outputs are:

- `runtime_v0_3_shadow_json_v2_runs.jsonl`
- `runtime_v0_3_shadow_json_v2_router_telemetry.jsonl`
- `runtime_v0_3_shadow_json_v2_summary.json`
- `runtime_v0_3_shadow_json_v2_analysis.json`
- `runtime_v0_3_shadow_json_v2_analysis.csv`

Fatal execution writes:

- the retained `.partial` run and telemetry files; and
- `runtime_v0_3_shadow_json_v2_failure.json`, written atomically after the
  partial handles close.

The failure manifest records the stable failure code, stage, completed-row and
telemetry counts, current task/repetition when known, budget snapshot, partial
file hashes, frozen identities, and implementation revision. It must contain no
prompt or output text. Its presence blocks execution, analysis, and promotion.

The runner refuses execution if any V2 canonical, partial, or failure-manifest
path exists. It never overwrites, resumes, renames, or deletes partial evidence.
Analysis requires all three successful execution files, exactly 120 rows, no
partials, and no failure manifest.

Dry-run and preflight make zero provider generation requests and create no
repository outputs. Writers are atomic, LF-only, and refuse overwrite.

Before execution, committed code and tests must authenticate all frozen
identities; reject duplicate keys, unknown fields, and oracle leakage;
revalidate requests; prove remote-authoritative routing and text-free telemetry;
cross-check captured arms and telemetry; test recorded provider failures,
failure manifests, budgets, pairing, oracle independence, bootstrap
determinism, exact-bound fixtures, and state transitions; run focused tests and
the full suite; and record any instrumentation failure in `BUILD_HISTORY.md`.
