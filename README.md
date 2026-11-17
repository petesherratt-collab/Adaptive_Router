# Adaptive Router v0.3

A small Linux terminal router for deterministic execution and remote-authoritative generative inference through OpenRouter. Ollama is retained as an opt-in, non-authoritative shadow measurement path. The runtime preserves the research instruments that established this safety boundary, and each request produces metadata-only JSONL telemetry.

## Research endpoint

The initial local-authority research cycle closed on 2026-09-22. The tested mechanisms did not establish a safe semantic boundary for serving local generative output, so runtime v0.3 remains remote-authoritative and no promotion experiment is active.

See [`RESEARCH_ENDPOINT_2026-09-22.md`](RESEARCH_ENDPOINT_2026-09-22.md) for the terminal claim, decisive evidence, preserved branches and conditions for reopening.

## Fast path (developmental, started 2026-11-15)

A second line of work reopens the project with a different question: for
repeated single-step tasks, how much answer time can be removed by moving work
into verified code and racing remote models for the rest? Cost is not an
objective. Local generative authority stays closed; this line does not use it.

A `fast_path_request_v1` names a task shape (a specification plus a `solve`
signature), supplies JSON arguments and may supply examples.

- If a promoted function exists for the shape, it runs in a sandbox and no
  model is called.
- Otherwise the request is raced across `fast_path.race_models` and the first
  parseable JSON answer is returned.
- After the answer is returned, every racer's answer is collected. Unanimous
  agreement among at least `agreement_quorum` models becomes a stored example.
- Once a shape has `min_gate_examples` examples, the synthesis model is asked
  for a function from the specification alone. It never sees the examples.
- The promotion gate is execution only: a static screen, then every stored
  example must be reproduced exactly. No model judges a candidate.
- A promoted function is demoted if it raises at run time, or if a sampled
  audit race later agrees on an answer it does not reproduce.

```bash
python main.py --fast-request-json examples/fast_path_request_run_length.json
python main.py --fast-status
python evaluate_fast_path_gate.py                                   # CCC development set
python evaluate_fast_path_gate.py --bank fast_path_gold_items_v1.py # fresh set
```

Settings live in `config_fast_path.json`, separate from `config.json` because
sealed experiment runners read the latter. `fast_path_runs.jsonl` holds
metadata only. `fast_path_store/` holds specifications, example arguments,
example answers and promoted source, because the gate needs them; both are
git-ignored.

### What has been measured

Only the promotion gate, without any model call. Using the Contextual
Conclusion Capture recipe (mechanical gold, a correct reference and a plausible
single-bug variant per item), the gate was shown k of an item's tests and the
share of k-subsets that let the buggy variant through was recorded:

| Examples shown | CCC development set (16 items) | Fresh set (28 items) |
|---:|---:|---:|
| 1 | 50.5% | 66.5% |
| 2 | 21.2% | 42.4% |
| 3 | 3.8% | 25.7% |
| 4 | 0.0% | 14.5% |
| 6 | n/a | 3.0% |
| 8 | n/a | 0.0% |

The gate never rejected a reference implementation. The right-hand end of each
column is zero by construction, because every buggy variant fails at least one
test of its full set. The usable reading is the slope: acceptance of a wrong
function falls only as fast as inputs that expose the fault arrive. In the
fresh set roughly one test in three exposes the bug; ordinary traffic may
expose it far less often. The checked-in `min_gate_examples` of 8 and the
post-promotion audit follow from that, and neither is a validated threshold.

### Development gold run (2026-11-16, not frozen, not citable)

`run_fast_path_gold.py` was run once against the draft fresh bank: 28 items,
251 test cases, five models, no retries. Observations are in
`fast_path_gold_dev_run_v1.jsonl`. The 251 cases are 28 task clusters, not 251
independent tasks.

| Model | Wrong or unusable | Of which unparseable or empty | Median ms |
|---|---:|---:|---:|
| `openai/gpt-5.6-luna` | 3/251 | 0 | 1049 |
| `openai/gpt-6-luna` | 3/251 | 0 | 2135 |
| `google/gemini-3.8-flash` | 5/251 | 5 | 2407 |
| `deepseek/deepseek-v4.1-flash` | 10/251 | 9 | 832 |
| `anthropic/claude-haiku-5.5` | 84/251 | 77 | 799 |

