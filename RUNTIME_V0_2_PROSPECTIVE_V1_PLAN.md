# Runtime v0.2 Prospective Evaluation v1 — Frozen Design Plan

Date: 2026-09-02
Branch: `experiment/runtime-v0.2-prospective-v1`
Released runtime: `v0.2.0` at commit
`307a47389fea10df38623bc2f238a14a11081269`
Suite: `runtime_v0_2_prospective_v1`

## Status and execution boundary

This is a prospective evaluation of the assembled v0.2 product runtime, not a
replay of earlier model evidence. The plan and a fresh benchmark document must
be reviewed, committed, and hashed before the execution harness is implemented.
The harness and its tests must then be committed and pass a no-model dry run
before any canonical Ollama or OpenRouter request is permitted.

No output from earlier Simulation Zero, scaling, contract-replay, prospective-
contract, or measured-routing experiments may be used as an observation in
this suite. Earlier results justify the product policy being tested, but may
not tune these tasks after execution begins.

Canonical execution is one-shot. No prompt, expected answer, contract, order,
threshold, model setting, or oracle may be changed after the first provider
request. A defect discovered after execution begins is documented and the run
halts unless this plan already defines the recovery.

## Questions and estimands

The primary question is whether released runtime v0.2 returns a correct final
user-visible result on fresh, deterministically scored requests while reducing
OpenRouter use relative to always-remote execution.

Primary generative estimands, reported overall and by cohort/contract type:

1. final runtime correctness;
2. OpenRouter logical calls and HTTP attempts;
3. reported OpenRouter cost;
4. end-to-end runtime latency;
5. local acceptance, escalation, and final-contract-failure counts; and
6. accepted-error count: an oracle-incorrect final output returned to the user.

Secondary paired estimands compare the provider outputs actually obtained for
the same task and repetition:

- local-only oracle correctness;
- remote-only oracle correctness;
- both/local-only/remote-only/neither overlap;
- the runtime policy versus always-local and always-remote correctness; and
- remote calls avoided and correctness difference versus always remote.

The deterministic cohort is reported separately. It demonstrates the product
bypass path, not model routing or validator effectiveness.

No claim is made about other hardware, models, prompts, task distributions,
semantic correctness in general, or deployment readiness.

## Frozen suite

The suite contains 40 fresh tasks and three repetitions per task: 120 runtime
observations. The exact task and repetition order is frozen in the benchmark.

| Cohort | Tasks | Runtime observations | Actual v0.2 path |
|---|---:|---:|---|
| `deterministic` | 10 | 30 | Python executor; neither provider |
| `structural_json` | 12 | 36 | local first; contract-gated fallback |
| `line_format` | 8 | 24 | local first; contract-gated fallback |
| `classification` | 10 | 30 | direct OpenRouter |
| **Total** | **40** | **120** | |

The 30 generative tasks also receive one paired local output and one paired
remote output per repetition. An output produced during the actual runtime
path supplies that provider arm; only a missing arm is executed as a control.
Therefore the canonical budget is exactly 90 logical Ollama generations and
90 logical OpenRouter generations, plus 30 deterministic executions. A remote
logical generation may make at most the released adapter's two bounded HTTP
attempts, so the hard HTTP-attempt ceiling is 180.

There are no warm-up requests, semantic repair requests, experiment-level
retries, skipped observations, or replacement tasks.

### Contracts

The 20 local-first tasks use the released `runtime_request_v1` contracts:

- eight `structured_json` tasks;
- four `json_format` tasks;
- four `bullet_format` tasks; and
- four `label_format` tasks.

The ten classification tasks use `classification_labels` and route directly
remote. Five are sentiment and five priority. Every classification prompt
contains the frozen rubric needed to interpret its labels.

The ten deterministic tasks use all ten allowlisted executor operations once.

Contracts contain shape, type, line, label-membership, or executable-operation
declarations only. Expected semantic values remain oracle-only. The harness
must prove that it passes only the four runtime request fields to `Router`.

## Actual path and paired controls

For every observation, the released `Router.route_request()` is invoked once
without policy overrides. Its dedicated telemetry record is retained.

Provider calls made by that route are captured through transparent wrappers:

- if the runtime attempted local generation, that result is the local arm;
- if the runtime attempted remote generation, that result is the remote arm;
- if a generative observation lacks a local arm, one direct local control is
  run after the actual route; and
- if it lacks a remote arm, one direct remote control is run after the actual
  route.

