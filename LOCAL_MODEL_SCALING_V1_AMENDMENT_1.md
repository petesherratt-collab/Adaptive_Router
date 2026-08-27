# Local Model Scaling Comparison v1 — Amendment 1

Date: 2026-08-27  
Status: pre-execution amendment  
Original preregistration commit: `19ac907`

## Reason for amendment

An external review after preregistration, but before any 1B or 4B evidence
collection, identified that the original analysis reported accuracy and latency
without applying the live router's post-generation gates.

This amendment adds a derived operational comparison. It does not change model
selection, order, prompts, repetitions, evidence collection, strict oracle,
primary outcome, or stopping rules.

## Derived post-generation gate simulation

For every frozen 270M observation and every new 1B and 4B observation, replay
the committed post-generation gate sequence:

1. generation succeeded;
2. `ttft_ms` is absent or no greater than the committed
   `maximum_ttft_ms` of 8,000;
3. `tokens_per_second` is absent or no lower than the committed
   `minimum_generation_rate` of 1.5;
4. the production validator at the execution revision does not return `FAIL`.

The missing-value behaviour deliberately matches `router.py`: absent TTFT or
throughput does not itself trigger escalation. Missing timing values must also
be counted explicitly so this behaviour remains visible.

Apply gates in production order and assign each rejected observation its first
applicable rejection reason:

- `GENERATION_FAILED`;
- `TTFT_EXCEEDED`;
- `GENERATION_TOO_SLOW`;
- `VALIDATOR_FAILED`;
- otherwise `SURVIVED`.

## Required reporting

For each model, report:

- observation count;
- post-generation survivor count and rate;
- strict pass count and rate among survivors;
- false-accept count: survived but failed the strict oracle;
- rejected-correct count: rejected but passed the strict oracle;
- first-rejection-reason counts;
- missing-TTFT and missing-throughput counts;
- all of the above separately for resident and non-resident observations;
- unknown-residency count separately.

This derived result is secondary. Overall strict accuracy remains the primary
descriptive comparison.

## Scope boundary

This is a **post-generation gate simulation**, not full live-router survival.

It cannot reproduce:

- prompt classification and local eligibility;
- preflight RAM or active-swap rejection;
- probe behaviour;
- remote fallback success;
- arbitrary production traffic.

In particular, the frozen suite uses supplied task classes and capability
families. Some classification tasks are not locally reachable through the
current production classifier, and `NOT_APPLICABLE` validator results survive
the current router because only explicit `FAIL` causes escalation.

The simulation therefore answers:

> Assuming this observation reached local generation, would its recorded
> generation and output have survived the committed post-generation gates?

It does not answer whether the live router would have selected the model.

## Validator version boundary

The derived validator replay uses the fail-closed validator merged in PR #1,
commit `d83d5c6`, and present on `main` through merge commit `a40a4fa`.

This validator is intentionally weaker than the strict benchmark oracle.
Required-key presence and JSON syntax do not establish value correctness or
value types. Consequently, false accepts must be reported rather than treating
gate survival as correctness.

## Evidence boundary

No 1B or 4B benchmark requests had been made when this amendment was written.
Dry runs only had occurred, and all four future evidence/summary files were
absent.

The frozen 270M evidence and its SHA-256 remain unchanged.