- All valid answers agreed on 240 cases and every one of those was correct.
  The other 11 cases had a dissenting answer. Some pairs of models agreed on a
  wrong answer once; no case had every valid answer wrong.
- Taking the fastest parseable answer per case from the recorded latencies
  gives a median of 716 ms and one wrong answer in 251. This is a replay of
  separately recorded calls, not a run of the router.
- The synthesis model wrote a gold-correct function for 27 of 28 items
  (median 3.7 s per function). The one failure omitted an import and fails
  every example, so the gate rejects it.
- Most `claude-haiku-5.5` failures are format: it wrapped or explained the
  answer despite the instruction. The answer prompt has not been tuned.

After that run the answer prompt was changed to require a final `ANSWER:` line
and the answer token limit was raised to 1024. Tuned on the vendored CCC items
only, unusable answers there fell from 7 of 300 to 0 of 300
(`fast_path_prompt_dev_ccc_before.jsonl`, `fast_path_prompt_dev_ccc_after.jsonl`).
The fresh bank was not re-run with the new prompt.

### Timing V1 primary result (2026-11-16)

The frozen three-arm experiment in
[`FAST_PATH_TIMING_V1_PLAN.md`](FAST_PATH_TIMING_V1_PLAN.md) completed once:
30 task shapes, 30 requests each, every request served by all three arms.
Decision under the frozen criteria: `SUPPORTED`.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. Direct `openai/gpt-5.6-luna` | 824/900 | 1198 | 3205 | 1651 |
| B. Race only | 884/900 | 864 | 1125 | 891 |
| C. Fast path | 892/900 | 30 | 961 | 290 |

- Time: median C over median A was 0.025 (95% interval 0.024 to 0.027);
  the criterion was an interval wholly below 0.5.
- Correctness: C minus A was +7.6 points (95% interval +3.8 to +11.9); the
  criterion was an interval wholly above -2 points.
- All 30 shapes were promoted, at a median request index of 7. Every promoted
  function was gold-correct on the hand-written tests and the full stream.
  629 of 900 fast-path requests were served by code (median 27 ms), none wrong.
- No stored example was wrong, and no function was demoted.
- The 8 wrong fast-path answers all came from the model race before promotion.

Read the result with its limits. The 900 requests are 30 task clusters. The
tasks are short pure functions written for the experiment, and the benchmark
was not reviewed by the owner before the freeze. Background learning was
allowed to finish between requests of a shape, the favourable case; it took
about 1,170 s in total against 261 s of answer time. The median reflects a
30-request stream in which promotion arrives by about the eighth request; a
shorter stream, or tasks no function can capture, would not show it. Nothing
here concerns one-off tasks, natural workloads or multi-step work.

Evidence: `fast_path_timing_v1_primary.jsonl`,
`fast_path_timing_v1_primary_analysis.json`.

### Sensitivity: no pause for learning (descriptive)

The same benchmark was run again with `--arrival immediate`: the next request
of a shape is issued without waiting for learning to finish. This reuses a
seen benchmark, so it is descriptive and not a second prospective result.

| | Primary (learning drained) | Immediate arrival |
|---|---:|---:|
| Fast-path median ms | 30 | 33 |
| Fast-path mean ms | 290 | 337 |
| Fast-path correct | 892/900 | 892/900 |
| Requests served by code | 629 | 573 |
| First code-served request, median index | 8 | 10 |
| First code-served request, latest index | 17 | 19 |
| Direct arm median ms | 1198 | 1233 |
| Direct arm correct | 824/900 | 815/900 |

All 30 shapes were still promoted on the first attempt, with no wrong
function, no wrong stored example and no demotion. Removing the pause delayed
the first code-served answer by about two requests. The median gap between
consecutive fast-path requests of a shape was 2.2 s (10th percentile 0 s, 90th
4.8 s), set by the other two arms taking their turns; faster arrival than that
is untested. The direct arm returned no answer on 22 requests in this run.

