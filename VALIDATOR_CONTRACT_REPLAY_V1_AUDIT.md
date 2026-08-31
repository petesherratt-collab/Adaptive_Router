# Validator Contract Replay v1 — Audit

Date: 2026-08-30
Branch: `experiment/validator-contract-replay-v1`
Auditor scope: read-only review of the committed plan, contract file,
implementation, tests, and canonical results.

This audit read the committed artifacts only. It did not run the replay, did
not use `--write`, made no model or network calls, and modified, regenerated,
staged, or committed no existing file.

---

## 1. Authentication and identity

### 1.1 Commit chain

| Role | Commit | Date | Contents |
|---|---|---|---|
| Plan (preregistration) | `99927cfeb409d15fc77cdc42af8d85b30a7f4cdc` (`99927cf`) | 2026-08-28 14:52:52 +0100 | `VALIDATOR_CONTRACT_REPLAY_V1_PLAN.md` only (482 insertions) |
| Implementation | `c1fb5e0010e46c5a0ef0bf17ea2635da36f30426` (`c1fb5e0`) | 2026-08-29 09:21:49 +0100 | `replay_validator_contracts.py`, `validator_contracts.py`, `validator_contracts_oos_v1.json`, `tests/test_validator_contracts.py`, `tests/test_validator_contract_replay.py` (2034 insertions) |
| Results | `0cbb019facbbe9842f334f8f94d801cb9204e361` (`0cbb019`) | 2026-08-29 17:27:25 +0100 | `validator_contract_replay_v1.json`, `validator_contract_replay_v1.csv` only (15580 insertions) |

The ordering required by the plan's execution protocol holds: plan committed
first, implementation and tests second, canonical results third and in a
commit that adds nothing else. The plan commit introduced no implementation or
result artifact, and the result commit introduced no code change.

### 1.2 Declared SHA-256 values — all confirmed

Computed against the working tree, which is byte-identical to the commits
above (verified by `git hash-object` against `git rev-parse <commit>:<path>`).

| Artifact | Declared SHA-256 | Verdict |
|---|---|---|
| `VALIDATOR_CONTRACT_REPLAY_V1_PLAN.md` | `ac7cb2ee4b47ee07c4a0a63b122d56ce47d49dffb88ff82e19fd9a32d638edf0` | **MATCH** |
| `validator_contracts_oos_v1.json` | `ea585eaf7775426ca9d58e8b8276a7bc18d7789545f84bb370aae6ac4ce6a1f0` | **MATCH** |
| `validator_contract_replay_v1.json` | `45c4a04438adc1761de54f130b231b562c5b60c14fcfd9a75c3f90b7761a05ed` | **MATCH** |
| `validator_contract_replay_v1.csv` | `d33b0e92f7984893f4ea936d18a960ae35bbbc51a1cdaabc559bc086d4a33ad0` | **MATCH** |

### 1.3 Self-recorded provenance inside the results

Both canonical result files carry the provenance block, and its contents are
internally consistent with the commit chain above:

- `schema_version`: `validator_contract_replay_v1`
- `plan_sha256`: `ac7cb2ee…8edf0` — equals the committed plan hash, and equals
  the hardcoded `PLAN_SHA256` constant at `replay_validator_contracts.py:23`,
  which the replay checks before any analysis (`replay_validator_contracts.py:144`).
- `contract_file_sha256`: `ea585eaf…6a1f0` — equals the committed contract hash.
- `implementation_git_revision`: `c1fb5e0010e46c5a0ef0bf17ea2635da36f30426` —
  equals the implementation commit exactly.
- `benchmark_sha256`: `6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295`,
  matching the plan's required benchmark hash.
- `evidence_sha256`:

  | Model stratum | Evidence file | SHA-256 recorded in results |
  |---|---|---|
  | `gemma3:270m` | `benchmark_runs_oos_local_v1.jsonl` | `425fa9328781ff2e53f69ce0a054531e106be3a6ed1380c148e35ec3d47c8ca0` |
  | `gemma3:1b` | `benchmark_runs_scaling_gemma3_1b_v1.jsonl` | `a3bde560ccf875658f9129c3eaa321b51c6c29f3f5a7096d9a97eca070310622` |
  | `gemma3:4b` | `benchmark_runs_scaling_gemma3_4b_v1.jsonl` | `c0576396252f39523840ca1d970648a84ec03960ca746451a10c0ef83b6cb676` |

  All three equal the values preregistered in the plan.

### 1.4 Integrity checks recorded in the canonical JSON

