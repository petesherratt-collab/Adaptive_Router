# Flag fallback V1 (Phase B): serve what the models agree on, decide the rest by majority

**Status:** FROZEN 2026-11-25, before any provider call.
**Scope:** DESCRIPTIVE. It reuses the V6 hard jobs, which have been run before.

## Question

On jobs that need many readings, the uncertainty flag separated good answers from bad
(reading fixes V1: unflagged 135/143 right, flagged 3/17). Two questions follow:

- **Arm F.** Serve a program's answer only when its readings agreed. Send a flagged
  answer to a full whole-task race decided by **majority**. Is what F serves at least as
  accurate as the race (R), and at what time?
- **Arm M.** Decide every reading by majority instead of by first answer, and add no
  fallback. Does that recover the accuracy that narrower reading lost?

## Run

`run_fast_path_planned_v1.py` on `fast_path_planned_bench_v6.py`:
- all 8 shapes, the same 20 jobs per shape (stream seed 20261120);
- arms **R, F and M**, drained arrival;
- `plan_shadow` false and `program_probes` 6, as in the reading-fixes run.

```
python run_fast_path_planned_v1.py --bench fast_path_planned_bench_v6.py \
  --output fast_path_flag_fallback_v1.jsonl --label flag_fallback_v1 \
  --set plan_shadow=false --probes 6 --flagged --arms R,F,M --jobs 20
```

What each arm does:
- **R** races the whole task and serves the first valid answer.
- **F** is the same as P (write once, readings raced per item), plus:
  - `uncertainty_gate` on;
  - `flag_fallback: "majority"`: a flagged program answer is replaced by a five-model
    whole-task race decided by majority;
  - the program's own answer is recorded on each fallback row (`program_correct`).
- **M** is the same as P, with `decision: "majority"`. Every reading waits for all
  racers and takes the majority. A tie, or any dissent, flags the answer, but there is
  no fallback.

P is not re-run, to save about $1.70 at the 50% margin. P's result on these same jobs
from `fast_path_reading_fixes_v1.jsonl` (147/160, median 2,595 ms) is quoted as a
reference from a different run.

## Readings fixed in advance

**Primary (Phase B's "done when"):** F against R.

- **Served accuracy.** The correctness difference is reported with a 95% interval from
  the shape-cluster bootstrap. F "serves answers at least as accurate as the race" if
  the interval's lower bound is above −2 points.
- **Time.** The median-time ratio, which includes the fallback's time, is reported with
  its interval. F is faster than R if the upper bound is below 1.0.

**Also reported for F:**
- the share of program answers flagged;
- the accuracy of unflagged program answers;
- the accuracy of fallback answers;
- how many flagged program answers would have been right anyway.

**M:**
- M against R: correctness and time, with intervals;
- M against the quoted P: descriptive only, because it comes from a different run;
- M's flag: accuracy of flagged against unflagged answers.

Calls, tokens and cost are reported for each arm.

## Cost and stop rules

- **Estimate: about $6.20.** In the reading-fixes run, R took about $0.73 of $2.97 and
  P about $1.66. This run is R + F (P plus a fallback race on roughly 10% of jobs) + M
  (P's calls), which comes to about $4.10, plus 50%.
- **Credit at freeze:** $10.85, shared with the change-signals key.
- **Stop rules:** the runner's provider-failure monitor, as before.
- **Credit check:** credit is checked after the run. If it is below $3, nothing more
  is run until the owner tops up.