Evidence: `fast_path_timing_v1_arrival_immediate.jsonl`,
`fast_path_timing_v1_arrival_immediate_analysis.json`.

### Sensitivity: promotion after 4 examples (descriptive)

A first attempt at `min_gate_examples=4` is invalid: the provider account ran
out of credits partway through. See
[`FAST_PATH_TIMING_V1_GATE4_EXECUTION_INCIDENT.md`](FAST_PATH_TIMING_V1_GATE4_EXECUTION_INCIDENT.md).
The runner now records provider errors and stops on sustained failure. The
run was repeated in full with no provider failure affecting any request.

| | 8 examples (primary) | 4 examples (rerun) |
|---|---:|---:|
| Fast-path median ms | 30 | 31 |
| Fast-path mean ms | 290 | 158 |
| Fast-path 90th pct ms | 961 | 779 |
| Fast-path correct | 892/900 | 895/900 |
| Requests served by code | 629 | 768 |
| First code-served request, median index | 8 | 4 |
| First code-served request, latest index | 17 | 8 |
| Gold-wrong promoted functions | 0 | 0 |
| Wrong code-served answers | 0 | 0 |

Halving the gate did not admit a wrong function on this benchmark: all 30
shapes were promoted on the first attempt and every function was gold-correct.
That is weak evidence about the gate, because the synthesis model wrote no
wrong function for the gate to catch. The offline gate measurement above
still says four examples pass a deliberately buggy variant about one time in
seven. Descriptive only, on a benchmark already used.

Evidence: `fast_path_timing_v1_gate4_rerun.jsonl`,
`fast_path_timing_v1_gate4_rerun_analysis.json`.

### Timing V2: harder task shapes (prospective, 2026-11-16)

[`FAST_PATH_TIMING_V2_HARD_PLAN.md`](FAST_PATH_TIMING_V2_HARD_PLAN.md) froze
one run on 20 new shapes chosen to be easy to implement subtly wrong, under
the V1 rules and criteria. Decision: `SUPPORTED`.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. Direct `openai/gpt-5.6-luna` | 571/600 | 2964 | 4951 | 2987 |
| B. Race only | 593/600 | 1161 | 2157 | 1344 |
| C. Fast path | 598/600 | 32 | 1660 | 458 |

- Time ratio C/A 0.011 (95% interval 0.009 to 0.015). Correctness C minus A
  +4.5 points (interval +2.0 to +7.5).
- All 20 shapes were promoted; 418 of 600 fast-path requests were served by
  code, none wrong. No stored example was wrong. No function was demoted.
- One first synthesis attempt (`eval_expression`) was a syntax error and was
  rejected statically; the second attempt was correct.
- **One promoted function is wrong.** The `number_to_words` function returns
  an empty string for 0 instead of 'zero'. It agrees with the reference on
  the other 9,999 inputs in range, passed the gate on 8 examples, and served
  22 correct answers because 0 never arrived. By the plan's definition this
  is not a gate failure, since no wrong answer was served, but it is the
  failure mode the offline gate measurement predicted: a fault is caught only
  when an input that exposes it arrives, and the audit can only see inputs
  that do arrive.

The shapes were selected to be error-prone and the benchmark was not reviewed
by the owner before the freeze. 20 task clusters.

Evidence: `fast_path_timing_v2_hard_primary.jsonl`,
`fast_path_timing_v2_hard_primary_analysis.json`.

### Boundary probing before promotion (descriptive)

The V2 run promoted a function with a fault no arriving input exposed. With
`probe_enabled`, a probe model (a different vendor from the synthesis model)
proposes up to `max_probes` boundary inputs from the specification alone, all
race models answer each one, and unanimous answers become examples the gate
must reproduce. The proposer never sees examples. A probe step that fails does
not block synthesis.

Measured on the 44 development items that have a known single-bug variant,
using probe examples alone (`fast_path_probe_eval_v2.jsonl`):

| | Count |
|---|---:|
| Probes proposed / unanimously answered | 516 / 502 |
| Buggy variants rejected | 42 of 44 |
| Buggy variant accepted: probes did not expose the fault | 1 (`longest_common_prefix`) |
| Buggy variant accepted: probe reply unusable, nothing tested | 1 (`transpose`) |
| References rejected | 1 (`caesar_decode`) |

