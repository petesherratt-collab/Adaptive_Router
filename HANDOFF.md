# Handoff: Adaptive Router fast-path work (updated 2026-11-17, second session)

Read this first. Detail: `README.md` (fast-path sections, newest at the end of
the planned-jobs part) and `BUILD_HISTORY.md` (every freeze, hash and result).

## State

- Work branch `ccr-23487558-3yzwx4` (this repo and `evolab`); not merged.
- Full suite: `python -m unittest discover -s tests` (568 tests, passing).
- OpenRouter credit left: about $4.75.
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

## Open items

- Steps that resist promotion (date arithmetic, lookups) keep plans slower
  than the race; a later synthesis retry or refinement aimed at them is the
  clearest next lever.
- A learning pair chosen for price (`openai/gpt-6-luna` +
  `deepseek/deepseek-v4.1-flash`) is untested.
- EvoLab: the next generator version should fail tasks that `scripted_code`
  already solves.
- Shared write-up and spreadsheet artifacts are not yet updated for this
  session.
