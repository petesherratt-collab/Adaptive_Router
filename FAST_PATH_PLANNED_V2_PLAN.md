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

## Follow-up runs (descriptive), 2026-11-17

The owner asked to work through the next steps in order. These runs reuse the
V2 jobs, so they are descriptive and do not change the primary result.

1. `majority`: `job_agreement_min` 4. A whole-task answer becomes a job example
   when at least four of the five racers give it and no other answer is as
   common, instead of requiring every valid answer to match. Aimed at shapes
   such as `timesheet`, where disagreement delayed the plan to job 8. The
   cost to watch is wrong job examples and wrong plans adopted.
2. `immediate`: jobs arrive back to back, with no pause for background work
   (`--arrival immediate`), using whichever agreement rule the first follow-up
   supports.

Both runs record, per arm, every provider call and token, background work
included, so the cost of the planning router's learning is measured for the
first time.

3. `shadow`: at the owner's choice, the fix for the flaw follow-up 2 exposed.
   An adopted plan starts in shadow mode (`plan_shadow`): jobs are still
   answered by the whole-task race, and the plan runs in the background on each
   job's inputs, so its function steps learn and its answer is checked against
   the race (an agreed mismatch drops the plan). It goes live only when its
   last `plan_live_window` (2) shadow runs each took under `plan_live_ratio`
   (0.75) of the median race time for that task. Run with jobs back to back
   (`--arrival immediate`) and `job_agreement_min` 4, as in follow-up 2, so
   the two runs differ only in the shadow rule.

4. `ceiling`: written down before the run, at the owner's request and to the
   owner's specification.

   **Arm D is a ceiling, not a baseline.** It stands for a programmer having
   already written the job. Its mechanical work is the benchmark's reference
   function, the same code that produces the correct answers, so those steps
   are correct by definition and the arm's overall accuracy says nothing about
   them. A 105/105 from arm D must not be read as code beating models. Only two
   results from it are informative:

   - how long its jobs take, especially the first few of each shape, against
     arm C, which has to learn its code;
   - how accurate its reading steps are.

   Its reading steps (`fast_path_ceiling_v1.py`, written from the task
   descriptions) are answered exactly as arm C answers its judgement steps:
   the same race roster, through `FastPathRouter.handle` with learning off,
   first usable answer wins. Neither arm uses agreement to choose a judgement
   answer. The only intended difference between C and D is hand-written
   versus learned code. A reading answer the reference code cannot use makes
   the job wrong.

   Arrival is drained between jobs, as in the frozen fresh-jobs run, and
   `plan_shadow` is off and `job_agreement_min` unset, as they were then. The
   code has changed since in one way that matters only under load: live and
   background work now use separate pools. Calls and tokens are metered per
   arm. The comparison of interest is arm C's learning cost against arm D's
   near-zero one: the price of not having a programmer.

   This run does not test the research endpoint's rule that a model-based
   approach must beat ordinary code. That needs a version with keyword rules
   for the reading steps, fair only on text nobody has seen: the rules are
   written from the task descriptions alone, their file's hash is recorded,
   and only then are the tasks' texts opened. That version is reserved for
   the owner's real tasks.
