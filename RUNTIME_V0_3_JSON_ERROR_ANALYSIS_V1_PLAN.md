# Runtime v0.3 structural-JSON error analysis V1

**Status:** frozen retrospective developmental protocol  
**Date:** 2026-09-08  
**Provider generation requests:** forbidden  
**Runtime policy changes:** forbidden  
**Promotion authority:** none

## Purpose

The completed runtime v0.3 structural-JSON shadow V2 experiment rejected local
authority. This analysis asks why the local model failed and whether the sealed
evidence supports a materially different candidate worth testing later.

This is not a prospective effectiveness evaluation. The headline V2 outcomes
were known before this protocol was written. Any pattern, threshold, subgroup,
or candidate derived here is retrospective and developmental. It may motivate a
new frozen experiment with fresh tasks, but it cannot validate or promote a
routing policy.

## Authenticated inputs

Use only these committed files from merge commit
`49220d2`:

| Input | SHA-256 |
|---|---|
| `benchmark_runtime_v0_3_shadow_json_v2.json` | `b160537b15f25941227d9381c0bee625f2af8ed385463b1608a6568f1079e278` |
| `runtime_v0_3_shadow_json_v2_runs.jsonl` | `1b846bb04cbf335d8bce8b37e5d94cb509a4a06f9a476408023ee7cf80060702` |
| `runtime_v0_3_shadow_json_v2_router_telemetry.jsonl` | `333a073ab9c50aaa4aafed2f1bc09e65bff49fa7bf45960db016d50a1ae16ba6` |
| `runtime_v0_3_shadow_json_v2_summary.json` | `d2a1a1f1d007ebb226f1fadb3df63e7e8248d0ff7514414b35fdec5bfd5c2a6e` |
| `runtime_v0_3_shadow_json_v2_analysis.json` | `b4a93b8ecee9dc45d17dc281c903cd5a1629ef7f95edc42433562438e0393160` |

The analyzer must authenticate every hash, all 40 task IDs, all three
repetitions, all 120 rows, task order, strata, contracts, model identity, and
the existing analysis totals before producing output. Duplicate JSON keys,
unknown schema fields, missing rows, extra rows, malformed values, or
cross-file disagreement are fatal.

Raw local output and hidden oracle values may be read only for retrospective
error classification. They must never be presented as features available to a
deployed router unless the same information is independently available without
the oracle.

## Questions

1. Which structural and semantic failure modes account for local errors?
2. How often did contract PASS distinguish correct from incorrect local output?
3. Were failures stable across the three repetitions of a task or stochastic?
4. Did any pre-output task/contract subgroup or post-output contract signal
   isolate a credible local-authority niche?
5. Does the evidence point toward a routing-rule change, a validator change, a
   larger local model, or deterministic extraction?
6. What, if anything, is justified as a candidate for fresh prospective
   evaluation?

## Frozen error taxonomy

Compare each local candidate recursively with the exact JSON oracle. JSON
numbers compare by numeric value, but booleans are not numbers. Object key
order is irrelevant; array order is significant.

Record every observed difference by JSON Pointer path using these leaf classes:

- `missing_member`: an expected object member is absent;
- `unexpected_member`: an unrequested object member is present;
- `container_type`: object or array occurs where the other or a scalar is
  expected;
- `scalar_type`: string, number, Boolean, or null type differs;
- `array_length`: candidate and expected arrays have different lengths;
- `scalar_value`: scalar types agree but values differ;
- `provider_failure`: no candidate exists because local generation failed;
- `unparseable_candidate`: local output cannot supply normalized JSON.

A row may have multiple leaf differences. For mutually exclusive row totals,
assign the primary class by this precedence:

1. provider failure;
2. unparseable candidate;
3. missing or unexpected member;
4. container type;
5. scalar type;
6. array length;
7. scalar value;
8. exact.

Do not infer a psychological cause such as confusion, hallucination, or
reasoning failure from an output difference.

## Frozen descriptive measures

Report overall and by stratum:

- observations, tasks, local provider successes, contract PASS, oracle correct,
  and accepted errors;
- the 2x2 contract PASS × oracle correctness table;
- every leaf-difference count and mutually exclusive primary-class count;
- number of differing JSON paths per row;
- task-level counts of correct repetitions, contract-pass repetitions, and
  accepted-error repetitions;
- candidate-output uniqueness per task after canonical JSON normalization;
- tasks with unanimous correctness, unanimous error, mixed correctness,
  unanimous contract PASS, and mixed contract status;
- median local latency and generation rate, reported descriptively;
- local/remote correctness overlap already authenticated by the sealed V2
  analysis.

