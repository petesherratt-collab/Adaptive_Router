# Out-of-Sample Capability Routing Validation v1 — Pre-run Plan

Date: 2026-08-26

## Purpose

Test whether the frozen fine capability-family routing policy generalizes to
new tasks that were not used to design it.

This experiment validates routing conditional on a supplied task-family label.
It does not yet test automatic classification of arbitrary user prompts.

## Frozen policy

Route locally to Gemma 3 270M:

- structured extraction
- sentiment classification
- JSON formatting

Route remotely to OpenRouter GPT-5.6 Luna:

- priority classification
- Markdown bullets
- key/value labels
- deterministic transformations

The policy must not change after either model produces an observation.

## New suite

The suite contains 40 entirely new tasks:

| Route | Capability family | Tasks |
|---|---|---:|
| Local | `structured_extraction` | 10 |
| Local | `sentiment` | 5 |
| Local | `json_format` | 5 |
| Remote | `priority` | 5 |
| Remote | `markdown_bullets` | 5 |
| Remote | `key_value_labels` | 5 |
| Remote | `transformation` | 5 |

Each task receives five local and five remote repetitions:

- 200 local observations
- 200 remote observations
- 200 paired task/repetition keys
- fine routing selects 100 local and 100 remote observations

Every task contains an explicit `capability_family`. Routing uses this field,
not task-ID membership or observed outcomes.

## Specification rules

### Structured extraction

Prompts state the exact required keys. Expected strings preserve the source
spelling and capitalization. Inputs contain no honorific-removal or implicit
case-normalization requirement.

### Sentiment

Each prompt defines:

- `Positive`: clearly favourable evaluation
- `Negative`: clearly unfavourable evaluation
- `Neutral`: factual statement without evaluation

Items contain no mixed sentiment, sarcasm, or unstated context.

### JSON formatting

Prompts specify the exact keys, key casing, allowed values, and prohibition on
additional keys. JSON comparison uses canonical deterministic normalization.

### Priority

Each prompt includes this operational rubric:

- `High`: a present safety/security incident, work blocked now, or an explicit
  deadline within 24 hours
- `Medium`: action required after 24 hours but within seven days, with no
  present safety/security incident and no current blocker
- `Low`: no action required, or an explicit deadline more than seven days away

Items are constructed so exactly one rule applies.

### Markdown bullets

Prompts specify the exact number and order of lines, the literal `-` marker,
one space after the marker, exact item text, and no surrounding prose.

### Key/value labels

Prompts specify exact key spelling, capitalization, separator, spacing, order,
values, and prohibition on additional lines.

### Transformations

Prompts define a single mechanical character operation and require exact output
with no prose or code fences.

## Oracle and evidence rules

- Deterministic validators only
- No LLM judge
- No semantic repair
- No post-run normalization changes
- Raw outputs preserved
- Failed, empty, filtered, timed-out, and transport-error observations retained
- No automatic retries
- Existing evidence files are never overwritten
- Local and remote observations retain task ID, repetition, model identity,
  telemetry, validator result, and error state
- Remote observations additionally retain token usage, reported cost, routing
  metadata, and cache information

Any post-run specification audit is reported separately and does not replace
the frozen strict result.

## Fixed execution settings

Local:

- model: `gemma3:270m`
- provider: Ollama
- same generation configuration as Simulation Zero v2
- five repetitions

Remote:

- gateway: OpenRouter
- requested model: `openai/gpt-5.6-luna`
- temperature: 0
- maximum completion tokens: 256
- timeout: 90 seconds
- reported cumulative-cost stop: USD 0.10
- five repetitions

The suite, runner, validators, policy, tests, and analysis code must be committed
before execution.

## Primary result

Compare fine capability routing with always remote under the frozen strict
oracle.

The descriptive success criterion is:

1. fine routing uses exactly 100 rather than 200 remote calls; and
2. fine routing's strict pass rate is no more than five percentage points below
   always remote.

This is a pilot criterion based on the point estimate, not a formal
non-inferiority claim.

## Secondary results

Report:

- always local, always remote, coarse class, and fine capability success
- per-family and per-task local and remote pass rates
- beneficial, unnecessary, harmful, and missed escalations
- selected transport failures
- remote-call count and rate
- reported remote cost
- selected median time and summed sequential work
- paired oracle ceiling
- strict and separately documented audited interpretations

## Uncertainty analysis

Repetitions from one task are not treated as independent tasks.

Use a paired task-cluster bootstrap:

- resampling unit: task
- retain all five repetitions within each sampled task
- 6,000 bootstrap samples
- fixed random seed
- estimate: fine pass rate minus always-remote pass rate
- report percentile 95% interval

The interval is a sensitivity analysis. It does not replace the frozen
descriptive success criterion.

## Interpretation boundaries

A successful result supports generalization to new items within these seven
pre-labelled capability families.

It does not establish:

- automatic classification of arbitrary prompts
- production-distribution performance
- general performance outside these families
- measured energy savings
- causal equivalence between local inference time and remote request time

Monetary cost may be reported from OpenRouter. Energy may not be inferred from
remote-call count or latency alone.

## Stop conditions

Stop before model execution if:

- task count or family balance differs from this plan;
- duplicate task IDs exist;
- any prompt/expected pair is ambiguous under the rules above;
- the old policy would require alteration to route the new family labels;
- tests fail;
- the working implementation is not committed;
- either evidence output already exists.

During remote execution, stop before another request once accumulated reported
cost reaches USD 0.10.
