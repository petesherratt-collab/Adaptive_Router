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
