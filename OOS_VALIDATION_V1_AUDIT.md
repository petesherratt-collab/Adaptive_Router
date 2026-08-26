# Out-of-Sample Routing Validation v1 Audit

Date: 2026-08-26

## Purpose

This document records the post-run audit of the frozen out-of-sample paired
routing validation. It does not alter the frozen prompts, observations,
strict-oracle results, or routing policy.

## Frozen identities

- Suite: `oos_validation_v1`
- Tasks: 40
- Repetitions: 5 per model
- Paired observations: 200
- Benchmark SHA-256:
  `6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295`
- Execution-runner revision:
  `50387be90fca40cf6f3f9467106a09abdc9a3c71`

Local evidence:

- File: `benchmark_runs_oos_local_v1.jsonl`
- Observations: 200
- SHA-256:
  `425fa9328781ff2e53f69ce0a054531e106be3a6ed1380c148e35ec3d47c8ca0`

Local summary:

- File: `benchmark_summary_oos_local_v1.json`
- SHA-256:
  `68fc6384cf328f3992735db24abf1ec6945b79ddf8f0649fc8de7977106ad5e4`

Remote evidence:

- File: `benchmark_runs_oos_openrouter_luna_v1.jsonl`
- Observations: 200
- SHA-256:
  `cd2029a23d73bbef0287b3028d3c97b9ecad44613f091448972bdd551398caae`

Remote summary:

- File: `benchmark_summary_oos_openrouter_luna_v1.json`
- SHA-256:
  `05f0e99204b2ca7dd87a5c8bf177c6592702644b9453340713aa7f4a90e83738`

Strict analysis:

- CSV: `routing_analysis_oos_v1.csv`
- SHA-256:
  `e0a92ab04bd6497084380e138f2c834392d0226d1ceec6a7831a7fe0b39bb5f8`
- JSON: `routing_analysis_oos_v1.json`
- SHA-256:
  `c8a94eee9f1eee8e528d60e9d03cd222952126add7f86b728df2928b66c41d9b`

## Evidence integrity

The local and remote evidence each contain 200 unique `(task_id, repetition)`
keys. Their key sets are identical.

All 400 observations record the frozen benchmark hash and execution-runner
revision. Provider and requested-model identities are uniform within each
evidence file.

No observation was removed or retried. Raw outputs, empty outputs, errors,
telemetry, validator results, remote usage, and reported remote costs were
preserved.

## Frozen strict results

- Always local: 78/200 = 39.0%
- Always remote: 200/200 = 100.0%
- Coarse task-class routing: 157/200 = 78.5%
- Fine capability routing: 171/200 = 85.5%

Fine routing used 100 remote calls rather than 200, but its success rate was
14.5 percentage points below always remote. It therefore failed the
preregistered descriptive criterion, which allowed a maximum five-point loss.

The paired task-cluster bootstrap sensitivity interval for fine minus always
remote was:

- Estimate: -14.5 percentage points
- Percentile 95% interval: [-25.0, -5.5] percentage points
- Resampling unit: task
- Repetitions retained within task: 5
- Samples: 6,000
- Seed: 20260826

This interval is descriptive sensitivity analysis, not a formal
non-inferiority result.

## Family results

| Capability family | Local | Remote |
|---|---:|---:|
| Structured extraction | 40/50 | 50/50 |
| Sentiment | 10/25 | 25/25 |
| JSON formatting | 21/25 | 25/25 |
| Priority | 7/25 | 25/25 |
| Markdown bullets | 0/25 | 25/25 |
| Key/value labels | 0/25 | 25/25 |
| Transformation | 0/25 | 25/25 |

## Fine-policy failure audit

Fine capability routing selected local execution for structured extraction,
sentiment, and JSON formatting. It incurred 29 strict failures.

### Sentiment: 15 genuine capability failures

The five prompts defined Positive, Negative, and Neutral explicitly. The
positive and negative examples contained clear evaluative language, while the
neutral example was purely factual.

Gemma 3 270M nevertheless produced incorrect labels in 15 of 25 observations.
The errors included classifying clearly favourable or unfavourable evaluations
as Neutral and one clearly favourable evaluation as Negative.

The prompts, expected labels, normalization, and oracle were adequately
specified. No score adjustment is made.

### Structured extraction: 10 genuine capability failures

`oos_extract_device` failed all five repetitions by representing version `42`
as the JSON string `"42"`. The prompt explicitly required numeric values to be
represented as JSON numbers.

`oos_extract_weather` failed all five repetitions by emitting the key
`temperature` rather than the explicitly required key `temperature_c`.

Both are genuine exact-schema failures. No score adjustment is made.

### JSON formatting: 4 genuine capability failures

`oos_json_server` passed one repetition and failed four by representing port
`8443` as the JSON string `"8443"` rather than the supplied numeric value.

The prompt required use of the supplied values without modification. No score
adjustment is made.

## Other local failures

The local model failed all observed Markdown-bullet, key/value-label, and
transformation tasks. These families were routed remotely by the frozen fine
policy, so their local failures did not reduce fine-policy success.

Sixteen local observations produced empty outputs:

- 7 Markdown-bullet observations
- 9 transformation observations

All were transport-successful generations and were preserved as strict task
failures. None belonged to a fine-policy local family.

Priority classification achieved 7/25 locally, but priority was also routed
remotely by the frozen fine policy.

## Remote audit

OpenRouter GPT-5.6 Luna produced:

- 200 successful responses
- 200 strict-oracle passes
- 0 empty outputs
- reported cost: USD 0.00664640

No remote specification, normalization, oracle, transport, or instrumentation
failure was demonstrated.

## Audited interpretation

Failure inspection found no defensible post-hoc adjustment.

Therefore:

- audited always local = strict always local = 78/200
- audited always remote = strict always remote = 200/200
- audited coarse routing = strict coarse routing = 157/200
- audited fine routing = strict fine routing = 171/200

## Efficiency observations

Fine routing used 100 remote calls rather than 200.

Reported OpenRouter cost:

- Always remote: USD 0.00664640
- Fine routing: USD 0.00321820
- Reduction: approximately 51.6%

Measured selected median total time:

- Always remote: 1,690.078 ms
- Fine routing: 1,115.469 ms

Summed sequential selected work:

- Always remote: 476,651.369 ms
- Fine routing: 327,977.701 ms

Remote-call count, monetary cost, latency, and summed work are not direct
energy measurements. No energy reduction is inferred from them.

## Procedural deviations

Two analysis-stage deviations are disclosed:

1. OOS-specific analysis code was not committed before model execution,
   although the suite, policy, runner, validators, and tests were committed.
2. The preregistration required a fixed bootstrap seed but did not record its
   numeric value. The date-derived seed `20260826` was selected after data
   collection.

Neither deviation altered the frozen observations or strict point estimates.
They limit claims that the statistical analysis was fully code-preregistered.

## Conclusion

The previous fine-grained capability map generalized better than coarse
task-class routing but did not satisfy the preregistered success criterion.

The central failure was sentiment classification: prior in-sample success did
not generalize to new, explicitly specified examples. Structured extraction
and JSON formatting generalized strongly but not perfectly.

The result rejects the current fine policy as a sufficiently reliable fixed
routing rule. It supports narrower local routing, probabilistic or
evidence-thresholded capability estimates, and explicit treatment of
within-family heterogeneity rather than treating a capability family as
uniform.
