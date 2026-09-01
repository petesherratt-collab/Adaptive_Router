# Prospective Contract Validation v1 — Execution Incident

Date: 2026-09-01
Branch: `experiment/prospective-contract-validation-v1`

## Classification

**PARTIAL / EXECUTION HALTED DUE TO FROZEN PROTOCOL-INSTRUMENT CONTRADICTION**

The completed 270M evidence is not characterized as invalid. The intended
three-model v1 experiment is not characterized as completed.

## Frozen identities

- Design freeze: `9021d4b2c51d05f247c7d3f04c087a62ad789d03`
- Implementation freeze: `34f5f1f3451524325d98fb8d672fd03baebb8747`

## Completed evidence

The following 270M canonical files completed successfully and were not
deleted, renamed, rewritten, or analyzed during this incident:

- `benchmark_prospective_contract_v1_gemma3_270m.jsonl`
- `benchmark_prospective_contract_v1_gemma3_270m_summary.json`

Recorded completion facts:

- exit code `0`;
- exactly 200 rows;
- 200 unique task/repetition pairs;
- 200 task successes;
- implementation and provenance hashes authenticated; and
- no partial file.

SHA-256 values recorded from the completed files:

```text
b4c87280ef0abd45f0c7243d6a0a66d4bf1307c4118d0078f99bd5f1943ae345  benchmark_prospective_contract_v1_gemma3_270m.jsonl
301ecdb47707917ce681b7bdbab6ca2e1be93f0a8d48487b536ee8d387a819a0  benchmark_prospective_contract_v1_gemma3_270m_summary.json
```

No operation in this incident modified either file; these hashes record their
current byte contents after the halted attempt.

## Halted attempt and protocol contradiction

The next command was attempted:

```text
./.venv/bin/python run_prospective_contract_validation.py --model gemma3:1b
```

It failed during preflight with `FileExistsError` because the already-completed
270M canonical files existed.

The contradiction is present in the frozen plan and runner:

1. The plan requires every evidence, summary, and analysis path to be absent
   before execution.
2. The implementation's global `canonical_paths()` includes all three model
   evidence paths, all three summaries, and both analysis paths.
3. `preflight_output_paths()` rejects any existing canonical path or partial.
4. The runner calls `preflight()` on every invocation, including each
   `--model` invocation.

Therefore, separate sequential invocations cannot proceed after the first
successful stratum, even though each stratum is intended to be executed once.

## Scope after halt

- 1B generation requests: none.
- 1B JSONL, summary, and partial files: absent.
- 4B output files and partials: absent.
- Analysis JSON, CSV, and partials: absent.
- 270M canonical files: present and byte-for-byte untouched by the halted
  attempt, with the hashes recorded above.

No model call, analysis run, output rewrite, commit, or push was performed as
part of this incident response.

## Proposed v2 semantics — not implemented

1. Initial experiment preflight requires all canonical outputs to be absent.
2. A subsequent-stratum preflight requires completed prior strata to exist and
   authenticate; completed files are immutable; current and future outputs must
   be absent; and any current or future partial blocks execution.
3. Analysis is allowed only after three authenticated 200-row strata exist.
4. A canonical stratum is never overwritten or resumed.

v2 requires a fresh prospective suite and design freeze. v1 must not be
quietly edited after observing the 270M outputs.
