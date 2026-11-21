# Adaptive Router roadmap

**Drafted:** 2026-11-21. **Status:** Phase A done; line **paused** 2026-11-21 for want of a
real repeated task (`RESEARCH_PAUSE_2026-11-21.md`).

The roadmap covers the fast-path line (started 2026-11-15). The earlier
local-authority line closed on 2026-09-22 (`RESEARCH_ENDPOINT_2026-09-22.md`)
and is not on it.

## Goal

Answer repeated tasks sooner than asking models every time, by moving the work
that code can do into verified code and racing models only for what needs
reading. **Time is the objective; cost is not**, though calls and spend are
metered and the remaining credit is a hard limit.

Rules that hold throughout:

- No model judges code, plans or answers. Adoption is by execution against
  answers the racing models agreed on.
- Every experiment is frozen and hashed before its first provider call.
  Results on reused jobs are descriptive; only unseen jobs are prospective.
- Evidence is never overwritten.

## Where we are

| Stage | Status | Evidence |
|---|---|---|
| 1. Single steps turned into code | **Done.** Passed prospectively on easy and hard step shapes (about 40x to 90x faster than one model). | README, timing V1 and V2 |
| 2. Multi-step jobs with given plans | **Done.** Passed on large jobs; missed the speed bar on small ones. | Jobs V1, V2 |
| 3. Router writes its own step plans | **Superseded.** Passed once, margin not secure; lost every later comparison. | Planned jobs V1 to V3 |
| 4. Write the whole job once | **Current path** (`main.py --task-json`). Prospective: one pass (0.50 of the race's time, +2.1 points), one fail (a rounding rule). | Write-once V1 to V3 |
| 5. Jobs with many readings each | **Open.** Write-once loses its speed edge; the planner does worst; batching cut calls but cost accuracy; the uncertainty flag separates good answers from bad (94% against 18% right). | Hard jobs V1, reading fixes V1 |
| 6. Real tasks | **Paused** (no repeated task). Bank transaction categories (owner's Monzo export): hybrid 94.9% against code 84.6% and models 63.6%, a model needed for 3% to 16% of transactions. | `REAL_BANK_V1_PLAN.md` |

Side line: EvoLab's code-only condition is done (evolab PR #1).

## Next phases

### Phase A: consolidate (no provider cost)

- Merge Adaptive_Router PR #19 and evolab PR #1 after review.
- Turn the uncertainty gate on by default for write-once; leave batching and
  narrow racing off (they cost accuracy).
- Remove or archive the superseded planner path from the default code paths,
  keeping it for the record.

**Done when:** `main` holds the current path, and the defaults match the
evidence. **Done 2026-11-21:** gate on, batching and narrow racing off; the planner
was already off the default path (`planner.py` kept, marked superseded).

### Phase B: make the flag pay (about $3 to $5)

- Serve unflagged answers from the program; send flagged ones to a fallback
  (the full whole-task race, or "needs review").
- Measure on the hard jobs: accuracy of what is served unflagged, share of
  answers flagged, and time including the fallback.
- Then test batching and narrow racing separately, to see which one cost
  accuracy, and keep only what does not.

**Done when:** a frozen run shows served answers at least as accurate as the
race, with a stated share flagged.

### Phase C: prove it on unseen work (about $6 to $8)

- A prospective run of the Phase B design on fresh job shapes, mixing one- and
  many-reading jobs, with jobs arriving back to back.
- First measurement of early writing (`write_early`), built but never tested.

**Done when:** the frozen primary test passes on unseen jobs under live
arrival, or fails with a stated reason.

### Phase D: real work (cost depends on the tasks)

- Run the router on tasks the owner actually repeats, through `real_tasks/`.
  This is the test every earlier result stands in for. Started 2026-11-21
  with bank transaction categories; next on the same data: the monthly or
  weekly spending summary as a whole job (race against write-once), and the
  router itself learning the merchant table (an answer cache for agreed
  answers) instead of a table built by hand.
- Without real tasks, the project ends at Phase C with a bounded claim, as the
  first line did on 2026-09-22.

**Done when:** a frozen run on real tasks gives a decision, or the owner
closes the line.

## Not on the roadmap

- Local models serving answers (closed 2026-09-22).
- Step-by-step plan learning as the main path (superseded by write-once).
- Cost as an objective (dropped by the owner).

## Open questions for the owner

1. Is there a source of real repeated tasks, even a small one? Phase D depends
   on it.
2. Is "needs review" an acceptable answer for flagged cases, or must every
   request get an answer?
3. What credit is available? Recent estimates have run up to twice the actual
   cost, so each phase is priced from the last comparable run plus 50%.
