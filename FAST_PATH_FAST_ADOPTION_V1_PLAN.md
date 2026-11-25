# Fast adoption V1: do programs go live sooner when jobs arrive back to back?

**Status:** FROZEN 2026-11-25, before any provider call.
**Scope:** DESCRIPTIVE. It uses the same jobs as long stream V1.

## Question

Under back-to-back arrival, programs went live late: at jobs 11 to 14 of 20 (Phase C V1),
and at 15 to 21 of 50 (long stream V1). The diagnosis is in Phase C's attempt
records:

- Writing a program takes 5 to 9 s, while a job arrives about every 2 s.
- Write-once's background work ran on 4 workers. Each observation holds a worker until
  every racer has answered, and the program write held a worker for longer still.
- So the agreed examples a program is checked against queued behind that work.

`fast_adoption` gives observation 16 workers and writes programs on a separate pool of
their own. Arm **L** is P with `fast_adoption` on.

## Run

```
python run_fast_path_planned_v1.py --bench fast_path_planned_bench_v7.py \
  --output fast_path_fast_adoption_v1.jsonl --label fast_adoption_v1 \
  --set plan_shadow=false --probes 6 --fast-adoption --arms R,P,L --jobs 50 --arrival immediate \
  --shapes parcel_postage,room_booking,tip_split,library_fines
```

These are the same 200 jobs as long stream V1, back to back.

## Readings fixed in advance

1. **Mechanism.** L's first program job per shape is compared with P's in this run. The
   fix **works** if L's is earlier on at least 3 of the 4 shapes.
2. **Primary: L against R**, using the shape-cluster bootstrap and the usual bounds. L
   is **SUPPORTED** if both hold:
   - the upper bound of the median-time ratio interval is below 1.0;
   - the lower bound of the correctness-difference interval is above −2 points.
3. **Also:** L against P on time and correctness; L's and P's accuracy before and after
   adoption; the flag; calls, rate-limit errors and cost.

## Cost and stop rules

- **Estimate: about $3.75.** R and P cost $1.65 in long stream V1. L adds about P's
  share (about $0.85). That is $2.50 before the margin; adding 50% gives $3.75.
- **Credit at freeze:** $16.81.
- **Stop rules:** the runner's provider-failure monitor.

## Result (2026-11-25)

**1. Mechanism: NOT met.** L's programs went live earlier than P's on only 1 of 4 shapes.

| Shape | P's first program job | L's first program job |
|---|---:|---:|
| parcel_postage | 11 | 10 |
| room_booking | 11 | 15 |
| tip_split | 11 | 21 |
| library_fines | 13 | 13 |

Separate pools for observation and writing did not bring adoption forward.

**2. Primary: L against R is SUPPORTED.**
- Time: 0.68 of R's (0.58 to 0.77).
- Correctness: +1.0 point (0.0 to +2.0).

L answered 197/200 right at a median of 1.11 s. R answered 195/200 at 1.64 s.

**3. P against R in this run would also pass clearly** (descriptive): time 0.64 (0.58
to 0.70), correctness +2.5 points (+2.0 to +3.5). P answered 200/200 right at 1.04 s.
Its programs went live at jobs 11 to 13, against 15 to 21 for the same arm on the same
jobs in long stream V1.

**L against P:** time 1.06 (0.99 to 1.12), correctness −1.5 points (−3.0 to 0.0).

**L's misses:**
- Two came from its program on `room_booking` (jobs 28 and 29, unflagged). The fastest
  reading racer read a meeting note as a workshop. The code was right; the reading was
  wrong.
- One came from a race before adoption, and it was flagged.
- P's unflagged answers were right 198 of 198 times.

Calls: R 1,000, P 1,338, L 1,349; 1 invalid response, no rate-limit errors. Cost about
$2.23 (estimate $3.75). Credit left: $14.58.

**Reading:**
- **The pool fix does not address the delay.** Adoption timing varies a lot from run to
  run on the same jobs: P went live at 15 to 21 jobs in one run and 11 to 13 in the
  next.
- **The delay is the end-to-end time to collect agreed examples, write a program and
  probe it.** That takes about 20 to 30 s while jobs arrive every 1 to 2 s. It is not
  worker contention.
- **`fast_adoption` stays off by default.**
- **The speed claim for calculation-heavy jobs is now backed by three back-to-back
  runs on the same jobs:**

| Run | Time | Correctness | Frozen test |
|---|---|---|---|
| P in long stream V1 | 0.66 | −2.0 to +4.0 | Not passed |
| P in this run | 0.64 | +2.0 to +3.5 | Passed (descriptive) |
| L in this run | 0.68 | 0.0 to +2.0 | Passed |
