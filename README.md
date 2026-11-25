# Adaptive Router v0.3

A small Linux terminal router for deterministic execution and remote-authoritative generative inference through OpenRouter. Ollama is retained as an opt-in, non-authoritative shadow measurement path. The runtime preserves the research instruments that established this safety boundary, and each request produces metadata-only JSONL telemetry.

## Research endpoint

The initial local-authority research cycle closed on 2026-09-22. The tested mechanisms did not establish a safe semantic boundary for serving local generative output, so runtime v0.3 remains remote-authoritative and no promotion experiment is active.

See [`RESEARCH_ENDPOINT_2026-09-22.md`](RESEARCH_ENDPOINT_2026-09-22.md) for the terminal claim, decisive evidence, preserved branches and conditions for reopening.

## Fast path (developmental, started 2026-11-15)

**Summary of findings to 2026-11-25: [`FINDINGS_2026-11-25.md`](FINDINGS_2026-11-25.md).**

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

### Planned jobs V1: the router writes its own plans (descriptive, 2026-11-17)

[`FAST_PATH_PLANNED_V1_PLAN.md`](FAST_PATH_PLANNED_V1_PLAN.md) froze one run in
which each job arrives as a plain-language task with no step plan. The router
races the whole task until it has three agreed answers, has a planner model
write a step plan, and adopts the plan only if it reproduces those answers.
The jobs are those of jobs V2, so the run is descriptive. Decision under its
criteria: `NOT_SUPPORTED`, narrowly on time.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct call | 96/105 | 3823 | 5867 | 3962 |
| R. Whole-task race | 103/105 | 2528 | 3152 | 2504 |
| C. Planning router | 105/105 | 1986 | 3138 | 1999 |

- C against R: time ratio 0.79, 95% interval 0.47 to 1.00; the criterion
  required the interval wholly below 1.0. Correctness +1.9 points, interval
  0.0 to +3.8. The planning router made no wrong answer.
- Six of seven task shapes got an adopted plan, from the fourth or fifth job.
  On the 69 jobs served by a plan the median was 1553 ms, against 2422 ms for
  the race over the same jobs.
- Plans were checked by execution and two wrong ones were caught: one
  reproduced 1 of 3 agreed answers, another 0 of 3. Both shapes adopted a
  correct plan on the second attempt.
- `order_batch` never got a plan: both planner replies were refused by the
  plan validator for a malformed step signature, and that shape stayed on the
  race. The plan text was not kept, so whether the plans were otherwise sound
  is unknown.
- The planner wrote 26 steps in all, 19 function and 7 judgement. Every
  judgement step read prose (tone, topic, intent, language); 16 function steps
  were promoted to code. No plan was dropped by the audit.

Evidence: `fast_path_planned_v1.jsonl`, `fast_path_planned_v1_analysis.json`.

A second descriptive run applied two fixes: the plan validator tidies minor
signature slips and returns a refusal to the planner for one retry, and plans
are written after two agreed answers instead of three. Decision: still
`NOT_SUPPORTED` on time.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct call | 101/105 | 3736 | 6011 | 3941 |
| R. Whole-task race | 102/105 | 2391 | 3077 | 2419 |
| C. Planning router | 103/105 | 2009 | 3532 | 2249 |

- C against R: time ratio 0.84 (interval 0.72 to 1.09), correctness +1.0
  point (interval -1.9 to +3.8). Not better than the first run's 0.79.
- All seven shapes got a plan, every one on its first attempt, and plans now
  served from the third or fourth job: 88 of 105 jobs ran on a plan.
- The validator fix was never exercised: no plan was refused in this run.
  `order_batch` got a plan because the planner happened to write a valid one.