- The recorded wrong `number_to_words` function from V2 is rejected: the first
  proposed probe was 0 (`fast_path_probe_case_number_to_words_result.jsonl`).
- The `caesar_decode` rejection is the reference's own doing. The
  specification says the shift applies to lowercase letters; the probe
  'ABCxyz' drew the unanimous answer 'ABCuvw', while the vendored reference
  shifts uppercase letters as well and returns 'rstuvw'. The bank's own tests
  contain no uppercase input, so its gold labels are unaffected.
- An earlier run (`fast_path_probe_eval_v1.jsonl`) is invalid as a
  measurement: 18 of 44 probe replies were truncated by a 1,024-token limit.
  The limit is now 4,096 and an unparseable probe reply is retried once.

End to end on the harder benchmark with probing enabled
(`fast_path_timing_v2_hard_probes.jsonl`, descriptive, benchmark already
seen): all 20 shapes were promoted on the first attempt against 18 to 20
examples each, at the same request index as before (median 7, latest 12).
Every promoted function was gold-correct, including `number_to_words`. Of 240
probes proposed, 234 were answered unanimously and every one of those matched
the reference. Fast-path answers: 598/600 correct, median 33 ms, 425 served by
code. Background work rose from about 1,170 s to about 1,440 s. In this run
the synthesis model wrote no wrong function, so the probes rejected nothing;
the evidence that they reject a wrong one is the replay above.

Both banks were already development evidence, so these figures are
descriptive. Probing depends on the models answering edge cases correctly and
unanimously; a unanimous wrong answer would block a correct function.

### Multi-step jobs (developmental, 2026-11-16)

`pipeline.py` runs a caller-declared plan over the fast path. A
`fast_path_job_v1` document names its inputs, lists steps and names one
output. A step's arguments are literal values, job inputs or results of
earlier steps. The orchestrator is plain code and makes no model call of its
own; per step it only looks up whether promoted code exists.

- `function` steps are fully determined by their specification. They learn
  and may be promoted to code.
- `judgement` steps need a model's reading of the input. They are always
  raced and are never stored, synthesised or promoted.
- Steps whose arguments are all available run concurrently. A step may refer
  only to inputs and earlier steps, so a plan cannot contain a cycle.
- If a step returns no answer the job fails, dependants are not started, and
  no partial answer is returned.

```bash
python main.py --job-json examples/fast_path_job_ticket_triage.json
```

Probes can now be fetched before enough traffic has arrived
(`probe_after_examples`, 3) and their answers count toward
`min_gate_examples`. Without this a function with a small input domain, such
as a rule over three tones and four categories, never accumulated eight
distinct examples.

One live demonstration, not a measurement: the ticket-triage example (two
judgement steps, three function steps) was run on 16 hand-written messages
against the five-model roster. The first three jobs took 2.3 to 2.8 s with
every step on the model race. All three function steps were promoted after the
third job, and the remaining thirteen took 0.86 to 1.66 s (median about 1.0 s),
which is the time of the two judgement steps running side by side. No gold
labels were defined, so nothing is claimed about correctness, and no
comparison with a single whole-job model call was made.

### Jobs V1: multi-step jobs (prospective, 2026-11-16)

[`FAST_PATH_JOBS_V1_PLAN.md`](FAST_PATH_JOBS_V1_PLAN.md) froze one four-arm
run on 12 mixed job shapes, 20 jobs each. Decision under the frozen criteria:
`NOT_SUPPORTED`. The correctness criterion was met; the time criterion was not.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct whole-job call | 234/240 | 2218 | 3238 | 2269 |
| R. Whole-job race | 238/240 | 1233 | 1576 | 1240 |
| B. Step pipeline, race only | 238/240 | 2616 | 3339 | 2614 |
| C. Step pipeline, fast path | 240/240 | 1115 | 2433 | 1402 |

- Primary, C against A: time ratio 0.50, 95% interval 0.42 to 0.78. The
  criterion required the interval wholly below 0.75. Correctness +2.5 points,
  interval 0.0 to +5.4.
