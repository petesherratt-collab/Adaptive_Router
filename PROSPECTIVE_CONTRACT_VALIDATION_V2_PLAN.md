# Prospective Contract Validation v2 — Frozen Design Plan

Date: 2026-09-01
Branch: `experiment/prospective-contract-validation-v2`
Suite: `prospective_contract_validation_v2`

## Status and information boundary

This document, `benchmark_prospective_contract_v2.json`, and
`validator_contracts_prospective_v2.json` are design artifacts only. V2 is a
new prospective experiment with new task IDs, prompts, source literals, and
oracle values. No V2 model output may exist before these files are reviewed,
committed, hashed, and authenticated, and before the implementation is
completed, committed, and passed through its no-model preflight.

V1 has a sealed completed 270M evidence stratum and a documented execution
halt. That evidence is not read, parsed, summarized, sampled, analyzed, or
used for V2 task selection, difficulty tuning, oracle construction, or
implementation decisions. The only V1 execution fact carried into this plan
is the documented protocol contradiction: a global output nonexistence check
was repeated on every standalone stratum invocation. V2 changes that protocol
explicitly through the monotonic state machine below. V1 files are never V2
outputs.

V2 preserves the methodological structure frozen before V1 execution while
using entirely fresh content. Freshness checks compare only against V1 design
task text, never against V1 raw evidence or model results.

## Suite and estimand

The suite has 40 tasks, five repetitions per task, 200 observations per model,
and 600 observations overall. Tasks are in this exact order:

1. `pcv2_a_schema_01` through `pcv2_a_schema_10`
2. `pcv2_b_format_01` through `pcv2_b_format_10`
3. `pcv2_c_label_01` through `pcv2_c_label_10`
4. `pcv2_d_exec_01` through `pcv2_d_exec_10`

The four ten-task cohorts are:

| Cohort | Role | Primary estimand |
|---|---|---|
| A `structural_schema` | JSON/object extraction and JSON-format shape/type tasks | included |
| B `format_conformance` | bullet, label, and fence shape tasks | included |
| C `label_conformance` | five sentiment and five priority classifications | separate |
| D `deterministic_executor` | mechanical executable transformations | separate bypass work |

The primary estimand is A+B only: 20 tasks, 100 observations per model, and
300 observations overall. C is reported separately, including wrong but
permitted labels. D is reported separately as deterministic bypassable work and
is never included in the primary validator-effectiveness denominator or catch
rate.

Models and canonical execution order are:

1. `gemma3:270m`
2. `gemma3:1b`
3. `gemma3:4b`

Within each task, repetitions run in order 1 through 5. There is one
canonical sequential execution per stratum, with no retries, skipped failures,
prompt repair, warm-up request, or interleaving between strata.

## Fresh content

Every V2 prompt, source literal, and oracle value is newly authored. V2 keeps
the functional roles and broad difficulty of the four cohorts but copies no V1
literal, task ID, expected value, prompt, or close paraphrase. A contains ten
new object schemas using new domains, field names, values, and combinations of
string, number, and boolean fields. B contains fresh unfenced and fenced
bullets and labels with varied markers, separators, and line counts. C contains
five unambiguous fresh sentiment items and five unambiguous fresh priority
items. D contains ten fresh source literals paired with the frozen named
operation vocabulary.

The C sentiment rubric is frozen as follows: `positive` means a clearly
approving or favourable judgement; `negative` means a clearly disapproving or
unfavourable judgement; `neutral` means a factual statement without
evaluation. The C priority rubric is frozen as follows: `high` applies to an
active safety or security event, blocked work, or a deadline within 24 hours;
`medium` applies to action due after 24 hours and within 7 days when work can
continue and no such event exists; `low` applies when no action is needed or
the deadline is beyond 7 days.

## Model identity

The installed local identities must match this table before the first request.
Authentication is fail-closed on tag, digest, parameter count, quantization,
format, and package bytes. `family` may be recorded diagnostically but is not
an independent fail-closed criterion.

