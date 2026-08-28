# Local Model Scaling Comparison v1 Audit

Date: 2026-08-27

## Purpose

This document records the post-run audit of the frozen local model scaling
comparison across Gemma 3 270M, 1B, and 4B on fixed hardware.

It does not alter the frozen benchmark, prompts, expected values,
normalization, validators, strict oracle, evidence, or committed analysis
output. Every figure below is either read directly from committed files or
derived from committed evidence by a stated rule.

## Frozen identities

- Comparison: `local_model_scaling_v1`
- Suite: `oos_validation_v1`
- Tasks: 40
- Repetitions: 5 per model
- Observations per model: 200
- Benchmark SHA-256:
  `6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295`
- Plan SHA-256:
  `97359083cc1f4b2352ea383e02076cc8ba6170336499d745be4f15742bf98363`
- Amendment 1 SHA-256:
  `f10c2a890a8e543e97bb80f53a8dabcbe3d5633caeafc40fe3cfef8bcbace71f`
- Execution-runner revision:
  `2538ac9db7470b7e5fa184393dc5335b7cb51fd0`
- Evidence commit:
  `8a8b459d9a8a2e2b82e2979fcd5ebd5540f93fa8`
- Baseline 270M evidence SHA-256 (unchanged):
  `425fa9328781ff2e53f69ce0a054531e106be3a6ed1380c148e35ec3d47c8ca0`

### Model identities

