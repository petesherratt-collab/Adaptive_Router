# Benchmark Leakage Controls v2 — Corrected Full-Run Audit

Date: 2026-09-17  
Provider: local Ollama  
Status: canonical 540-row run completed

## Principal result

The corrected frozen bundle produced 540 observations: 180 ordinary model
observations and 360 input-ablation observations, across three repetitions,
20 task variants, and the three authenticated local models. The ordinary
condition produced 42 normalized oracle passes; the ablations produced 3.
There were 498 normalized failures.

The ordinary normalized pass counts were:

| Model | Ordinary passes / 60 | Ablation passes / 120 |
|---|---:|---:|
| `gemma3:270m` | 12 | 0 |
| `gemma3:1b` | 18 | 3 |
| `gemma3:4b` | 9 | 0 |

The three 270M raw passes were exact model passes; nine additional 270M
passes and all 18 1B ordinary passes were obtained only after the declared
normalization step. All nine 4B ordinary passes were raw exact passes.

This is evidence about this frozen observation set. It does not establish
semantic correctness, eliminate false acceptance, or generalize beyond the
frozen suite.

## Authentication and provenance

The execution parameters were frozen before model execution in commit
`e6b20dd94150332b827d9a3df60f2fed4cf38743` (`Correct leakage expansion bundle
and restart plan`). The canonical run records that implementation revision,
the frozen plan hash, and the configuration hash in every row's
`run_metadata`.

The authenticated model identities were:

| Model | Digest |
|---|---|
| `gemma3:270m` | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` |
| `gemma3:1b` | `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc` |
| `gemma3:4b` | `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` |

No router policy was invoked or modified. No remote model or network provider
was used for the canonical observations.

### SHA-256 values

| Artifact | SHA-256 |
|---|---|
| `BENCHMARK_LEAKAGE_V2_CORRECTED_PLAN.md` | `a3195365841200649668f1005fd56a83718753474f22dad8bea0e827f4917663` |
| `benchmark_tasks_leakage_v2.json` | `f83126da7ca0203074297680d88bfe8b5d00c30306902e5481194ed57e13f6b7` |
| `benchmark_oracle_leakage_v2.json` | `70c20a3586669791498f9aa7b8e2eba56f18fb555fb53b7a369549ba63e2f86d` |
| `run_benchmark_leakage_v2_corrected.py` | `c36d0d7248bc4e849d8784572d327026339b0eb464788402e63852ae2700857d` |
| `benchmark_leakage_v2_corrected_runs.jsonl` | `bcbbc595c41827d3b5e47440d1de0f79fca8f349a5d117d3161a0eb2474690cd` |
| `benchmark_leakage_v2_corrected_report.json` | `a8f128c4fb92cb0fc9eba49179b2ee633d7e4d7143852f11fd1f726b69bca529` |

The canonical output contains exactly 540 rows: 180 per model, 60 ordinary
and 120 ablation rows per model, with repetitions 1–3. The `.partial` path is
absent after atomic publication. Earlier partials and the count-mismatched
4B continuation are preserved as incident artifacts and are excluded from
this report.

## Construct-validity controls

The separated v2 suite contains ten task IDs, each with `base` and `mut1`:

- structured extraction: `extract_device`, `extract_location`;
- classification: `classify_priority`, `classify_risk`;
- formatting: `format_labels`, `format_json_nested`, `format_bullets_numbered`, `format_json_array`;
- transformation: `transform_rotate`, `transform_swap_case`.

All 20 variants passed the offline null-baseline screen (`CV_OK`). Mutation
pairs preserve task class and change the prompt input. The model evidence is
kept separate from this design-stage screening: `CV_OK` is not a claim that a
model solved the task or that the oracle is semantically complete.

The only ordinary normalized passes were:

| Model | Task variants with passes |
|---|---|
| `gemma3:270m` | both `extract_device` variants; both `extract_location` variants |
| `gemma3:1b` | both `extract_device` variants; both `extract_location` variants; `classify_priority__base`; `classify_risk__base` |
| `gemma3:4b` | `extract_device__base`; both `extract_location` variants |

The 4B `extract_device__mut1` variant failed in all three repetitions. All
formatting and transformation variants failed in the ordinary condition for
all three models. All 4B classification variants failed.

## Classification-label limitation

The classification checks test permitted-label/oracle conformance for the
frozen examples; they are not a general semantic correctness test. A wrong
but permitted priority or sentiment label can survive a label contract. This
run used `classify_priority` and `classify_risk`; its passes should therefore
not be promoted into a claim that the model understood the underlying
priority or risk semantics.

## Separation of measurement layers

1. **Output/oracle conformance:** raw and normalized output strings or JSON
   were compared with the independent oracle. Normalization-dependent passes
   are explicitly identified and are not exact raw passes.
2. **Operational execution:** the local Ollama provider returned observations,
   including explicit empty-output failures. This run did not measure router
   gate survival, fallback behavior, latency policy, or production promotion.
3. **Construct validity:** null baselines, input removal, input shuffling, and
   base/mutant checks test selected shortcut controls. They do not establish
   semantic correctness.

These layers must not be collapsed into one benchmark-accuracy or routing-
safety number.

## Procedural incident history

The first v2 launch exposed a pre-request wrapper bug and retained an empty
partial. A subsequent 270M/1B retry retained 180 rows but did not include 4B.
An initial 4B continuation then executed 90 observations for the superseded
10-variant bundle and failed its row-count assertion; those outputs were not
published as canonical evidence. The corrected 20-variant run was frozen with
new paths and completed at 540 rows. These events are documented in
`BENCHMARK_LEAKAGE_V2_EXECUTION_INCIDENT.md`; no earlier partial is merged
into the corrected result.

## Limitations and withheld claims

- The bundle has 20 variants and three repetitions, not a replacement for a
  broad benchmark suite.
- The controls and oracle were authored after benchmark-development context
  existed, then frozen and hashed before this canonical replay. This is
  evidence about the frozen observations, not an unbiased prospective estimate
  for unseen tasks.
- Classification labels remain permitted-label checks rather than semantic
  proofs.
- Passing ablations would not prove leakage, and failing ablations would not
  prove its absence; here only three ablation observations passed, all for the
  1B model and only after normalization.
- No claim is made about other models, unseen prompts, router safety, cost,
  latency, or production behavior.

## Audit verdict

The corrected run is structurally complete and provenance-consistent. Its
narrow empirical result is that 42 of 180 ordinary observations passed the
normalized oracle, while 3 of 360 ablation observations did. The proper
conclusion is controlled evidence from this frozen suite, not proof of
semantic correctness, absence of leakage, or generalization.