Controls use the same frozen prompt and released provider configuration. They
do not pass through routing health gates and cannot change the actual result.
Control order is necessarily conditional on the actual route and is therefore
not randomized; this limitation must appear in the analysis.

An internal OpenRouter retry is part of the released runtime/provider adapter,
not an experiment retry. A timeout can represent a request processed remotely
whose response was lost, so reported cost is a lower bound when an attempt has
no valid usage response. Attempt counts are reported alongside logical calls.

## Runtime and provider identity

Execution must authenticate all of the following before the first provider
request:

- Git revision descends from released commit
  `307a47389fea10df38623bc2f238a14a11081269`;
- the working tree has no tracked modifications;
- the plan and benchmark SHA-256 values match the implementation constants;
- `config.json` matches its frozen SHA-256;
- local model tag is `gemma3:270m`;
- installed Ollama identity matches the previously authenticated 270M digest,
  parameter count, quantization, format, and package-byte identity;
- remote model is exactly `openai/gpt-5.6-luna`;
- temperature is zero and maximum output tokens are 256 for both providers;
- local `keep_alive` is `-1`;
- remote maximum attempts is 2 with 0.25-second backoff; and
- an OpenRouter key is present without recording it.

Frozen 270M identity:

| Field | Value |
|---|---|
| tag | `gemma3:270m` |
| digest | `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` |
| parameters | `268.10M` |
| quantization | `Q8_0` |
| format | `GGUF` |
| package bytes | `291554930` |

The harness records the exact implementation revision and public model
identity in every observation. It never records credentials.

## Oracles

All tasks have deterministic expected outputs frozen in the benchmark.

- JSON tasks use the strict parsing, fence, duplicate-key, finite-number, and
  type-sensitive recursive equality rules from Prospective Contract Validation
  v2. Numeric JSON values compare mathematically; booleans are not numbers.
- Bullet and label tasks apply the declared line/fence normalization and then
  compare the complete semantic lines exactly.
- Classification applies the released label normalization and compares the
  resulting canonical label to the expected label.
- Deterministic tasks require exact equality with the independently frozen
  expected string. The executor and oracle compute the same declared function
  by construction, so this cohort provides no validator-effectiveness claim.

Oracle evaluation receives raw provider/final output only after the relevant
call. Expected values are never included in model prompts, contracts, router
objects, or provider configuration.

Transport failure, empty output, withheld final output, or missing required
provider arm is oracle-incorrect and retained rather than retried.

## Correctness and policy definitions

`runtime_correct` means the non-withheld final user-visible runtime output
passes the frozen oracle. `accepted_error` means the runtime returned a
non-empty output but the oracle marked it incorrect. A withheld
`REMOTE_CONTRACT_FAILED` result is incorrect but is not a false acceptance.

For generative observations:

```text
always_local_correct  = oracle(local raw output)
always_remote_correct = oracle(remote raw output)
runtime_correct       = oracle(runtime final visible output)
```

The overlap table is computed from the two provider correctness booleans.
Remote calls avoided versus always remote are `90 - actual_runtime_remote_calls`.
The comparison does not assign monetary cost to local computation because this
experiment does not measure energy.

## Cost and failure limits

Canonical execution stops before starting another remote logical call when:

- 90 remote logical calls have already been made;
- fewer than two of the 180 remote HTTP-attempt slots remain (the released
  adapter may consume two attempts in one logical call); or
- cumulative reported OpenRouter cost exceeds USD 0.02.

Because a timeout may hide a billed attempt, the USD threshold is not a hard
upper bound on account charges. The logical-call and attempt ceilings are the
normative safety bounds. A crossing request is retained, and execution halts
before any next request.

Provider or machine failure produces a retained failed arm. There is no
experiment-level retry. An interruption leaves partial files and requires an
explicitly documented successor decision; canonical files are never resumed,
overwritten, or silently repaired.

## Canonical order and state machine

Tasks execute in benchmark order. For each task, repetitions execute 1, 2, 3.
For each observation: run the actual v0.2 route, run only the missing provider
control arm if generative, authenticate the resulting record, append and fsync
the evidence partial, then proceed.

Legal states are:

```text
EMPTY -> EXECUTING(partials only) -> COMPLETE -> ANALYZED
```

`EMPTY` requires all canonical results, summaries, analyses, and partials to
be absent. Any partial at startup blocks canonical execution. `COMPLETE`
requires exactly 120 ordered evidence rows, 120 ordered router telemetry rows,
90 local logical results, 90 remote logical results, 30 deterministic results,
and an authenticated summary. Analysis is permitted once from `COMPLETE` and
refuses existing outputs.

