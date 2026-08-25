# Routing Simulation Zero v1

Date: 2026-08-25

## Purpose

This is an offline replay of four deterministic routing policies over the 150
frozen observations from Simulation Zero v2.

No model was called during this simulation. Local outcomes and local generation
times are empirical. Remote success is counterfactual because no successful
remote/frontier benchmark has yet been run.

## Policies

### Always local

Route all observations to Gemma 3 270M.

### Always remote

Route all observations to the hypothetical remote model.

### Coarse task-class routing

Route structured extraction and classification locally. Route formatting and
transformation remotely.

### Fine capability-family routing

Route structured extraction, sentiment classification, and JSON formatting
locally. Route priority classification, bullet formatting, label formatting,
and deterministic transformations remotely.

The fine policy is family-based rather than an individual-task outcome lookup.
Therefore `extract_event_2` remains local despite failing, while the one
successful priority observation is routed remotely.

## Interpretation layers

Two local-correctness interpretations are reported:

- **Strict:** the frozen validator result, 66/150.
- **Audited:** the documented post-hoc interpretation treating the five
  `extract_person_2` honorific-preserving outputs as specification defects,
  producing 71/150.

The audited interpretation does not replace the frozen result.

## Empirical routing results

### Strict interpretation

| Policy | Local calls | Remote calls | Local passes | Missed escalations | Unnecessary escalations |
|---|---:|---:|---:|---:|---:|
| Always local | 150 | 0 | 66 | 84 | 0 |
| Always remote | 0 | 150 | 0 | 0 | 66 |
| Coarse class | 75 | 75 | 51 | 24 | 15 |
| Fine capability | 75 | 75 | 65 | 10 | 1 |

### Audited interpretation

| Policy | Local calls | Remote calls | Local passes | Missed escalations | Unnecessary escalations |
|---|---:|---:|---:|---:|---:|
| Always local | 150 | 0 | 71 | 79 | 0 |
| Always remote | 0 | 150 | 0 | 0 | 71 |
| Coarse class | 75 | 75 | 56 | 19 | 15 |
| Fine capability | 75 | 75 | 70 | 5 | 1 |

Coarse and fine routing both reduce remote calls by 50% relative to always
remote. At the same remote-call count, fine routing reduces missed escalations
from 24 to 10 under the strict interpretation and from 19 to 5 under the
audited interpretation. It reduces unnecessary escalations from 15 to 1 under
both interpretations.

## Counterfactual sensitivity analysis

Remote success rates of 80%, 90%, 95%, and 100% were applied uniformly to
remotely routed observations.

### Expected success: strict interpretation

| Assumed remote success | Always local | Always remote | Coarse class | Fine capability |
|---:|---:|---:|---:|---:|
| 80% | 44.0% | 80.0% | 74.0% | 83.3% |
| 90% | 44.0% | 90.0% | 79.0% | 88.3% |
| 95% | 44.0% | 95.0% | 81.5% | 90.8% |
| 100% | 44.0% | 100.0% | 84.0% | 93.3% |

### Expected success: audited interpretation

| Assumed remote success | Always local | Always remote | Coarse class | Fine capability |
|---:|---:|---:|---:|---:|
| 80% | 47.3% | 80.0% | 77.3% | 86.7% |
| 90% | 47.3% | 90.0% | 82.3% | 91.7% |
| 95% | 47.3% | 95.0% | 84.8% | 94.2% |
| 100% | 47.3% | 100.0% | 87.3% | 96.7% |

Under the uniform-success assumption, fine routing breaks even with always
remote at:

- 86.7% assumed remote success under the strict interpretation
- 93.3% assumed remote success under the audited interpretation

Below those points, the selected local subset has a higher observed pass rate
than the assumed remote rate while using half as many remote calls.

## Metric boundaries

Measured or directly replayed:

- local validator outcome
- local/remote routing decision
- missed escalation
- unnecessary escalation
- remote-call count and rate
- summed observed local generation work in milliseconds

Counterfactual:

- remote success
- expected remote passes
- expected total success

Not measured:

- actual remote quality
- actual remote latency
- monetary cost
- token usage
- compute consumption
- energy consumption
- end-to-end policy latency

Remote-call count must not be described as measured compute or energy.

## Limitations

The fine policy was designed after inspecting this same benchmark. This is an
in-sample policy replay, not an out-of-sample validation or evidence that the
policy generalizes.

The uniform remote-success assumption ignores task-dependent frontier
performance. Applying the same scalar rate to different routed task mixtures is
a simplifying sensitivity analysis, not a model of measured remote behaviour.

The workload contains five repetitions of 30 tasks and is not representative of
an uncontrolled production task distribution.

No monetary, compute, or energy conclusion can yet be drawn.

## Conclusion

The replay demonstrates that task-family granularity matters. Coarse and fine
routing used the same number of remote calls, but the fine capability map
retained substantially more locally successful work and made fewer routing
errors.

The result supports testing capability-aware routing against a real remote
baseline. It does not yet validate a production routing policy.

## Preserved artifacts

`simulate_routing.py`

- Bytes: 4,500
- SHA-256:
  `4327f2f29224d5d3f6195ce46b915107bed5710ef47e685bf6239d42d2f46215`

`tests/test_simulate_routing.py`

- Bytes: 3,537
- SHA-256:
  `8b554ebfe03e524474f7022de15cd11966f0e5b22f388e188dbf92979dfb3ac0`

`routing_simulation_zero_v1.csv`

- Bytes: 2,994
- SHA-256:
  `9b15a7c6dbcd4f96e54ceb325638d1147b114538ed1e3fce65795fc29f78dd22`