| Model | Parameters | Quantization | Package bytes | Digest |
|---|---|---|---:|---|
| `gemma3:270m` | 268.10M | Q8_0 | 291,554,930 | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` |
| `gemma3:1b` | 999.89M | Q4_K_M | 815,319,791 | `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc` |
| `gemma3:4b` | 4.3B | Q4_K_M | 3,338,801,804 | `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` |

Quantization is not held constant across all three packages. The 1B/4B pair is
the only quantization-matched comparison in the set. No result may be
attributed to parameter count alone, and the 270M-to-1B contrast in particular
confounds size with quantization.

## Committed output SHA-256s

| File | SHA-256 |
|---|---|
| `local_model_scaling_v1.json` | `e93fc2be593256ffce0e7f5dcd587a21c7916d6611651dc1c626c285beb7e0ca` |
| `local_model_scaling_v1.csv` | `24c2bcec0110475f033329015d4fbca051116af1656ca83f61dbe320d62371ab` |
| `benchmark_summary_scaling_gemma3_1b_v1.json` | `bcddf854832a83ca6a04d2dbc633877cadea68567d7b934b900a4172cccc58ab` |
| `benchmark_summary_scaling_gemma3_4b_v1.json` | `1cc8daec80df9d443f39d2d95040bcfe325dc91a0531ecf1cd9dacf16159d4a3` |
| `benchmark_runs_scaling_gemma3_1b_v1.jsonl` | `a3bde560ccf875658f9129c3eaa321b51c6c29f3f5a7096d9a97eca070310622` |
| `benchmark_runs_scaling_gemma3_4b_v1.jsonl` | `c0576396252f39523840ca1d970648a84ec03960ca746451a10c0ef83b6cb676` |

## Canonical evidence versus non-canonical records

The preregistration and Amendment 1 require raw JSONL evidence, per-model
summary JSON, and the committed analysis outputs. Those six files are the
**canonical evidence**. Every claim in this audit is traceable to them.

Console transcripts produced during execution are **non-canonical operational
records**. They were not required by the preregistration, are not hashed, are
not part of the evidence set, and no figure in this audit is sourced from them.
They may be retained for operational history, but a discrepancy between a
console transcript and the canonical JSONL is resolved in favour of the JSONL.

This distinction is recorded because interim discussion took place during
execution, before the committed analysis existed. The headline pass counts used
in that discussion came from the runner's own summary output, and interim
per-family and per-task figures were derived from per-observation console
lines. All of them were subsequently reproduced by the committed analyzer.
Every figure in this audit is read from, or checked against, the committed
analyzer output; none is sourced from a console transcript.

## Evidence integrity

Each new evidence file contains 200 unique `(task_id, rep)` keys, and both key
sets match the frozen 270M evidence. All observations record the frozen
benchmark hash, the execution-runner revision, the requested model, and the
installed digest.

- Successful responses: 200/200 for all three models.
- Errors: 0 for all three models.
- Empty outputs: 16 for 270M, 0 for 1B, 0 for 4B.
- Non-resident observations: exactly 1 per model, the first request.

No observation was removed or retried, and no post-run semantic repair was
applied.

## 1. Strict outcomes

### Overall

| Model | Passes | Pass rate |
|---|---:|---:|
| `gemma3:270m` | 78/200 | 39.0% |
| `gemma3:1b` | 99/200 | 49.5% |
| `gemma3:4b` | 158/200 | 79.0% |

### Per capability family

| Family | Obs | 270M | 1B | 4B |
|---|---:|---:|---:|---:|
| Structured extraction | 50 | 40 | 29 | 40 |
| Sentiment | 25 | 10 | 25 | 25 |
| JSON formatting | 25 | 21 | 23 | 20 |
| Priority | 25 | 7 | 12 | 15 |
| Markdown bullets | 25 | 0 | 4 | 23 |
| Key/value labels | 25 | 0 | 3 | 25 |
| Transformation | 25 | 0 | 3 | 10 |

No model dominates. JSON formatting peaks at 1B. Structured extraction falls at
1B and recovers at 4B. The capability profile changes shape across tiers rather
than rising uniformly.

### Per task

Pass count out of 5 repetitions.

| Task | 270M | 1B | 4B |
|---|---:|---:|---:|
| `oos_bullets_codes` | 0 | 3 | 5 |
| `oos_bullets_dates` | 0 | 0 | 5 |
| `oos_bullets_directions` | 0 | 0 | 3 |
| `oos_bullets_fruit` | 0 | 1 | 5 |
| `oos_bullets_stages` | 0 | 0 | 5 |
| `oos_extract_book` | 5 | 3 | 5 |
| `oos_extract_device` | 0 | 1 | 5 |
| `oos_extract_event` | 5 | 4 | 5 |
| `oos_extract_meeting` | 5 | 0 | 0 |
| `oos_extract_order` | 5 | 2 | 5 |
| `oos_extract_person` | 5 | 4 | 5 |
| `oos_extract_product` | 5 | 5 | 5 |
| `oos_extract_shipment` | 5 | 4 | 5 |
| `oos_extract_train` | 5 | 4 | 0 |
| `oos_extract_weather` | 0 | 2 | 5 |
| `oos_json_contact` | 5 | 3 | 5 |
| `oos_json_coordinates` | 5 | 5 | 5 |
| `oos_json_inventory` | 5 | 5 | 5 |
| `oos_json_server` | 1 | 5 | 0 |
| `oos_json_ticket` | 5 | 5 | 5 |
| `oos_labels_account` | 0 | 1 | 5 |
| `oos_labels_build` | 0 | 0 | 5 |
| `oos_labels_owner` | 0 | 1 | 5 |
| `oos_labels_route` | 0 | 0 | 5 |
| `oos_labels_sensor` | 0 | 1 | 5 |
| `oos_priority_high_blocked` | 0 | 1 | 5 |
| `oos_priority_high_deadline` | 0 | 1 | 5 |
| `oos_priority_low_fourteen_days` | 4 | 2 | 5 |
| `oos_priority_medium_five_days` | 1 | 5 | 0 |
| `oos_priority_medium_three_days` | 2 | 3 | 0 |
| `oos_sentiment_negative_device` | 1 | 5 | 5 |
| `oos_sentiment_negative_room` | 3 | 5 | 5 |
| `oos_sentiment_neutral_delivery` | 4 | 5 | 5 |
| `oos_sentiment_positive_report` | 1 | 5 | 5 |
| `oos_sentiment_positive_service` | 1 | 5 | 5 |
| `oos_transform_remove_spaces` | 0 | 0 | 5 |
| `oos_transform_replace_o` | 0 | 0 | 0 |
| `oos_transform_reverse` | 0 | 0 | 0 |
| `oos_transform_underscores` | 0 | 3 | 5 |
| `oos_transform_uppercase` | 0 | 0 | 0 |

Three tasks fail 0/5 for every model: `oos_transform_reverse`,
`oos_transform_uppercase`, and `oos_transform_replace_o`. Character-level
string transformation is the one family no tested local tier performs at all.

## 2. Exact paired outcomes against 270M

Paired on identical `(task_id, rep)` keys, 200 pairs per comparison.

| Comparison | Both pass | Gained | Lost | Both fail | Net | Rate difference |
|---|---:|---:|---:|---:|---:|---:|
| 1B vs 270M | 58 | 41 | 20 | 81 | +21 | +10.5 pp |
| 4B vs 270M | 64 | 94 | 14 | 28 | +80 | +40.0 pp |

The net figures conceal substantial two-way movement. 1B gained 41 observations
and lost 20; 4B gained 94 and lost 14. A net improvement of 80 observations
still means 14 observations that 270M answered correctly and 4B did not.

## 3. Timing, resident and non-resident

Exactly one observation per model was non-resident: the first request, which
includes model load.

| Model | Scope | Obs | Median TTFT ms | Median total ms | Median tok/s |
|---|---|---:|---:|---:|---:|
| 270M | all | 200 | 50.455 | 514.327 | 54.067 |
| 270M | resident | 199 | 50.383 | 512.366 | 54.064 |
| 270M | non-resident | 1 | 3,673.003 | 4,147.974 | 54.844 |
| 1B | all | 200 | 180.170 | 1,896.970 | 15.695 |
| 1B | resident | 199 | 180.038 | 1,891.544 | 15.714 |
| 1B | non-resident | 1 | 9,685.346 | 11,435.578 | 14.862 |
| 4B | all | 200 | 500.178 | 4,287.656 | 6.590 |
| 4B | resident | 199 | 500.160 | 4,269.531 | 6.589 |
| 4B | non-resident | 1 | 26,674.948 | 29,646.639 | 6.732 |

Unknown-residency observations: 0 for all three models.

Cold-load cost and sustained generation throughput separate cleanly.
Non-resident median tokens per second is within roughly 2% of the resident
figure for every model, while non-resident TTFT is 73×, 54×, and 53× the
resident figure respectively. Cold-start latency is model-load time, not
degraded generation.

Resident-only median total time rises 512 ms → 1,892 ms → 4,270 ms, roughly
8.3× from 270M to 4B, against a 40 percentage-point strict accuracy gain.

No energy claim is made. Latency, throughput, RAM, package size, and
remote-call avoidance are not energy measurements.

## 4. Post-generation gate survival

Derived under Amendment 1: generation succeeded, `ttft_ms` absent or
≤ 8,000, `tokens_per_second` absent or ≥ 1.5, and the production validator at
the execution revision does not return `FAIL`. First applicable rejection
reason is assigned. This is a post-generation simulation, not live-router
survival; it cannot reproduce classification, local eligibility, preflight
health rejection, or remote fallback.

| Model | Survivors | Survivor rate | Strict passes among survivors | False accepts | Rejected correct |
|---|---:|---:|---:|---:|---:|
| 270M | 176/200 | 88.0% | 78 (44.3%) | 98 | 0 |
| 1B | 198/200 | 99.0% | 98 (49.5%) | 100 | 1 |
| 4B | 196/200 | 98.0% | 154 (78.6%) | 42 | 4 |

First-rejection-reason counts:

| Reason | 270M | 1B | 4B |
|---|---:|---:|---:|
| `GENERATION_FAILED` | 0 | 0 | 0 |
| `TTFT_EXCEEDED` | 0 | 1 | 4 |
| `GENERATION_TOO_SLOW` | 0 | 0 | 0 |
| `VALIDATOR_FAILED` | 24 | 1 | 0 |
| `SURVIVED` | 176 | 198 | 196 |

Missing-value counts, which do not themselves trigger escalation:

| Model | Missing TTFT | Missing throughput |
|---|---:|---:|
| 270M | 16 | 16 |
| 1B | 0 | 0 |
| 4B | 0 | 0 |

All 16 missing values belong to 270M's 16 empty outputs. They survived the
timing gates by design and were rejected by the validator.

Resident and non-resident breakdown: for 270M the single non-resident
observation survived and passed. For 1B and 4B the single non-resident
observation was rejected by `TTFT_EXCEEDED` and was strictly correct, so each
model's non-resident stratum contributes exactly one rejected-correct
observation and zero false accepts. All remaining gate activity is in the
resident stratum.

### The gates lose discriminative power as capability rises

Reading the rejections by whether the rejected observation was strictly
correct:

| Model | Rejections | Rejected wrong (useful) | Rejected correct (harmful) |
|---|---:|---:|---:|
| 270M | 24 | 24 | 0 |
| 1B | 2 | 1 | 1 |
| 4B | 4 | 0 | 4 |

At 270M the gate stack rejected 24 observations, every one of them wrong. At 4B
it rejected 4 observations, every one of them right. The validator rejected
nothing at all at 4B.

This is the sharpest operational result in the comparison. The current
post-generation gates work as a crude malformedness filter on a model whose
failures are malformed, and contribute nothing but harm on a model whose
failures are well-formed and semantically wrong. At the tier where local
routing first becomes plausible, the gate stack has zero true-rejection rate
and a 100% false-rejection rate.

The four 4B rejections are all `TTFT_EXCEEDED` on the first repetition of a
task: `oos_extract_person` rep 1 at 26,675 ms (the cold load),
`oos_priority_high_deadline` rep 1 at 8,331 ms,
`oos_priority_high_blocked` rep 1 at 9,870 ms, and `oos_bullets_stages` rep 1
at 8,356 ms. The three resident cases sit just above the committed 8,000 ms
threshold. No threshold change is proposed here; moving a threshold after
seeing which observations it rejects is precisely what the project rules
forbid.

### False accepts by family, 4B

| Family | False accepts |
|---|---:|
| Transformation | 15 |
| Priority | 10 |
| Structured extraction | 10 |
| JSON formatting | 5 |
| Markdown bullets | 2 |
| **Total** | **42** |

Of these 42, seventeen received a `PASS` from an applicable validator
(structured extraction 10, JSON formatting 5, Markdown bullets 2) and
twenty-five received `NOT_APPLICABLE` because no validator exists for their
task class (transformation 15, priority 10). Section 7 separates the two
mechanisms.

Gate survival does not imply strict correctness. It establishes only that
generation completed within the committed latency and throughput bounds and
that the production validator found no explicit failure.

## 5. Task-level output invariance and outcome variation

### Comparison rule

Three distinct properties are measured and must not be conflated. For each
model and each of the 40 tasks, the five repetitions are grouped by exact
string equality, with no trimming, whitespace folding, case folding, or
parsing:

- **raw-identical**: all five values of the `raw_output` field in the canonical
  JSONL are byte-identical;
- **normalized-identical**: all five values of the `normalized_output` field
  are byte-identical, `normalized_output` being the committed harness
  normalization already applied to the recorded evidence;
- **outcome-unanimous**: all five values of `oracle_correct` are equal.

These are ordered by strength: raw identity implies normalized identity, which
implies outcome unanimity, but not the converse.

### Results across all 40 tasks

| Model | Raw-identical | Normalized-identical | Outcome-unanimous |
|---|---:|---:|---:|
| 270M | 6/40 | 16/40 | 31/40 |
| 1B | 3/40 | 14/40 | 21/40 |
| 4B | 20/40 | 37/40 | 39/40 |

Outcome unanimity is not monotone in capability. It is U-shaped: 270M is
unanimous largely because it fails consistently, 4B largely because it succeeds
consistently, and 1B sits in a transition band where the same prompt produces
different strict outcomes across repetitions.

Output invariance behaves differently from outcome unanimity. At 270M, 31 tasks
were outcome-unanimous but only 16 produced an identical normalized output;
15 tasks varied in output while every repetition reached the same verdict. The
equivalent figure at 4B is 2 tasks. Identical verdicts therefore do not
demonstrate identical outputs, and the two must be reported separately.

### Variation at 4B

Three tasks varied in normalized output at 4B. Only one of them varied in
strict outcome.

| Task | Distinct normalized outputs | Outcome |
|---|---:|---|
| `oos_bullets_directions` | 2 | mixed, 3/5 |
| `oos_transform_replace_o` | 2 | unanimous fail, 0/5 |
| `oos_transform_uppercase` | 4 | unanimous fail, 0/5 |

`oos_bullets_directions` is the only task at 4B whose strict pass/fail outcome
varied, and the variation is trailing whitespace: three repetitions emitted
`- north\n- east\n- south\n- west` and two emitted the same four lines with a
trailing space on each. The oracle accepts the former and rejects the latter.
**The only within-task variance affecting strict pass/fail outcomes at 4B was
trailing whitespace on `oos_bullets_directions`.** That is a narrower claim than
output invariance, and it is the claim the evidence supports.

The other two varying tasks fail unanimously while producing different wrong
answers. `oos_transform_uppercase` produced four distinct outputs across five
repetitions, each of them a Python code block rather than the transformed
string. Substantial output variation therefore persists at 4B in the family it
performs worst on; it is simply invisible to a pass-rate view because every
variant is wrong.

On the three systematically failing extraction and formatting tasks discussed
in section 6, the normalized output is byte-identical across all five
repetitions under the rule above:

```text
oos_extract_meeting  {"room":"Cedar","time":1430,"topic":"budget review"}         ×5
oos_extract_train    {"departure":9,"destination":"Cambridge","origin":"Norwich"} ×5
oos_json_server      {"host":"edge-7","port":"8443"}                              ×5
```

### What this does and does not support

Two observations, stated as hypotheses for testing rather than established
results:

1. At 4B on this suite, only one task exhibited strict-outcome variation across
   five repetitions. This bounds how much *outcome* information the repetitions
   added, but repetitions also establish stability, and stability is itself a
   reportable property rather than a wasted measurement. Whether fewer
   repetitions would suffice at this tier cannot be inferred from the number of
   mixed tasks alone and requires replication on a fresh suite.
2. If per-task strict outcomes at higher tiers are close to deterministic,
   task-level capability estimation may be cheap at exactly the tier where
   local routing is most attractive. This is a candidate direction for the OOS
   audit's call for evidence-thresholded capability estimates, and it must be
   tested on a fresh task set before being relied upon.

Neither observation generalizes beyond these packages, this suite, and this
hardware. Low outcome variation on 40 frozen tasks is not determinism in
general, and a suite whose tasks were constructed to have exact expected values
may favour it.

## 6. Open failure-analysis item: capability inversions

Five tasks were answered better by a smaller model than by a larger one. These
are recorded as open items. No score is adjusted.

| Task | 270M | 1B | 4B |
|---|---:|---:|---:|
| `oos_extract_meeting` | 5 | 0 | 0 |
| `oos_extract_train` | 5 | 4 | 0 |
| `oos_json_server` | 1 | 5 | 0 |
| `oos_priority_medium_five_days` | 1 | 5 | 0 |
| `oos_priority_medium_three_days` | 2 | 3 | 0 |

### `oos_json_server`: 1B passed 5/5, 4B failed 5/5

Expected: `{"host": "edge-7", "port": 8443}`.

```text
270m  {"host":"edge-7","port":"8443"}   1/5
1b    {"host":"edge-7","port":8443}     5/5
4b    {"host":"edge-7","port":"8443"}   0/5
```

4B emits the port as a JSON string on every repetition. The prompt reads:
"Format the supplied fields as one JSON object. Use exactly these lowercase
keys: host, port. Use the supplied values without modification. Include no
additional keys or prose. Source: Host is edge-7 and port is 8443."

The prompt requires the supplied values without modification and specifies the
keys exactly. It does not state that numeric values must be represented as JSON
numbers. The extraction prompts in the same suite do state this explicitly.
Whether `"8443"` modifies the supplied value, given that the source is prose,
is not settled by the prompt text.

This is therefore an open **benchmark specification** question, not a
demonstrated capability failure, and it must be resolved before this task's
result is used to support a claim about 4B. Two points bear on it:

- the requirement the oracle enforces is implicit in this prompt and explicit
  in the sibling extraction prompts;
- the OOS v1 audit ruled this task a genuine capability failure, but did so
  when only 270M evidence existed.

Under the standing rule, an underspecified benchmark should be fixed and a
frozen result should not be. Clarifying the prompt would change the stimulus
and could therefore change future model behaviour; what any model would then
produce is unknown and cannot be predicted from these observations. Any
correction belongs only in a successor suite with a new hash, leaving
`oos_validation_v1` and all evidence collected under it untouched. The frozen
scores stand as recorded.

### `oos_extract_meeting` and `oos_extract_train`: the mirror image

These are the more consequential inversions and were not previously flagged.

```text
oos_extract_meeting  expected {"topic":"budget review","time":"14:30","room":"Cedar"}
  270m  {"room":"Cedar","time":"14:30","topic":"budget review"}   5/5
  1b    {"room":"Cedar","time":"14:30","topic":"Meeting review"}  0/5
  4b    {"room":"Cedar","time":1430,"topic":"budget review"}      0/5