| Model | Tag | Digest | Parameters | Quantization | Format | Package bytes |
|---|---|---|---|---|---|---:|
| 270M | `gemma3:270m` | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` | 268.10M | Q8_0 | GGUF | 291554930 |
| 1B | `gemma3:1b` | `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc` | 999.89M | Q4_K_M | GGUF | 815319791 |
| 4B | `gemma3:4b` | `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` | 4.3B | Q4_K_M | GGUF | 3338801804 |

Read-only local metadata inspection is allowed during execution preflight.
It may use installed Ollama metadata or an equivalent metadata-only local
command/API, but must not generate, pull, download, update, or contact an
external service. Every generation response must expose and authenticate its
returned model tag against the requested frozen tag. Digest and package
metadata are installed-model preflight criteria, not response fields assumed
to be present in generation responses. Model-identity source hashes, if
required by the implementation provenance, are recorded before the first
request and carried into every result row.

## Independent normalization and oracle

The contract declaration is evaluated independently from the benchmark oracle.
A/B/C contract validators receive only their relevant contract declaration and
raw model output. They receive no prompt, expected value, oracle, normalized
oracle, prior validator result, model identity, or task history. D is
deliberately different: its executable declaration contains its source literal
and named operation.

### Shared text normalization

For every text contract, CRLF becomes LF. A lone CR is invalid. After that
conversion, exactly one terminal LF is ignored; a second terminal LF remains a
blank line. No other leading or trailing character is removed.

### A: `structured_json` and `json_format`

The model output must be one JSON object, optionally wrapped in one complete
outer fence whose opening line is exactly ```` ``` ```` or ```` ```json ````
and whose closing line is exactly ```` ``` ````. The wrapper is removed once.
Incomplete, nested, multiple, language-mismatched, or surrounding-prose
fences fail. Without a fence, JSON parser whitespace is allowed, but prose or
a second JSON value fails.

The strict parser rejects duplicate keys, non-finite constants, non-object
roots, missing keys, extra keys, and undeclared types. JSON booleans are never
numbers. Integer, decimal, and exponent JSON numbers are all type `number` and
compare by mathematical numeric equality, so `7`, `7.0`, and `7e0` are equal.
`"7"` is not equal to `7`. Canonical serialization is permitted only for
stable recording or fingerprinting, never as the semantic equality test.

Contracts contain exact key sets and declared types only. They contain no
semantic field values. The oracle compares the parsed object recursively with
type-sensitive string/boolean/object/array semantics and mathematical numeric
equality; object key order is not semantic.

### B: `bullet_format` and `label_format`

The shared line rule is applied first. A required fence has the exact language
and outer-only form declared by the contract; an unfenced contract forbids any
fence. Surrounding prose, incomplete or nested fences, blank lines, and extra
lines fail.

Bullet contracts check only exact content-line count and each line's literal
marker plus separator. Label contracts check only exact content-line count and
exactly one declared separator per line. B contracts do not contain or inspect
item text, key text, values, or semantic order. Those are oracle-only. The
oracle normalizes the same shape and compares the complete expected semantic
line string.

### C: `classification_labels`

There must be exactly one non-empty label line. One terminal LF is ignored;
additional or blank lines and surrounding prose fail. Only ASCII spaces and
tabs at the two edges are stripped. ASCII case is folded to lowercase; other
characters and interior whitespace remain significant. Contracts store the
permitted labels canonically as lowercase: sentiment
[`positive`, `negative`, `neutral`] and priority [`high`, `medium`, `low`].
Benchmark expected labels are lowercase. A wrong-but-permitted label is
contract-accepted but oracle-incorrect and is reported separately.

### D: `deterministic_executor`

D is explicitly not a validator cohort. The executor applies the named
operation to the contract source literal and computes `executor_accept` from
exact output equality. For D only, `contract_accept` aliases `executor_accept`
solely to keep the common result schema rectangular; it is never called
validator acceptance. D counterfactual survival is baseline survival AND
`executor_accept`, and is reported only as deterministic bypass analysis.

The ten operation definitions are frozen:

| Operation | Definition |
|---|---|
| `rotate_left_one` | Move the first Unicode code point to the end. |
| `rotate_right_two` | Move the final two Unicode code points to the front, preserving order. |
| `remove_vowels` | Remove lowercase ASCII `a`, `e`, `i`, `o`, and `u`; leave all else unchanged. |
| `replace_letter_e_with_7` | Replace lowercase ASCII `e` with ASCII `7`; leave all else unchanged. |
| `collapse_whitespace_runs` | Replace every maximal Unicode whitespace run with one ASCII space. |
| `swap_ascii_case` | Swap ASCII `A`–`Z` and `a`–`z`; leave all other code points unchanged. |
| `remove_hyphens` | Remove ASCII hyphen U+002D; leave all other code points unchanged. |
| `sort_codepoints_ascending` | Sort Unicode code points by ascending numeric code point. |
| `duplicate_final_character` | Append one copy of the final Unicode code point to a non-empty source. |
| `alphabetize_words` | Split on one or more ASCII spaces, sort case-sensitive Unicode words, and join with one ASCII space. |

## Baseline and counterfactual gates

The legacy baseline is reproduced exactly with committed `validators.py`:

