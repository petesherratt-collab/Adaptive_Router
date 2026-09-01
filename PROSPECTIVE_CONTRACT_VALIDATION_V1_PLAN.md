# Prospective Contract Validation v1 — Frozen Pre-run Plan

Date: 2026-08-31
Branch: `experiment/prospective-contract-validation-v1`

## Purpose and information boundary

This is a prospective validation of deterministic output contracts. The
benchmark, semantic oracle, contract declarations, normalization rules,
metrics, interpretation rules, model identities, execution order, and output
paths are frozen before any output from this prospective suite exists.

The suite is deliberately independent of `benchmark_oos_v1.json`: it has 40
new task IDs, new prompt/source material, and new oracle values. No contract
may be generated from benchmark oracle data. A contract validator receives
only one contract and one raw model output. It cannot read the benchmark,
prompt, oracle, prior validator result, normalized output, or model metadata.

Before execution/design freeze, no model generation, API call, external
network access, or output from this prospective suite is permitted. During
execution preflight, read-only inspection of installed local Ollama metadata
is permitted before the first inference request. That metadata-only
inspection may use installed Ollama metadata/files or a metadata-only Ollama
command/API, but it must not generate tokens, pull/download/update a model, or
contact an external service. The later execution phase is the only phase
authorized to generate with the authenticated local models.

## Frozen artifacts and identity authentication

The three design artifacts are:

| Role | File |
|---|---|
| plan | `PROSPECTIVE_CONTRACT_VALIDATION_V1_PLAN.md` |
| suite and oracle | `benchmark_prospective_contract_v1.json` |
| contract declarations | `validator_contracts_prospective_v1.json` |

After these files are reviewed and committed, the implementation must record
their SHA-256 values before execution. The plan hash is recorded as an
external authentication value in the implementation's preflight/result
provenance rather than embedded in this file, because embedding a file's own
hash would be self-referential. The suite and contract hashes are authenticated
as a pair, including the contract's exact task-ID set and the suite's exact
task contents. The model-identity source hashes are also recorded before the
first request.

The exact model identities copied from the committed scaling evidence are:

| Stratum | Exact Ollama tag | Digest | Parameters | Quantization | Format | Package bytes |
|---|---|---|---:|---|---|---:|
| 270M | `gemma3:270m` | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` | 268.10M | Q8_0 | GGUF | 291554930 |
| 1B | `gemma3:1b` | `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc` | 999.89M | Q4_K_M | GGUF | 815319791 |
| 4B | `gemma3:4b` | `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` | 4.3B | Q4_K_M | GGUF | 3338801804 |

The implementation must authenticate the installed tag, digest, parameter
count, quantization, format, and package size against this table during that
read-only metadata preflight and before any inference request. A mismatch
fails closed before generation. Every generation response must also
authenticate the returned model identity against the same frozen table.

## Suite inventory

`benchmark_prospective_contract_v1.json` contains exactly 40 tasks, in the
canonical order A01 through D10. Every task declares `repetitions: 5`; the
runner schedules repetitions 1 through 5. The four cohorts each contain ten
tasks:

| Cohort | Meaning | Task IDs | Primary estimand |
|---|---|---:|---|
| A `structural_schema` | JSON/object extraction and JSON-format shape/type tasks | `pcv1_a_schema_01`–`pcv1_a_schema_10` | included |
| B `format_conformance` | bullets, labels, and fenced/unfenced formatting | `pcv1_b_format_01`–`pcv1_b_format_10` | included |
| C `label_conformance` | five sentiment and five priority classifications | `pcv1_c_label_01`–`pcv1_c_label_10` | reported separately |
| D `deterministic_executor` | mechanical executable transformations | `pcv1_d_exec_01`–`pcv1_d_exec_10` | reported separately; excluded |

The primary cohort is A+B: 20 tasks, 100 observations per model, and 300
observations across the three model strata. C and D each contain 10 tasks,
so each has 50 observations per model and 150 observations overall. C and D
never enter the primary false-accept catch-rate denominator.

The D entries are executable tasks, not validators. Their declarations specify
a source literal and a named deterministic operation so deterministic code
could bypass model inference. They are retained to quantify that bypassable
work separately.

## Oracle rules

The benchmark `expected` member is the semantic oracle and is allowed only in
the benchmark file. Oracle correctness is exact after the oracle-side
normalization below; there is no LLM judge, semantic repair, or human review in
the canonical result.

For A JSON tasks, the oracle is the exact object with the declared key set and
types. Values are compared recursively: strings are exact Unicode strings,
numbers are JSON numbers, booleans are booleans, and no type coercion occurs.
For B format tasks, the oracle is the exact canonical line/fence string after
the format normalizer. For C classifications, the oracle is the lower-case
semantic label selected by the prompt's frozen rubric. For D, the oracle is
the exact result of applying the named operation to the declared source.

## Independent normalization specifications

Normalization is frozen independently for each contract type. Contract
acceptance is never obtained by comparing to the benchmark oracle. The
implementation must expose stable failure reasons for malformed input and
must not silently repair output.

### Shared line-ending and terminal-newline rule

For every text contract, CRLF is converted to LF. A lone CR is invalid. After
that conversion, exactly one terminal LF is ignored if present. A second
terminal LF therefore remains as a blank line and is rejected wherever blank
lines are forbidden. No other leading or trailing character is removed.

### A1 `structured_json`

The model output is either one JSON object or one complete outer fenced JSON
object. A permitted fence consists of a first line exactly ```` ```json ````
or ```` ``` ```` and a final line exactly ```` ``` ````; the wrapper is removed
once. There must be no content outside that wrapper. Incomplete, nested,
multiple, or language-mismatched fences fail. Without a fence, surrounding
ASCII JSON whitespace is accepted by the JSON parser, but any prose or second
JSON value fails.