`identity_checks` is `true` in every cell, for each of the three model strata
and overall:

- `observation_count_is_200` (per model) and `observation_count_is_600` (overall);
- `transition_count_sum_is_200` / `transition_count_sum_is_600`;
- `false_accept_identity_holds`;
- `counterfactual_identity_holds`.

Both preregistered identities were re-checked directly against the reported
figures and hold at every level:

- `false_accept_count_before_replay = false_accept_caught_count + false_accept_remaining_count`
  → overall 240 = 167 + 73; 270M 98 = 61 + 37; 1B 100 = 79 + 21; 4B 42 = 27 + 15.
- `counterfactual_false_accept_count = false_accept_remaining_count + newly_admitted_incorrect_count`
  → overall 73 = 73 + 0; 270M 37 = 37 + 0; 1B 21 = 21 + 0; 4B 15 = 15 + 0.

The eight paired transition cells sum to exactly 200 per model and 600 overall.

### 1.5 Single-run provenance

`git log --all` shows exactly one commit — `0cbb019` — that has ever touched
either canonical result path. No earlier or alternate version of
`validator_contract_replay_v1.json` or `validator_contract_replay_v1.csv`
exists anywhere in the repository history.

---

## 2. Overall baseline versus counterfactual outcomes

All figures below are read from `validator_contract_replay_v1.json`. The CSV
carries the same records in long form (`scope` ∈ {`overall`, `model`,
`capability_family`, `capability_family_by_model`, `contract_type`,
`contract_type_by_model`, `task_id`, `task_id_by_model`}).

### 2.1 Overall (600 observations)

| Field | Value |
|---|---:|
| `observation_count` | 600 |
| `oracle_correct_count` | 335 |
| `oracle_incorrect_count` | 265 |
| `baseline_gate_survived_count` | 570 |
| `counterfactual_gate_survived_count` | 391 |
| `contract_accept_count` (raw conformance) | 396 |
| `contract_reject_count` (raw conformance) | 204 |
| `false_accept_count_before_replay` | 240 |
| `false_accept_caught_count` | 167 |
| `false_accept_remaining_count` | 73 |
| `newly_admitted_incorrect_count` | 0 |
| `counterfactual_false_accept_count` | 73 |
| `correct_rejected_count` (raw selectivity) | 12 |
| `newly_rejected_correct_count` | 12 |
| `newly_recovered_correct_count` | 0 |
| `false_accept_catch_rate` | 0.6958333… (69.6%) |
| `precision_among_contract_accepted_observations` | 0.8156565… (raw denominator: 396 contract accepts) |

The baseline false-accept total of 240 equals the sum of the per-model
regression totals preregistered in the plan (98 + 100 + 42).
Together with inspection of the committed implementation and its adversarial
tests, the exact reproduction confirms that the baseline decisions were
recomputed rather than taken from the recorded benchmark validator fields.

### 2.2 Per-model

| Field | 270M | 1B | 4B |
|---|---:|---:|---:|
| `observation_count` | 200 | 200 | 200 |
| `oracle_correct_count` | 78 | 99 | 158 |
| `oracle_incorrect_count` | 122 | 101 | 42 |
| `baseline_gate_survived_count` | 176 | 198 | 196 |
| `counterfactual_gate_survived_count` | 115 | 117 | 159 |
| `contract_accept_count` | 115 | 118 | 163 |
| `contract_reject_count` | 85 | 82 | 37 |
| `false_accept_count_before_replay` | 98 | 100 | 42 |
| `false_accept_caught_count` | 61 | 79 | 27 |
| `false_accept_remaining_count` | 37 | 21 | 15 |
| `newly_admitted_incorrect_count` | 0 | 0 | 0 |
| `counterfactual_false_accept_count` | 37 | 21 | 15 |
| `correct_rejected_count` | 0 | 2 | 10 |
| `newly_rejected_correct_count` | 0 | 2 | 10 |
| `newly_recovered_correct_count` | 0 | 0 | 0 |
| `false_accept_catch_rate` | 0.6224 (62.2%) | 0.7900 (79.0%) | 0.6429 (64.3%) |
| `precision_among_contract_accepted_observations` | 0.6783 | 0.8220 | 0.9080 |

`newly_admitted_incorrect_count` and `newly_recovered_correct_count` are
empirically zero in every stratum. The counterfactual cannot recover an
observation that failed a hardware or generation gate, but it could in
principle admit an observation rejected only by the legacy validator. That did
not occur here: all 25 legacy-validator failures also failed their frozen
contracts.