- The plans were coarser: 16 function steps in place of 19, several of them
  large ("parse every line and compute all the statistics", "format the whole
  result"), and only 12 promoted by the end. 80 function-step executions still
  went to the models, against 36 in the first run. Plan-served jobs had a
  median of 1862 ms, against 1553 ms before.
- Two wrong answers in arm C: one whole-task race answer before any plan
  (the same kind of error arm R made), and one plan job whose final formatting
  step, still on the models, returned null. The audit then dropped that plan,
  and a second plan for the shape was adopted.

The two runs together say that a model-written plan can be verified and used
safely, but how much it speeds a job up depends on how the planner happens to
split the work, which varied between runs more than either fix changed it.

Evidence: `fast_path_planned_v1_fixes.jsonl`,
`fast_path_planned_v1_fixes_analysis.json`.

A third descriptive run steered the planner toward small function steps that
return simple values, and added speed feedback: after a plan has served four
jobs, the planner is told which of its function steps became code and which
are still answered by models, and asked to split the slow ones. A revision is
adopted only if it passes the same trial. Decision: `NOT_SUPPORTED` on the
interval, but the clearest speed result of the three runs.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct call | 95/105 | 3675 | 5783 | 3904 |
| R. Whole-task race | 104/105 | 2429 | 3014 | 2435 |
| C. Planning router | 105/105 | 1370 | 4352 | 2225 |

- C against R: time ratio 0.56 (interval 0.40 to 1.09); correctness +1.0
  point (0.0 to +2.9). No wrong answer in arm C.
- Plans were much finer: 83 function steps across seven plans, against 16 to
  19 before, and 79 of them were promoted to code. 768 function-step
  executions ran as code, against 130 in the second run.
- On the last five jobs of each shape the medians were A 3723, R 2375,
  C 969 ms. Plan-served jobs had a median of 1058 ms.
- Speed feedback revised five of seven plans after four jobs; all five
  revisions passed their trial and were adopted. Their separate effect is not
  isolated: this run changed the prompt as well.
- The cost of small steps is a slow first plan job: with ten or more steps all
  still on the models, it took 4 to 8 s. `order_batch`, which ended with a
  16-step plan, three steps still on the models, stayed slower than the race
  (median 3.9 s against 2.7 s) and is what widened the interval past 1.0.
- 26 provider rate-limit responses (HTTP 429) occurred, absorbed by retries.

Evidence: `fast_path_planned_v1_steer.jsonl`,
`fast_path_planned_v1_steer_analysis.json`.

### Planned jobs V2: the router plans fresh jobs (prospective, 2026-11-17)

[`FAST_PATH_PLANNED_V2_PLAN.md`](FAST_PATH_PLANNED_V2_PLAN.md) froze one run of
the planning router, with small-step steering and speed feedback, on 7 job
shapes no model had seen, 15 jobs each, given only plain-language
descriptions. Decision: `SUPPORTED`.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct call | 98/105 | 4275 | 5954 | 4355 |
| R. Whole-task race | 102/105 | 2469 | 3472 | 2552 |
| C. Planning router | 104/105 | 1534 | 3692 | 2090 |

- C against R: time ratio 0.62 (95% interval 0.41 to 0.92), wholly below 1.0.
  Correctness +1.9 points (interval -1.9 to +6.7), above the -2 point margin.
- C against A: time ratio 0.36 (0.23 to 0.59), correctness +5.7 points.
- All 7 shapes adopted a plan. 84 of 105 jobs ran on a plan, all 84 correct,
  median 1261 ms. The one wrong answer in arm C was a whole-task race answer
  before any plan existed.
- Over the last five jobs of each shape: A 4623, R 2486, C 1063 ms.
- Plans held 74 function steps (70 promoted to code) and 7 judgement steps;
  689 function-step executions ran as code.
- Speed feedback revised 6 plans: 5 revisions passed their trial and were
  adopted, 1 (`playlist`) matched 0 of 2 agreed answers and was rejected, so
  the working plan stayed in use.
- `timesheet` was the weak shape: the five models disagreed on 5 of its first
  7 whole-task answers, so two agreed examples took until job 7 and the plan
  served only the last 8 jobs. Its arm-C median matched the race (3.4 s).

Limits: 7 task clusters; constructed jobs with unambiguous prose fields;
benchmark not owner-reviewed before the freeze; background work drained
between jobs.

Evidence: `fast_path_planned_v2_primary.jsonl`,
`fast_path_planned_v2_primary_analysis.json`.

Follow-up, descriptive: the same jobs with `job_agreement_min` 4, so a 4-of-5
majority answer can serve as a job example. Plans arrived earlier everywhere
(first plan job 3 or 4 for every shape; `timesheet` moved from job 8 to job 3),
no wrong job example was stored, and arm C answered all 105 jobs correctly.
Overall it was not faster: C/R 0.72 (interval 0.47 to 1.02), because the
`timesheet` and `playlist` plans stayed slow (3.9 s and 3.1 s medians). Over
the last five jobs of each shape: A 3908, R 2641, C 967 ms.

This run also metered every provider call per arm, background work included.
Over 105 jobs, arm A made 105 calls and arm R 525. Arm C made 8,962, and used
about 3.4 million tokens against 0.64 million for arm R: some 17 times the
calls and 5 times the tokens. Nearly all of that is learning (plan trials,
probes, step races before promotion), front-loaded in the first jobs of each
shape; with 15 jobs per shape it is not amortised. The speed-up therefore
costs compute, which cost was dropped as an objective but is real.

Evidence: `fast_path_planned_v2_majority.jsonl`,
`fast_path_planned_v2_majority_analysis.json`.

Follow-up 2, descriptive: the same jobs with the majority rule, but arriving
back to back, so background learning ran alongside live jobs instead of being
given time between them. **The planning router lost on both measures.**

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct call | 96/105 | 4074 | 5767 | 4138 |
| R. Whole-task race | 100/105 | 2579 | 3657 | 2709 |
| C. Planning router | 99/105 | 3117 | 14150 | 6058 |

- C/R 1.21 (interval 1.05 to 1.57): slower than the race. Correctness -1.0
  point (interval -8.6 to +5.7).
- Plans arrived late (job 6 to job 14; `expense_claims` never ran on one),
  because writing and checking a plan takes tens of seconds while jobs keep
  arriving. Only 36 of 78 plan function steps became code.
- Plan-served jobs had a median of 6.6 s: a plan whose steps are still answered
  by models runs them one after another, each a full model race, and is much
  slower than racing the whole task once.
- Five wrong answers came from the race route and one from a plan: the first
  wrong plan-served answer in any run (`bank_statement`, job 10).

The lesson is a design flaw, not just a slow run: the router switches a task to
its plan as soon as the plan is correct, not when it is fast. Under live
traffic that is before most steps are code. The fix to test is to keep racing
the whole task while the plan learns in the background, and switch only once
its steps run as code.

Evidence: `fast_path_planned_v2_immediate.jsonl`,
`fast_path_planned_v2_immediate_analysis.json`.

Follow-up 3, descriptive: the shadow fix, under the same back-to-back
conditions. **The fix did its narrow job and exposed a second flaw.**

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. One direct call | 98/105 | 4020 | 5420 | 4092 |
| R. Whole-task race | 101/105 | 2451 | 3380 | 2611 |
| C. Planning router | 98/105 | 2834 | 13753 | 5364 |

- No slow plan served a job: every arm-C answer came from the race. But no
  plan ever went live either. Recorded shadow runs took 6 to 43 seconds,
  against race medians of 2 to 4.5 seconds.
- Arm C's own race answers were slower than arm R's, with a 90th percentile of
  13.8 s, and the gap grew over the run (last five jobs per shape: C 7967 ms
  against R 2506 ms). The live race in arm C shares one thread pool with the
  background work (shadow runs, plan trials, probes, step races), so live calls
  queued behind background calls. The run also drew 108 rate-limit (HTTP 429)
  responses, against 7 in follow-up 2.
- C/R 1.16 (1.07 to 1.28); correctness -2.9 points (-6.7 to 0.0). All seven
  arm-C wrong answers came from the race route.

The second flaw: background learning must not compete with the answer path
for the same workers or provider capacity. A fix would give live requests
their own pool and limit background work to one shadow run per task at a
time, dropping shadow runs that would queue.

Evidence: `fast_path_planned_v2_shadow.jsonl`,
`fast_path_planned_v2_shadow_analysis.json`.

Follow-up 4, descriptive: a ceiling arm D, specified by the owner before the
run. D stands for a programmer having already written the job: the benchmark's
reference code does the mechanical work and only the reading step goes to
models, raced exactly as arm C races its judgement steps. D's mechanical work
is correct by definition, so **its accuracy says nothing about code against
models**; only its time and its reading accuracy inform. Drained arrival, as in
the frozen run.

| Arm | Correct | Median ms | 90th pct ms | Mean ms | Model calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| A. One direct call | 96/105 | 3891 | 5585 | 4042 | 105 | 78,759 |
| R. Whole-task race | 98/105 | 2360 | 3502 | 2486 | 525 | 643,665 |
| C. Planning router | 104/105 | 2146 | 4257 | 2519 | 8,182 | 3,123,268 |
| D. Ceiling | 105/105 | 834 | 1043 | 846 | 525 | 110,195 |

- D's reading steps were right on all 105 jobs. On these unambiguous texts the
  reading is not where the ceiling loses anything.
- C took 2.57 times D's median time (interval 1.59 to 3.53). Over each
  shape's first three jobs, C 2533 ms against D 834 ms; over the later jobs,
  1956 against 838; over the last five, 1198 against 870. Once learned, the
  planning router gets within about 1.4 times the ceiling.
- The price of not having a programmer: C made 16 times D's calls and used 28
  times its tokens, nearly all of it learning.
- **The re-run of arm C, under the same settings as the frozen fresh-jobs run,
  was not as fast:** C/R 0.91 (interval 0.54 to 1.25) against 0.62 in the
  frozen run. With seven task shapes, run-to-run variation is large, and the
  frozen run's margin should be read with that in mind.

This does not test the rule that a model-based approach must beat ordinary
code; that needs keyword rules for the reading steps, written before the text
is seen, and is reserved for the owner's real tasks.

Evidence: `fast_path_planned_v2_ceiling.jsonl`,
`fast_path_planned_v2_ceiling_analysis.json`.

Follow-up 5, descriptive: the two isolation fixes (separate live and
background model pools, one shadow run per task at a time) under the
back-to-back conditions of follow-up 3, with the ceiling arm for reference.

| Arm | Correct | Median ms | 90th pct ms | Model calls |
|---|---:|---:|---:|---:|
| A. One direct call | 102/105 | 3620 | 5042 | 105 |
| R. Whole-task race | 101/105 | 2448 | 3366 | 525 |
| C. Planning router | 103/105 | 2432 | 3405 | 5,505 |
| D. Ceiling | 105/105 | 838 | 1060 | 525 |

- **The isolation fix worked.** Arm C's answers, all from the race, took the
  same time as arm R's (median 2432 against 2448 ms; C/R 0.99, interval 0.96
  to 1.08) and no longer slowed down as the run went on (last five jobs: 2386
  against 2432 ms). In follow-up 3 they reached 7967 ms. No HTTP 429 responses.
