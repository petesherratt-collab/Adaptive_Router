# Write-once arm V1: the competitor the planning router has to beat

**Status:** FROZEN 2026-11-18 before any provider call. **Scope:** DESCRIPTIVE
(the V3 jobs are reused; arm W has not seen them, but they have been run).

## Why

The obvious alternative to learning a job step by step is to write it once:
ask one model for the whole job's code at the start, keep it only if it
reproduces answers the racers agreed on, and from then on send only the
reading steps to models. That is close to the ceiling arm D, but nobody
writes the code by hand. If W reaches D's speed within a few jobs, the
planning router's step-by-step learning is the wrong design; if W's programs
fail, step-by-step learning has a reason to exist.

## Arm W (`write_once.py`)

- Until a program is adopted, each job is answered by the whole-task race;
  agreed answers become examples by the planner's rule (unanimous, quorum 2).
- After `plan_examples` (2) examples, `planner_model` (`openai/gpt-6-luna`)
  is given the description and one job's inputs, no answer, and asked for
  reading steps (one input each, fixed labels) and one Python function
  `solve(inputs, readings)` for everything else, under the sandbox's rules.
- The program is run on the two examples, readings raced as the planner races
  judgement steps; adopted only if both answers match. At most
  `max_plan_attempts` (2) programs per shape, no feedback between them.
- Adopted: each job races its readings in parallel and runs the code in the
  sandbox. `plan_audit_rate` (0.1) of jobs are checked against a fresh race;
  an agreed mismatch drops the program.

## Run

`fast_path_planned_bench_v3.py`, 8 shapes, the same 20 jobs per shape as the
V3 primary run. Arms R, D, E and W only (`--arms R,D,E,W`): A and C are not
re-run, to save credit; C's figures from the V3 primary run are quoted for
reference only. Settings as committed with `plan_shadow` false, drained
arrival, four shapes at a time.

## Readings fixed in advance

W against R (shape-cluster bootstrap, as before), W against D and E; shapes
with a program adopted and from which job; attempts and their outcomes;
readings per program; W's median after adoption against D's; W's correctness,
wrong program answers and demotions; calls and tokens per arm.

Expectation, stated now: most shapes adopt a program at job index 2 and then
run near D's ~0.9 s. The risk is programs that fail the two-example trial on
fiddly rules (rounding, ties, date arithmetic), leaving those shapes on the
race. Expected cost about $1.
