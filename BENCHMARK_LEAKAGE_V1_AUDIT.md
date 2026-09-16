# Benchmark Leakage Controls v1 — Final Audit

Date: 2026-09-16
Model: `gemma3:270m`
Provider: local Ollama

## Principal result

The frozen 10-variant control bundle produced 90 observations: 30 ordinary
model observations and 60 prompt-ablation observations, with three
repetitions per task variant and condition.

The model produced **6 normalized passes**, all on the two `extract_person`
variants. Every one was a `PASS_VIA_NORMALIZATION` result: the raw output had a
single trailing newline, while the normalized output matched the oracle. The
remaining 24 ordinary model observations were oracle mismatches.

All 60 ablation observations failed. Six were empty-output failures, all on
the two `format_bullets` variants; the other 54 were oracle mismatches.

This audit does not claim that the six normalized passes establish semantic
capability, that the benchmark is free of all leakage, or that these results
generalize beyond this frozen bundle.

## Provenance and authentication

The execution parameters were frozen before model execution in commit
`f664f90` (`Freeze leakage benchmark execution wrapper`). The evidence and
analysis were recorded afterward in commit `6b71343` (`Record benchmark
leakage control results`). The control implementation and fresh bundle were
first committed in `3faf107`.

The installed model preflight passed before execution:

- Ollama endpoint reachable;
- requested tag `gemma3:270m` installed and resident;
- digest `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be`;
- parameter size `268.10M`;
- quantization `Q8_0`;
- installed package size `291554930` bytes;
- resident size reported by `/api/ps`: `325666733` bytes.

No router policy was invoked or changed. No remote provider was used.

### SHA-256 values

| Artifact | SHA-256 |
|---|---|
| `BENCHMARK_LEAKAGE_CONTROLS_V1_PLAN.md` | `d3e8f5c459b813c7c4f1a92cee57e2da5ec185548feca5dd11d835bc08506960` |
| `BENCHMARK_LEAKAGE_V1_EXECUTION_PLAN.md` | `f610a468fe0bdf3c7ec9befcad5573df8efb30e23518ed8a15c0a6d212a2629e` |
| `benchmark_tasks_leakage_v1.json` | `5ab3acf293e24d586f7c174221d7e1c89cfe3a92bea3f0d9b53d0e93d15a9da5` |
| `benchmark_oracle_leakage_v1.json` | `a2593bd02f0a39762368346af68c24c8702267fa5e3b900fb40256e4549b8875` |
| `benchmark_leakage_controls.py` | `671502409e1c5042e804c31014e586a77fca32fe219759d1e5d9ae5425b72a54` |
| `benchmark_leakage_preflight.py` | `6e0990beb0b490d37f753ea5b3194b1e69f82cdc6a0f7b47999c3caf37fd34f5` |
| `benchmark_leakage_runner.py` | `457c29b3459ee461d7638aedafe2076e95e92d48c1484bdaa47b1bedc7dc2624` |
| `run_benchmark_leakage_v1.py` | `0fde692a8a4a2e4a2d26d8cde40a96e045139d890fd7c8f1890e9d7626c9dd71` |
| `benchmark_leakage_v1_null_baseline_report.json` | `c9a4af2d4928a77daa77cac14ee945bd72a2f2641614e307fb36aabf2dd8e374` |
| `benchmark_leakage_v1_runs.jsonl` | `7a42790d492c3f810d50a25d91e568475f8722cc59be7da81e9367638833e0a4` |
| `benchmark_leakage_v1_construct_validity_report.json` | `1c825de1034a3c55182840f0f91f846a09c55e59c6515bd5a8b9e7e24b4ad255` |

The canonical run has no `.partial` counterpart. The runner refused existing
canonical or partial output paths and published the result only after the
completed row set was written.

## Offline construct-validity review

The fresh suite contains five task IDs, each with a `base` and `mut1` variant:

- `extract_person`;
- `classify_sentiment`;
- `format_bullets`;
- `format_json`;
- `transform_reverse`.

Tasks and oracle values are structurally separated. Task data contains no
`expected` field. Ten task/oracle keys match exactly. Mutation pairs preserve
task class and change prompt content. Twenty ablation prompts were generated
deterministically from the ten variants.

The initial draft had three null-baseline failures: the sentiment base was
passed by `constant_positive`, and both person variants were passed by the
capitalized-span baseline. Before freezing, the sentiment base was changed to
a neutral case and longer capitalized distractor spans were added to both
person prompts. The updated offline report marks all 10 variants `CV_OK`.

That redesign is a design-stage resolution, not evidence from the model run.
It must be retained in the history of the benchmark and not confused with a
prospective result on the original prompts.

## Model versus ablation outcomes

| Condition | Rows | Normalized passes | Failures | Empty failures | Normalization-dependent |
|---|---:|---:|---:|---:|---:|
| model | 30 | 6 | 24 | 0 | 6 |
| input-removed ablation | 30 | 0 | 30 | 3 | 0 |
| input-shuffled ablation | 30 | 0 | 30 | 3 | 0 |
| **overall** | **90** | **6** | **84** | **6** | **6** |