- **No plan went live.** Every shape adopted a plan into shadow mode, but only
  six shadow runs finished across all seven shapes, taking 4.9 to 47 s each.
  With jobs back to back, each shape's 15 jobs pass in about two minutes,
  while a plan's learning (probes, synthesis and step races for about ten
  function steps) takes longer than that.
- So under live traffic the planning router is now safe (never slower than
  the race, no wrong plan answer) but gains nothing within 15 jobs. A speed-up
  would need longer streams of the same job, or cheaper learning: fewer
  probes, fewer racers for step examples.

Evidence: `fast_path_planned_v2_isolated.jsonl`,
`fast_path_planned_v2_isolated_analysis.json`.

Follow-up 6, descriptive: a longer stream with cheaper learning, jobs back
to back: four shapes, 40 jobs each, edge-case probes cut from 12 to 4 per
step, everything else as follow-up 5. **Plans went live under steady traffic
for three of the four shapes.**

| Arm | Correct | Median ms | 90th pct ms | Model calls | Tokens |
|---|---:|---:|---:|---:|---:|
| A. One direct call | 143/160 | 4014 | 6108 | 160 | 128,987 |
| R. Whole-task race | 149/160 | 2755 | 3739 | 800 | 1,054,178 |
| C. Planning router | 151/160 | 2239 | 3502 | 5,265 | 2,673,113 |
| D. Ceiling | 160/160 | 836 | 1057 | 800 | 171,737 |

