# Hard jobs V1: many readings per job (steps 2 and 3 of 2026-11-18)

**Status:** stage 1 FROZEN 2026-11-18 (benchmark, ceiling steps, prose
prompt) before any text exists; stage 2 (the runs) frozen below before any job
is sent.

**Scope:** PROSPECTIVE. No model has seen these jobs.

## Why

Write-once beat the planning router on every job set so far, all of which had
one prose field per job. These jobs are built to be hard for writing the job
whole: each job is a list of 4 to 12 records, and every record carries its own
text whose reading (topic, severity, category, sentiment, allergen, role,
outcome, outdoor space) feeds counts, filters, rankings and rules. If
step-by-step learning still has a place, it is here. The same jobs also test
early writing (step 2).

Write-once readings may now be made on every item of a list
(`"each": true`, `"field"`), as the planning router's judgement steps may
take a list; without that, write-once could not express these jobs at all.

## Stage 1

`fast_path_planned_bench_v6.py` (8 shapes: `review_digest`,
`incident_log`, `expense_lines`, `survey_comments`, `menu_check`,
`applicant_screen`, `delivery_feedback`, `listing_filter`),
`fast_path_ceiling_v6.py` (every item raced), `make_bench_v6_prose.py`
(12 texts per label, `mistralai/mistral-large-4-0`). No keyword-rules arm.

## Stage 1 result

Texts: 12 per label, 336 in all. 13 `menu_check` texts excluded after the hand
check: dishes with a second allergen fit two labels, and the description
gives no priority. 4 borderline texts kept with reasons. Jobs average about
7.4 readings each.

## Stage 2: the runs (frozen before any job is sent)

Both runs use `fast_path_planned_bench_v6.py`, all 8 shapes, the first 20
jobs of each stream (160 jobs). Settings as committed (`program_probes` 6,
`plan_shadow` set false so plans serve once adopted, as in earlier planner
runs).

**Run A, primary, prospective, drained arrival.** Arms R (whole-task race), C
(planning router), D (ceiling: every item raced, reference code), P (write
once with probes).

- **Primary:** P against R, shape-cluster bootstrap, 10,000 replicates, seed
  20261116. Supported only if the median-time ratio's 95% interval lies
  wholly below 1.0 and the correctness difference's wholly above -2 points.
- **Key secondary:** C against P on time and correctness. Step-by-step
  learning "wins" on hard jobs only if C is more accurate than P (interval
  wholly above zero) or faster (time-ratio interval wholly below 1.0).
- Also: P against D, first program and first plan job per shape, attempts and
  reasons for rejection, probe outcomes (probes are skipped where every input
  is read), wrong program answers split into code and reading, calls and
  tokens per arm. Expected cost about $6.

**Run B, jobs back to back.** Arms R, P and Q (write once with probes, written
early). Readings: first program job per shape for P and Q, Q against P and
against R. Expected cost about $2.

## Run A result (2026-11-18)

**Not supported.** Write once with probes: 1.11 of the race's time (1.02 to
1.20), correctness equal (-3.8 to +3.8 points). The planning router was the
least accurate arm (-21.9 points against write once) and cost three times its
calls. Run A cost $12.90 against $6 estimated; run B awaits the owner.