## Files and atomic publication

Frozen inputs:

- `RUNTIME_V0_2_PROSPECTIVE_V1_PLAN.md`
- `benchmark_runtime_v0_2_prospective_v1.json`

Implementation:

- `runtime_v0_2_prospective_v1.py`
- `run_runtime_v0_2_prospective_v1.py`
- `analyze_runtime_v0_2_prospective_v1.py`
- `tests/test_runtime_v0_2_prospective_v1.py`

Canonical outputs:

- `runtime_v0_2_prospective_v1_runs.jsonl`
- `runtime_v0_2_prospective_v1_router_telemetry.jsonl`
- `runtime_v0_2_prospective_v1_summary.json`
- `runtime_v0_2_prospective_v1_analysis.json`
- `runtime_v0_2_prospective_v1_analysis.csv`

Evidence and telemetry are written to unique same-directory `.partial` files,
flushed and fsynced after each complete observation, authenticated after all
120 rows, and atomically renamed. Summary and analysis use write-once partial
publication. Existing canonical or partial paths fail closed.

## Observation schema

Each evidence row records:

- schema/suite identifiers and frozen input hashes;
- implementation revision and authenticated configuration/model identities;
- task ID, repetition, cohort, task class, and contract type;
- actual route, reason, trigger, final visible output, runtime correctness,
  accepted-error and withheld flags;
- local and remote raw outputs, stable errors, timing/rate/usage/cost/attempt
  metadata, contract results, and oracle correctness;
- exact dedicated router telemetry request ID and decision; and
- cumulative logical-call, HTTP-attempt, and reported-cost counters.

Prompts and expected answers exist in the frozen benchmark and need not be
duplicated in every row. Raw model outputs are canonical experimental evidence
and are therefore retained here even though normal product telemetry excludes
them.

## Analysis

Report counts and rates overall, by cohort, contract type, task, repetition,
actual route, and reason. Include:

- runtime correctness and accepted errors;
- withheld final outputs;
- local/remote correctness and overlap;
- local acceptances and escalations;
- actual remote logical calls, HTTP attempts, retries, and reported cost;
- remote calls avoided versus always remote;
- median and percentile runtime/provider latency; and
- exact paired correctness differences against always local and always remote.

Uncertainty for the primary generative runtime-correct rate and paired
runtime-minus-always-remote difference uses a task-cluster bootstrap with
10,000 deterministic SHA-256-defined draws. The namespace is
`runtime_v0_2_prospective_v1`, seed `20260902`, and the 30 generative tasks are
the sampling units. Each sampled task carries all three repetitions. Percentile
calculation uses Hyndman-Fan type 7. Zero-denominator or otherwise undefined
draws are counted explicitly.

No hypothesis test, non-inferiority margin, or universal capability claim is
predeclared.

## Mandatory tests and dry run

Before execution, tests must prove:

- exact task/cohort/contract counts and canonical order;
- fresh unique IDs, non-empty prompts, and three repetitions;
- strict benchmark schema and duplicate-key rejection;
- expected values never enter `RuntimeRequest` or provider calls;
- all runtime request objects revalidate through released schema code;
- oracle/contract separation with wrong-but-conforming fixtures;
- actual route wrappers capture calls without changing arguments/results;
- missing control logic produces exactly 90 local and 90 remote logical calls;
- deterministic tasks make neither provider call;
- remote logical-call, attempt, and reported-cost ceilings fail closed;
- malformed, truncated, reordered, duplicated, or forged evidence rejects
  completion and analysis;
- partial/canonical files prevent overwrite or resume;
- every runtime route yields exactly one matching telemetry row;
- analysis transition totals reconcile; and
- bootstrap sampling and percentiles match fixed fixtures.

`--dry-run` uses synthetic provider results and temporary output paths. It must
exercise all 120 routes, control completion, state transitions, oracle logic,
analysis, and safety counters while making zero Ollama/OpenRouter requests and
creating zero repository canonical outputs.

## Decision rule after analysis

The analysis supports a v0.3 policy decision only within this frozen suite.
No single pass-rate threshold automatically authorizes deployment. The review
must consider final correctness, accepted errors, remote savings, latency,
reported cost, failure modes, and the paired overlap together.

Any post-result change to task contracts, prompts, normalization, or routing
belongs to a separately versioned successor experiment.
