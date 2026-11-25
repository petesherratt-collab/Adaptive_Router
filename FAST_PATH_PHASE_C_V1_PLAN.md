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
