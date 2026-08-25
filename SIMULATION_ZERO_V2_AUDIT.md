# Simulation Zero v2 Failure Audit

Date: 2026-08-25

## Preserved evidence

- Raw observations: `benchmark_runs_simzero_v2.jsonl`
- Bytes: 80,476
- SHA-256: `5637130c56894a0263c534bb87c5037901f0e535df28e658f68d5e85c03f7f6e`
- Summary: `benchmark_summary_simzero_v2.json`
- Bytes: 4,086
- SHA-256: `ab878c4e4320c602da41c0e16f0ed8341f0f6e23e8c372883708bf23b71346b3`

The original JSONL was not modified during this audit.

## Frozen result

- 150 observations
- 66 oracle passes
- Strict recorded pass rate: 44.0%
- Two empty outputs

The frozen result must remain unchanged.

## Failure classification

### `extract_person_2`: specification problem

All five outputs preserved the source value `Dr. Grace Hopper`. The oracle expected
`Grace Hopper`, but the prompt did not instruct the model to remove honorifics.

These are not defensible model-capability failures. They remain failures in the frozen
strict-oracle result, but are treated as specification defects in the post-hoc audit.

### `extract_event_2`: genuine model failure

All five outputs selected the explicitly irrelevant `TEAM CALENDAR` header as the event
rather than `product launch briefing`. The prompt and expected value were adequately
specified.

### Priority classification: observed semantic failure with rubric limitation

The model produced incorrect labels consistently on the low and medium examples and on
four of five high-priority repetitions. The high and low examples are strongly
face-valid failures.

However, the benchmark did not define an operational low/medium/high severity rubric.
Future classification experiments should define the rubric before execution.
No post-hoc score adjustment is made.

### Exact formatting: genuine model failure

The bullet tasks omitted the required Markdown markers. The label tasks violated the
specified key:value structure and sometimes omitted or invented content. These are
genuine exact-instruction failures.

### Deterministic transformations: genuine model failure

Representative inspection confirmed genuine failures for all six transformation tasks:
reverse, uppercase, remove spaces, hyphen substitution, underscore substitution, and
character replacement. Outputs commonly repeated the input, generated unrelated text,
or produced malformed transformations.

### Empty outputs

Two observations were empty:

- `format_bullets_colors`, repetition 3
- `transform_remove_spaces`, repetition 4

Both were transport-successful but task-failing generations. Their unavailable TTFT and
TPS values were represented as `None`. No absurd TPS value was recorded.

## Audited interpretation

The five `extract_person_2` specification failures yield a separate post-hoc
specification-adjusted result:

- 71/150 = 47.3%
- adjusted extraction result: 40/45 = 88.9%

This does not replace the frozen 66/150 result.

## Audit conclusion

Failure inspection found:

- 5 specification defects
- systematic genuine failures in event extraction, exact bullet/label formatting,
  priority classification, and deterministic transformations
- no demonstrated normalization defect
- no demonstrated oracle-implementation defect
- no demonstrated telemetry defect

The principal finding survives audit: Gemma 3 270M capability is sharply task-dependent
and is poorly represented by a scalar easy-to-hard ordering.
