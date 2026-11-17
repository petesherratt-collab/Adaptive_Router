# Fast-path timing V1 plan

**Status:** FROZEN 2026-11-16. One primary run is authorized.

**Runtime policy authority:** none. Runtime v0.3 is unchanged.

**Provider generation requests:** permitted only through
`run_fast_path_timing_v1.py` against the frozen files whose hashes are listed
in the `BUILD_HISTORY.md` freeze entry.

The owner accepted the proposed numbers and the arrival assumption in session
on 2026-11-16, describing them as a starting point to be varied later. The
benchmark was written by the assistant and delegated without owner review;
that is a limitation of this freeze and must be stated with any result.

## Question

For repeated single-step tasks, does the running fast-path router return
answers sooner than direct service from one remote model, without returning
materially more wrong answers?

Cost is not an objective and is not a success criterion. It is recorded only
as an observation.

## Why a new benchmark is required

`fast_path_gold_items_v1.py` was used in the development run of 2026-11-16 and
its results informed the answer prompt and the roster. It is development
evidence and must not be reused here. The vendored CCC items were used to tune
the answer prompt and are excluded for the same reason.

## Benchmark

- 30 new task shapes, none sharing a specification with either
  earlier bank.
- Each shape has a specification, a `solve` signature, a reference
  implementation and at least 6 hand-written tests whose expected values come
  from the specification. No single-bug variant is included because no
  analysis in this plan uses one.
- Each shape also has a request stream of 30 distinct inputs drawn
  by a seeded generator committed with the benchmark. Gold for a stream input
  is the reference implementation's output. The reference earns that role only
  by passing every hand-written test.
- The stream order is fixed at freeze time. Requests carry no caller examples,
  so every stored example must come from model agreement.

900 requests form 30 task clusters. Requests within a shape are not
independent; no analysis may treat them as 900 independent tasks.

## Arms

Every request is served by all three arms. Arm order is randomised per request
from a frozen seed so that provider load drifts affect the arms alike.

| Arm | Service |
|---|---|
| A. Direct | One call to the baseline model, answer parsed by the same parser. |
| B. Race | Fast-path router with synthesis disabled. |
| C. Fast path | Fast-path router as configured, starting from an empty store. |

- Baseline model for arm A: `openai/gpt-5.6-luna`, chosen now because it had
  the joint-lowest failure count and the lower latency of that pair in the
  development run. It is not chosen from this experiment's results.
- Race roster, synthesis model, token limits, `agreement_quorum`,
  `min_gate_examples`, `max_synthesis_attempts` and `audit_sample_rate` are the
  values in `config_fast_path.json` at freeze time.
- All arms use the same answer prompt and the same parser. No retries beyond
  those already in `remote.py`. No repair of answers.

### Arrival model

Arm C's background learning is allowed to finish before the next request of
the same shape is issued. This is the favourable case for the fast path and
must be reported as such. Time spent in background work is recorded and
reported separately; it is not part of answer time.

## Measurements

Per request and arm: wall-clock answer time from call to returned value;
route (`code`, `model`, `none`); winning model; whether the returned value
equals gold under type-strict canonical JSON. Cost is not recorded.

Per shape for arm C: the request index at which a function was promoted, if
any; whether the promoted function is gold-correct on all hand-written tests
and all stream inputs; demotions and their reasons; synthesis attempts.

Raw observations are appended to a new JSONL file that must not already exist.
Prompts are reconstructible from the frozen benchmark; argument values and
answers are recorded because gold comparison requires them.

## Primary analysis

Uncertainty is from a paired bootstrap that resamples the 30 shapes and keeps
each shape's 30 requests together: 10,000 replicates, percentile intervals,
seed 20261116.

1. **Time.** Median answer time of arm C divided by median answer time of
   arm A, over all 900 requests. Criterion: the ratio's 95%
   interval lies wholly below 0.5.
2. **Correctness.** Share of requests answered correctly, arm C minus arm A.
   Criterion: the difference's 95% interval lies wholly above
   −2 percentage points.

The fast path is supported for this workload only if both criteria hold. A
request for which an arm returns no answer counts as wrong for correctness and
takes its full elapsed time for the time measure.

## Secondary analyses, descriptive only

- Arm B against arm A on both measures, to separate the effect of racing from
  the effect of code.
- Arm C answer time by route, and the share of requests served by code.
- Wrong answers served by code, with a one-sided 95% upper bound computed over
  shapes, and the count of shapes whose promoted function was gold-wrong.
- Stored examples that were gold-wrong.
- 90th-percentile answer times for each arm.
- Requests to promotion per shape.

No secondary result may be promoted to a headline, and no subgroup chosen
after the run may be described as prospectively validated.

## Stop rules

- The first 3 shapes run before the rest. If any arm returned no answer on
  more than 20% of their requests, stop, record an execution incident, and do
  not analyse.
- A crash leaves the partial file in place with a `.partial` suffix. A rerun
  uses a new file and the incident is documented; partial evidence is never
  merged into a completed run.

## What a result would and would not establish

A positive result would show a time advantage on constructed, repeated,
function-like tasks with a favourable arrival pattern, for this roster on the
day of the run. It would not establish a result for one-off tasks, for
natural workloads, for tasks that are not pure functions of their arguments,
or for multi-step work. It makes no energy claim.

A negative result on time would most likely mean promotions arrive too late in
a 30-request stream to move the median; the route and requests-to-promotion
tables are there to show that.

## Execution

- Benchmark: `fast_path_timing_bench_v1.py`. Runner:
  `run_fast_path_timing_v1.py`. Analysis: `analyze_fast_path_timing_v1.py`.
- Shapes run six at a time; within a shape, requests and arms are sequential.
  Concurrent shapes add provider load, which falls on all three arms alike.
- The arm-order seed and stream seed are 20261116.
- Before the freeze the pipeline was exercised live once on three shapes from
  the development bank, none of which is in this benchmark.

## Sensitivity runs after the primary run

The owner intends to repeat the run with one setting varied at a time
(`--set name=value`) to map the starting position. Those runs reuse a
benchmark that has already been seen. They are descriptive, are labelled in
their headers, and may not be reported as prospective results. Only the first
completed run with label `primary` and no override counts against the
criteria above.
