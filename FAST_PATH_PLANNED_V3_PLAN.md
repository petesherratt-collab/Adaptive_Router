# Fast-path planned jobs V3: fresh, more varied jobs and a code-only arm

**Status:** stage 1 FROZEN 2026-11-17 (benchmark, reading rules, ceiling
steps and the prose prompt). The run itself is frozen in stage 2, below,
before any job is sent to a provider.

**Scope:** PROSPECTIVE. No model has seen these jobs, and nobody had seen the
reading texts when the code-only rules were written.

This covers items 2 and 4 of the 2026-11-17 handoff, which the owner asked to
be worked through in order.

## Why one benchmark serves both items

- Item 4 asks for more, and more varied, job shapes to narrow the intervals.
- Item 2 asks for a code-only arm: ordinary code for the whole job, keyword
  rules included for the reading steps. That comparison is fair only on text
  nobody has seen, so the rules must be written and hashed from the task
  descriptions before the texts exist.

## Stage 1 order (each step hashed before the next)

1. `fast_path_planned_bench_v3.py`: 8 new job shapes (`ticket_queue`,
   `room_bookings`, `recipe_scaling`, `fleet_fuel`, `library_loans`,
   `sensor_alerts`, `invoice_vat`, `event_rsvps`). Inputs vary more than V2:
   text lines, JSON arrays of numbers, JSON arrays of objects, plain numbers
   and dates. Each has one prose field and a different reading (urgency,
   department, diet, vehicle issue, library request, site, delivery country,
   formality), several of them indirect. Gold is by construction from a
   reference function per shape, qualified by hand-worked tests.
2. `fast_path_code_only_v1.py`: keyword rules per reading, written by the
   assistant from the descriptions alone. The only thing assumed about the
   texts is that they are short English messages of the kind each
   description names.
3. `fast_path_ceiling_v3.py`: the ceiling arm's reading-step specifications,
   from the descriptions.
4. `make_bench_v3_prose.py`: the prompt that writes the texts, 12 per label,
   one call per shape, to `mistralai/mistral-large-4-0`, a model outside the
   race roster. The prompt asks for natural, varied messages that a careful
   reader can assign to exactly one label; it does not ask to avoid or to use
   any word.

After the hash of steps 1 to 4 is recorded, the prose is generated and kept
verbatim. Before any rule or model reads it, the assistant reads every text
and excludes any whose planted label is not clearly right, or that fits
another label too; exclusions are recorded in the prose file with reasons.
The prose file's hash is recorded after the check. Only then are the rules
scored on the texts (no provider cost): accuracy per shape and overall, on
every distinct text and on the job stream.

The rules are not changed after the texts are opened. Any later version is a
version 2 and is scored only on new unseen text.

## Stage 1 result: code-only rules on unseen text (no provider cost)

After the hand check (no exclusions; hashes in `BUILD_HISTORY.md`),
`score_code_only_v1.py` scored the frozen rules: 293 of 324 distinct texts
(90.4%) and 220 of 240 jobs on the 30-job stream (91.7%). By shape, texts:
`ticket_queue` 24/24, `room_bookings` 43/48, `recipe_scaling` 29/36,
`fleet_fuel` 47/48, `library_loans` 39/48, `sensor_alerts` 48/48,
`invoice_vat` 41/48, `event_rsvps` 22/24. The misses are complaints worded
without a complaint word, places the lists lack (Maynooth, Dún Laoghaire,
Marbella, Fuengirola, carriers), negations ("I'm not vegan"), and department
meetings described only by their subject. The rules stay as frozen.

## Stage 2: the run (frozen before any job is sent)

**Question (primary, as in V2):** on fresh and more varied jobs, does the
planning router answer sooner than racing the whole task across the roster,
without returning materially more wrong answers?

**Jobs:** `fast_path_planned_bench_v3.py`, all 8 shapes, the first 20 jobs of
each stream (`--jobs 20`), 160 jobs in 8 task clusters.

**Arms**, order randomised per job (seed 20261117):

- A: one direct call (`openai/gpt-5.6-luna`);
- R: the whole-task race;
- C: the planning router from an empty store;
- D: the ceiling, `fast_path_ceiling_v3.py` reading steps raced, reference
  code for the rest (a ceiling, not a baseline: only its time and reading
  accuracy inform);
- E: code only, `fast_path_code_only_v1.py` rules and the reference code, no
  provider call. Its mechanical work is correct by definition, like D's; it
  differs from D only in who reads.

**Settings:** `config_fast_path.json` as committed, with `plan_shadow` set to
false, so that plans serve once adopted as in the frozen V2 primary run
(`job_agreement_min` and `learning_models` stay null, `max_probes` 12).
Arrival drained, as in V2. Four shapes at a time.

**Primary analysis:** `analyze_fast_path_planned_v1.py`, C against R,
shape-cluster bootstrap, 10,000 replicates, seed 20261116. Supported only if
the median-time ratio's 95% interval lies wholly below 1.0 and the
correctness difference's lies wholly above -2 points.

**Code-only test (secondary, fixed now):** the research endpoint's rule that a
model-based approach must beat ordinary code. E answers in well under a
millisecond, so no model arm can beat it on time; the test is on
correctness. A model arm beats code only if its correctness minus E's has a
95% interval wholly above zero. Reported for R, C and D (D against E isolates
the reading). Expected from stage 1: E about 148 of 160 (the rules get 148 of
the 160 stream labels right).

**Readings fixed in advance:** as in V2 (C against A, per-shape results,
plans adopted, rejected and refined, promoted steps, first plan job per shape,
wrong job examples, demotions, any shape where C is slower than R with its
reason), plus D and E reading accuracy per shape and calls and tokens per arm
and purpose.

**Execution:** `run_fast_path_planned_v1.py --bench fast_path_planned_bench_v3.py
--jobs 20 --ceiling fast_path_ceiling_v3.py --code-only fast_path_code_only_v1.py
--set plan_shadow=false --label v3_primary`. Stops on HTTP 401 or 402 or
sustained provider failure. Credit at the freeze: about $8.75; the run is
expected to cost about $4.5.

## Result (2026-11-17)

**Primary: NOT SUPPORTED.** C/R median-time ratio 1.06 (95% interval 0.68 to
1.44); correctness C minus R +1.9 points (+0.6 to +3.7). The planner was more
accurate than the race but not faster overall: one shape got no plan, and two
kept three unpromoted steps (date arithmetic, floor lookups) that ran on the
models in a chain. Over the last five jobs per shape C was faster (1186 against
1834 ms), as plans finished learning.

**Code-only test:** E 148/160. C and D beat it on correctness (intervals above
zero); R did not (-0.6 to +9.4 points). Full figures in `BUILD_HISTORY.md`.