oos_extract_train    expected {"origin":"Norwich","destination":"Cambridge","departure":"09:17"}
  270m  {"departure":"09:17",...}   5/5
  1b    {"departure":"09:17",...}   4/5
  4b    {"departure":9,...}         0/5
```

4B's two extraction failures share one behaviour: it applies the instruction
"Represent numeric values as JSON numbers" to colon-separated clock times,
producing `1430` from `14:30` and `9` from `09:17`. The same prompt also
requires preserving punctuation in string values, which should govern. This is
a genuine instruction-conflict failure in which the more capable model follows
one instruction more aggressively and thereby violates another.

Note the direction relative to `oos_json_server`: on extraction 4B over-applies
numeric typing, and on JSON formatting it under-applies it. That combination is
consistent with a model that is sensitive to the explicit numeric instruction
and applies it wherever it appears, rather than with a model that has a stable
internal type policy.

1B's `oos_extract_meeting` failure is unrelated: it substitutes `"Meeting
review"` for `"budget review"`, a content error rather than a typing error.

### Priority inversions

`oos_priority_medium_three_days` and `oos_priority_medium_five_days` both
expect `medium`. 4B answered `low` on all ten observations, as did 270M on
most.

The rubric is explicit: Medium means action required after 24 hours but within
seven days with no present incident and no blocker; the items specify three
days and five days respectively with nothing blocked and no incident. Three and
five days fall unambiguously inside the Medium band.

