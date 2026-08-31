# Validator Contract Replay v1 — Preregistered Plan

Date: 2026-08-28  
Branch: `experiment/validator-contract-replay-v1`

## Purpose

Run a retrospective, zero-model-call replay of deterministic validator
contracts over the 600 already-frozen observations in the three existing
JSONL evidence files. The replay estimates which recorded false accepts would
have been rejected by explicitly preregistered contracts, while preserving the
separation between contract conformance and the frozen benchmark oracle.

This is a post-hoc measurement exercise. It does not make model calls, rerun
generation, alter evidence, change routing, or create a new benchmark.

## Scope and frozen inputs

The only replay observations are the 200 rows in each of:

- `benchmark_runs_oos_local_v1.jsonl`
- `benchmark_runs_scaling_gemma3_1b_v1.jsonl`
- `benchmark_runs_scaling_gemma3_4b_v1.jsonl`

The authenticated SHA-256 values are:

| Evidence file | Required SHA-256 |
|---|---|
| `benchmark_runs_oos_local_v1.jsonl` | `425fa9328781ff2e53f69ce0a054531e106be3a6ed1380c148e35ec3d47c8ca0` |
| `benchmark_runs_scaling_gemma3_1b_v1.jsonl` | `a3bde560ccf875658f9129c3eaa321b51c6c29f3f5a7096d9a97eca070310622` |
| `benchmark_runs_scaling_gemma3_4b_v1.jsonl` | `c0576396252f39523840ca1d970648a84ec03960ca746451a10c0ef83b6cb676` |

`benchmark_oos_v1.json` is not replay input to contract validation. It is used
only for benchmark identity/integrity and retrospective outcome measurement.
Its required SHA-256 is:

`6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295`

The benchmark identity check must confirm suite identity, the 40 frozen task
IDs, task classes, capability families, and the benchmark hash recorded in
the evidence. It must not generate or repair contracts from benchmark
`expected` values.

The frozen observation key is `(task_id, rep)`. Each model file must contain
exactly 200 unique keys with repetitions 1 through 5 for each of the 40 task
IDs. The three key sets must be identical, giving exactly 600 observations.
Duplicate rows, missing rows, extra rows, malformed JSONL, wrong model/evidence
identity, or a mismatch between files fails closed.

## Non-negotiable information boundary

Contract validation must never receive or read `task["expected"]`,
`record["oracle_correct"]`, `record["normalized_output"]`, or
`record["validator"]`. This prohibition applies to direct arguments, nested
objects, closures, globals, imports used as hidden state, and helper calls.

`contract_validate(contract, raw_output)` has exactly two logical inputs and
may access only those two inputs. It must not access benchmark data, evidence
records, an oracle, a prior validator result, normalized output, or any model
metadata. It returns a deterministic contract result containing acceptance and
machine-readable rejection reason(s), without semantic correctness claims.

The replay layer may read the allowlisted observation identity fields and
`raw_output`. After `contract_validate` returns, the measurement layer may
join that result to the recorded `oracle_correct` value solely to calculate
retrospective outcomes. The recorded `validator_status` and `validator`
fields belong to `benchmark_oracle_v2`; neither is a live-gate result and
neither may be used to define baseline gate survival. No benchmark expected
value is available on the validator path. The task prompt may be used only by
the separate baseline-gate reproduction below, never by
`contract_validate()`.

## Future artifacts

The implementation phase is preregistered to create these artifacts and no
others as part of this experiment:

- `validator_contracts_oos_v1.json`
- `validator_contracts.py`
- `replay_validator_contracts.py`
- `tests/test_validator_contracts.py`
- `tests/test_validator_contract_replay.py`
- `validator_contract_replay_v1.json`
- `validator_contract_replay_v1.csv`
- `VALIDATOR_CONTRACT_REPLAY_V1_AUDIT.md`

None of these artifacts is created by this plan commit. Existing files must
never be modified or regenerated. Result paths must be checked before any
write and the replay must refuse to overwrite an existing result file.

## Contract inventory

The contract file contains exactly 40 contracts, exactly one for each frozen
task ID below. IDs must be unique and must match the benchmark task-ID set
exactly; order is canonicalized for comparison but does not change semantics.

