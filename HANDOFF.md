# Handoff: Adaptive Router fast-path work (to 2026-11-17)

Read this first in a new session. Full detail is in `README.md` (results,
newest sections near the bottom of the fast-path part) and `BUILD_HISTORY.md`
(every freeze, hash and result, in order).

## Where things stand

- All work is merged to `main` (PR #18, merge commit `e43e950`). Working branch
  was `ccr-29a53f53-nj6nlk`; this file was added on it afterwards.
- Runtime v0.3 (`router.py`, `config.json`) is unchanged. The new line sits
  beside it: `fast_path.py`, `sandbox.py`, `pipeline.py`, `planner.py`,
  settings in `config_fast_path.json`.
- Full suite: `python -m unittest discover -s tests` (558 tests, all passing).
  Needs `pip install psutil requests python-dotenv`.

## The owner's direction

- Goal reset after the closed local-authority cycle: **time** is the objective;
  **cost was dropped** as a parameter (but per-arm calls and tokens are now
  metered and reported honestly).
- Idea: an evaluator kicks work down to code (written on the fly) and up to a
  race of OpenRouter models; single steps first, then multi-step jobs.
- Complementary to the owner's `evolab` repo. The owner suggested a code-only
  arm there too (version 1.5 offline checker plus scripted client as a fifth
  condition, no provider cost); not started, needs push access to evolab.
- The owner has **no real tasks** to supply; the real-task harness
  (`real_tasks/`, `fast_path_real_bench.py`) exists but is unused.

## Working conventions used throughout

- Freeze a plan (`*_PLAN.md`) and record SHA-256 hashes in `BUILD_HISTORY.md`
  before any provider call. Reused benchmarks give **descriptive** results
  only; prospective means unseen jobs.
- Never overwrite evidence; runners write `.partial` until complete and stop on
  HTTP 401/402 or sustained failure. One run was invalidated when credit ran
  out and kept with `FAST_PATH_TIMING_V1_GATE4_EXECUTION_INCIDENT.md`.
- No model judges a function or a plan: promotion and adoption are by
  execution against agreed or caller examples (CCC finding).
- Provider calls from the cloud session go through the `adaptive-router`
  environment, where the OpenRouter key is a network secret; run scripts with
  `OPENROUTER_API_KEY=proxy-injected`. Credit left: about $13.30
  (check: `curl -sS https://openrouter.ai/api/v1/credits -H "Authorization: Bearer proxy-injected"`).
- The stop hook flags `.partial` files while a run is in progress; they are
  committed with the analysis once the run completes.

## Results in brief

Prospective (frozen before running):

| Experiment | One model | Whole-task race | Fast path / planner | Verdict |
|---|---|---|---|---|
| Single step, 30 easy shapes | 1198 ms, 824/900 | — | 30 ms, 892/900 | Passed |
| Single step, 20 hard shapes | 2964 ms, 571/600 | — | 32 ms, 598/600 | Passed |
| Multi-step, 12 small job shapes | 2218 ms | 1233 ms | 1115 ms, 240/240 | Missed speed bar |
| Multi-step, 7 large job shapes | 3786 ms | 2791 ms | 1129 ms, 105/105 | Passed (vs race) |
| Router writes own plans, 7 fresh shapes | 4275 ms | 2469 ms | 1534 ms, 104/105 | Passed (C/R 0.62) |

Descriptive follow-ups on the fresh jobs:

- Repeat with identical settings: C/R 0.91, so the 0.62 margin is not secure.
- Back to back (no pause for learning): plans served before steps were code
  (slower); shadow mode then exposed live/background pool contention; with
  separate pools the router matched the race but no plan went live in 15 jobs.
- 40 jobs per shape, back to back, `max_probes` 4: plans went live at jobs
  20, 25, 34 for 3 of 4 shapes, then about half the race's time.
- Ceiling arm D (reference code + raced reading steps): 834 ms, reading 105/105;
  the planner gets within about 1.4x of it after learning; planner learning
  costs 6.6x to 17x the race's calls.
- Boundary probes rejected 42 of 44 planted bugs; one wrong function was ever
  promoted (zero case), caught by probes since; probes found reference gaps.

## Open items, if the project continues

1. Back-to-back gains need cheaper learning or long streams; `expense_claims`
   never went live (3 of 20 steps stayed on models).
2. Version 1 code-only arm (keyword rules for reading steps) is only fair on
   unseen text; rules must be written and hashed from task descriptions before
   opening examples.
3. EvoLab code-only fifth condition (owner's suggestion).
4. More, and more varied, job shapes to narrow intervals.

## Shared artifacts (claude.ai, private until shared)

- Write-up: https://claude.ai/artifact/J7ViVmL3PyuZq4hzJWoo6G (links point to `main`).
- Spreadsheet: https://claude.ai/artifact/RpNUVkEV3QJVsWhtFaWQQq (sheets:
  Experiments, By task shape, Promotion gate, Models, Planning, Ceiling).
