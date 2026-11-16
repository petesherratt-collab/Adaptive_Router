# Fast-path timing V2 plan: harder task shapes

**Status:** FROZEN 2026-11-16. One primary run is authorized.

**Runtime policy authority:** none. Runtime v0.3 is unchanged.

This plan inherits every rule of `FAST_PATH_TIMING_V1_PLAN.md` except where
stated below. The owner asked for this run in session after the V1 runs. The
benchmark was written by the assistant and was not reviewed by the owner
before the freeze.

## Why

Across the V1 primary run and two sensitivity runs the synthesis model wrote a
correct function for every shape on its first attempt. Those runs therefore
say nothing about what happens when a synthesised function is wrong: whether
the gate rejects it, whether a wrong one is promoted and serves wrong answers,
and whether the audit removes it.

## Question

On task shapes that are easy to implement subtly wrong, does the fast path
still return answers sooner than direct single-model service without
returning materially more wrong answers, and where does it fail?

## Benchmark

`fast_path_timing_bench_v2_hard.py`: 20 new task shapes, 30 seeded requests
each (stream seed 20261117), 600 requests in 20 task clusters. No shape
appears in any earlier bank. Each reference passes its hand-written tests;
seven references were additionally cross-checked against the Python standard
library on random inputs before the freeze.

The shapes were chosen by the assistant to be error-prone. That selection is
deliberate and means results describe a hard corner, not typical work.

## Arms, settings, arrival, analysis

Unchanged from V1: arms A, B and C; `config_fast_path.json` as committed
(`min_gate_examples` 8, `audit_sample_rate` 0.1); learning drained between
requests; the same two criteria (time ratio interval wholly below 0.5,
correctness difference interval wholly above -2 points); shape-cluster
bootstrap, 10,000 replicates, seed 20261116. The runner is the current
`run_fast_path_timing_v1.py`, which stops on sustained provider failure.

With 20 clusters the intervals will be wider than in V1.

## Readings fixed in advance

Reported whatever the headline decision:

- shapes whose first synthesised function was gold-wrong, and for each whether
  the gate rejected it;
- shapes in which a gold-wrong function was promoted, the number of wrong
  answers it served, and whether and when it was demoted;
- stored examples that were gold-wrong;
- shapes never promoted, with the cause: too few agreed examples, synthesis
  attempts exhausted, or static rejection;
- arm B against arm A, as in V1.

A promoted gold-wrong function that serves any wrong answer is a gate failure
and is reported as such even if both criteria are met.

No prediction of the outcome is made. A `NOT_SUPPORTED` decision is an
acceptable and informative result.

## Sensitivity runs

As in V1: later runs on this benchmark are descriptive only.
