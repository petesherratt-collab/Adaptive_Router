# Handoff: Adaptive Router fast-path work (updated 2026-11-18)

Read this first. Detail: `README.md` (fast-path sections, newest at the end of
the planned-jobs part) and `BUILD_HISTORY.md` (every freeze, hash and result).

## State

- Work branch `ccr-23487558-3yzwx4` (this repo and `evolab`); not merged.
- Full suite: `python -m unittest discover -s tests` (568 tests, passing).
- OpenRouter credit left: about $7.45.
- Conventions unchanged: freeze and hash before provider calls; never
  overwrite evidence; promotion and adoption by execution, never by a model.

## This session (the four open items of the previous handoff)

1. Cheaper learning (follow-up 7, descriptive): `learning_models` setting
   (two-model roster for background learning) and per-purpose call metering.
   Learning calls halved; time and money did not improve (the chosen pair
   includes the dearest model). Run-to-run plan variation dominates.
2. Code-only arm v1: keyword rules frozen before the texts existed
   (`fast_path_code_only_v1.py`); 293/324 texts right offline.
3. EvoLab fifth condition `scripted_code` (amendment 0.1-G, new files only;
   frozen manifests still verify): Brier 0 on all nine sealed development
   tasks at minimum cost, no provider calls. No model condition beat it.
4. Planned jobs V3, prospective, 8 new varied shapes, arms A/R/C/D/E:
   primary NOT SUPPORTED on time (C/R 1.06, 0.68 to 1.44), correctness
   +1.9 points (holds). C and D beat code-only on correctness; R did not.

## 2026-11-18

5. Write-once arm (`write_once.py`, descriptive on V3 jobs): one model writes
   the whole job, kept only if it reproduces two agreed answers. All 8
   programs adopted at the first attempt (jobs 3 to 6); 0.52 of the race's
   time, 1.1 times the ceiling's, 948 calls against the planner's 8,393.
   **The most important result so far: step-by-step learning is beaten.**
6. Repair V1: stuck steps have ample agreed examples but their code mismatches
   (structured list outputs); an optional repair (`repair_attempts`) did worse.
7. Shared write-up and spreadsheet updated with everything above.

8. Write-once on unseen jobs: V4 (prospective) not supported on correctness
   (a half-cent rounding rule, also missed by the planner); edge-case probes
   added (`program_probes`); V5 (prospective) **supported**: 0.50 of the
   race's time, +2.1 points, level with the ceiling; back to back 0.65,
   programs live after 11 to 22 jobs. Probes have caught nothing yet.

## Open items

- Write-once now has two prospective tests (one failed on a rounding rule, one
  passed) and a back-to-back run: the case for replacing the planner with it
  is strong. Next: make it the multi-step path in code, shorten its start-up
  under live traffic, and find a job a model cannot write whole.
- Jobs a model cannot write whole are where step learning could still matter;
  none has been found yet.
- A learning pair chosen for price (`openai/gpt-6-luna` +
  `deepseek/deepseek-v4.1-flash`) is untested.
- EvoLab: the next generator version should fail tasks that `scripted_code`
  already solves.