### 2.3 Paired transition tables

Cells are `baseline` × `counterfactual` × `oracle`.

| Cell | 270M | 1B | 4B | Overall |
|---|---:|---:|---:|---:|
| survive · survive · correct | 78 | 96 | 144 | 318 |
| survive · survive · incorrect | 37 | 21 | 15 | 73 |
| survive · fail · correct | 0 | 2 | 10 | 12 |
| survive · fail · incorrect | 61 | 79 | 27 | 167 |
| fail · survive · correct | 0 | 0 | 0 | 0 |
| fail · survive · incorrect | 0 | 0 | 0 | 0 |
| fail · fail · correct | 0 | 1 | 4 | 5 |
| fail · fail · incorrect | 24 | 1 | 0 | 25 |
| **Sum** | **200** | **200** | **200** | **600** |

### 2.4 Rejection reason counts

Baseline gate first-rejection reasons (operational):

| Reason | 270M | 1B | 4B | Overall |
|---|---:|---:|---:|---:|
| `SURVIVED` | 176 | 198 | 196 | 570 |
| `TTFT_EXCEEDED` | 0 | 1 | 4 | 5 |
| `VALIDATOR_FAILED` | 24 | 1 | 0 | 25 |
| `GENERATION_FAILED` | 0 | 0 | 0 | 0 |
| `GENERATION_TOO_SLOW` | 0 | 0 | 0 | 0 |

Raw contract conformance reasons (all 600 observations, not operational):

| Reason | 270M | 1B | 4B | Overall |
|---|---:|---:|---:|---:|
| `ACCEPTED` | 115 | 118 | 163 | 396 |
| `TRANSFORM_MISMATCH` | 25 | 24 | 25 | 74 |
| `LINE_CONTENT_MISMATCH` | 11 | 38 | 2 | 51 |
| `LINE_COUNT_MISMATCH` | 39 | 5 | 0 | 44 |
| `JSON_VALUE_TYPE_MISMATCH` | 5 | 12 | 10 | 27 |
| `KEY_SET_MISMATCH` | 5 | 0 | 0 | 5 |
| `SUPPLIED_VALUE_MISMATCH` | 0 | 2 | 0 | 2 |
| `INVALID_JSON` | 0 | 1 | 0 | 1 |

Each column sums to 200 and the overall column to 600.

---

## 3. Principal result

**Contracts caught 167 of 240 retained baseline false accepts (69.6%),
reducing counterfactual false accepts to 73, while newly rejecting 12 correct
outputs.**

Stated with its full qualifications:

- The denominator 240 is *retained* baseline false accepts only — observations
  that survived the reproduced baseline gate (generation, TTFT, throughput,
  and the committed production validator) and were recorded as
  `oracle_correct == false`. The 25 incorrect observations already rejected by
  the baseline gate are excluded from the numerator and denominator by
  construction and are not credited to the contracts.
- 167 of those 240 became counterfactual-gate failures. 73 remained.
- Because `newly_admitted_incorrect_count` is 0, the counterfactual false
  accept total is exactly the 73 remaining, with no offsetting new admissions.
- The 12 newly rejected correct outputs are the incremental operational cost:
  observations that survived the baseline gate, are recorded as
  `oracle_correct == true`, and fail the counterfactual gate. In this replay
  `correct_rejected_count` (raw selectivity, 12) happens to equal
  `newly_rejected_correct_count` (operational, 12); these are distinct metrics
  with distinct definitions and their coincidence here is not a general identity.

This is a retrospective counterfactual over a frozen suite. It is not a
measurement of a deployed gate, and Section 9 states the limits on reading it
forward.

---

## 4. Family, task, and contract-type findings

### 4.1 By capability family (overall, all 600 observations)

| Family | n | oracle correct | contract accept | FA before | caught | remaining | newly admitted | CF FA | newly rejected correct | catch rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `structured_extraction` | 150 | 109 | 117 | 35 | 27 | 8 | 0 | 8 | 0 | 77.1% |
| `json_format` | 75 | 64 | 73 | 11 | 2 | 9 | 0 | 9 | 0 | 18.2% |
| `markdown_bullets` | 75 | 27 | 27 | 29 | 29 | 0 | 0 | 0 | 0 | 100% |
| `key_value_labels` | 75 | 28 | 28 | 47 | 47 | 0 | 0 | 0 | 0 | 100% |
| `transformation` | 75 | 13 | 1 | 62 | 62 | 0 | 0 | 0 | 12 | 100% |
| `sentiment` | 75 | 60 | 75 | 15 | 0 | 15 | 0 | 15 | 0 | 0% |
| `priority` | 75 | 34 | 75 | 41 | 0 | 41 | 0 | 41 | 0 | 0% |

