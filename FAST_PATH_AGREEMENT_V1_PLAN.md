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