- Plans went live at job 20 (`timesheet`), 25 (`survey_scores`) and 34
  (`shipment_tracking`). From that point on, arm C's medians were 1678, 1789
  and 845 ms against the race's 3110, 3261 and 1900 ms. `expense_claims` never
  went live: three of its twenty function steps stayed on the models, so its
  shadow runs (about 3 to 5 s) never beat three-quarters of the race.
- Before going live, arm C's answers came from the race, as intended.
- C/R 0.81 over all 160 jobs (interval 0.70 to 1.00, four task clusters).
- One plan-served answer was wrong (`survey_scores`, job 34); eight wrong
  answers came from the race route, as in arm R.
- Cheaper learning narrowed the price: arm C made 6.6 times the race's calls
  and 2.5 times its tokens, against 17 and 5 times in the majority run.

Evidence: `fast_path_planned_v2_long.jsonl`,
`fast_path_planned_v2_long_analysis.json`.

Follow-up 7, descriptive (2026-11-17, handoff item 1): cheaper learning by
asking fewer models. Same jobs and settings as follow-up 6, plus a learning
roster: function steps learned in the background (step races in plan trials
and shadow runs, and probe answers) ask two models,
`google/gemini-3.8-flash` and `openai/gpt-5.6-luna`, instead of five; an
example still needs both to agree. Live answers and judgement steps keep all
five. The pair was the most often agreeing pair from different providers in
the development data. Calls are now metered by purpose.

