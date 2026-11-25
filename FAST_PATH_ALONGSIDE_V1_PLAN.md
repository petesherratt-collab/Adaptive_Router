# Race alongside V1: start the race and the program together, serve the first trusted answer

**Status:** FROZEN 2026-11-25, before any provider call.
**Scope:** DESCRIPTIVE. It reuses the V6 hard jobs, which have been run before.

## Question

Flag fallback V1 found the following on many-reading jobs:

- The written program was more accurate than the race: F 147/160 against R 140/160.
- The program was slower: 1.42 times the race's median time.
- Re-deciding flagged answers added time but no accuracy.

Arm S tests whether starting both at once recovers the speed without losing the
accuracy. The program and the whole-task race start together, and S serves whichever
first gives an answer worth trusting:

- the program's answer, if none of its readings was flagged; or
- the race's answer, once two racing models agree on it.

If nothing is trusted when everything has finished, S serves the flagged program
answer, marked uncertain. If the program failed, it serves the race's majority.
Before a program exists, S races as R does.

## Run

```
python run_fast_path_planned_v1.py --bench fast_path_planned_bench_v6.py \
  --output fast_path_alongside_v1.jsonl --label alongside_v1 \
  --set plan_shadow=false --probes 6 --alongside --arms R,S --jobs 20
```

This is the same 160 jobs as flag fallback V1 (stream seed 20261120), with drained
arrival. S is P with `uncertainty_gate` on and `race_alongside` on.

## Readings fixed in advance

**Primary: S against R**, using the shape-cluster bootstrap as before.

S **restores the speed advantage** if both of these hold:
- the upper bound of its median-time ratio interval is below 1.0;
- the lower bound of its correctness-difference interval is above −2 points.

These are the usual bounds, reported descriptively.

**Also reported:**
- **S's routes:** the share served by the program, the share served by the race, and
  the share served flagged, each with its accuracy and median time.
- **S's flag:** accuracy of flagged and of unflagged answers.
- **S against F and P from earlier runs:** descriptive only, because those are
  different runs on the same jobs.
- **Calls, tokens and cost.** S pays for both a race and a program on every job once a
  program exists, so its calls are reported against R's.

## The "needs review" option, measured without a run

`flag_fallback: "review"` returns a flagged answer marked for review and adds no time.
Its effect can be read off flag fallback V1's arm F without spending anything:

| | Jobs | Right |
|---|---:|---:|
| Served | 151 | 142 (94.0%) |
| Sent for review | 9 (5.6%) | 5 of these would have been right |

The median time stays at the program's (3.2 s). The fallback's 30-second tail on
those 9 answers goes away.

## Cost and stop rules

- **Estimate: about $4.70.** Flag fallback V1 cost $4.30 for 5.48M tokens. This run is
  R (0.86M) plus S (about F's 2.28M plus one race per job, 0.86M), so about 4.0M
  tokens, or about $3.10. Adding 50% gives $4.70.
- **Credit at freeze:** $26.53, shared with the change-signals key.
- **Stop rules:** the runner's provider-failure monitor.