### 4.2 By contract type (overall)

| Contract type | n | oracle correct | accept | FA before | caught | remaining | CF FA | newly rejected correct | catch rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `extract_structured` | 150 | 109 | 117 | 35 | 27 | 8 | 8 | 0 | 77.1% |
| `classification` | 150 | 94 | 150 | 56 | 0 | 56 | 56 | 0 | 0% |
| `format_bullets` | 75 | 27 | 27 | 29 | 29 | 0 | 0 | 0 | 100% |
| `format_json` | 75 | 64 | 73 | 11 | 2 | 9 | 9 | 0 | 18.2% |
| `format_labels` | 75 | 28 | 28 | 47 | 47 | 0 | 0 | 0 | 100% |
| `transform` | 75 | 13 | 1 | 62 | 62 | 0 | 0 | 12 | 100% |

The 73 remaining counterfactual false accepts decompose exactly as
56 (`classification`) + 9 (`format_json`) + 8 (`extract_structured`) = 73.
All 12 newly rejected correct outputs fall in `transform`.

### 4.3 By task (overall, 15 observations each)

| Task | correct | accept | FA before | caught | remaining | CF FA | newly rej. correct | catch rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `oos_bullets_codes` | 8 | 8 | 2 | 2 | 0 | 0 | 0 | 100% |
| `oos_bullets_dates` | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 100% |
| `oos_bullets_directions` | 3 | 3 | 10 | 10 | 0 | 0 | 0 | 100% |
| `oos_bullets_fruit` | 6 | 6 | 7 | 7 | 0 | 0 | 0 | 100% |
| `oos_bullets_stages` | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 100% |
| `oos_extract_book` | 13 | 14 | 2 | 1 | 1 | 1 | 0 | 50% |
| `oos_extract_device` | 6 | 6 | 9 | 9 | 0 | 0 | 0 | 100% |
| `oos_extract_event` | 14 | 15 | 1 | 0 | 1 | 1 | 0 | 0% |
| `oos_extract_meeting` | 5 | 10 | 10 | 5 | 5 | 5 | 0 | 50% |
| `oos_extract_order` | 12 | 12 | 3 | 3 | 0 | 0 | 0 | 100% |
| `oos_extract_person` | 14 | 14 | 1 | 1 | 0 | 0 | 0 | 100% |
| `oos_extract_product` | 15 | 15 | 0 | 0 | 0 | 0 | 0 | n/a |
| `oos_extract_shipment` | 14 | 15 | 1 | 0 | 1 | 1 | 0 | 0% |
| `oos_extract_train` | 9 | 9 | 5 | 5 | 0 | 0 | 0 | 100% |
| `oos_extract_weather` | 7 | 7 | 3 | 3 | 0 | 0 | 0 | 100% |
| `oos_json_contact` | 13 | 13 | 2 | 2 | 0 | 0 | 0 | 100% |
| `oos_json_coordinates` | 15 | 15 | 0 | 0 | 0 | 0 | 0 | n/a |
| `oos_json_inventory` | 15 | 15 | 0 | 0 | 0 | 0 | 0 | n/a |
| `oos_json_server` | 6 | 15 | 9 | 0 | 9 | 9 | 0 | 0% |
| `oos_json_ticket` | 15 | 15 | 0 | 0 | 0 | 0 | 0 | n/a |
| `oos_labels_account` | 6 | 6 | 9 | 9 | 0 | 0 | 0 | 100% |
| `oos_labels_build` | 5 | 5 | 10 | 10 | 0 | 0 | 0 | 100% |
| `oos_labels_owner` | 6 | 6 | 9 | 9 | 0 | 0 | 0 | 100% |
| `oos_labels_route` | 5 | 5 | 10 | 10 | 0 | 0 | 0 | 100% |
| `oos_labels_sensor` | 6 | 6 | 9 | 9 | 0 | 0 | 0 | 100% |
| `oos_priority_high_blocked` | 6 | 15 | 9 | 0 | 9 | 9 | 0 | 0% |
| `oos_priority_high_deadline` | 6 | 15 | 9 | 0 | 9 | 9 | 0 | 0% |
| `oos_priority_low_fourteen_days` | 11 | 15 | 4 | 0 | 4 | 4 | 0 | 0% |
| `oos_priority_medium_five_days` | 6 | 15 | 9 | 0 | 9 | 9 | 0 | 0% |
| `oos_priority_medium_three_days` | 5 | 15 | 10 | 0 | 10 | 10 | 0 | 0% |
| `oos_sentiment_negative_device` | 11 | 15 | 4 | 0 | 4 | 4 | 0 | 0% |
| `oos_sentiment_negative_room` | 13 | 15 | 2 | 0 | 2 | 2 | 0 | 0% |
| `oos_sentiment_neutral_delivery` | 14 | 15 | 1 | 0 | 1 | 1 | 0 | 0% |
| `oos_sentiment_positive_report` | 11 | 15 | 4 | 0 | 4 | 4 | 0 | 0% |
| `oos_sentiment_positive_service` | 11 | 15 | 4 | 0 | 4 | 4 | 0 | 0% |
| `oos_transform_remove_spaces` | 5 | 0 | 10 | 10 | 0 | 0 | 5 | 100% |
| `oos_transform_replace_o` | 0 | 0 | 15 | 15 | 0 | 0 | 0 | 100% |
| `oos_transform_reverse` | 0 | 0 | 15 | 15 | 0 | 0 | 0 | 100% |
| `oos_transform_underscores` | 8 | 1 | 7 | 7 | 0 | 0 | 7 | 100% |
| `oos_transform_uppercase` | 0 | 0 | 15 | 15 | 0 | 0 | 0 | 100% |