The six ordinary model passes were:

| Task variant | Repetitions | Raw output pattern | Normalized result |
|---|---|---|---|
| `extract_person__base` | 1–3 | `Mira Okafor\n` | `Mira Okafor` |
| `extract_person__mut1` | 1–3 | `Tomasz Zielinski\n` | `Tomasz Zielinski` |

No ordinary model observation was an exact raw pass. This is a model-output
and normalization finding, not an instrumentation failure: the raw output was
preserved, the normalization step was explicit, and both oracle verdicts were
recorded.

The six ablation empty outputs were the three repetitions of each
`format_bullets` variant under `input_removed` and `input_shuffled`. They are
reported as `FAIL_EMPTY_OUTPUT`, not transport failures.

## Per-task construct-validity findings

| Task | Baseline status | Model status | Ablation status | Mutation status | Final status |
|---|---|---|---|---|---|
| `classify_sentiment` | `CV_OK` | model fail | ablation fails | `CV_OK` | `CV_OK` |
| `extract_person` | `CV_OK` | model pass | ablation fails | `CV_OK` | `CV_OK` |
| `format_bullets` | `CV_OK` | model fail | ablation fails | `CV_OK` | `CV_OK` |
| `format_json` | `CV_OK` | model fail | ablation fails | `CV_OK` | `CV_OK` |
| `transform_reverse` | `CV_OK` | model fail | ablation fails | `CV_OK` | `CV_OK` |

`CV_OK` here means that the task passed the implemented null-baseline and
ablation controls and showed no base/mutant divergence in the observed model
results. It does not mean that the task is semantically validated or that the
model succeeded on it.

## Exact interpretation of the findings

### Model failures

The model failed all 24 ordinary observations outside person extraction under
the normalized oracle. Those are model-output failures for this frozen bundle,
subject to the narrow oracle and normalization rules. The audit does not infer
why each mismatch occurred beyond the recorded outputs.

### Normalization dependence

Six of 30 ordinary observations, 20%, were correct only after normalization.
All six were a single terminal newline away from the expected text. The raw
oracle called them incorrect; the normalized oracle called them correct. This
is exactly the kind of harness contribution the control is designed to expose.

The result must not be reported as six exact raw model passes. Conversely, the
normalization is not silently treated as semantic repair: it is a declared,
logged boundary operation.

### Ablation

Zero of 60 ablation observations passed. This provides evidence that these
observed passes were not reproduced by the tested instruction-only/input-
removed/input-shuffled controls. It does not prove that no other shortcut,
memorization path, or prompt artifact exists.

### Mutation comparison

Both variants of `extract_person` passed after normalization; the other four
task IDs failed on both variants. The observed base/mutant outcomes therefore
show no `CV_MUTANT_DIVERGENCE`. With only three repetitions and one mutant per
task, this is limited evidence and not a contamination test with high power.

## Separation of measurement layers

This pilot does not have a live router gate or a validator-contract replay.
Accordingly, its evidence should be read in three separate layers:

1. **Output/oracle conformance:** the raw and normalized strings or JSON were
   compared with the independent task oracle. A normalized pass is not a
   semantic proof.
2. **Operational execution:** the local provider returned a result or an
   explicit empty-output failure. No routing survival, latency gate, or remote
   fallback decision was measured here.
3. **Construct validity:** null baselines, prompt ablations, and mutations were
   used to test whether the task could be passed through selected shortcuts.

The report must not collapse these layers into a single “benchmark accuracy”
or “safe routing” number.

Classification remains especially limited: a permitted-label check, if added
later, would test label conformance rather than whether the label is
semantically correct. Wrong but permitted sentiment or priority labels can
survive such a contract. This pilot’s independent oracle is what distinguishes
the reported model result from that conformance question.

## Limitations and withheld claims

- The bundle has 10 variants, not a full replacement benchmark.
- Contracts and controls were authored before this run but after earlier
  benchmark experience; the bundle is not a blinded prospective estimate.
- The three initial null-baseline failures were redesigned before freeze, so
  the final bundle's `CV_OK` status applies only to the revised prompts.
- Three repetitions and one mutant per task provide limited variance and
  contamination evidence.
- Passing ablation does not prove leakage, and failing ablation does not prove
  its absence; here all ablations failed.
- The six normalization-dependent passes do not establish semantic correctness
  or exact-output competence.
- No claim is made about other models, unseen tasks, other prompts, router
  promotion, cost savings, latency savings, or production safety.
- The results do not eliminate false acceptance in general and do not
  generalize beyond this frozen suite.

## Audit verdict

The frozen bundle, separated oracle boundary, mutation inventory, null-baseline
screen, ablation generation, model identity, immutable output, and 90-row
evidence set are internally consistent. The principal empirical finding is
narrow: on this frozen 10-variant bundle, `gemma3:270m` produced six
normalization-dependent extraction passes, while all tested ablations failed.

The proper conclusion is evidence about this controlled observation set, not a
claim that the benchmark establishes semantic correctness, that the model is
safe to route, or that the controls generalize to unseen work.
