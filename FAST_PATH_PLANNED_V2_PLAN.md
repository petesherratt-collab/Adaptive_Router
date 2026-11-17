# Fast-path planned jobs V2 plan: a prospective test on fresh jobs

**Status:** FROZEN 2026-11-17. One primary run is authorized.

**Scope:** PROSPECTIVE. No model has seen these jobs.

After three descriptive runs of the planning router on reused jobs, the owner
added credit and asked to continue. This run tests the planning router as it
now stands (small-step steering and speed feedback) on fresh jobs. The
benchmark was written by the assistant and not reviewed by the owner.

## Question

Given only plain-language task descriptions, does the planning router answer
mixed multi-step jobs sooner than racing the whole task across the roster,
without returning materially more wrong answers?

## Benchmark

`fast_path_planned_bench_v2.py`: 7 new job shapes (expense claims, shipment
tracking, survey scores, timesheet, bank statement, playlist, pick list), 15
jobs each, stream seed 20261120, 105 jobs in 7 task clusters. Each job has a
record list of 8 to 22 lines and one prose field whose label is planted. Gold
is computed by a reference function per shape, qualified by hand-worked tests.
The router receives the description and inputs only.

## Arms and settings

As in planned jobs V1: A one direct call (`openai/gpt-5.6-luna`), R the
whole-task race, C the planning router from an empty store. Order randomised
per job, seed 20261117. `config_fast_path.json` as committed: planner
`openai/gpt-6-luna`, `plan_examples` 2, `max_plan_attempts` 2, `plan_retries`
1, `refine_after_jobs` 4, `max_refinements` 1, `plan_audit_rate` 0.1, and the
fast-path settings of the earlier runs. Background work is drained between
jobs of a shape.

## Primary analysis

`analyze_fast_path_planned_v1.py`, arm C against arm R, shape-cluster
bootstrap, 10,000 replicates, seed 20261116.

1. Time: median C over median R, 95% interval wholly below 1.0.
2. Correctness: C minus R, 95% interval wholly above -2 points.

Supported only if both hold.

## Readings fixed in advance

Whatever the decision: C against A; per-shape correctness and medians; medians
over the last five jobs of each shape; plans adopted, rejected and refined;
plan step counts by kind and how many function steps were promoted; wrong job
examples; plan demotions; the job index from which each shape ran on a plan;
and any shape where C is slower than R, with the reason found in its record.

With 7 clusters the interval will be wide. The first runs suggest the first
plan job of each shape is slow (all steps still on the models) and that one
long chain with an unpromoted step can keep a shape slower than the race. No
prediction is made beyond that.

## Execution

`run_fast_path_planned_v1.py --bench fast_path_planned_bench_v2.py`, four
shapes at a time. Stops on HTTP 401 or 402 or sustained provider failure.
Provider credit at the freeze: about $23.40.