These are genuine model failures. The specification is adequate and no
adjustment is warranted. The observed failure mode is a bias toward `low` for
items described as routine, which the rubric does not license.

## 7. Capability gain does not close the validation gap

4B gained 80 net strict passes over 270M, a 40 percentage-point improvement,
and its post-generation survivor rate is 98%. Nevertheless **42 strict failures
survived the full gate stack**, and the production validator rejected none of
them.

The two facts are connected rather than in tension. 270M's failures were often
malformed enough for a shape-level validator to catch: 16 empty outputs and 24
validator rejections.

4B's 42 surviving failures divide into two distinct mechanisms, which should
not be reported as one:

| Validator result | Families | Count |
|---|---|---:|
| `PASS` from an applicable validator | structured extraction 10, JSON formatting 5, Markdown bullets 2 | 17 |
| `NOT_APPLICABLE`, no validator for the task class | transformation 15, priority 10 | 25 |

The 17 are well-formed outputs that satisfied the validator's actual check —
valid JSON with the required keys present, or correctly marked bullets — and
were still wrong. The 25 were never examined at all: `validate()` has no branch
for the frozen task classes `transform` or `classification`. The gate
simulation supplies those frozen labels directly; `validate()` returns
`NOT_APPLICABLE`, and only explicit `FAIL` causes escalation. Some of those 25
are not well-formed in any sense; four `oos_transform_uppercase` repetitions
returned Python code blocks rather than a transformed string.