- C against R: time ratio 0.90, interval 0.80 to 1.28; correctness +0.8
  points. On this workload the step pipeline is not distinguishable in speed
  from simply racing the whole job, and it is slower in the mean.
- B against A: time ratio 1.18. Splitting a job into steps without code makes
  it slower than one direct call.
- Every judgement step was answered correctly in both pipeline arms, and none
  was stored. All four wrong step answers in arm B were function steps
  answered by a model; arm C had no wrong step.
- 27 of 29 function steps were promoted, all gold-correct, no wrong stored
  example, no demotion. Two were never promoted: `store_aisle.aisle` and
  `greeting.hello` have three and four possible inputs, so they could not
  reach eight distinct examples even with probes. Those two shapes, and
  `dial_code` with its two judgement steps in sequence, ran at about 1.7 s.

What this supports: a step pipeline is worth having only where code replaces
model calls, and its floor is the time of its slowest chain of judgement
steps. Against a single model it roughly halved job time and made no errors.
Against a whole-job race it bought little. The judgement texts were short and
unambiguous, the jobs small, learning was drained between jobs, and there are
12 task clusters.

Evidence: `fast_path_jobs_v1_primary.jsonl`,
`fast_path_jobs_v1_primary_analysis.json`.

### Jobs V1 rerun with the saturation rule (descriptive, 2026-11-17)

Two lookup steps in jobs V1 could never be promoted because their whole input
domain (three and four values) was smaller than `min_gate_examples`. With
`saturation_window` 5 and `saturation_min_examples` 2, a step whose last five
agreed inputs were all already known may be promoted on fewer examples; the
gate still requires every stored example. Same benchmark, rerun, descriptive.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct whole-job call | 233/240 | 2205 | 3187 | 2269 |
| R. Whole-job race | 239/240 | 1071 | 1372 | 1090 |
| B. Step pipeline, race only | 240/240 | 2266 | 2914 | 2282 |
| C. Step pipeline, fast path | 240/240 | 963 | 2081 | 1204 |

- `store_aisle.aisle` and `greeting.hello` were promoted under the saturation
  rule on 3 and 4 examples, both gold-correct. Those shapes' arm-C medians fell
  from 1714 and 1844 ms to 930 and 1267 ms.
- C against A: time ratio 0.44 (interval 0.38 to 0.57). Under the V1 plan's
  criteria this would pass, but the run is descriptive and does not replace
  the frozen result.
- C against R: time ratio 0.90 (interval 0.80 to 1.30), correctness +0.4
  points. Still not distinguishable from the whole-job race.
- **A unanimous wrong probe answer blocked a correct function.** In
  `shipping_estimate.zone`, all five models agreed on an answer to one probe
  input that the reference contradicts. Both synthesised functions matched 12
  of 13 examples and were rejected, so the step was never promoted. The input
  was not recorded; the runner now records wrong examples in full. This is the
  false-rejection risk of probing observed for the first time.

Evidence: `fast_path_jobs_v1_saturation.jsonl`,
`fast_path_jobs_v1_saturation_analysis.json`.

### Jobs V2: larger jobs (prospective, 2026-11-17)

[`FAST_PATH_JOBS_V2_LARGE_PLAN.md`](FAST_PATH_JOBS_V2_LARGE_PLAN.md) froze one
four-arm run on 7 job shapes of 7 steps each, 15 jobs per shape, with long
structured inputs, judging the pipeline against the whole-job race. Decision:
`SUPPORTED`.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct whole-job call | 99/105 | 3786 | 5642 | 3969 |
| R. Whole-job race | 105/105 | 2791 | 3504 | 2800 |
| B. Step pipeline, race only | 104/105 | 5317 | 7573 | 5531 |
| C. Step pipeline, fast path | 105/105 | 1129 | 5314 | 2155 |

- Primary, C against R: time ratio 0.41 (95% interval 0.34 to 0.88), wholly
  below 1.0. Correctness difference 0.0 (both 105/105).
- C against A: time ratio 0.30 (0.23 to 0.66); correctness +5.7 points.
- B against A: 1.41. Decomposition without code remains a cost, larger here
  because there are more steps.
