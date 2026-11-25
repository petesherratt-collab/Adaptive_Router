# Long stream V1: does the speed gain carry a longer back-to-back stream?

**Status:** FROZEN 2026-11-25, before any provider call.
**Scope:** DESCRIPTIVE. The four shapes ran once in Phase C V1, so they are no longer
unseen. Jobs 1 to 20 are Phase C's jobs; jobs 21 to 50 are new.

## Question

In Phase C V1, with 20 jobs per shape arriving back to back, programs for the
calculation-heavy shapes went live only at jobs 11 to 14. Over the whole stream, the
router (P) was no faster than the race (R). After adoption it took 0.64 of R's time,
with 31/31 right. Write-once V5, also back to back but with 30 jobs per shape, took 0.65
of R's time overall.

**Over a 50-job stream, does P beat R on time overall without losing accuracy?**

## Run

```
python run_fast_path_planned_v1.py --bench fast_path_planned_bench_v7.py \
  --output fast_path_long_stream_v1.jsonl --label long_stream_v1 \
  --set plan_shadow=false --probes 6 --arms R,P --jobs 50 --arrival immediate \
  --shapes parcel_postage,room_booking,tip_split,library_fines
```

That is 4 calculation-heavy shapes × 50 jobs (seed 20261125), arms R and P as in Phase
C, back-to-back arrival.

## Readings fixed in advance

**Primary: P against R over all 200 jobs**, with the shape-cluster bootstrap and the
usual bounds. P is **SUPPORTED** if both hold:
- the upper bound of the median-time ratio interval is below 1.0;
- the lower bound of the correctness-difference interval is above −2 points.

**Also reported (descriptive):**
- the first job served by a program per shape;
- P and R on jobs from that point on: correctness and median time;
- P against R on jobs 21 to 50 only;
- P's flag: accuracy of flagged and of unflagged answers;
- calls, rate-limit errors and cost.

## Cost and stop rules

- **Estimate: about $2.70.** In Phase C, R and P cost about $1.77 for 160 jobs, and the
  one-reading shapes cost less than the many-reading ones. 200 one-reading jobs come to
  about $1.80; adding 50% gives $2.70.
- **Credit at freeze:** $18.46.
- **Stop rules:** the runner's provider-failure monitor.
