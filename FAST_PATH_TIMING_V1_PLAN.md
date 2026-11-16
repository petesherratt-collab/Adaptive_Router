# Fast-path timing V1 plan

**Status:** DRAFT for review. Not frozen. No run is authorized by this document.

**Runtime policy authority:** none. Runtime v0.3 is unchanged.

**Provider generation requests:** forbidden until this plan, the benchmark,
the configuration and the runner are frozen and their hashes recorded.

Every number marked *proposed* is a placeholder for the owner to accept or
change before the freeze.

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

- *Proposed:* 30 new task shapes, none sharing a specification with either
  earlier bank.
- Each shape has a specification, a `solve` signature, a reference
  implementation, a single-bug variant and at least 8 hand-written tests whose
  expected values come from the specification, as in the CCC recipe.
- Each shape also has a request stream of *proposed* 30 distinct inputs drawn
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
equals gold under type-strict canonical JSON; reported provider cost.

Per shape for arm C: the request index at which a function was promoted, if
any; whether the promoted function is gold-correct on all hand-written tests
and all stream inputs; demotions and their reasons; synthesis attempts.

Raw observations are appended to a new JSONL file that must not already exist.
Prompts are reconstructible from the frozen benchmark; argument values and
answers are recorded because gold comparison requires them.

## Primary analysis

Uncertainty is from a paired bootstrap that resamples the 30 shapes and keeps
each shape's 30 requests together. The bootstrap seed is recorded in this plan
before the freeze.

1. **Time.** Median answer time of arm C divided by median answer time of
   arm A, over all 900 requests. *Proposed* criterion: the ratio's 95%
   interval lies wholly below 0.5.
2. **Correctness.** Share of requests answered correctly, arm C minus arm A.
   *Proposed* criterion: the difference's 95% interval lies wholly above
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

- If the first 3 shapes show a provider failure rate above *proposed* 20% in
  any arm, stop, record an execution incident, and do not analyse.
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

## Still to build before the freeze

- The 30-shape benchmark and its seeded input generators.
- A switch that disables synthesis, for arm B.
- The three-arm runner and the analysis script, each with tests against fakes.
- Recorded SHA-256 hashes of the benchmark, `config_fast_path.json`,
  `fast_path.py`, `sandbox.py`, the runner and the analysis script.