- After the fifth job of each shape, medians were A 3577, R 2711, B 5302,
  C 1020 ms.
- Arm C made no wrong step: 459 function steps on code (median 31 ms), 156 on
  the race, 120 judgement steps, all correct. No judgement step was stored.
- 39 of 41 function steps were promoted. Not promoted:
  `thread_digest.span`, where the gate rejected both synthesised functions
  (3 of 15 and 3 of 16 examples matched), and `stock_reorder.order_line`,
  where the five models agreed unanimously on only one answer in fifteen jobs,
  so it never had enough examples. That shape stayed at 2.7 s.
- One promoted function is counted gold-wrong: `log_triage.worst`. It is
  correct on every request input but fails the benchmark's own hand-written
  tests, which use lines like '1 ERROR b: x' that do not follow the
  specification's 'HH:MM:SS' format. This is a flaw in the tests, not in the
  function.
- Three stored probe examples contradict the reference. In each, the probe
  input lies where the reference is weaker than the specification or the
  specification is silent: a negative total (the reference's euro formatting
  is wrong below zero), a quoted CSV field, and a name containing a hyphen.
  None blocked a promotion and none lies in the request stream.

Limits: 7 task clusters; constructed jobs with unambiguous judgement texts;
learning drained between jobs; benchmark not owner-reviewed before the freeze.

Evidence: `fast_path_jobs_v2_large_primary.jsonl`,
`fast_path_jobs_v2_large_primary_analysis.json`.

The sandbox (separate process, stripped builtins, module allowlist, resource
limits, best-effort network namespace) guards against accidents. It is not a
hardened boundary against adversarial code.

## Prospective deterministic-contract case study

A prospectively frozen experiment across Gemma 3 270M, 1B, and 4B found that
deterministic output contracts caught 144 of 175 false accepts admitted by the
legacy gate: 82.3%, with a task-cluster bootstrap 95% interval of 63.9%–96.7%.
No baseline-correct survivor was rejected. A separate label cohort demonstrates
the semantic boundary, while deterministic execution identifies work that
should bypass the model entirely.

Read the illustrated
[prospective contract validation V2 case study](PROSPECTIVE_CONTRACT_VALIDATION_V2_CASE_STUDY.md)
for the methodology, results, limitations, experiment lineage, and
reproducibility references.

## Out-of-sample case study

The first frozen out-of-sample validation rejected the current fine-grained
routing policy. Fine capability routing used 100 rather than 200 remote calls
and achieved 85.5% strict accuracy, outperforming coarse routing at 78.5%, but
fell 14.5 percentage points below always remote. The preregistered tolerance
allowed a maximum five-point loss.

Read the illustrated [`CASE_STUDY.md`](CASE_STUDY.md) for the research question,
method, negative result, limitations, and proposed accuracy–remote-capacity
experiments. The complete frozen result and procedural deviations remain in
[`OOS_VALIDATION_V1_AUDIT.md`](OOS_VALIDATION_V1_AUDIT.md).

## What this project does

It measures RAM, swap, load, time to first output, generation throughput, adapter failures, and task-specific deterministic validation. Classification is a small ruleset, not a difficulty estimate. Every gate has a stable reason code and no opaque score. Direct observations, deterministic derivations, and interpretations are kept separate.

## What it does not claim

It does not detect intelligence, directly measure semantic difficulty, guarantee answer correctness, infer model confidence, use an LLM judge, prove latency predicts correctness, or assume the SHA probe is useful. A normal, fast response can still be semantically wrong when no validator applies; that unresolved failure mode is intentionally visible.

Deterministic validators are task-specific. For many open-ended question-answering tasks no defensible generic deterministic correctness validator is currently implemented.

Probe latency remains observational in v0.3. It does not influence routing decisions, and its predictive value has not been established.

Routing statistics must display both sample size and uncertainty. Categories with fewer than 30 observations are not treated as established evidence.

## Setup