| Arm | Correct | Median ms | Model calls | Tokens |
|---|---:|---:|---:|---:|
| A. One direct call | 143/160 | 3631 | 160 | 128,583 |
| R. Whole-task race | 148/160 | 2830 | 800 | 1,053,611 |
| C. Planning router | 148/160 | 2759 | 3,106 | 2,051,539 |
| D. Ceiling | 160/160 | 854 | 800 | 171,024 |

- **Learning calls fell by about half**: about 2,390, against an estimated
  4,660 in follow-up 6 (which did not meter purposes; its 116 race-routed jobs
  and a few audits account for about 600 whole-task calls of its 5,265). Of arm C's calls, 720 were whole-task races, 2,217
  step and probe answers, 85 syntheses, 74 probe proposals and 10 plans.
- **Neither time nor money improved.** Plans went live for two shapes, not
  three: `expense_claims` (job 31, which never went live in follow-up 6) and
  `survey_scores` (job 35). `shipment_tracking` stayed in shadow with one step of
  26 unpromoted; `timesheet` lost its plan to a shadow mismatch. C/R 0.97
  (interval 0.94 to 1.03). The run cost about $4.45 against $4.15, because the
  learning pair includes the roster's most expensive model per token.
- Which plans the planner writes, and whether one step resists promotion,
  varied more between follow-ups 6 and 7 than anything the roster changed. A
  pair chosen for price (`openai/gpt-6-luna` with `deepseek/deepseek-v4.1-flash`)
  is untested.

Evidence: `fast_path_planned_v2_lean.jsonl`,
`fast_path_planned_v2_lean_analysis.json`.

### Planned jobs V3: fresh, more varied jobs and a code-only arm (prospective, 2026-11-17)

Eight new job shapes (`fast_path_planned_bench_v3.py`), with more varied inputs
(text lines, JSON arrays of numbers and objects, dates) and eight different
readings (urgency, department, diet, vehicle issue, library request, site,
delivery country, formality). A fifth arm, **E, uses no model at all**: keyword
rules read the prose and the reference code does the rest. To make that fair,
the rules (`fast_path_code_only_v1.py`) were written from the task descriptions
and their hash recorded **before the texts existed**. The texts were then
written by a model outside the roster (`mistralai/mistral-large-4-0`) and
hand-checked against their labels. Plan: `FAST_PATH_PLANNED_V3_PLAN.md`.

| Arm | Correct | Median ms | Last five per shape, ms | Model calls |
|---|---:|---:|---:|---:|
| A. One direct call | 153/160 | 3086 | 3210 | 160 |
| R. Whole-task race | 155/160 | 1957 | 1834 | 800 |
| C. Planning router | 158/160 | 2078 | 1186 | 8,393 |
| D. Ceiling (models read, reference code) | 160/160 | 872 | 870 | 800 |
| E. Code only (rules read, reference code) | 148/160 | 0.16 | 0.15 | 0 |

- **Primary result: not supported.** C/R 1.06 (interval 0.68 to 1.44); C was
  1.9 points more accurate than R (0.6 to 3.7). The V2 result did not
  replicate on time. `fleet_fuel` got no plan (both rejected). `library_loans`
  and `room_bookings` each kept three function steps (date arithmetic, floor
  lookups) on the models, chained, so their plans ran slower than the race.
  Shapes whose steps all became code ran in about 0.8 to 1.1 s against the
  race's 1.6 to 2.7 s, and over the last five jobs C was clearly faster.
