# Phase C V1: write-once on unseen job shapes, both kinds mixed, jobs back to back

**Status:** FROZEN 2026-11-25, before any provider call.
**Scope:** PROSPECTIVE. All eight job shapes are new (`fast_path_planned_bench_v7.py`,
frozen before its prose, prose written by a model outside the race roster and hand
checked: 288 texts, 1 excluded).

## Question

Does the current design hold on job shapes it has never seen, when jobs arrive back to
back rather than one at a time? The design is write once with probes, with the
uncertainty flag on as a filter and no fallback (Phase B's outcome).

- **Primary:** is the router (arm P) faster than the whole-task race (R) without losing
  accuracy?
- **Also:** the same comparison for each family separately, and the first measurement
  of writing the program on first sight (`write_early`, arm Q).

## Run

```
python run_fast_path_planned_v1.py --bench fast_path_planned_bench_v7.py \
  --output fast_path_phase_c_v1.jsonl --label phase_c_v1 \
  --set plan_shadow=false --probes 6 --early --arms R,P,Q --jobs 20 --arrival immediate
```

The run covers all 8 shapes, with 20 jobs each from stream seed 20261125.

| Arm | What it does |
|---|---|
| R | Races the whole task and serves the first valid answer |
| P | Write once with 6 edge-case probes, `uncertainty_gate` on (from `config_fast_path.json`). A flagged answer is served and marked, with no fallback |
| Q | P with `write_early`: the program is written and probed as soon as a shape is first seen |

**Arrival is immediate:** the next job starts without waiting for background learning
to finish.

## Readings fixed in advance

**Primary: P against R over all 8 shapes**, using the shape-cluster bootstrap and the
usual bounds. It is **SUPPORTED** if both hold:
- the upper bound of the median-time ratio interval is below 1.0;
- the lower bound of the correctness-difference interval is above −2 points.

**Secondary (descriptive):**
- **P against R by family** (one-reading, many-reading), using the same bounds and
  `analyze_phase_c.py`.
- **Q against P and Q against R:** time, correctness, and the first job served by a
  program per shape.
- **P's flag as a filter:** the accuracy of unflagged and of flagged answers, and the
  share flagged.
- **Calls, tokens and cost** per arm.

## Expectations, stated before the run (not criteria)

| Family | Expected result for P against R |
|---|---|
| One-reading | Faster, and at least as accurate (as in write-once V5) |
| Many-reading | More accurate and slower (as on the V6 jobs, 1.1 to 1.4 times the race's time) |

The overall primary result depends on how those two balance, and could go either way.

## Cost and stop rules

- **Estimate: about $4.50.**
  - On the V6 jobs, P cost about $1.66 per 160 many-reading jobs. One-reading jobs cost
    roughly a third as much.
  - Here P comes to about $1.15, Q about $1.15 and R about $0.70, so about $3.00.
  - Adding 50% gives $4.50.
- **Credit at freeze:** $21.50, shared with the change-signals key.
- **Stop rules:** the runner's provider-failure monitor. With immediate arrival, the
  rate-limit errors seen before (56 of them in race alongside V1) are recorded, not
  retried beyond the client's own attempts.

## Result (2026-11-25)

**Primary: NOT SUPPORTED.**

| Comparison | Result | 95% interval | Bound met? |
|---|---|---|---|
| P against R, median time | 1.18 times R's | 1.05 to 1.31 | No (upper bound must be below 1.0) |
| P against R, correctness | +0.6 points | −2.5 to +3.8 | No (lower bound must be above −2) |

P answered 157/160 right at a median of 2.20 s; R answered 156/160 at 1.86 s.

**The race was unusually accurate on these shapes (97.5%).** That left the program
little accuracy to add.

**By family, with the same bounds (descriptive):**

| Family | P against R, time | P against R, correctness | Right |
|---|---|---|---|
| One-reading | 1.10 (0.91 to 1.29) | −1.2 points (−3.7 to 0) | P 79/80, R 80/80 |
| Many-reading | 1.30 (1.23 to 1.41) | +2.5 points (−2.5 to +7.5) | P 78/80, R 76/80 |

The many-reading result is slower, as expected. Its accuracy gain is not significant.

**Why the one-reading family did not show a speed gain: programs were adopted late.**
With jobs arriving back to back, P's first program-served job per shape came at
index 11 to 14 of 20 on the one-reading shapes. Racing the first jobs is what produces
the agreed examples a program is checked against. Drained arrival adopted at job 2 to
4 (write-once V3, the same design). So most one-reading jobs in this run were plain
races.

**After adoption (descriptive, not a criterion), on the jobs from P's first program
job onward:**

| Family | Jobs | P right | R right | P median | R median | P time as a share of R's |
|---|---:|---:|---:|---:|---:|---:|
| One-reading | 31 | 31 | 31 | 1.02 s | 1.60 s | 0.64 |
| Many-reading | 52 | 52 | 50 | 2.98 s | 2.23 s | 1.34 |

Every answer the program served was right: 83 out of 83.

**The flag as a filter:**
- P: unflagged answers right 154 times out of 155; flagged answers right 3 of 5.
- Q: unflagged right 156 of 156; flagged right 3 of 4.

**Early writing (Q) did not help:**
- Q against P on time: 1.04 (0.90 to 1.12).
- Q adopted no earlier on most shapes, and never adopted a program for `room_booking`.
- Q was slightly more accurate: 159/160, +1.3 points against P (0.0 to +2.5).

**Rate limiting:** there were 274 HTTP 429 errors under back-to-back arrival. They slow
every arm, but they fall most on the program arms, which make more calls.

Calls: R 800, P 3,299, Q 3,417. Cost about $3.04 (estimate $4.50). Credit left:
$18.46.

**Reading.** On unseen shapes the design stays accurate, and its answers are trusted
correctly: unflagged answers were 99% right. Its speed gain on one-reading jobs is
real once a program exists (0.64 of the race's time). Under back-to-back arrival,
though, it takes about half of a 20-job stream to get there, so a short stream shows
no gain. On many-reading jobs it is slower, as found before. The prospective claim the
evidence supports is therefore conditional: **faster on calculation-heavy jobs once a
job type has repeated enough to adopt a program, not faster on reading-heavy jobs.**