The parser rejects duplicate object keys, non-finite JSON constants, a
non-object root, missing keys, extra keys, and undeclared value types. JSON
booleans are never numbers; a declared `number` accepts JSON integer and
decimal numbers, including exponent notation, but not booleans; a declared
`string` accepts only strings. Numeric strings are not numbers and numbers are
not strings. For semantic oracle comparison, integer and decimal JSON numbers
use mathematical numeric equality rather than serialized lexical equality:
`7`, `7.0`, and `7e0` are equal numeric values. Canonical JSON serialization
may be used only for stable recording or fingerprinting, never as the
semantic equality test. Object key order is not semantically relevant for A.
No whitespace or value repair occurs.

The oracle-side A normalizer parses the benchmark's already-decoded expected
object using the same duplicate/type/key/value rules and canonicalizes it with
sorted keys and compact JSON. The intentional difference is that only the
model-output side permits one complete outer fence and surrounding JSON
whitespace; the benchmark oracle is already an object and has neither prose
nor a fence. This difference is declared now and does not alter semantic
comparison.

### A2 `json_format`

`json_format` uses the identical JSON parser, fence, line-ending, duplicate-key,
root, key-set, and exact-type rules as `structured_json`. It checks only the
declared keys and types. It does not contain or inspect any field value. The
oracle-side normalizer is the same A oracle normalizer; only the model-side
complete-fence/JSON-whitespace allowance differs as declared above.

### B1 `bullet_format`

Apply the shared line-ending rule, then remove one optional complete outer
fence only when the contract says a fence is required. A required fence has an
exact opening line and exact closing line specified by the contract; no fence
is allowed for an unfenced contract. Surrounding prose, incomplete or nested
fences, and fence text on content lines fail.

After wrapper removal, there must be exactly `line_count` non-wrapper lines.
Blank lines and additional lines fail. Each line must begin with the literal
declared marker followed by the exact declared separator; no extra whitespace
is accepted before the marker or between marker and separator. The contract
does not inspect item text or item order: those are semantic oracle
comparisons, not pre-inference shape checks. The oracle normalizer applies the
same line/fence rules and then compares the complete canonical bullet string,
including semantic item text and order. Its only intentional difference is
that the oracle text is a benchmark value rather than model output.

### B2 `label_format`

Apply the shared line-ending rule and the same exact required/forbidden outer
fence handling as `bullet_format`. There must be exactly `line_count` content
lines, with no blank or additional lines or surrounding prose. Each line must
contain the declared separator exactly once. The contract does not inspect key
names, values, or their order: those are semantic oracle comparisons, not
available to a pre-inference contract. The oracle normalizer uses the same
format rules and compares the complete canonical key/value string, including
names, values, and order. The only intentional difference is that the oracle
has the benchmark's semantic line content.

