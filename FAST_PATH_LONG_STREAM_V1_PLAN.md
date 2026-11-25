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

## Result (2026-11-25)

**NOT SUPPORTED under the frozen rule, by the narrowest margin.**

| Reading | Result | 95% interval | Bound | Met? |
|---|---|---|---|---|
| Time, P against R | 0.66 | 0.62 to 0.72 | Upper bound below 1.0 | Yes |
| Correctness, P minus R | +1.0 point | −2.0 to +4.0 | Lower bound above −2 points | No: it falls exactly on −2.0 |

P answered 198/200 right at a median of 1.10 s; R answered 196/200 at 1.66 s.

**Adoption under back-to-back arrival was still late.** The first program job per shape
was 15, 20, 21 and 15.

**Descriptive readings:**

| Jobs | P | R | Time ratio | Correctness, P minus R |
|---|---|---|---|---|
| From adoption on (129 jobs) | 129/129 right, 1.01 s | 125/129 right, 1.64 s | | |
| 21 to 50 only (120 jobs) | 120/120 right, 1.01 s | 116/120 right, 1.65 s | 0.61 (0.56 to 0.69) | +3.3 points (0.0 to +6.7) |

- Every answer the program served was right: 129 of 129.
- Unflagged answers were right 194 of 194 times; flagged answers 4 of 6.

Calls: R 1,000, P 1,358; 1 invalid response, no rate-limit errors. Cost about $1.65
(estimate $2.70). Credit left: $16.81.

**Reading:**
- **Over a 50-job stream the router took two-thirds of the race's time,** which settles
  the speed question for calculation-heavy jobs.
- **Accuracy was not shown to be no worse.** The interval's lower edge sits exactly on
  the bound. All of P's misses came from races before adoption. Once the program was
  live, it was never wrong in this run.
- **Late adoption remains the cost:** 15 to 21 jobs.