- **Code against models.** The rules read 148 of 160 texts right (the same
  number stage 1 predicted offline: 293 of 324 distinct texts). Models reading
  the same jobs (D) got 160. The planning router beat code-only on correctness
  (+6.3 points, interval +1.3 to +11.3); the plain whole-task race did not
  (+4.4, interval -0.6 to +9.4). Code-only answered about 10,000 times faster.
  Rules failed on complaints with no complaint word, places missing from
  their lists, negations ("I'm not vegan") and meetings described only by
  subject.

Evidence: `fast_path_planned_v3_primary.jsonl`,
`fast_path_planned_v3_primary_analysis.json`, `code_only_v1_scores.json`.

### Write the job once (descriptive, 2026-11-18)

The obvious competitor to step-by-step learning: arm W (`write_once.py`) races
the whole task until two answers agree, then asks one model to write the whole
job (reading steps with fixed labels, plus one Python function for everything
else) from the description alone. The program is kept only if it reproduces
both agreed answers; after that, only its reading steps go to models. Same V3
jobs, so descriptive. Plan: `FAST_PATH_WRITE_ONCE_V1_PLAN.md`.

| Arm | Correct | Median ms | Model calls |
|---|---:|---:|---:|
| R. Whole-task race | 155/160 | 1963 | 800 |
| D. Ceiling (reference code) | 160/160 | 925 | 800 |
| E. Code only (keyword rules) | 148/160 | 0.17 | 0 |
| **W. Write once** | **156/160** | **1018** | **948** |
| C. Planning router (V3 primary run) | 158/160 | 2078 | 8,393 |

- **All eight programs were adopted at the first attempt**, from job 3 to
  job 6, and none was later dropped. 133 of 134 program-served answers were
  right; the one miss was a reading of the borderline "No steak or salmon"
  text, not the code.
- W took 0.52 times the race's median time (interval 0.42 to 0.61) and 1.1
  times the hand-written ceiling's, with about a ninth of the planning
  router's calls.
- **This is the most important result of the fast-path work so far.** On jobs
  like these, writing the job once and checking it by execution beats learning
  it step by step on speed, coverage and cost, and gets within 10% of a
  programmer's version. The planning router's step learning would only earn
  its place on jobs a model cannot write whole.

Evidence: `fast_path_write_once_v1.jsonl`, `fast_path_write_once_v1_analysis.json`.

Repair V1 (descriptive, 2026-11-18): on the three shapes whose plans kept
steps on the models, new per-step diagnostics show why: each stuck step had
28 agreed examples and no disagreement, but the code written for it matched
only 12 of 15 or 16. An optional repair attempt (`repair_attempts`, off by
default) that shows the code writer two failing cases did worse (6 and 10 of
17) and promoted nothing. The shapes ran faster than in the V3 run only
because the planner wrote different plans. Plan:
`FAST_PATH_REPAIR_V1_PLAN.md`; evidence: `fast_path_repair_v1.jsonl`,
`fast_path_repair_v1_analysis.json`.

### Write once on unseen jobs (prospective, 2026-11-18)

Eight unseen job shapes (`fast_path_planned_bench_v4.py`), with keyword rules
frozen before the texts existed. Plan: `FAST_PATH_WRITE_ONCE_V2_PLAN.md`.

| Arm | Correct | Median ms | Model calls |
|---|---:|---:|---:|
| R. Whole-task race | 153/160 | 2296 | 800 |
| C. Planning router | 150/160 | 1753 | 11,627 |
| D. Ceiling | 159/160 | 912 | 800 |
| E. Code only (keyword rules) | 127/160 | 0.14 | 0 |
| **W. Write once** | **151/160** | **963** | **979** |

- **Not supported**: write-once took 0.42 of the race's time (interval 0.35 to
  0.47), but its accuracy interval against the race (-10 to +5 points) crossed
  the -2-point bound.
- Every program was adopted at its first attempt. Five of its seven wrong
  answers came from one rule in `wine_orders`: it rounded the discounted value
  rather than the discount, which differs only when a discount ends in half a
  cent. The two examples it was checked against had no such case. The
  planning router's plans made the same error; the race made none.
