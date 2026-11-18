# Write-once V3: edge-case probes, on fresh unseen jobs

**Status:** stage 1 FROZEN 2026-11-18 (benchmark, ceiling steps, prose
prompt) before any text exists; stage 2 (the runs) frozen below before any job
is sent to a provider.

**Scope:** PROSPECTIVE. No model has seen these jobs.

## Why

On unseen V4 jobs, write-once was twice as fast as the whole-task race but
failed the correctness bound: five of its seven wrong answers were one
rounding rule that its two-example trial could not expose. The single-step
fast path already guards against this with boundary probes. This version adds
them to write-once (`program_probes`): after a program passes its two-example
trial, the probe model (`google/gemini-3.8-flash`) proposes up to 6
edge-case input sets (prose inputs held at the example's values, so readings
are unchanged), the whole-task race answers each, and the program must
reproduce every answer the racers agree on. No model judges the program; the
probes only add agreed examples. A program that fails is rejected; the next
attempt is written blind, as before.

## Stage 1

`fast_path_planned_bench_v5.py`: 8 new shapes (`car_park`, `gym_classes`,
`shared_bills`, `plant_watering`, `train_fares`, `reading_challenge`,
`lab_ph`, `donation_match`), several with rules that turn on exact halves,
ties or thresholds. `fast_path_ceiling_v5.py`; `make_bench_v5_prose.py`
(12 texts per label, `mistralai/mistral-large-4-0`). No keyword-rules arm this
time, to save effort; the code-only comparison stands on V3 and V4.

## Stage 1 result

Texts: 12 per label, 324 in all; 3 excluded after the hand check (water notes
that do not say what was sampled), 4 borderline kept with reasons.

## Stage 2: the runs (frozen before any job is sent)

**Run 1, primary, prospective.** `fast_path_planned_bench_v5.py`, 8 shapes,
the first 30 jobs of each stream (240 jobs). Arms R (whole-task race), D
(ceiling, `fast_path_ceiling_v5.py`), W (write once, no probes) and P (write
once with `program_probes` 6). Settings as committed; drained arrival.

- **Primary:** P against R, shape-cluster bootstrap, 10,000 replicates, seed
  20261116. Supported only if the median-time ratio's 95% interval lies
  wholly below 1.0 and the correctness difference's wholly above -2 points.
- **Secondary:** P against W (do probes help correctness, at what time and
  call cost?), W against R, P against D; per shape, attempts rejected by
  probes, probes proposed and agreed, wrong program answers split into code
  and reading, first program job, calls and tokens per arm.
- Expected cost about $2.50.

**Run 2, descriptive.** The same jobs, arms R and P, jobs back to back
(`--arrival immediate`). Readings: P against R, first program job per shape,
wrong program answers. Expected cost about $1.50.

## Run 1 result (2026-11-18)

**Supported.** Write once with probes: 0.50 of the race's time (0.45 to 0.58),
+2.1 points (0.0 to +5.4); every program answer right. The probes rejected no
program (0 of 46 agreed probes failed), and write once without probes was also
right on all 240 jobs. Details in `BUILD_HISTORY.md`.

## Run 2 result (2026-11-18)

Back to back: 0.65 of the race's time (0.54 to 0.74), -0.8 points (-1.7 to
0.0). Programs went live at jobs 11 to 22; every program answer was right.
