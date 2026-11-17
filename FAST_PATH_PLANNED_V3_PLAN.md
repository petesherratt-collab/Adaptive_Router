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
