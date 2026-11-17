# Fast-path jobs V2 plan: larger jobs

**Status:** FROZEN 2026-11-17. One primary run is authorized.

**Runtime policy authority:** none. Runtime v0.3 is unchanged.

The owner asked in session for a test of jobs where the step pipeline should
have the most to gain, after the V1 jobs result. The benchmark was written by
the assistant and was not reviewed by the owner before the freeze. Rules not
restated here are those of `FAST_PATH_JOBS_V1_PLAN.md`.

## Why

In jobs V1 the pipeline over the fast path halved job time against one direct
call but was not distinguishable from racing the whole job across the roster
(time ratio 0.90, interval 0.80 to 1.28). Those jobs were small: short inputs
and two or three function steps. The whole-job race is now the competitor to
beat. A pipeline should gain most when the job has a long structured input
and many mechanical steps, because a single call must then read and work
through all of it while the pipeline hands those steps to code.

## Question

For larger mixed jobs, does the step pipeline over the fast path return the
job's answer sooner than racing the whole job across the roster, without
returning materially more wrong answers?

## Benchmark

`fast_path_jobs_bench_v2_large.py`: 7 job shapes, 15 seeded jobs each (stream
seed 20261119), 105 jobs in 7 task clusters. Every shape has one or two
judgement steps and five or six function steps over an input of 8 to 25
records (invoice lines, log lines, CSV rows, a message thread, scores, stock
lines, meeting minutes). Whole-job prompts are about 2,500 to 3,000
characters. No shape appears in any earlier bank. Gold is by construction as
in V1.

With 7 clusters the intervals will be wide; a clear result is needed for the
criteria to be met.

## Arms and settings

The four V1 arms: A one direct whole-job call (`openai/gpt-5.6-luna`), R the
whole-job prompt raced across the roster, B the step pipeline with every step
raced, C the step pipeline over the fast path from an empty store. Order
randomised per job, seed 20261118.

Settings are `config_fast_path.json` as committed at the freeze. Changes since
jobs V1, recorded here because they affect every arm or arm C:

- `answer_max_tokens` is raised from 1024 to 4096 so that no arm is cut short
  by the cap on a long input; it applies to whole-job calls and step calls
  alike;
- the saturation rule (`saturation_window` 5, `saturation_min_examples` 2)
  is enabled.

Learning is drained between jobs of a shape, the favourable case.

## Primary analysis

Arm C against arm R, shape-cluster paired bootstrap, 10,000 replicates, seed
20261116, percentile intervals.

1. **Time.** Median job time of C over median job time of R. Criterion: the
   95% interval lies wholly below 1.0.
2. **Correctness.** Share of jobs correct, C minus R. Criterion: the 95%
   interval lies wholly above -2 percentage points.

Supported only if both hold. An unanswered job counts as wrong and takes its
full elapsed time.

## Readings fixed in advance

Reported whatever the decision: C against A; R against A; B against A;
step-level errors by kind and route in B and C, with the kind of each wrong
job's earliest wrong step; job medians after the fifth job of each shape;
function steps promoted, gold-wrong promoted functions, promotions under the
saturation rule, demotions and wrong stored examples; confirmation that no
judgement step was stored; per-shape correctness and medians for every arm.

No prediction is made.

## Execution

Runner `run_fast_path_jobs_v1.py --bench fast_path_jobs_bench_v2_large.py`,
analysis `analyze_fast_path_jobs_v1.py --baseline R --time-limit 1.0`, whose
`decision` field then applies the criteria above.

The run stops on HTTP 401 or 402 or when more than half of the last 100
provider calls fail; a stopped run is not analysed. Remaining provider credit
at the freeze is recorded in `BUILD_HISTORY.md`.

Later runs on this benchmark are descriptive only.