### C `classification_labels`

Apply CRLF-to-LF conversion and ignore exactly one terminal LF. There must be
exactly one non-empty line, with no additional or blank lines and no
surrounding prose. Strip only ASCII spaces and tabs at the two ends of that
line. Interior whitespace, punctuation, and any other characters remain
significant. ASCII case is converted to lower case, and the result must be
checked against the contract's permitted labels, which are stored canonically
in lower case. The benchmark expected labels are also canonical lower case.
No synonym, explanation, or semantic repair is accepted.

The oracle applies the same whitespace and ASCII lower-case rule to the
benchmark label and then checks semantic correctness. Thus a wrong-but-
permitted canonical label is contract-accepted but oracle-incorrect and is
reported separately.

### D `deterministic_executor`

These are explicitly not validators and are not validator acceptance tests.
The deterministic executor applies the named operation to the contract's
source literal and computes `executor_accept` from exact output equality.
For D only, the stored `contract_accept` field equals `executor_accept` solely
to keep the common result schema rectangular; it must never be described as
validator acceptance. Apply the
shared line-ending rule, ignore one terminal LF, reject all fences, prose,
blank lines, and additional lines, and perform no surrounding whitespace
trimming. The output is compared with the computed operation result. The
benchmark oracle applies the same named operation to the same source literal;
there is no intentional normalization difference beyond the model's allowed
single terminal LF.

The ten operation names and definitions are frozen as follows:

| Operation | Exact definition |
|---|---|
| `rotate_left_one` | Move the first Unicode code point to the end; preserve every other code point. |
| `rotate_right_two` | Move the final two Unicode code points to the front, preserving their order. |
| `remove_vowels` | Remove every lowercase ASCII `a`, `e`, `i`, `o`, or `u`; leave every other code point unchanged. |
| `replace_letter_e_with_7` | Replace every lowercase ASCII `e` with ASCII digit `7`; leave every other code point unchanged. |
| `collapse_whitespace_runs` | Replace each maximal run of Unicode whitespace with exactly one ASCII space. |
| `swap_ascii_case` | Map ASCII `A`–`Z` to lowercase and ASCII `a`–`z` to uppercase; leave all other code points unchanged. |
| `remove_hyphens` | Remove every ASCII hyphen U+002D; leave every other code point unchanged. |
| `sort_codepoints_ascending` | Sort all Unicode code points into ascending numeric code-point order. |
| `duplicate_final_character` | Append one copy of the final Unicode code point to the non-empty source. |
| `alphabetize_words` | Split on one or more ASCII spaces, sort words by case-sensitive Unicode lexicographic order, and join with one ASCII space. |

## Baseline and counterfactual gates

The baseline is the legacy production post-generation gate, reproduced before
the prospective contract is applied. It uses the committed `validators.py`
implementation and the exact task prompt for this separate baseline path:

`baseline_gate_survived = success AND (ttft_ms is absent OR ttft_ms <= 8000) AND (tokens_per_second is absent OR tokens_per_second >= 1.5) AND validators.validate(task_class, prompt, raw_output).status != FAIL`.

Missing TTFT or throughput telemetry survives its respective legacy check.
A generation transport/error row fails the baseline. The first failure reason
is recorded in this order: `GENERATION_FAILED`, `TTFT_EXCEEDED`,
`GENERATION_TOO_SLOW`, `VALIDATOR_FAILED`; otherwise `SURVIVED`. The
baseline reproduction must not use any recorded validator result from an
output row as a substitute for calling the committed production validator.

For A, B, and C, the counterfactual retains those same generation/telemetry
and legacy-validator decisions and adds the prospective contract:

`counterfactual_gate_survived = baseline_gate_survived AND contract_accept`.

For D, the descriptive deterministic bypass counterfactual is instead:

`counterfactual_gate_survived = baseline_gate_survived AND executor_accept`.

D counterfactual survival is reported only as deterministic bypass work. D is
never included in the primary validator false-accept catch-rate denominator
or in any claim about validator effectiveness.

The contract result is evaluated for every retained observation, including
baseline failures, but raw conformance is not called operational gate
survival. A contract rejection of an observation already rejected by the
baseline is not a contract-caught operational false accept.

