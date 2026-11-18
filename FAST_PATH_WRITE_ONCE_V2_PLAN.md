# Write-once V2: a prospective test on unseen jobs

**Status:** stage 1 FROZEN 2026-11-18 (benchmark, reading rules, ceiling
steps, prose prompt), before any text exists. Stage 2 (the runs) is frozen
below before any job is sent to a provider.

**Scope:** PROSPECTIVE. No model, and no rule, has seen these jobs.

## Why

The write-once arm beat the planning router decisively on reused V3 jobs
(`FAST_PATH_WRITE_ONCE_V1_PLAN.md`). That result is descriptive. This test
repeats it on eight unseen job shapes, then checks it with jobs arriving back
to back.

## Stage 1 (each hashed before the next)

1. `fast_path_planned_bench_v4.py`: 8 new shapes (`hotel_stays`,
   `parcel_lockers`, `exam_marks`, `energy_meter`, `flight_delays`,
   `bike_rentals`, `volunteer_rota`, `wine_orders`), varied inputs (text
   lines, arrays of objects, an array of numbers, an object of lists, dates and
   times) and new readings. Gold from reference functions qualified by
   hand-worked tests.
2. `fast_path_code_only_v2.py`: keyword rules from the descriptions alone.
3. `fast_path_ceiling_v4.py`: the ceiling's reading-step specifications.
4. `make_bench_v4_prose.py`: the prompt that writes 12 texts per label with
   `mistralai/mistral-large-4-0`, outside the race roster.

Then the texts are generated, hand-checked against their labels before any
rule or model reads them (exclusions recorded with reasons), hashed, and the
rules scored offline.

## Stage 1 result (no provider cost)

Texts: 360 generated, 1 excluded after the hand check. Keyword rules v2:
308 of 359 texts (85.8%), 127 of the 160 stream labels used below. Weakest:
`exam_marks` effort (18 of 36), `parcel_lockers` issue (40 of 48).

## Stage 2: the runs (frozen before any job is sent)

**Run 1, primary, prospective.** `fast_path_planned_bench_v4.py`, all 8
shapes, the first 20 jobs of each stream. Arms R (whole-task race), C
(planning router), D (ceiling, `fast_path_ceiling_v4.py`), E (code only,
`fast_path_code_only_v2.py`) and W (write once). Settings as committed with
`plan_shadow` false (as in the V3 primary run); drained arrival.

- **Primary:** W against R, shape-cluster bootstrap, 10,000 replicates,
  seed 20261116. Supported only if the median-time ratio's 95% interval lies
  wholly below 1.0 and the correctness difference's wholly above -2 points.
- **Secondary, fixed now:** W against C (is write-once better than step
  learning on unseen jobs?), W against D (gap to the ceiling), W and C against
  E (does a model-based arm beat ordinary code on correctness; intervals
  wholly above zero), C against R, first program job per shape, attempts,
  wrong program answers, demotions, calls and tokens per arm.
- Expected cost about $3.80.

**Run 2, descriptive.** The same jobs with arms R and W only, jobs back to back
(`--arrival immediate`), to see whether write-once adoption survives live
traffic. Readings: W against R, first program job per shape. Expected cost
about $1.30.

Stop rules as before (HTTP 401/402 or sustained provider failure).

## Run 1 result (2026-11-18)

**Not supported.** Write-once took 0.42 of the race's time (0.35 to 0.47) but
was 1.3 points less accurate (interval -10.0 to +5.0), failing the -2-point
bound. Five of its seven wrong program answers were one rounding error in
`wine_orders` that two trial examples could not expose; the planning router's
plans made the same error. Write-once beat the planning router on time
(0.55), calls (1/12) and correctness. Cost $5.62 against $3.80 estimated.