| Contract type | Capability family | Frozen task IDs | Count |
|---|---|---|---:|
| `extract_structured` | `structured_extraction` | `oos_extract_person`, `oos_extract_shipment`, `oos_extract_event`, `oos_extract_device`, `oos_extract_order`, `oos_extract_meeting`, `oos_extract_weather`, `oos_extract_product`, `oos_extract_book`, `oos_extract_train` | 10 |
| `format_json` | `json_format` | `oos_json_server`, `oos_json_contact`, `oos_json_coordinates`, `oos_json_inventory`, `oos_json_ticket` | 5 |
| `format_bullets` | `markdown_bullets` | `oos_bullets_fruit`, `oos_bullets_stages`, `oos_bullets_directions`, `oos_bullets_codes`, `oos_bullets_dates` | 5 |
| `format_labels` | `key_value_labels` | `oos_labels_account`, `oos_labels_sensor`, `oos_labels_route`, `oos_labels_build`, `oos_labels_owner` | 5 |
| `transform` | `transformation` | `oos_transform_reverse`, `oos_transform_uppercase`, `oos_transform_remove_spaces`, `oos_transform_underscores`, `oos_transform_replace_o` | 5 |
| `classification` | `sentiment`, `priority` | `oos_sentiment_positive_service`, `oos_sentiment_negative_device`, `oos_sentiment_neutral_delivery`, `oos_sentiment_positive_report`, `oos_sentiment_negative_room`, `oos_priority_high_deadline`, `oos_priority_high_blocked`, `oos_priority_medium_three_days`, `oos_priority_medium_five_days`, `oos_priority_low_fourteen_days` | 10 |

The contract file is a declarative description of task-specific conformance,
not a second oracle. It may contain only fields needed to express the frozen
contract, such as `task_id`, `task_class`, `capability_family`,
`contract_type`, exact keys, explicit JSON types, permitted labels, source
literals, supplied field values, ordered literals, separators, and
deterministic operation parameters.

The contract JSON must contain no field named `expected`, `oracle_correct`,
`normalized_output`, `validator`, `passed`, `answer`, or
`reference_answer`. The forbidden-name check is recursive and applies to
every object, including extension or metadata objects. Missing required
fields, extra fields outside the declared contract schema, duplicate IDs,
unknown contract types, invalid types, contradictory parameters, and
malformed JSON fail closed.

Contracts must not contain a precomputed expected transformation output.
Transformation results are computed at validation time from the declared
source literal and operation parameters.

## Contract semantics

All classes reject malformed output, surrounding prose, and unlisted syntax
unless the class definition below explicitly permits it. Rejection reasons
are stable, documented codes. Multiple defects may be retained as a sorted
reason list, but the primary reason must be deterministic.

### `extract_structured`

- Parse either a JSON object directly or one optional complete outer JSON
  fence. A fence must be complete and have no non-whitespace content outside
  it; nested or multiple fences are rejected.
- Require the parsed value to be a JSON object.
- Require the exact declared key set: no missing or extra keys.
- Check only JSON value types explicitly declared by the contract. Do not
  infer a type from an oracle value and do not compare extracted values with
  expected values.
- Do not perform semantic normalization, key-value repair, or type coercion.

### `format_json`