### 4.4 The 4B result

The 4B stratum is the one that most clearly shows the contract mechanism's
limits, because it is the stratum with the fewest false accepts to catch and
the most correct outputs to lose.

**27 of 42 false accepts caught, 15 remaining, and 10 correct outputs newly
rejected.**

4B catch rate is 64.3%, below the 1B's 79.0% and above the 270M's 62.2%.

4B by capability family:

| Family | n | correct | accept | FA before | caught | remaining | CF FA | newly rej. correct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `structured_extraction` | 50 | 40 | 40 | 10 | 10 | 0 | 0 | 0 |
| `json_format` | 25 | 20 | 25 | 5 | 0 | 5 | 5 | 0 |
| `markdown_bullets` | 25 | 23 | 23 | 2 | 2 | 0 | 0 | 0 |
| `key_value_labels` | 25 | 25 | 25 | 0 | 0 | 0 | 0 | 0 |
| `transformation` | 25 | 10 | 0 | 15 | 15 | 0 | 0 | 10 |
| `sentiment` | 25 | 25 | 25 | 0 | 0 | 0 | 0 | 0 |
| `priority` | 25 | 15 | 25 | 10 | 0 | 10 | 10 | 0 |

The 27 caught 4B false accepts resolve to exactly six tasks:
`oos_extract_meeting` 5, `oos_extract_train` 5, `oos_transform_replace_o` 5,
`oos_transform_reverse` 5, `oos_transform_uppercase` 5,
`oos_bullets_directions` 2.

The 15 remaining resolve to exactly three tasks, five observations each:
`oos_json_server` 5, `oos_priority_medium_five_days` 5,
`oos_priority_medium_three_days` 5. Ten of these fifteen are wrong-but-permitted
priority labels (Section 6); the other five are the `oos_json_server` port
representation ruling (Section 7). Both groups are uncaught because of the
frozen declared scope: catching the priority cases would require semantic
classification, while catching the server cases would require reversing the
frozen type-ambiguity ruling.

The 10 newly rejected correct outputs resolve to exactly two tasks, five
observations each: `oos_transform_remove_spaces` 5 and
`oos_transform_underscores` 5. Section 8 identifies the cause.

The 4B transformation family is the sharpest single figure in the replay: of 25
observations the contract accepted **zero**, catching all 15 false accepts and
rejecting all 10 correct outputs. On this family, for this model, the contract
carried no discriminating power at all — its accept rate was 0 regardless of
correctness.

---

## 5. Separation of the three concepts

The replay keeps three things apart, and this audit preserves that separation.
Conflating them is the principal way results of this kind get overstated.

1. **Contract conformance** — the raw result of
   `contract_validate(contract, raw_output)` over all 600 observations, a
   two-input deterministic function (`validator_contracts.py:455`). Reported as
   `contract_accept_count` / `contract_reject_count` (396 / 204 overall) and
   the `raw_contract_rejection_reason_counts` table. This is a statement about
   output *shape and declared literals*, and about nothing else. It has no
   operational meaning on its own.

