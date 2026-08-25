# Measured Paired Routing Simulation v1

Date: 2026-08-25

## Purpose

Replay four deterministic routing policies over paired, measured local and
remote outcomes for the same 150 `(task_id, repetition)` observations.

Unlike Routing Simulation Zero v1, this analysis does not assume a uniform
remote-success rate. It uses the preserved Gemma 3 270M and OpenRouter GPT-5.6
Luna observations directly.

No model was called during this replay.

## Evidence inputs

Local:

- Model: Gemma 3 270M via Ollama
- Observations: 150
- Raw evidence:
  `benchmark_runs_simzero_v2.jsonl`
- SHA-256:
  `5637130c56894a0263c534bb87c5037901f0f6e23e8c372883708bf23b71346b3`

Remote:

- Model: `openai/gpt-5.6-luna` through OpenRouter
- Observations: 150
- Raw evidence:
  `benchmark_runs_openrouter_luna_v1.jsonl`
- SHA-256:
  `341d203f34f3789e489329030895970e719483334e42d2ac144080516e3c0405`

The two evidence sets contained exactly the same 150 unique task/repetition
keys and matching task classes.

## Policies

### Always local

Select the measured Gemma observation for every paired key.

### Always remote

Select the measured Luna observation for every paired key.

### Coarse task-class routing

Route structured extraction and classification locally. Route formatting and
transformation remotely.

### Fine capability-family routing

Route structured extraction, sentiment classification, and JSON formatting
locally. Route priority classification, bullet formatting, label formatting,
and deterministic transformations remotely.

The fine policy remains the capability map defined after inspecting the local
benchmark. It was not learned from the remote outcomes.

## Metric definitions

- **Selected pass:** the outcome chosen by the policy passes the applicable
  strict or audited interpretation.
- **Beneficial escalation:** local fails and the selected remote outcome passes.
- **Unnecessary escalation:** the policy routes remotely when local passes.
- **Harmful escalation:** local passes but the selected remote outcome fails.
- **Missed escalation:** the policy stays local when local fails and remote
  would pass.
- **Unrecoverable local failure:** the policy stays local and both measured
  outcomes fail.
- **Oracle ceiling:** the number of paired observations for which either
  measured outcome passes. This is descriptive and is not a deployable policy.

## Frozen strict-oracle replay

| Policy | Passes | Pass rate | Remote calls | Beneficial | Missed | Unnecessary | Harmful | Transport failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Always local | 66/150 | 44.0% | 0 | 0 | 62 | 0 | 0 | 0 |
| Always remote | 128/150 | 85.3% | 150 | 62 | 0 | 66 | 0 | 2 |
| Coarse class | 116/150 | 77.3% | 75 | 50 | 12 | 15 | 0 | 0 |
| Fine capability | 125/150 | 83.3% | 75 | 59 | 3 | 1 | 0 | 0 |

The strict paired oracle ceiling is 128/150. Fine routing reaches 125/150,
three observations below that ceiling, while using half as many remote calls as
always remote.

## Audited replay

The audited interpretation applies the separately documented local and remote
specification corrections. It does not replace either frozen result.

| Policy | Passes | Pass rate | Remote calls | Beneficial | Missed | Unnecessary | Harmful | Transport failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Always local | 71/150 | 47.3% | 0 | 0 | 74 | 0 | 0 | 0 |
| Always remote | 143/150 | 95.3% | 150 | 74 | 0 | 71 | 2 | 2 |
| Coarse class | 131/150 | 87.3% | 75 | 60 | 14 | 15 | 0 | 0 |
| Fine capability | 140/150 | 93.3% | 75 | 69 | 5 | 1 | 0 | 0 |

The audited paired oracle ceiling is 145/150. The remaining five observations
are the priority-medium cases lacking an operational rubric.

Fine routing reaches 140/150, five observations below the audited ceiling and
three below always remote. It avoids both measured remote transport failures
because those paired tasks are retained locally.

## Measured cost

| Policy | Remote calls | Reported remote cost |
|---|---:|---:|
| Always local | 0 | $0 |
| Always remote | 150 | $0.005432 |
| Coarse class | 75 | $0.0027282 |
| Fine capability | 75 | $0.0024892 |

Fine routing reduces remote calls by 50% and reported remote cost by
approximately 54.2% relative to always remote. The cost reduction exceeds the
call reduction because the remotely selected task mixture used fewer tokens.

Two always-remote calls failed before reporting billable usage, so reported cost
was present for 148/150 calls. Fine and coarse routing each had reported cost
for all 75 selected remote calls.

## Measured timing

| Policy | Median selected time | Summed selected work |
|---|---:|---:|
| Always local | 262.133 ms | 62.311 s |
| Always remote | 1,847.455 ms | 438.850 s |
| Coarse class | 966.929 ms | 190.713 s |
| Fine capability | 990.314 ms | 204.695 s |

Fine routing reduces median selected time by approximately 46.4% and summed
selected work by approximately 53.4% relative to always remote.

These timing comparisons are operational rather than hardware-equivalent.
Local time measures local generation; remote time includes network, gateway,
provider routing, and inference. Summed work describes a sequential replay and
is not a parallel-throughput estimate.

## Principal result

At half the remote-call volume, fine capability routing preserved nearly all of
the measured always-remote success:

- strict: 83.3% versus 85.3%
- audited: 93.3% versus 95.3%

Fine routing substantially outperformed coarse routing at the same 75-call
remote budget:

- strict: 125 versus 116 passes
- audited: 140 versus 131 passes
- unnecessary escalations: 1 versus 15
- reported cost: $0.0024892 versus $0.0027282

This is direct evidence that task-family granularity matters more than broad
task-class labels on this workload.

## Limitations

The fine policy was designed after inspecting the same local benchmark.
Therefore, this remains an in-sample replay rather than out-of-sample policy
validation.

Five repetitions of 30 fixed tasks do not represent an uncontrolled production
task distribution.

The local and remote execution windows occurred at different times and measure
different system boundaries.

Remote monetary cost is measured. Local electricity and remote energy use are
not measured, so no energy-saving percentage is claimed.

The audited interpretation contains documented post-hoc judgments and must
always be reported separately from strict-oracle results.

## Next experiment

Freeze a new out-of-sample task suite before observing either model. Define
priority and formatting rules operationally, remove the known specification
ambiguities, and evaluate the existing fine policy without changing it.

Only after that validation should the capability map be considered for live
routing logic.

## Preserved artifacts

`simulate_paired_routing.py`

- Bytes: 8,742
- SHA-256:
  `b6845bccfe2c538be243d527bdbc63b186252fa13d1a3e6b27426abca5e824fc`

`tests/test_paired_routing.py`

- Bytes: 5,028
- SHA-256:
  `cda39e839066fcfd7915fc598ccf3ffbf195b147e72a0d4b3515cb0fdbfdf1af`

`routing_simulation_paired_v1.csv`

- Bytes: 1,535
- SHA-256:
  `946ef61243ffdf7a90dc3e0604375f8742f3462da4152f4a4edf59e00263e568`