- Accept either a direct JSON object or exactly one complete outer ```json
  fence, using the same narrow fence rules as `extract_structured`; reject
  incomplete, nested, or multiple fences and prose outside the fence.
- Require a JSON object with no prose or extra keys.
- Require the exact declared key set and explicitly declared value types.
- Compare supplied field values only where their representation and type are
  unambiguous from the task contract.
- `oos_json_server` is explicitly ambiguous for `port`: accept either JSON
  number `8443` or JSON string `"8443"`. A port type mismatch between those two
  representations is not a caught false accept and must not be reported as a
  contract rejection.
- No other implicit coercion, normalization, or semantic repair is permitted.

### `format_bullets`

Require exactly the declared number of lines, the literal bullet marker and
separator, the declared order and supplied literal values, and no blank,
additional, or surrounding-prose lines. Line endings and surrounding
whitespace must be handled according to the explicit contract; no content may
be silently repaired.

### `format_labels`

Require exactly the declared number of lines, exact key spelling, exact
separator and spacing, supplied literal values, and declared order. Reject
blank or additional lines and surrounding prose. Do not accept reordered keys,
alternate separators, or repaired formatting.

### `transform`

Deterministically execute only the explicitly enumerated frozen operations,
represented by explicit contract fields:

- `reverse`: reverse the source string character-for-character;
- `uppercase`: uppercase the source string as specified by the frozen
  operation;
- `remove_spaces`: remove every space from the source string;
- `replace_spaces_with_underscores`: replace every space with `_`;
- `replace_lowercase_o_with_0`: replace every lowercase `o` with digit `0`.

The named frozen operation variants above are the complete allowed set; no
other transform, composition, or inferred operation is valid. The contract
stores the source literal and operation parameters, never a precomputed
expected output. The raw output must equal the deterministic result exactly,
with no prose or code fence.

### `classification`

Require exactly one label from the explicitly permitted label set, with no
surrounding prose or additional labels. This checks label conformance only;
it cannot detect a wrong label when that label is still in the permitted set.
Therefore a wrong but permitted classification label is accepted as
conformant and remains a measured semantic false accept when joined to
`oracle_correct == false`.

## Baseline and counterfactual gates

The recorded evidence `validator_status`/`validator` fields belong to
`benchmark_oracle_v2` and MUST NOT be used as the pre-replay live-gate result.
The baseline must reproduce the existing post-generation gate in the
committed `analyze_local_model_scaling.py`, using the task prompt only in this
separate baseline-gate reproduction:

```text
generation succeeds
and (ttft_ms is absent or ttft_ms <= 8000)
and (tokens_per_second is absent or tokens_per_second >= 1.5)
and validators.validate(task_class, prompt, raw_output).status != FAIL
```

The checks run in the existing order: generation failure, TTFT rejection,
throughput rejection, then the production validator. A validator result of
`NOT_APPLICABLE` survives because only explicit `FAIL` rejects. Call this
result `baseline_gate_survived`. Its first rejection reason is one of
`GENERATION_FAILED`, `TTFT_EXCEEDED`, `GENERATION_TOO_SLOW`, or
`VALIDATOR_FAILED`; otherwise it is `SURVIVED`. Missing TTFT and missing
throughput survive their respective checks, matching the existing analysis.

Define the hardware portion independently:

`hardware_generation_gates_survived` is generation success plus the unchanged
TTFT and throughput decisions. The contract is an additional gate applied
only after an observation survives this hardware/generation portion. For the
primary counterfactual, replace the old live-validator decision with the
contract decision while keeping the frozen generation, TTFT, and throughput
decisions unchanged:

`counterfactual_gate_survived = hardware_generation_gates_survived and contract_accept`

The replay still evaluates raw contract conformance for all 600 observations
so that contract selectivity is reported. That raw conformance result must
not be described as an operational gate outcome. An observation already
rejected by generation, TTFT, or throughput cannot be called a contract-caught
operational false accept, even if its raw contract result is reject.

The committed scaling analysis supplies regression totals for reproducing the
baseline gate. These are required test expectations, not values obtained by
using the recorded benchmark validator fields:

| Model | Baseline false accepts (`baseline_gate_survived` and not `oracle_correct`) |
|---|---:|
| 270M | 98 |
| 1B | 100 |
| 4B | 42 |

The baseline reproduction may use `success`, `ttft_ms`,
`tokens_per_second`, `task_class`, `prompt`, and `raw_output`, plus the
committed `validators.validate` implementation. It must not use
`record["validator_status"]` or `record["validator"]` as a substitute. The
task prompt is forbidden on the contract-validation path.

## Replay procedure

1. Before any analysis, `replay_validator_contracts.py` must verify the
   SHA-256 of the final committed `VALIDATOR_CONTRACT_REPLAY_V1_PLAN.md`
   against a hardcoded implementation constant. The plan-hash placeholder is
   intentionally unresolved in this file: it must be filled only after the
   final reviewed plan is committed, through a separately reviewed
   implementation commit. The plan file itself must not be edited merely to
   insert its own hash.
2. Authenticate the SHA-256 of all three evidence files and the benchmark
   SHA-256 before parsing observations.
3. Parse benchmark identity data without exposing `expected` to validation;
   verify the 40-task inventory, class/family mapping, and exact task-ID set.
4. Parse and schema-check the contract file, recursively reject forbidden
   fields, validate all contract semantics, require exactly 40 contracts, and
   require exact task-ID equality.
5. Parse each evidence file using an allowlist sufficient for identity,
   `(task_id, rep)`, model label, capability/task identity, raw output,
   hardware/generation fields, and the later `oracle_correct` join. Do not use
   recorded `validator_status` or `validator` fields for gate decisions.
6. Reproduce `baseline_gate_survived` using the task prompt and committed
   `validators.validate` implementation. This is the only replay step allowed
   to use the task prompt.
7. For every one of the 600 observations, select the contract by `task_id` and
   call only `contract_validate(contract, raw_output)`. There are no model
   calls, retries, prompt execution, benchmark expected values, or access to
   normalized outputs or recorded validator objects.
8. Calculate raw conformance for all observations. Then apply
   `counterfactual_gate_survived` only from the already-computed hardware
   generation gates and the contract acceptance result.
9. Join the baseline/counterfactual results to the observation's recorded
   `oracle_correct` only after validation, and calculate the preregistered
   outcome metrics. Keep conformance, operational gate survival, and semantic
   correctness as separate fields.
10. Produce deterministic JSON and CSV representations. Each result file must
    record `plan_sha256`, `contract_file_sha256`, all three evidence
    SHA-256 values, the benchmark SHA-256, and the implementation Git
    revision, together with the result schema version, counts, and rejection
    reasons. The audit file is written only in the later audit step, not during
    this plan phase.

The command-line interface is dry-run by default. Dry run performs all input,
contract, and result calculations in memory and writes no result or audit
file. `--write` is required to create outputs. `--write` must refuse to run
if any target result file exists, and must not replace, append to, or partially
overwrite an existing file. A failed validation must leave no result files.

## Reporting

Report the following primary fields per model and overall across all 600
observations. Unless marked operational, these are raw conformance or
descriptive fields over all observations:

- `observation_count`
- `oracle_correct_count`
- `oracle_incorrect_count`
- `contract_accept_count`
- `contract_reject_count`
- `false_accept_count_before_replay`
- `false_accept_caught_count`
- `false_accept_remaining_count`
- `newly_admitted_incorrect_count`
- `counterfactual_false_accept_count`
- `correct_rejected_count` (raw contract selectivity)
- `newly_rejected_correct_count`
- `newly_recovered_correct_count`
- `false_accept_catch_rate`
- `precision_among_contract_accepted_observations`
- `baseline_gate_survived_count`
- `counterfactual_gate_survived_count`

Definitions are fixed as follows:

- `false_accept_count_before_replay` = `baseline_gate_survived == true` and
  `oracle_correct == false`.
- `false_accept_caught_count` = `baseline_gate_survived == true` and
  `oracle_correct == false` and `counterfactual_gate_survived == false`.
- `false_accept_remaining_count` = `baseline_gate_survived == true` and
  `counterfactual_gate_survived == true` and `oracle_correct == false`.
- `newly_admitted_incorrect_count` = `baseline_gate_survived == false` and
  `counterfactual_gate_survived == true` and `oracle_correct == false`.
- `counterfactual_false_accept_count` = `counterfactual_gate_survived == true`
  and `oracle_correct == false`.
- `newly_rejected_correct_count` = `baseline_gate_survived == true` and
  `oracle_correct == true` and `counterfactual_gate_survived == false`.
- `newly_recovered_correct_count` = `baseline_gate_survived == false` and
  `counterfactual_gate_survived == true` and `oracle_correct == true`.
- `correct_rejected_count` = `oracle_correct == true` and
  `contract_accept == false`, over all observations; this is a raw
  contract-selectivity metric, not an incremental operational harm count.

`false_accept_caught_count` is limited to retained baseline false accepts.
An observation already rejected by generation, TTFT, or throughput is not
counted as a false accept caught by the contract. A wrong observation that
failed the legacy validator but is admitted by the contract is
`newly_admitted_incorrect_count`, not `false_accept_remaining_count`.
Require these identities per model and overall:

`false_accept_count_before_replay = false_accept_caught_count + false_accept_remaining_count`

`counterfactual_false_accept_count = false_accept_remaining_count + newly_admitted_incorrect_count`

Catch rate is
`false_accept_caught_count / false_accept_count_before_replay`, reported as
not available when the denominator is zero. Raw precision among
contract-accepted observations is accepted-and-oracle-correct divided by all
raw contract accepts, also reported as not available when the denominator is
zero. If operational precision or rates are reported, their denominator must
be explicitly labeled as counterfactual survivors.

Report the complete paired transition table per model and overall. It has the
eight cells formed by:

`baseline_gate_survived` (survive/fail) ×
`counterfactual_gate_survived` (survive/fail) ×
`oracle_correct` (correct/incorrect).

The eight transition counts must sum exactly to 200 for each model and 600
overall. This table is the authoritative separation between legacy gate
survival, counterfactual gate survival, and correctness.

Also report the same conformance/outcome breakdown by:

- capability family;
- task ID; and
- contract type.

The grouped JSON and CSV reports must include
`newly_admitted_incorrect_count` and `counterfactual_false_accept_count`, in
addition to the other primary fields, wherever the grouping has observations.
The top-level per-model and overall JSON and CSV records must include these
two fields as well.
Both result files must also include the complete transition table and both
identity checks per model and overall.

Report rejection reason counts overall and by model, capability family, task,
and contract type where applicable. Report classification label conformance
separately from semantic correctness: permitted-label acceptance, rejected
label/nonconformance, oracle-correct classification, oracle-incorrect
classification, and the overlap showing wrong permitted labels accepted as
conformant. Do not collapse label conformance into a claim of answer
correctness.

## Required tests

`tests/test_validator_contracts.py` must prove the contract schema and each
contract class, including rejection of wrong keys, wrong types, wrong line
counts, wrong markers/separators, wrong order, blank/additional lines,
surrounding prose, malformed fences, and wrong deterministic transformations.
It must prove that both numeric `8443` and string `"8443"` satisfy the
explicitly ambiguous `oos_json_server` contract, and that this type mismatch
is not counted as caught. It must prove that a wrong but permitted
classification label is accepted as conformant. It must prove that
`format_json` accepts exactly one complete outer ```json fence, while
incomplete, nested, multiple, or prose-surrounded fences are rejected.