2. **Operational gate survival** — `baseline_gate_survived` (570) and
   `counterfactual_gate_survived` (391). The counterfactual gate is
   `hardware_generation_gates_survived and contract_accept`, so the frozen
   generation, TTFT, and throughput decisions are carried through unchanged and
   only the validator decision is swapped. An observation already rejected by
   generation, TTFT, or throughput is never counted as a contract-caught
   operational false accept, even where its raw contract result is reject. This
   is why the overall counterfactual survival count (391) is below the raw
   accept count (396): five raw accepts sit behind a hardware/generation
   rejection and cannot be credited to the contract.

3. **Oracle correctness** — `oracle_correct`, joined only *after*
   `contract_validate` returns, purely to compute retrospective outcomes. The
   plan forbids the validator path from touching `task["expected"]`,
   `record["oracle_correct"]`, `record["normalized_output"]`, and
   `record["validator"]`; the contract schema check rejects those names
   recursively (`validator_contracts.py:19`, `:93`).

A related distinction, also preserved: the recorded evidence
`validator_status` / `validator` fields belong to `benchmark_oracle_v2` and are
**not** the baseline live-gate result. The baseline was reproduced from
`success`, `ttft_ms`, `tokens_per_second`, `task_class`, `prompt`, and
`raw_output` through the committed `validators.validate`. The reproduction
recovers the preregistered regression totals exactly (270M 98, 1B 100, 4B 42),
which is the evidence that the reproduction is faithful.

Finally, `correct_rejected_count` (raw contract selectivity over all
observations) and `newly_rejected_correct_count` (incremental operational
harm among baseline survivors) are reported as separate fields throughout,
even where they coincide numerically.

---

## 6. Classification contracts test conformance, not correctness

The `classification` contract type checks **permitted-label conformance only**.
Its whole content is a permitted-label set — for example
`oos_priority_medium_three_days` declares
`"permitted_labels": ["High", "Medium", "Low"]` and nothing else. Validation
accepts if the trimmed output is one of those labels
(`validator_contracts.py:450`). Under the frozen validator API, this contract
receives only the contract and raw output, so it cannot assess semantic
correctness. A mechanism that computes which permitted label is correct would
be a semantic classifier or oracle, outside this contract type’s declared scope.

The consequence is measured directly and is stark:

| Stratum | label conformant | label nonconformant | oracle correct | oracle incorrect | wrong-but-permitted accepted |
|---|---:|---:|---:|---:|---:|
| 270M | 50 | 0 | 17 | 33 | 33 |
| 1B | 50 | 0 | 37 | 13 | 13 |
| 4B | 50 | 0 | 40 | 10 | 10 |
| **Overall** | **150** | **0** | **94** | **56** | **56** |

Every one of the 150 classification observations was label-conformant. Zero
were rejected. Yet 56 of them were wrong. Contract conformance and correctness
diverged on 56 observations out of 150 — over a third of the family — and the
contract had no visibility into any of it.

Those 56 wrong-but-permitted labels are 56 of the 73 remaining counterfactual
false accepts: **77% of everything that survives the contract gate and is
still wrong is a wrong but permitted classification label.** The catch rate for
`classification` is 0%, and it is 0% by construction rather than by oversight.

A concrete instance: on `oos_priority_medium_three_days` the 4B model emitted
`Low` where the frozen expectation is `Medium`. `Low` is a permitted priority
label, so the contract accepted it. The same pattern accounts for the 4B's
`oos_priority_medium_five_days` observations. Wrong-but-permitted priority and
sentiment labels survive this gate.

---

## 7. The `oos_json_server.port` ruling — preserved

The plan rules explicitly, in advance, that `oos_json_server` is **ambiguous
for `port`**: the task prompt supplies `port is 8443` without specifying a JSON
type. The audit records this ruling under the label
**`TYPE_UNSPECIFIED_BY_PROMPT`**. That label is the name for the ruling, not a
code constant — the string appears nowhere in the implementation, contract
file, or tests. The ruling is encoded structurally in the contract:

```json
{
  "task_id": "oos_json_server",
  "contract_type": "format_json",
  "exact_keys": ["host", "port"],
  "explicit_types": { "host": "string", "port": ["number", "string"] },
  "supplied_field_values": { "host": "edge-7", "port": [8443, "8443"] }
}
```

Both JSON number `8443` and JSON string `"8443"` conform. A port type mismatch
between those two representations is **not** a caught false accept and is not
reported as a contract rejection. `tests/test_validator_contracts.py:182-183`
asserts acceptance for both representations, and the surrounding cases confirm
that narrowing the declared type or value set changes the outcome — i.e. the
permissiveness is a deliberate declared property of this contract, not a gap in
the checker.

