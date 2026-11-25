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
