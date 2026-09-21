# Verifiable-witness routing V1 developmental plan

**Status:** provider-free developmental framing

**Runtime policy authority:** none

**Promotion authority:** none

**Provider generation requests:** forbidden in this phase

**Local model generation requests:** forbidden in this phase

**Runtime integration and sealed-experiment changes:** forbidden

## Decision being recorded

The structural-JSON local-authority line is closed for now. Exact keys and
types admitted semantically wrong values, and source-aware byte spans still
admitted same-typed field-role swaps. Adding enough trusted field semantics to
repair extraction may make deterministic code capable of producing the answer
without a model.

V1 therefore changes the task family rather than tuning the failed acceptance
rule. It investigates outputs that are expensive or nontrivial to find but
cheap and complete to verify from a trusted, machine-readable problem
definition. This is a developmental architecture review, not an experiment
freeze.

## Candidate question

Can an untrusted model propose a useful combinatorial assignment witness while
deterministic code independently verifies every condition that defines task
success, without receiving an expected answer and without reconstructing the
witness itself?

The candidate is not granted authority because it is local, confident,
well-formed or source-grounded. Authority would derive only from a complete
task-specific verifier over the submitted witness.

## V1 task family

V1 is limited to finite assignment problems supplied as structured data. A
problem contains stable entity and slot identifiers plus explicit constraints
drawn from an allowlist:

- every required entity is assigned exactly once;
- each assignment uses a declared entity and slot;
- slot capacities are not exceeded;
- eligibility allowlists are obeyed;
- declared fixed assignments are preserved;
- declared pairs are colocated or separated as required; and
- any declared minimum-coverage counts are met.

The candidate returns only a strict JSON assignment witness. Natural-language
interpretation, inferred constraints, executable code, free-text
justifications, hidden business rules and open-ended optimization are outside
V1. Feasibility is the initial success claim. Optimality must not be claimed
unless a later plan defines a separately checkable optimality certificate.

Multiple witnesses may be valid. The verifier receives no expected assignment
and must not compare against a canonical answer.

## Trust boundary

Trusted input, fixed before candidate generation, consists of:

- the exact problem document and its SHA-256;
- a versioned schema and constraint allowlist;
- unique entity and slot identifiers;
- all constraints that define success; and
- explicit resource bounds for parsing and verification.

The untrusted candidate supplies only the assignment witness. The verifier
must parse it strictly, reject duplicate JSON keys and non-finite constants,
canonicalize identifiers without semantic repair, and check every declared
constraint directly against the trusted problem.

A PASS may return a canonicalized witness reconstructed from the parsed
assignments. It must never execute candidate text, import candidate code,
consult a model, infer omitted constraints or silently repair a failure.

## What a PASS would establish

Within the versioned V1 problem language, PASS means that the submitted
assignment satisfies every declared feasibility constraint. It does not mean
that the structured problem accurately represents a real-world need, that
important constraints were not omitted by the caller, that the witness is
optimal, or that the mechanism generalizes beyond the declared language.

This is stronger than a conformance contract because the verifier checks the
property that defines bounded task success. The guarantee remains conditional
on the caller-authored problem specification.

## Deterministic-solver baseline and collapse gate

The same structured problem must be given to a deterministic baseline that
uses no model. The first implementation may use bounded exhaustive search or
backtracking from the Python standard library; later solvers must be identified
and version-pinned.

The model path has no research justification if ordinary code reliably finds
valid witnesses within the relevant latency and resource envelope. The review
must record separately:

- verifier cost;
- deterministic-solver success and cost;
- whether a simple greedy policy suffices;
- whether instance construction accidentally encodes a solution; and
- whether prompt rendering contributes information absent from the trusted
  problem.

If the deterministic baseline dominates, classify the family as a
`DETERMINISTIC_EXECUTOR_CANDIDATE`. Do not make instances artificially large
merely to preserve a role for a model.

## Required adversarial behavior

The verifier must reject at least:

1. missing, duplicated or additional entity assignments;
2. unknown entity or slot identifiers;
3. capacity overflow;
4. ineligible assignments;
5. violations of fixed, colocation or separation constraints;
6. unmet coverage constraints;
7. malformed JSON, duplicate keys and non-finite constants;
8. wrong schema or problem identity;
9. candidate-supplied constraints or attempts to weaken trusted constraints;
10. free text or executable content outside the witness schema; and
11. witnesses that exploit ordering, Unicode ambiguity or identifier coercion.

Negative fixtures must include failures that preserve valid JSON shape. Tests
must demonstrate that rejection follows from constraint violation rather than
mere formatting differences.

## Developmental deliverables

This phase may produce only:

1. a versioned problem and witness schema;
2. a deterministic verifier with stable reason codes;
3. a deterministic solver baseline;
4. synthetic valid, invalid and adversarial fixtures;
5. unit tests proving the bounded verifier semantics; and
6. a review recording whether any nontrivial model role remains.

It must not modify `router.py`, `runtime_contracts.py`, `config.json`, runtime
defaults, sealed benchmarks or sealed evidence. It must not call Ollama,
OpenRouter or another generation provider.

## Review outcomes

Development ends with exactly one of these conclusions:

- `DETERMINISTIC_EXECUTOR_CANDIDATE`: ordinary code should perform the work;
- `VERIFIER_BOUNDARY_INCOMPLETE`: the checker cannot certify the claimed task;
- `NO_USEFUL_WORKLOAD`: the bounded language is correct but not useful; or
- `PROSPECTIVE_EXPERIMENT_CANDIDATE`: a useful, nontrivial model search role
  remains after the deterministic baseline.

Only the last outcome permits drafting a separate prospective experiment.
It does not itself authorize model execution or local serving.

## Boundary for any successor experiment

A successor must be frozen and reviewed before generation. It must use fresh
problem instances, authenticate all inputs and implementations, expose the
same instances to every compared arm, and include the deterministic solver as
an arm rather than comparing only local and remote models.

The primary correctness outcome must be verifier PASS under the frozen
problem semantics. Results must distinguish feasibility from optimality,
logical requests from transport retries, and deployable sequential latency
from synchronous-shadow latency. Cost and latency may be reported from direct
measurement. Energy must not be claimed without direct, documented power
instrumentation.

Runtime v0.3 remains remote-authoritative throughout this work. No result may
be used to reopen structural-JSON local authority retrospectively.