The frozen benchmark expectation for the task is numeric (`"port": 8443`). All
five 4B observations emitted `"port": "8443"` as a string inside a `json`
fence, so the oracle records them incorrect while the contract accepts them.

**These five 4B false accepts therefore remain uncaught by construction.** They
are 5 of the 4B's 15 remaining false accepts and 9 of the 9 `oos_json_server`
remaining false accepts across all three models. This is the preregistered
ruling operating as designed, not a contract failure. A stricter numeric-only
contract could catch this mismatch, but adopting it now would reverse the
frozen TYPE_UNSPECIFIED_BY_PROMPT ruling after the outcomes are known. Whether
port should be numeric is therefore an open successor-specification question.

---

## 8. Transformation contracts — candid account

The `transform` contracts are the only executable-exact class in the suite.
They store a source literal and a named frozen operation, never a precomputed
expected output, and compute the result at validation time
(`validator_contracts.py:423-434`). Acceptance is strict equality:

```python
def _validate_transform(contract, raw_output):
    if not isinstance(raw_output, str):
        return _result(False, "INVALID_OUTPUT_TYPE")
    return _result(
        raw_output == _transform(contract["source_literal"], contract["operation"]),
        "TRANSFORM_MISMATCH",
    )
```

**What they caught.** All 62 baseline false accepts in the transformation
family were caught, a 100% catch rate — 15 each on `oos_transform_reverse`,
`oos_transform_uppercase`, and `oos_transform_replace_o` (where no model
produced a correct output at all), 10 on `oos_transform_remove_spaces`, and 7
on `oos_transform_underscores`. Wrong transformations really were wrong, and
the exact check found them.

**What they cost.** All 12 of the replay's newly rejected correct outputs are
in this family — 10 of them in the 4B stratum. The contract accepted exactly 1
of 75 transformation observations overall, and 0 of 25 in the 4B stratum.

**The exact task-level cause.** Verified directly against the frozen evidence
and the contract definitions: every one of the 12 rejected correct outputs
differs from the contract's computed result **only by a single trailing
newline**. There is no other difference — no prose, no fence, no casing or
spacing variation, no partial transformation.

| Model | Task | Reps | Raw output | Contract result |
|---|---|---|---|---|
| 4B | `oos_transform_remove_spaces` | 1–5 | `"pairedsample\n"` | `"pairedsample"` |
| 4B | `oos_transform_underscores` | 1–5 | `"frozen_policy_check\n"` | `"frozen_policy_check"` |
| 1B | `oos_transform_underscores` | 4, 5 | `"frozen_policy_check\n"` | `"frozen_policy_check"` |

The control case confirms the diagnosis: the single transformation observation
the contract *did* accept — 1B, `oos_transform_underscores`, rep 3 — emitted
`"frozen_policy_check"` with no trailing newline. Same model, same task, same
content; the only difference between acceptance and rejection is the newline.

The benchmark oracle normalizes trailing whitespace (its `normalized_output`
for these rows is the bare string) and marks all 13 correct. The transform
contract, per the plan's requirement that the raw output equal the
deterministic result exactly, does not.

**Scope of this finding.** This is a statement about these two tasks in these
strata and nothing more. It says the `transform` class's exactness is
calibrated on trailing whitespace in a way the oracle is not, and that on this
frozen evidence that single discrepancy accounts for 100% of the replay's
newly rejected correct outputs. It does **not** establish that trailing
whitespace is the dominant false-rejection mode for exact contracts generally,
that a whitespace-tolerant variant would preserve the 62 catches (that is
untested — it would have to be preregistered and rerun, not assumed), or
anything about the other contract classes, which contributed zero newly
rejected correct outputs. It also does not license reading 4B transformation's
0/25 accept rate as evidence about 4B transformation ability: the contract
accepted nothing in that cell, so the cell carries no discriminating signal.

---

## 9. Retrospective limitation

**These contracts were designed after the model evidence existed.** The three
evidence files were frozen on 2026-08-26 and 2026-08-27; the plan was written
on 2026-08-28 and the contracts on 2026-08-29. Their author had access to the
observed aggregate failure modes of this suite when choosing what each contract
would check. The plan states this itself under "Interpretation boundaries":
"These contracts are post-hoc and informed by observed aggregate failure modes.
The replay is not pristine prospective validation."