## Frozen execution and provenance

There will be 200 observations per model and 600 total: task order is the
benchmark array order A01..D10, repetition order is 1..5 inside each task,
and model-stratum order is `gemma3:270m`, then `gemma3:1b`, then `gemma3:4b`.
Each stratum has one canonical sequential execution. There are no retries,
no skipped failures, no prompt repair, no interleaving between strata, and no
second canonical run.

Generation settings are temperature `0` and maximum output tokens `256`,
matching the committed scaling evidence. The model is loaded on the first
request with no warm-up request. Within a stratum, inference is sequential;
the model is not manually unloaded between observations. Pre-request
residency is recorded for every observation, but residency never changes task
order, retries, acceptance, or exclusion. The installed identity is checked
before the first request and the returned identity is checked on every row.

Exact failure representation is retained in JSONL: `success: false`,
`task_success: false`, `raw_output: null`, `normalized_output: null`,
`oracle_correct: false`, `executor_accept: false`, `contract_accept: false`,
and a stable `error`
object with `kind` and `message` for transport/timeout/model failures. The
`task_success` field is present on every row and equals `success`; it makes
execution failure explicit while retaining the legacy field used by the
baseline reproduction. Empty successful output is `success: true`,
`task_success: true`, `raw_output: ""`, with normalization and both
correctness decisions false. Every output row records
`implementation_revision` as the full implementation commit SHA, plus suite,
contract, plan, and model identity hashes.

Canonical evidence files are:

| Stratum | Evidence JSONL | Summary JSON |
|---|---|---|
| 270M | `benchmark_prospective_contract_v1_gemma3_270m.jsonl` | `benchmark_prospective_contract_v1_gemma3_270m_summary.json` |
| 1B | `benchmark_prospective_contract_v1_gemma3_1b.jsonl` | `benchmark_prospective_contract_v1_gemma3_1b_summary.json` |
| 4B | `benchmark_prospective_contract_v1_gemma3_4b.jsonl` | `benchmark_prospective_contract_v1_gemma3_4b_summary.json` |

Every JSONL write is atomic via a same-directory temporary file and rename.
Every result or summary path is checked for nonexistence before execution and
the writer refuses to overwrite, append to, or partially replace an existing
file. A stratum writes to a unique same-directory partial file, flushes and
fsyncs it, and renames it to the canonical path only after exactly 200
complete rows and the final identity checks are present. An interruption
leaves the partial file quarantined; the runner neither resumes nor appends to
it, and refuses a later run while that partial file exists. A failed preflight
leaves no canonical output. The analyzer refuses partial, truncated, or
incomplete evidence.

The frozen analysis outputs are
`prospective_contract_validation_v1_analysis.json` and
`prospective_contract_validation_v1_analysis.csv`. Their paths, together with
the three evidence paths and three summary paths above, are part of the
nonexistence preflight and atomic-write rule.

Before execution, the implementation must authenticate the plan, suite,
contract, all declared model identities, exact task count/order/repetition
inventory, and all hashes. It must then perform a result-file nonexistence
preflight. These checks occur before the first model request.

## Frozen reporting metrics

The primary reports cover only A+B. They are emitted overall, per model,
cohort, contract type, and task ID. Each scope reports:

- observation count, task-success count, and oracle-correct count;
- baseline and counterfactual gate-survivor counts;
- baseline false accepts;
- false accepts caught and remaining;
- newly admitted incorrect outputs;
- newly rejected correct outputs;
- false-accept catch rate; and
- correct-rejection rate among baseline-correct survivors.

The same fields are reported for C and D in separate sections. C additionally
reports wrong-but-permitted labels (`contract_accept` true and oracle
incorrect), overall and by model/task. D is explicitly reported as
deterministic work that code could bypass; it is never included in the
primary validator catch rate.

Definitions are fixed:

- `baseline_false_accepts` = baseline survivor and oracle incorrect.
- `false_accepts_caught` = baseline survivor, oracle incorrect, and
  counterfactual failure.
- `false_accepts_remaining` = baseline survivor, oracle incorrect, and
  counterfactual survivor.
- `newly_admitted_incorrect` = baseline failure, counterfactual survivor, and
  oracle incorrect.
