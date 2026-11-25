# Agreement race V1: is waiting for two models to agree what made the race more accurate?

**Status:** FROZEN 2026-11-25, before any provider call.
**Scope:** DESCRIPTIVE. It reuses the V6 hard jobs, which have been run before.

## Question

In race alongside V1, arm S was 147/160 right against the plain race's (R) 140/160.
The race served 137 of S's answers, each one after two models had agreed, and 129 of
those were right. The program served only 23. That points to agreement, not the
written program, as the source of the gain. The run could not separate the two,
because it had no race that waited for agreement without a program.

Arm **G** is that race:

- the whole task is raced across the five models;
- G serves the first answer that two models agree on, and there is no program;
- if the race ends with no two agreeing, G serves the most common answer, marked
  uncertain.

## Run

```
python run_fast_path_planned_v1.py --bench fast_path_planned_bench_v6.py \
  --output fast_path_agreement_v1.jsonl --label agreement_v1 \
  --set plan_shadow=false --agreement --arms R,G --jobs 20
```

This is the same 160 jobs (stream seed 20261120), with drained arrival.

## Readings fixed in advance

**Primary: G against R**, using the shape-cluster bootstrap. Report the correctness
difference and the median-time ratio, each with its 95% interval.

The finding **"agreement alone gives the accuracy gain" is confirmed** if both hold:
- the lower bound of G − R correctness is above 0;
- G's accuracy is within 2 points of S's 147/160 in race alongside V1.

The second comparison is descriptive only, because it comes from a different run on
the same jobs.

**Also reported:**
- the share of G's answers served without agreement (no two models agreed), and their
  accuracy;
- G's median time against R's, and against S's 2.93 s from the earlier run;
- calls and cost.

## Cost and stop rules

- **Estimate: about $2.10.** G and R each make one five-model race per job, so about
  1.72M tokens. The last run cost about $0.81 per million tokens, giving $1.40; adding
  50% gives $2.10.
- **Credit at freeze:** $23.45.
- **Stop rules:** the runner's provider-failure monitor.

## Result (2026-11-25)

**Not confirmed.** Agreement alone did not give the accuracy gain.

| Comparison | Result | 95% interval |
|---|---|---|
| G against R, correctness | +1.25 points | −3.1 to +6.3 |
| G against R, median time | 1.24 times R's | 1.18 to 1.34 |

- **Correctness:** G answered 144/160 right and R 142/160. The interval's lower bound
  is not above 0, so the first condition fails.
- **Against S:** G was within 2 points of S's 147/160 (1.9 points), so the descriptive
  condition holds.
- **Agreement:** two models agreed on every one of the 160 jobs, so none was served
  unagreed.

**Correction to the reading of race alongside V1.** That run's route breakdown (race
answers 129/137 right) was confounded by selection. The race served the jobs where two
models agreed before the program finished, and that is not a random subset. Taken
across runs on these same jobs, every arm that uses the written program scored about
the same, and every whole-task race scored lower:

| Arm | Run | Right |
|---|---|---|
| P (program) | reading fixes | 147 |
| F (program, flag fallback) | flag fallback | 147 |
| M (program, majority readings) | flag fallback | 148 |
| S (program raced alongside) | alongside | 147 |
| R (race) | four runs | 144, 140, 140, 142 |
| G (race to agreement) | this run | 144 |

**Revised reading:** on these jobs the program, which reads each item separately, gives
roughly 3 to 7 points of accuracy over racing the whole task. Waiting for agreement
adds about 1 point and is not significant. Every program variant tried so far costs
1.1 to 1.4 times the race's time.

Calls: R 800, G 800; 11 invalid responses. Cost about $1.77 (estimate $2.10).
Credit left: $21.68.
