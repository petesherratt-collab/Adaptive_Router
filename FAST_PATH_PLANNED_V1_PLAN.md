# Fast-path planned jobs V1 plan: the router writes its own plans

**Status:** FROZEN 2026-11-17. One run is authorized.

**Scope:** DESCRIPTIVE. The jobs, inputs and gold are those of the jobs V2
benchmark, already used in a prospective run. What is new is that the router
receives a plain-language task instead of a step plan, and must write, check
and adopt its own plan. The run measures that mechanism; its numbers are
descriptive because the jobs have been seen before.

The owner asked in session for the router to write its own plans. The task
descriptions were written by the assistant and not reviewed by the owner.

## Question

Given only a plain-language task description and named inputs, can the router
write a step plan, verify it without a model judge, adopt it, and then answer
jobs sooner than racing the whole task across the roster, without returning
more wrong answers?

## Mechanism under test

`planner.py`. Per task template (description plus input names and types):

1. Until a plan is adopted, each job is answered by racing the whole task.
   Unanimous answers become job examples.
2. After `plan_examples` (3) examples, a planner model (`openai/gpt-6-luna`)
   writes a step plan from the description and one example's inputs. It sees
   no agreed answer.
3. The plan is run through the step pipeline on those 3 examples. It is
   adopted only if it reproduces all 3. Up to 2 attempts per template.
4. Adopted: jobs run the plan over the fast path, whose function steps learn
   and may be promoted to code. A 10% sample is audited by a whole-task race;
   an agreed mismatch drops the plan.

## Benchmark

`fast_path_planned_bench_v1.py`: the 7 shapes of
`fast_path_jobs_bench_v2_large.py`, 15 jobs each, each with one description
stating the same rules as its reference plan without saying how to break up
the work. 105 jobs in 7 task clusters.

## Arms

| Arm | Service |
|---|---|
| A. Direct | One call: `openai/gpt-5.6-luna` given the task and inputs. |
| R. Whole-task race | The same prompt raced across the roster. |
| C. Planning router | As described above, from an empty store. |

Order randomised per job, seed 20261117. Settings are `config_fast_path.json`
as committed. Background work, including planning and plan trials, is drained
between jobs of a shape and reported separately.

## Analysis

`analyze_fast_path_planned_v1.py`. Primary: C against R, shape-cluster
bootstrap, 10,000 replicates, seed 20261116.

1. Time: median C over median R, 95% interval wholly below 1.0.
2. Correctness: C minus R, 95% interval wholly above -2 points.

Reported whatever the outcome: shapes whose plan was adopted, attempts and
their outcomes, the job index from which each shape ran on its plan, plan step
kinds and how many function steps were promoted, wrong job examples, plan
demotions, C against A, per-shape results, and medians after adoption.

Because the router answers with the whole-task race until a plan is adopted,
arm C cannot be faster than arm R on those early jobs; with 15 jobs per shape
and adoption no earlier than the fourth, the median is weighted toward the
plan's steady state but not wholly in it.

## Execution

Runner `run_fast_path_planned_v1.py`, four shapes at a time. Stops on HTTP
401 or 402 or sustained provider failure. A two-shape, seven-job smoke run
before the freeze adopted a plan for both shapes; it is not evidence.