Both mechanisms produce the same routing decision. Only the first is a
limitation of validator strength; the second is a coverage gap.

This is the same finding recorded in BUILD_HISTORY.md on 2026-08-27 for the
live validator, now measured across a capability range rather than at one
model. It sharpens the conclusion: the gap between what the gates establish and
what the task requires **widens** as the local model improves, because
improvement removes exactly the malformedness the gates can detect while
leaving semantic error behind.

A local `LOCAL_ACCEPTED` at 4B on this suite establishes that generation
completed within latency bounds and that the output was well-formed. It
establishes nothing about correctness. On these observations, 21.4% of
survivors were wrong.

## 8. Interpretation boundaries

Carried forward from the committed analysis and the preregistration.

This comparison may establish the performance of these exact packages, on this
exact suite, on this exact hardware.

It does not establish:

- production-distribution performance;
- automatic routing of arbitrary prompts;
- performance of other quantizations or model families;
- parameter-count causality;
- energy savings;
- performance on other machines;
- future remote-inference prices or capacity;
- that any model should be deployed without task-specific validation.

Additional boundaries specific to this run:

- This is a frozen-suite regression comparison, not new out-of-sample
  validation. The 40 tasks are the same ones used for the OOS v1 result and
  have now been observed by three models; they are no longer out of sample in
  any useful sense for policy selection.