`tests/test_validator_contract_replay.py` must prove that:

- validator signatures cannot receive `expected` or oracle data;
- recorded benchmark `validator_status` is never treated as a live-gate
  result;
- baseline-gate reproduction matches the committed scaling-analysis totals:
  270M false accepts 98, 1B false accepts 100, and 4B false accepts 42;
- forbidden contract fields make the contract file invalid;
- monkeypatching `expected` and `oracle_correct` cannot change contract
  results;
- removing, adding, or duplicating observations fails closed;
- removing, adding, or duplicating contracts fails closed;
- unknown contract types, malformed contracts, missing fields, and extra
  forbidden fields fail closed;
- contract and evidence task-ID sets must match exactly;
- raw contract rejection and operational incremental rejection are distinct;
- an observation already rejected by TTFT is not counted as a false accept
  caught by the contract;
- paired transition counts sum exactly to each model's 200 observations and
  600 overall;
- both false-accept identities hold per model and overall;
- an incorrect output rejected by the legacy validator but accepted by the
  contract is counted as `newly_admitted_incorrect_count`, not
  `false_accept_remaining_count`;
- output paths are not overwritten and dry run creates no outputs; and
- a wrong permitted classification label remains a measured semantic false
  accept after the retrospective oracle join.

Tests must inspect the call boundary or use an instrumented validator to show
that `task["expected"]`, `record["oracle_correct"]`,
`record["normalized_output"]`, and `record["validator"]` are absent from
the validator inputs. Tests must not turn these prohibited fields into hidden
validator fixtures.

