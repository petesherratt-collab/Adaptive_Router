# Fast-path timing V1 `min_gate_examples=4` execution incident

**Date:** 2026-11-16

**Run:** `fast_path_timing_v1_gate4.jsonl`, label `min_gate_examples_4`,
override `min_gate_examples` 8 to 4, arrival drained.

**Status:** INVALID for any arm comparison. Partial descriptive use only.

## What happened

The OpenRouter account ran out of credits while the run was in progress. The
provider began answering HTTP 402, "Insufficient credits". The runner treats a
failed call as an unanswered request and continued to the end, so the file
carries a `COMPLETED` footer although the run was not sound.

After the run the account reported total credits 400 and total usage 400.20.
The key used by this session had spent 3.31 in total across every run on this
line.

## Extent

Unanswered requests out of 900 per arm: direct 451, race only 124, fast path
53. The direct arm began failing in the fourth shape and failed on every
request from the twenty-fourth shape onward. The race-only arm began failing
at the twenty-fourth shape. The fast-path arm failed only in the last two
shapes, `popcount` and `floor_multiple`, which were never promoted.

The early-stop rule examines only the first three shapes, which were clean,
so it did not trigger. Request rows do not record the provider error code;
the cause was established by direct probes after the run.

## What may and may not be read from the file

Not usable: every time ratio, correctness difference, interval and decision
in `fast_path_timing_v1_gate4_analysis.json`. The direct arm is missing half
its answers, so the printed `SUPPORTED` is meaningless.

Usable with caution, as a description of the 28 shapes in which the fast-path
arm had no unanswered request:

- all 28 were promoted on the first synthesis attempt;
- every promoted function was gold-correct on its hand-written tests and its
  full request stream;
- 720 requests were served by code, none wrong; no stored example was wrong
  and no function was demoted;
- the first code-served request had median index 4 and latest index 7.

Even this is weaker than it looks: as racers failed, agreement was formed by
fewer models than in the primary run, and the roster in effect drifted during
the run.

## Follow-up

- The run must be repeated in full on a funded account before any statement
  about `min_gate_examples=4` is made.
- The runner should record the provider error per request and stop when the
  failure rate rises mid-run, not only in the first three shapes.
- No further provider call is made on this line until the owner has added
  credit.

| Artifact | SHA-256 |
|---|---|
| `fast_path_timing_v1_gate4.jsonl` | `da79b9c428a2c8db6d39e1aab8c98c47945e67de260dba83eee508b3c2927126` |
| `fast_path_timing_v1_gate4_analysis.json` | `20dcde7dcc8a788124af23edfd9ccd8aa1ab1fcfb40772037039b0b92e07f87c` |