- Both 1B and 4B received a small number of manual qualification prompts before
  preregistration, so this is not a pristine out-of-sample model comparison.
- The gate simulation is post-generation only and does not model prompt
  classification, local eligibility, preflight health rejection, probe
  behaviour, or remote fallback.
- Gate survival does not imply strict correctness.

## 9. Conclusion and next direction

The comparison establishes a real accuracy–latency frontier on this hardware:
39.0% at 512 ms resident median, 49.5% at 1,892 ms, 79.0% at 4,270 ms. It also
establishes that the frontier is not a simple ordering. From 270M to 4B, five
of seven families improve, structured extraction is unchanged at 40/50, and
JSON formatting regresses from 21/25 to 20/25; five individual tasks are
answered better by a smaller model.

Three findings should drive the next experiment:

1. **For operational acceptance, validation is at least as important as
   additional model capability.** 4B still produced 42 strict failures, and the
   present gates did not discriminate them: 17 passed applicable but
   insufficient validators, while 25 encountered no validator for their frozen
   task class. Adding local capability without adding validation capability
   converts part of the model's improvement into undetected wrong answers
   rather than into acceptable output.
2. **Outcome variation is concentrated in the middle of the capability range.**
   1B produced 19 tasks with mixed strict outcomes against 9 at 270M and 1 at
   4B. Whether repetition budget can safely be reduced at the top tier is a
   question for fresh-suite replication, not something these observations
   settle.
3. **`oos_json_server` must be resolved before any successor policy uses it.**
   It is currently an unresolved specification question sitting inside a family
   the fine policy routes locally.

The natural next step is not another model. It is an explicit deterministic
schema per task, supplied to the validator rather than inferred from prompt
prose, so that value types and exact key names become checkable at routing time
— followed by a re-run of this gate simulation to measure how many of the 42
false accepts such a validator would catch. That measurement, unlike accuracy
alone, speaks directly to whether deterministic signals can right-size model
capability.

Any successor task suite must carry a new hash. `oos_validation_v1` and all
evidence collected under it remain frozen.