What the procedure *does* protect is the ordering between contract freezing and
measurement. The contracts were committed and hashed in `c1fb5e0`, the replay
binds itself to the plan hash before any analysis, and the canonical results in
`0cbb019` record both hashes. The contract file could not have been adjusted in
response to the canonical replay's output, and the audit confirms only one
result commit has ever existed.

That ordering guarantee is narrower than it may appear. It rules out tuning the
contracts against *the replay's aggregate numbers*. It does not and cannot rule
out the contracts having been shaped by prior familiarity with the underlying
evidence, because that familiarity predates the contracts by construction.

Accordingly: **this is evidence about the frozen observations, not an unbiased
prospective estimate for unseen tasks.** The 69.6% catch rate is a
retrospective figure over the 600 observations that informed the contracts. It
should not be quoted as an expected catch rate for new tasks, new prompts, new
models, or a new evidence collection. Establishing a prospective figure requires
a fresh suite with contracts frozen before the observations exist, as the plan's
final interpretation boundary requires.

---

## 10. Procedural deviation — disclosed

A discarded pre-commit version of the tests briefly exercised the replay's
internal write mode against the real frozen evidence, using temporary output
paths. This occurred before the implementation commit.

Disclosed facts:

- The run used the real frozen evidence files, not fixtures.
- It wrote to temporary output paths, not the canonical result paths.
- **No canonical result was retained from that run.** That test version was
  discarded and is not part of `c1fb5e0`.
- The canonical replay that produced `validator_contract_replay_v1.json` and
  `validator_contract_replay_v1.csv` was executed only after implementation
  commit `c1fb5e0`, and both files record
  `implementation_git_revision = c1fb5e0010e46c5a0ef0bf17ea2635da36f30426`.

What the audit could independently verify: `git log --all` on both canonical
result paths returns exactly one commit, `0cbb019`. No earlier, alternate, or
superseded result artifact exists anywhere in the repository history, and the
working-tree files are byte-identical to that commit. The
`implementation_git_revision` recorded inside the results matches `c1fb5e0`
exactly.

What the audit could **not** independently verify: the content or behaviour of
the discarded test version, since it was never committed. The disclosure above
is recorded on the strength of the author's account, not on the strength of
repository evidence. The repository evidence is consistent with that account
and excludes the specific risk that a pre-implementation run's output became
the canonical result — but consistency is not independent confirmation of the
discarded run's details.

This deviates from the plan's ordered execution protocol, which places the
`--write` run at step 7, after the implementation commit at step 6. The
canonical result itself was produced in the correct order; the deviation is
that an earlier internal write-mode execution against real evidence occurred
outside the protocol's sequence.

---

## 11. Claims this audit does not make

Explicitly withheld:

- **These contracts do not establish semantic correctness.** They check
  declared shape, keys, types, literals, ordering, separators, and
  deterministic transformations. Contract acceptance is not a correctness
  claim. The classification family demonstrates the gap concretely: 150/150
  conformant, 56 of them wrong.
- **These contracts do not eliminate false acceptance.** 73 counterfactual
  false accepts remain — 56 wrong-but-permitted classification labels, 9
  `oos_json_server` port representations that conform by explicit preregistered
  ruling, and 8 in `extract_structured`. The overall figure is a reduction from
  240 to 73, not an elimination.
- **These results do not generalise beyond this frozen suite.** 600
  observations, 40 tasks, three Gemma 3 strata, one benchmark, contracts
  authored after the evidence. Nothing here supports a claim about other tasks,
  other prompts, other models, or a production routing decision.
- No energy, cost, latency, or avoided-call claim is made or supported. The
  plan forbids it and this replay measured none of it.
- **No new model comparison is made.** The 270M / 1B / 4B labels are reporting
  strata over already-frozen observations. The differing catch rates (62.2% /
  79.0% / 64.3%) reflect differing failure-mode composition per stratum, not a
  new scaling result, and the strata are not independently re-measured here.
- The counterfactual gate is a retrospective construction. It was never
  deployed, and no claim is made about how it would behave live.

---

## Audit verdict

The commit chain, all four declared SHA-256 values, the recorded provenance
inside both result files, both preregistered false-accept identities, and the
transition-table sums all verify. The results are internally consistent, the
baseline reproduction recovers the preregistered regression totals exactly, and
the conformance / operational / correctness separation is preserved throughout
the reported artifacts and in this audit.

The principal result stands as stated: contracts caught 167 of 240 retained
baseline false accepts (69.6%), reducing counterfactual false accepts to 73,
while newly rejecting 12 correct outputs — a retrospective measurement over a
frozen suite whose contracts were authored after the evidence, subject to the
limitations in Sections 5–11.