Repeated observations from one task are not treated as independent tasks.
Task-level tables are primary for pattern discovery; row-level tables are
descriptive.

## Frozen subgroup inventory

Evaluate these rule families exhaustively and print every tested member, not
only favorable members:

1. contract PASS alone;
2. contract PASS intersected with each of the four single strata;
3. contract PASS intersected with every non-empty stratum allowlist;
4. pre-output stratum alone;
5. contract-signature groups derived only from declared contract shape:
   top-level key count, declared scalar/container type counts, and maximum
   declared nesting depth;
6. task-level three-repetition unanimity, explicitly labelled
   `MULTI_CALL_RESEARCH_ONLY`.

Task ID, source literal, expected value, oracle result, remote result, and
post-hoc error class are forbidden as router features. Latency and generation
rate may be summarized but are not candidate gates because they are observed
only after paying for local generation and their predictive validity is not
established.

For every subgroup report:

- accepted row count and accepted task-cluster count;
- correct and incorrect accepted rows;
- tasks containing at least one accepted error;
- accepted-error point estimate;
- exact one-sided 95% Clopper-Pearson upper bound;
- remote logical calls the rule would avoid on these observations;
- counterfactual correctness using the sealed remote outcome on rejection;
- a conspicuous `RETROSPECTIVE_ONLY` label.

No subgroup ranking metric may combine correctness, latency, or cost with
undisclosed weights.

## Candidate screen

A rule may be labelled `CANDIDATE_FOR_FRESH_TEST_ONLY` only if all are true in
this retrospective evidence:

- it uses only deployable, oracle-free features;
- it accepts observations from at least 10 distinct task clusters;
- it has zero accepted semantic errors;
- it does not reduce counterfactual correctness relative to the sealed runtime;
- its definition is not task-ID or literal specific; and
- its limitation as a post-hoc V2-derived rule is printed beside it.

This screen is deliberately not a promotion test. Passing it authorizes only a
proposal for a separately frozen experiment. Failure produces
`NO_RULE_CANDIDATE`.

The multi-call unanimity family cannot pass the deployable candidate screen. It
is reported only to learn whether repeated sampling changes discrimination.

## Interpretation boundary

Possible conclusions are limited to:

- `NO_RULE_CANDIDATE`;
- `VALIDATOR_CHANGE_CANDIDATE`;
- `MODEL_CHANGE_CANDIDATE`;
- `DETERMINISTIC_EXECUTOR_CANDIDATE`; or
- a named combination of those, each with explicit evidence and limitations.

A validator-change candidate requires an oracle-free deterministic check that
would reject at least one accepted error while retaining at least one correct
local PASS in these data. It remains retrospective and must be specified before
fresh validation.

A model-change candidate means the 270M model is inadequate on this task
distribution; V2 supplies no evidence that a particular replacement will pass.
Earlier model-scaling evidence may be cited separately but must not be merged
into V2 denominators.

A deterministic-executor candidate applies only where the requested operation
can be defined without model judgment. It must not be generalized from these
templated benchmark prompts to arbitrary natural-language extraction.

## Outputs and reproducibility

The implementation will create no provider request and will not mutate sealed
V2 evidence. Its eventual canonical outputs are:

- `runtime_v0_3_json_error_analysis_v1.json`;
- `runtime_v0_3_json_error_analysis_v1.csv`; and
- `RUNTIME_V0_3_JSON_ERROR_ANALYSIS_V1.md`.

The JSON contains complete machine-readable measures and subgroup inventory.
The CSV contains task-level and subgroup review tables with an explicit
`RETROSPECTIVE_ONLY` field. The Markdown report separates observations,
deterministic derivations, candidate hypotheses, and prohibited claims.

Writers must be atomic, LF-only, and refuse overwrite. Dry-run must authenticate
inputs, perform the complete analysis, make zero network requests, and create no
repository outputs. Tests must cover hash failure, duplicate keys, recursive
diff classification, task clustering, subgroup exhaustiveness, candidate-screen
failure and success fixtures, oracle-feature exclusion, and output
non-overwrite.

## Gotchas

The 120 rows are only 40 task clusters. Treating three repetitions as 120
independent tasks would exaggerate evidence.

A value can satisfy the declared JSON type and still be wrong. Contract PASS is
therefore an observable conformance signal, not a correctness oracle.

Searching all subgroup combinations creates selection bias. Exhaustive
reporting prevents silent cherry-picking but does not make the selected pattern
prospective.

The easiest apparent improvement is likely to memorize task identities or
literal patterns. Such a rule is forbidden and would say nothing about new
requests.

The analysis may explain why this candidate failed, but it cannot rescue the
rejected policy or turn V2 into validation data for its successor.