```text
baseline_gate_survived =
    success
    AND (ttft_ms absent OR ttft_ms <= 8000)
    AND (tokens_per_second absent OR tokens_per_second >= 1.5)
    AND validators.validate(task_class, prompt, raw_output).status != FAIL
```

The first failure reason is `GENERATION_FAILED`, `TTFT_EXCEEDED`,
`GENERATION_TOO_SLOW`, `VALIDATOR_FAILED`, then `SURVIVED`. `NOT_APPLICABLE`
survives the validator component. Unsupported task classes, including
`format_json`, are not improved after freeze.

For A/B/C:

```text
counterfactual_gate_survived = baseline_gate_survived AND contract_accept
```

For D:

```text
counterfactual_gate_survived = baseline_gate_survived AND executor_accept
```

The contract or executor is evaluated for every retained observation, including
baseline failures, but a contract rejection of an already rejected baseline
observation is not a caught operational false accept.

## Sequential output state machine

V2 replaces V1's contradictory global-per-invocation nonexistence rule with a
monotonic state machine. V2 canonical paths are never confused with V1 paths.

### Initial `EMPTY` state

Before the first 270M request, all V2 evidence paths, summaries, analysis
paths, and their `.partial` paths must be absent. Only `gemma3:270m` may
start from `EMPTY`.

### `270M_COMPLETE` state

Before 1B execution, the 270M JSONL and summary must exist, authenticate
against the frozen design and implementation, identify `gemma3:270m`, contain
exactly 200 complete rows covering all 40 task IDs with repetitions 1–5, and
remain read-only. Their SHA-256 values are recorded by this preflight. 1B and
4B outputs and partials, both analysis outputs and partials, and any prior
stratum partial must be absent.

### `1B_COMPLETE` state

Before 4B execution, authenticated immutable 270M and 1B JSONL/summary pairs
must each contain exactly 200 complete rows and the prior-stratum hashes must
be recorded. 4B outputs and partials and both analysis outputs and partials
must be absent.

### `4B_COMPLETE` and analysis

Before analysis, all three authenticated immutable strata must exist, each
must contain exactly 200 complete rows with correct model/order/provenance,
and no partial counterpart may exist. Analysis JSON and CSV, including their
partials, must be absent. Analysis is permitted only in this state and only
once.

A completed canonical stratum is never overwritten, appended to, resumed, or
regenerated within canonical V2. An interrupted stratum leaves a quarantined
partial and halts execution; there is no delete/retry under the same canonical
run without a separately recorded protocol decision. Any impossible mixed
state fails closed. The only legal progression is:

```text
EMPTY -> 270M_COMPLETE -> 1B_COMPLETE -> 4B_COMPLETE -> ANALYZED
```

## Canonical output paths and atomic writing

V2 uses only these paths:

| Stratum | Evidence | Summary |
|---|---|---|
| 270M | `benchmark_prospective_contract_v2_gemma3_270m.jsonl` | `benchmark_prospective_contract_v2_gemma3_270m_summary.json` |
| 1B | `benchmark_prospective_contract_v2_gemma3_1b.jsonl` | `benchmark_prospective_contract_v2_gemma3_1b_summary.json` |
| 4B | `benchmark_prospective_contract_v2_gemma3_4b.jsonl` | `benchmark_prospective_contract_v2_gemma3_4b_summary.json` |

Analysis paths are `prospective_contract_validation_v2_analysis.json` and
`prospective_contract_validation_v2_analysis.csv`.

Each stratum writes to a unique same-directory partial file, flushes and
fsyncs it, verifies exactly 200 complete rows and final identity/provenance,
and atomically renames only after completion. Summary publication occurs only
after evidence JSONL completion and authentication. Existing canonical or
partial paths refuse execution. No overwrite, append, resume, or partial
replacement is permitted.

## Generation and result rows

Generation uses temperature `0` and maximum output tokens `256`. The model is
kept resident between sequential observations within a stratum; residency is
recorded but never changes ordering or inclusion. There is no warm-up request.

Every row records the schema/version, suite and design hashes, implementation
revision, requested and returned model tags, installed model identity and
provenance, task ID, repetition, cohort, contract type, raw and normalized
output, oracle correctness, executor/contract acceptance, baseline and
counterfactual decisions and reasons, telemetry, residency, and error state.

A generation failure remains one retained observation and is never retried:

```text
success=false
task_success=false
raw_output=null
normalized_output=null
oracle_correct=false
executor_accept=false
contract_accept=false
```

The error is a stable `{kind, message}` object. An empty successful output is
distinct from a generation failure.

## Analysis and metrics

