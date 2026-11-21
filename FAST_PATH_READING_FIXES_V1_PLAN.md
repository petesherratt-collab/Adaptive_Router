# Reading fixes V1: batched readings, uncertainty gate, adaptive width

**Status:** FROZEN 2026-11-20 before any provider call. **Scope:** DESCRIPTIVE
(reuses the V6 hard jobs, already run once).

## Question

On jobs with many readings each, write-once with probes (P) was as accurate as
the whole-task race (R) but slower (1.11 of its time), because every item was
its own race. Does arm B (P plus `batch_readings`, `uncertainty_gate` and
`adaptive_width` {width 2, after 5}) restore the speed advantage, and does its
uncertainty flag pick out wrong answers?

## Run

`fast_path_planned_bench_v6.py`, all 8 shapes, the same first 20 jobs, arms R,
P and B, drained arrival, settings as committed with `plan_shadow` false and
`program_probes` 6. `--arms R,P,B --probes 6 --fixes`.

## Readings fixed in advance

- B against R and B against P: median-time ratio and correctness difference,
  shape-cluster bootstrap as before. B "restores the speed advantage" if its
  time ratio against R has a 95% interval wholly below 1.0 and its correctness
  difference against R an interval wholly above -2 points (the usual bounds,
  reported descriptively).
- The uncertainty flag: accuracy of flagged against unflagged answers for B,
  and the share of B's wrong answers that were flagged.
- Calls and tokens per arm; first program job per shape.

**Expected cost:** about $6 (last hard run's R and P shares, plus B, plus 50%).
Stop rules as before.

## Result (2026-11-20)

Not restored: B took 1.01 of the race's time (0.79 to 1.27) and was 3.8
points less accurate (-8.8 to -0.6), with a seventh of P's calls. The
uncertainty flag separated answers well: flagged 3/17 right, unflagged
135/143. Cost $2.97.