- Against the planning router, write-once was again better on every count:
  0.55 of its time, a twelfth of its calls, slightly more accurate.
- Lesson: checking a whole program against two agreed answers is too thin for
  rounding and tie rules. Edge-case probes, which already guard single steps,
  are the obvious addition.

Evidence: `fast_path_write_once_v2_primary.jsonl`,
`fast_path_write_once_v2_primary_analysis.json`.

### Write once with edge-case probes, fresh unseen jobs (prospective, 2026-11-18)

Write-once now also checks each program against up to six edge-case jobs
(rounding at halves, ties, empty lists, thresholds) proposed by a probe model
and answered by the race; a program is adopted only if it reproduces every
agreed answer. Eight more unseen job shapes (`fast_path_planned_bench_v5.py`),
several built around half-cent rounding and thresholds, 30 jobs each. Plan:
`FAST_PATH_WRITE_ONCE_V3_PLAN.md`.

| Arm | Correct | Median ms | Model calls |
|---|---:|---:|---:|
| R. Whole-task race | 233/240 | 1925 | 1,200 |
| D. Ceiling | 240/240 | 931 | 1,200 |
| W. Write once | 240/240 | 948 | 1,385 |
| **P. Write once with probes** | **238/240** | **961** | **1,866** |

- **Supported**: P took 0.50 of the race's time (interval 0.45 to 0.58) and
  was 2.1 points more accurate (0.0 to +5.4). All 222 program answers were
  right; its two misses came from the race before adoption. It matched the
  hand-written ceiling's speed.
- The probes rejected nothing (46 agreed, 0 failed), and write-once without
  probes was also perfect, so this run shows the probes are cheap (about a
  third more calls, no extra answer time), not that they help.
- **Jobs back to back** (same jobs, R and P only): P took 0.65 of the race's
  time (0.54 to 0.74), -0.8 points (-1.7 to 0.0). Programs went live after 11
  to 22 jobs, because writing and checking a program takes longer than a
  dozen jobs arriving; once live, every answer was right at about 0.9 s.

Evidence: `fast_path_write_once_v3_primary.jsonl`,
`fast_path_write_once_v3_primary_analysis.json`,
`fast_path_write_once_v3_immediate.jsonl`,
`fast_path_write_once_v3_immediate_analysis.json`.

### Write-once becomes the multi-step path (2026-11-18)

`write_once.WriteOnceRouter` is now the way to answer a plain-language
multi-step task: `python main.py --task-json task.json` (a
`fast_path_task_v1` document). Programs are kept in `fast_path_programs/`
between runs, edge-case probes are on by default (`program_probes` 6), and a
reading may be made on every item of a list (`"each": true`). Early writing
(`write_early`) is implemented and tested but off by default: it was never
measured, because the run that would have measured it was dropped to save
credit. `planner.py` is kept, marked superseded.

### Hard jobs: many readings per job (prospective, 2026-11-18)

Eight unseen job shapes (`fast_path_planned_bench_v6.py`), each a list of 4 to
12 records with a short text to read on every record (review topic, incident
severity, expense category, allergen, ...), about 7.4 readings per job. These
were built as the jobs most likely to defeat writing the whole job once, and
the only kind where step-by-step planning might still win. Plan:
`FAST_PATH_HARD_JOBS_V1_PLAN.md`.

| Arm | Correct | Median ms | 90th pct ms | Model calls |
|---|---:|---:|---:|---:|
| R. Whole-task race | 143/160 | 2245 | 3202 | 800 |
| C. Planning router | 108/160 | 2891 | 19,741 | 18,178 |
| D. Ceiling (reference code, every item raced) | 140/160 | 1806 | 3130 | 5,895 |
| P. Write once with probes | 143/160 | 2492 | 3941 | 5,934 |

- **Not supported**: write-once was as accurate as the race but slower (1.11
  of its time, interval 1.02 to 1.20). Each item's reading is its own race, so
  a job waits for the slowest of about seven races, where the whole-task race
  waits for one. Batching a job's readings into one call is the obvious fix;
  it is untested.
- **The planning router did worst**, on exactly the jobs meant to favour it:
  22 points less accurate than write-once, with median times of 12 to 18 s on
  three shapes and three times write-once's calls.