- `newly_rejected_correct` = baseline survivor, oracle correct, and
  counterfactual failure.
- `counterfactual_false_accepts` = counterfactual survivor and oracle
  incorrect.
- `baseline_correct_survivors` = baseline survivor and oracle correct.
- `correct_rejection_rate_among_baseline_correct_survivors` = newly rejected
  correct divided by baseline-correct survivors, or `null` for a zero
  denominator. This is explicitly a correct-output rejection (false-rejection)
  rate; lower is better.
- `false_accept_catch_rate` = false accepts caught divided by baseline false
  accepts, or `null` for a zero denominator.

The analyzer must hard-assert these invariants for every A/B/C scope and use
the D executor form where stated:

- counterfactual survivors <= baseline survivors;
- `newly_admitted_incorrect == 0`;
- baseline FAIL + counterfactual SURVIVE + oracle correct == 0;
- baseline FAIL + counterfactual SURVIVE + oracle incorrect == 0;
- false accepts caught + false accepts remaining == baseline false accepts;
- counterfactual false accepts == false accepts remaining; and
- newly rejected correct <= baseline-correct survivors.

The eight transition cells must still sum to the declared scope total. A
failed invariant is a hard analysis failure, not a warning or an expected
observation.

The primary report includes the complete eight-cell transition table formed by
baseline survive/fail × counterfactual survive/fail × oracle correct/incorrect.
Because every row has a boolean `oracle_correct` value, including failures,
the eight cells are complete. They must sum to 100 per model in A+B, 300
overall in A+B, and 50 per model/150 overall in each separately reported C or
D section.

## Bootstrap and interpretation

The primary catch rate uses a task-cluster bootstrap with 10,000 draws and
frozen seed `20260831`. The resampling unit is task. For draw `d` in 0..9999
and task slot `s` in 0..19, form the byte string

`ASCII("prospective_contract_validation_v1") || ASCII("|") || ASCII("20260831") || ASCII("|") || ASCII(decimal d) || ASCII("|") || ASCII(decimal s)`

and hash it with SHA-256. Interpret the first eight digest bytes as an
unsigned 64-bit big-endian integer and select `integer mod 20`. Index 0..19
means the canonical A+B task order in the benchmark. Sampling is with
replacement; each selected task carries all five repetitions and all three
model strata. Each draw is caught false accepts divided by baseline false
accepts. A zero-denominator draw is recorded as undefined, omitted only from
percentile calculation, and counted in the report.

For sorted defined values `x[0..n-1]`, percentile probability `p` uses frozen
Hyndman-Fan type 7 linear interpolation: `h=(n-1)*p`, `j=floor(h)`,
`g=h-j`; return `x[j]` when `j==n-1`, otherwise `x[j]+g*(x[j+1]-x[j])`.
Use `p=0.025` and `p=0.975`. No numpy, scipy, or default library percentile
behavior is normative; a library is permitted only when tests demonstrate
identical results.

Report the prospective interval alongside the retrospective 69.6% result as
a historical descriptive reference only. Do not issue an equivalence,
directional, or non-inferiority verdict from that comparison;
the interval is not a formal equivalence test and not a formal non-inferiority
test.

## Mandatory separation tests

Implementation tests must prove the information boundary. For A, an output
with correct exact keys and declared types but deliberately wrong semantic
values must be contract-accepted and oracle-incorrect. For B, an output with
the required line count, marker/separator, and fence shape but deliberately
wrong item/key/value content or order must be contract-accepted where its
shape conforms and oracle-incorrect. For C, a wrong but permitted canonical
lower-case label must be contract-accepted and oracle-incorrect. These are
required anti-leakage tests. D is different: its deterministic executor is
intentionally allowed to know the source literal and named operation.

## Frozen execution order

1. Review and commit these three design files.
2. Record their SHA-256 values and authenticate all identities.
3. Implement schema validation, runner, analyzer, and adversarial tests.
4. Dry-run without writes or model calls.
5. Commit the implementation.
6. Execute each model stratum once in the declared order.
7. Authenticate evidence.
8. Run analysis once.
9. Commit canonical evidence and results.
10. Write a separate audit.

No implementation, runner, analyzer, test, evidence, result, audit, commit,
push, model call, API call, or network access is part of this design-file
creation step.
