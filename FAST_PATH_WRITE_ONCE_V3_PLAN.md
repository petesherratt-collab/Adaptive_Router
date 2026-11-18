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
