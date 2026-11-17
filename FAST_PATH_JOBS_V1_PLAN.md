# Fast-path jobs V1 plan: multi-step jobs

**Status:** FROZEN 2026-11-16. One primary run is authorized.

**Runtime policy authority:** none. Runtime v0.3 is unchanged.

The owner asked for this benchmark and plan in session. The benchmark was
written by the assistant and was not reviewed by the owner before the freeze.
Rules not restated here are those of `FAST_PATH_TIMING_V1_PLAN.md`.

## Question

For mixed multi-step jobs, where some steps need a model's judgement and the
rest are fully determined by their specification, does running the declared
plan step by step over the fast path return the job's answer sooner than one
model carrying out the whole plan in a single call, without returning
materially more wrong answers?

## Benchmark

`fast_path_jobs_bench_v1.py`: 12 job shapes, 20 seeded jobs each (stream seed
20261118), 240 jobs in 12 task clusters. Each shape has one to three judgement
steps and one to three function steps. Two shapes test the awkward cases:
`dial_code` has two judgement steps in sequence, and `triple_code` has three
in parallel.

Gold is by construction. A judgement step's label is planted by the generator,
which builds each text from a sentence written to carry exactly that label,
and each judgement step reads a field that carries only its own signal. A
function step's gold is its reference output; each reference passes at least
four hand-written tests. A job is correct when its final value equals gold
under type-strict canonical JSON.

The judgement texts are short and unambiguous by design. That favours every
arm and says nothing about hard judgement calls.

## Arms

Every job is served by all four arms in an order randomised per job from seed
20261118.

| Arm | Service |
|---|---|
| A. Direct | One call: `openai/gpt-5.6-luna` is given the whole plan and the inputs. |
| R. Whole-job race | The same prompt raced across the roster; first usable answer wins. |
| B. Pipeline, race only | Steps run by the orchestrator; every step on the model race. |
| C. Pipeline, fast path | As B, but function steps learn and may be promoted to code. |

Arm R exists so that the effect of decomposing the job can be separated from
the effect of racing. Settings are `config_fast_path.json` as committed,
including boundary probing and `probe_after_examples` 3. Arm C starts from an
empty store. Judgement steps never learn in any arm. Learning is drained
between jobs of a shape, the favourable case, and reported as such.

## Primary analysis

Arm C against arm A, shape-cluster paired bootstrap, 10,000 replicates, seed
20261116, percentile intervals.

1. **Time.** Median job time of C over median job time of A. Criterion: the
   95% interval lies wholly below 0.75.
2. **Correctness.** Share of jobs correct, C minus A. Criterion: the 95%
   interval lies wholly above -2 percentage points.

The pipeline is supported for this workload only if both hold. An unanswered
job counts as wrong and takes its full elapsed time.

## Readings fixed in advance

Reported whatever the decision:

- arm C against arm R on both measures. If the whole-job race is as fast and
  as accurate as the pipeline, decomposition has not earned its place on this
  workload, and that is stated plainly;
- arm B against arm A, and arm R against arm A;
- step-level error counts in arms B and C by kind and route, and for each
  wrong job the kind of its earliest wrong step;
- function steps promoted, promoted functions that are gold-wrong, demotions,
  wrong stored examples;
- confirmation that no judgement step was stored;
- results for `dial_code` and `triple_code` separately, described only.

No prediction is made. With 12 clusters the intervals will be wide.

## Execution

Runner `run_fast_path_jobs_v1.py`, analysis `analyze_fast_path_jobs_v1.py`.
Four shapes run at a time. The run stops on HTTP 401 or 402 or when more than
half of the last 100 provider calls fail; a stopped run keeps its `.partial`
name and is not analysed. Before the freeze the pipeline was exercised live on
one six-job shape that is not in the benchmark.

Later runs on this benchmark are descriptive only.
