# Source-aware JSON verifier V1 developmental plan

**Status:** offline developmental candidate

**Runtime policy authority:** none

**Promotion authority:** none

**Provider generation requests:** forbidden in this phase

**Sealed experiment changes:** forbidden

## Decision being recorded

The existing structural-JSON local-authority line based on exact keys and
declared JSON types is closed for now. Runtime v0.3 remains
remote-authoritative. A separately frozen 4B shadow experiment is deferred
until a stronger acceptance mechanism or a different research question
justifies its compute and provider cost.

The 1B experiment reached 60 contract passes and 60 potential avoided remote
calls, but 17 of the 60 contract-accepted outputs were wrong. Every locally
correct result was also remotely correct. The immediate bottleneck is therefore
not insufficient acceptance volume; it is inability to distinguish grounded
values from plausible schema-conforming errors.

## Candidate question

Can a local model be reduced from answer authority to a pointer proposer, while
deterministic code reconstructs a narrowly defined JSON result directly from
authenticated source bytes?

This is stronger than shape validation but narrower than general structural
JSON. V1 covers only flat scalar extraction from one record selected by a
unique literal. It deliberately excludes nested values, arrays, derived values,
fuzzy matching, normalization, summarisation and semantic classification.

## Trust boundary

The trusted caller supplies before generation:

- the exact UTF-8 source text and its SHA-256;
- ordered, non-overlapping record byte spans;
- a selector literal that must occur in exactly one declared record;
- exact output keys; and
- the JSON scalar type of each output value.

The untrusted candidate supplies:

- a flat scalar JSON object;
- the index of the selected record; and
- one source byte span for every output field.

The verifier must authenticate the source, identify exactly one record
containing the selector, require the candidate to select that record, require
every proof span to lie inside it, decode each span without semantic repair,
and reconstruct every value from the source bytes. A PASS returns the
deterministically reconstructed object; it does not authorize serving the raw
model output.

This mechanism is oracle-free only in the bounded sense that it receives no
expected output values. It depends on trusted source segmentation, selector,
shape and type declarations. Those are task facts, not discovered truths.

## Required adversarial behavior

The prototype must reject:

1. fabricated values;
2. selection of a record that does not contain the unique selector;
3. field splicing across records;
4. missing or additional field proofs;
5. candidate key-set drift;
6. JSON type substitution, including Boolean-as-number;
7. ambiguous selector occurrences;
8. invalid, overlapping or out-of-range record spans;
9. field spans that split UTF-8 sequences;
10. nested candidate values outside the V1 scope; and
11. duplicate JSON keys or non-finite JSON constants in file input.

## Interpretation boundary

A prototype PASS establishes only that:

- the returned flat scalars were reconstructed exactly from one authenticated,
  caller-declared record;
- that record was selected by a caller-declared literal unique across the
  declared records; and
- the candidate matched the declared top-level key and scalar-type contract.

It does not establish that the caller chose the right selector, that record
segmentation is semantically correct, that omitted source material is
irrelevant, that a same-typed source value belongs to the claimed output field,
or that the mechanism generalizes to arbitrary natural-language extraction.

An executable known-limitation fixture deliberately swaps the same-record
string values for `city` and `owner`. V1 accepts the result because both spans
are authentic, correctly typed and inside the selected record. Field-specific
source-role constraints would be required to reject that error. Supplying such
constraints may make the extraction itself deterministic, which is the review
boundary this prototype is intended to expose.

The synthetic adversarial suite tests implementation logic, not model
effectiveness, coverage, false-accept rate, cost, latency or energy. Passing it
does not produce a `VALIDATOR_CHANGE_CANDIDATE` under the earlier retrospective
screen because the sealed model outputs did not contain these proofs.

## Review gate before any new experiment

After implementation and full-suite verification, review whether the trust
requirements describe a useful real workload. V1's same-type field-role swap
shows that authenticated spans alone are not a sufficient local-authority gate.
In particular, ask whether adding the field-specific constraints needed to
close that gap already makes the target output deterministically extractable
without an LLM. If so, classify that workload as a deterministic-executor
candidate rather than spending inference on it.

Only if a nontrivial and deterministically verifiable model role remains should
a new experiment be proposed. V1 by itself does not justify one.
That successor must use fresh tasks, freeze its evidence format and adversarial
oracle before generation, keep local output non-serving, compare deployable
local-first latency with direct remote service, and use a precommitted
promotion rule. No provider call is authorized by this plan.