- `incident_log` was hard for every arm (7 or 8 of 20): one misread severity
  among seven notes flips its escalation rule.
- The run cost about $12.90 against an estimate of $6, almost all of it the
  planning router.

Evidence: `fast_path_hard_v1_primary.jsonl`, `fast_path_hard_v1_primary_analysis.json`.

### Reading fixes on the hard jobs (descriptive, 2026-11-20)

Three opt-in fixes for write-once (`batch_readings`, `uncertainty_gate`,
`adaptive_width`), together as arm B, on the same hard jobs. Plan:
`FAST_PATH_READING_FIXES_V1_PLAN.md`.

| Arm | Correct | Median ms | Model calls |
|---|---:|---:|---:|
| R. Whole-task race | 144/160 | 2261 | 800 |
| P. Write once | 147/160 | 2595 | 5,862 |
| B. Write once with the fixes | 138/160 | 2289 | 840 |

- B needed a seventh of P's calls and was faster than P, but no faster than
  the race (1.01 of its time) and 3.8 points less accurate than it: reading a
  job's notes in one call, on fewer models, misread incident severities more.
- **The uncertainty flag is the keeper.** Answers B flagged (racers
  disagreed) were right 3 times in 17; unflagged answers 135 times in 143. It
  caught 14 of B's 22 wrong answers.

Evidence: `fast_path_reading_fixes_v1.jsonl`, `fast_path_reading_fixes_v1_analysis.json`.

### First real task: the owner's bank transactions (2026-11-21)

The owner's Monzo export, 4,166 transactions over 21 months, with Monzo's own
category for each as the correct answer. Trained on the first 12 months,
tested on the last 9 (1,934 transactions). Plan: `REAL_BANK_V1_PLAN.md`.

| Approach | Accuracy | Needs a model for | Mean time per transaction |
|---|---:|---:|---:|
| Code only: a table from past months | 84.6% | 0% | 0 ms |
| Models only: race each merchant name | 63.6% | 100% | 1,070 ms |
| Hybrid: table first, new merchants to the race | 94.9% | 16% | 200 ms |
| Hybrid that keeps learning | 94.1% | 3% | 39 ms |

On real data the project's thesis holds plainly: ordinary code (here, a
lookup of what is already known) does most of the work instantly, and models
earn their place only on what is new. Models alone did worst, because the
categories follow filing conventions a merchant's name does not reveal.

Only aggregate figures are in the repository (`real_bank_v1_summary.json`);
the export and per-merchant detail stay out of it.

### Ask your statement (a practical tool, 2026-11-21)

`ask_statement.py` answers plain-English questions about a bank statement
export (Monzo's search or full export):

```bash
python ask_statement.py --csv statement.csv "Compare my spending at Morrisons and Wetherspoons per month"
python ask_statement.py --csv statement.csv            # interactive
python ask_statement.py --csv statement.csv --show-code "..."
```

A model decides what the question means and which merchants count (it is told
every merchant name, so it can group variants and spot misleading ones, such as
a canteen at an Amazon site), then writes a short function; the function runs
locally in the sandbox over every transaction, so the arithmetic is exact. Its
assumptions are printed with the answer. A repeated question reuses its saved
code with no model call: on the owner's statement the first answer took about
14 s and $0.0013, the repeat 37 ms and nothing. The cache lives in the
git-ignored `real_tasks/private/`.

Two accounts can be asked about together. `statement_pdf.py` reads Nationwide
FlexAccount PDF statements locally (no model), by the column positions of
`pdftotext -layout`, and checks every printed running balance; on the owner's
11 statements (524 transactions) every balance reconciled and each statement
opened at the previous one's close. `combine_statements.py` merges that with a
Monzo export over the shared period and marks money moved between the owner's
own accounts (and Monzo pots) as `internal`, pairing each transfer out of one
account with the same amount arriving in the other within three days (all 115
paired). Asked for a ten-category breakdown of the combined spending, the tool's
total matched an independent computation to the penny (one question, two model
calls, about 94 s, $0.006).

The owner's `evolab` repository gained the matching code-only condition (branch
`ccr-23487558-3yzwx4`, amendment 0.1-G): a scripted client that reads only the
public task scored Brier loss 0 on all nine sealed development tasks at
minimum evidence cost, which no model condition beat.

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