Primary A+B reporting is overall, per model, cohort, contract type, and task.
Each scope reports observation count, task-success count, oracle-correct count,
baseline survivors, counterfactual survivors, baseline false accepts, false
accepts caught and remaining, newly admitted incorrect, newly rejected correct,
counterfactual false accepts, baseline correct survivors, false-accept catch
rate, and correct-rejection rate among baseline-correct survivors. The complete
eight-cell baseline-survive/fail × counterfactual-survive/fail × oracle-
correct/incorrect transition table is included. C is a separate section with
wrong-but-permitted labels. D is a separate deterministic bypass section and
never contributes to primary validator effectiveness.

The definitions are:

- baseline false accepts: baseline survivor and oracle incorrect;
- false accepts caught: baseline survivor, oracle incorrect, counterfactual fail;
- false accepts remaining: baseline survivor, oracle incorrect, counterfactual survive;
- newly admitted incorrect: baseline fail, counterfactual survive, oracle incorrect;
- newly rejected correct: baseline survivor, oracle correct, counterfactual fail;
- counterfactual false accepts: counterfactual survivor and oracle incorrect; and
- baseline correct survivors: baseline survivor and oracle correct.

Hard assertions apply to every scope, using the D executor form where stated:

```text
counterfactual survivors <= baseline survivors
newly_admitted_incorrect == 0
baseline FAIL + counterfactual SURVIVE + oracle correct == 0
baseline FAIL + counterfactual SURVIVE + oracle incorrect == 0
false_accepts_caught + false_accepts_remaining == baseline_false_accepts
counterfactual_false_accepts == false_accepts_remaining
newly_rejected_correct <= baseline_correct_survivors
sum(eight transition cells) == scope observation count
```

Any failed assertion is a hard analysis failure.

## V2 bootstrap

The primary A+B false-accept catch rate uses a task-cluster bootstrap with
10,000 draws, namespace `prospective_contract_validation_v2`, and seed
`20260901`. For draw `d` and task slot `s`, form:

```text
SHA256(
  ASCII("prospective_contract_validation_v2") ||
  ASCII("|") ||
  ASCII("20260901") ||
  ASCII("|") ||
  ASCII(decimal(d)) ||
  ASCII("|") ||
  ASCII(decimal(s))
)
```

The first eight digest bytes are an unsigned big-endian 64-bit integer;
integer modulo 20 selects the canonical A+B task index. Sampling is with
replacement. Each selected task carries all five repetitions and all three
model strata. A draw is caught false accepts divided by baseline false accepts.
Zero-denominator draws are recorded as undefined, omitted only from percentile
calculation, and counted.

Percentiles use frozen Hyndman-Fan type 7 linear interpolation at 2.5% and
97.5%:

```text
h = (n - 1) * p
j = floor(h)
g = h - j
percentile = x[j] if j == n-1 else x[j] + g * (x[j+1] - x[j])
```

No library RNG or default percentile behavior is normative. A library is
allowed only when tests demonstrate identical results. Retrospective context,
including the historical 69.6% figure, may be mentioned only after V2
analysis and only descriptively; no V1 partial result may influence V2 design,
and no equivalence or non-inferiority claim is made.

## Mandatory anti-leakage and state-machine tests

Tests must prove:

- A correct exact key/type shape with deliberately wrong values is contract
  accepted and oracle incorrect;
- B correct line/fence/marker/separator shape with deliberately wrong semantic
  text, keys, values, or order is contract accepted and oracle incorrect;
- C wrong but permitted lowercase label is contract accepted and oracle
  incorrect; and
- D executes only its declared source literal and named operation.

The V2 contract document must pass a static audit showing no A/B/C expected
semantic value is present as a contract field. The following state-machine
cases are mandatory: EMPTY→270M allowed; EMPTY→1B rejected; completed 270M→1B
allowed; rerun 270M rejected; malformed/truncated/forged 270M rejects 1B;
unexpected 4B before 1B rejects; completed 270M+1B→4B allowed; 270M only→4B
rejected; any required prior partial rejects; current/future partial rejects;
three valid strata→analysis allowed; fewer than three→analysis rejected;
existing analysis output rejects rewrite; changed prior hash rejects; and
preflight never modifies a canonical stratum.

## Execution order and freeze

1. Review and commit these three V2 design files.
2. Record their SHA-256 values and authenticate model identities.
3. Implement schema validation, state-machine runner, analyzer, and tests.
4. Dry-run without writes or model calls.
5. Commit the implementation.
6. Execute 270M once from `EMPTY`.
7. Authenticate 270M and advance to 1B.
8. Execute 1B once and authenticate it before advancing to 4B.
9. Execute 4B once and authenticate all three strata.
10. Run analysis once and commit canonical evidence/results.
11. Write a separate audit.

No V1 file is modified. No V2 output is created as part of this design phase.