Requires Python 3.11+. Ollama and its configured model are optional for tests but required for live local routing. This project does not install or download a model.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENROUTER_API_KEY` only in `.env`; do not commit `.env`. The checked-in remote default is `openai/gpt-5.6-luna`, the model used by the measured paired replay. Model names, retry limits, and routing thresholds in `config.json` are explicit operating settings, not scientific constants.

## Usage

```bash
python main.py
python main.py --prompt "Rewrite this paragraph..."
python main.py --request-json examples/runtime_request_deterministic.json
python main.py --request-json examples/runtime_request_structured_json.json
python main.py --request-json examples/runtime_request_classification.json
python main.py --diagnostics
python main.py --stats
python -m unittest discover -s tests -v
```

## Explicit runtime requests

`--request-json` accepts a strict `runtime_request_v1` document. The caller
declares a task class, the prompt, and one contract. Supported behavior is:

- `deterministic_executor`: execute one allowlisted operation in Python; call
  neither Ollama nor OpenRouter.
- `structured_json`, `json_format`, `bullet_format`, and
  `label_format`: route to OpenRouter and enforce the declared output shape
  on the final response.
- `classification_labels`: route to OpenRouter and enforce permitted-label
  membership, which cannot establish semantic correctness.

A malformed request is rejected before either provider is called. A valid
contract describes observable conformance, not truth: correctly typed JSON can
still contain wrong values. OpenRouter receives the original caller prompt; local shadow output is never
used as repair context or returned to the caller. A successful remote transport
response is checked against the declared contract; a nonconforming final
response is withheld and recorded as
`REMOTE_CONTRACT_FAILED`. OpenRouter retries are bounded and apply only to
timeouts, connection failures, HTTP 408/429, and HTTP 5xx. Authentication and
other client errors, plus malformed success responses, are not retried.

See the checked-in examples under `examples/`.

Prompts, answers, and contract source literals are not logged. `runs.jsonl` contains request mode, contract type, task class, input size, system/runtime measurements, local and remote validator states, route/reason, total route latency, deterministic shadow selection, and the Ollama-reported residency of the configured local model. When Ollama supplies it, the loaded model size is recorded in bytes. Shadow execution defaults off. When explicitly enabled, an eligible sampled
request is measured locally after the authoritative remote call; only
metadata and conformance status are logged. Shadow text is neither logged nor
returned, and a shadow failure cannot alter or withhold the remote result.

Rolling seven-day medians exclude hard-health rejections and local errors. They and Wilson 95% intervals are reported only as evidence; v0.3 never tunes or routes from aggregate statistics. Fewer than the configured 30 suitable observations produces `INSUFFICIENT_BASELINE_DATA` or `INSUFFICIENT_EVIDENCE`.

## Current safe policy

Deterministic executor requests bypass both models. Every generative request,
including legacy prompts and all generative contract types, is
remote-authoritative by default. `classification_labels` remains explicitly
remote-only because label membership is not semantic validation.

The checked-in `routing.allow_user_visible_local` setting is `false`. The old
local-first implementation remains behind that explicit operator override for
controlled comparison and rollback, but it is not the shipped policy.
`SAFE_REMOTE_POLICY` records requests kept remote by this boundary.

Optional local shadow execution requires `shadow.enabled` and
`shadow.execute`, plus deterministic sampling. It runs synchronously after the
remote result is fixed, so enabling it adds measurement latency. It never
changes the user-visible answer.

Before any local execution, the router checks Ollama's local `/api/ps`
endpoint. The minimum-available-RAM gate applies only when the configured model
is not resident. Swap occupancy is logged but does not reject local inference
by itself; swap-out activity observed during the fixed 0.1-second preflight
sampling window does. If residency cannot be confirmed, the router
conservatively treats the model as not resident.

## Current product direction

Runtime health signals and output contracts remain operational or conformance
checks, not correctness estimates. The prospective v0.2 runtime evaluation
produced 117/120 correct outputs overall and 87/90 on generative tasks. It
avoided 21 remote calls but accepted three repeated bullet-content errors;
the paired remote arm was correct on all 90 generative observations.

v0.3 therefore converts that measured result into a product boundary:
deterministic work executes in code, generative work is remote-authoritative,
and local candidates must be measured in shadow before any narrower capability
can earn user-visible authority.