## Interpretation boundaries

- These contracts are post-hoc and informed by observed aggregate failure
  modes. The replay is not pristine prospective validation.
- This is not fresh OOS validation and is not prospective routing evidence.
- Full deterministic format and transform checks can be equivalent to
  executing the task directly; that does not make them model-independent
  semantic validators.
- No energy claim may be made from replay results, rejection rates, latency,
  model identity, or avoided calls.
- This experiment makes no new model comparison. Model labels are reporting
  strata for the already-frozen observations, not a new scaling analysis.
- A successor fresh suite must test whether contract coverage generalizes
  beyond the observations and failure modes that informed these contracts.

## Ordered execution protocol

1. Commit and push this plan on `experiment/validator-contract-replay-v1`.
2. Obtain an independent review of the plan, hashes, information boundary,
   contract inventory, metrics, and adversarial-test requirements.
3. Implement the contracts, validator, replay layer, and tests in the listed
   future artifacts.
4. Run the full pytest suite; stop on any failure.
5. Run the replay dry run and verify that no result or audit output files were
   created.
6. Commit and push the implementation and tests.
7. Run exactly one `--write` replay against the authenticated frozen inputs.
8. Authenticate the two replay outputs and verify their counts, hashes,
   schemas, and deterministic consistency.
9. Write and review `VALIDATOR_CONTRACT_REPLAY_V1_AUDIT.md` in a separate
   commit/PR, preserving the implementation and result artifacts unchanged.

At every step, preserve existing files and unrelated worktree content. Any
integrity, schema, count, boundary, or output-path failure is a closed-run
failure and invalidates the replay until corrected by a separately reviewed
change.
