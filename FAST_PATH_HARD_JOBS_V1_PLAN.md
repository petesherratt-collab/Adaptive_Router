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
