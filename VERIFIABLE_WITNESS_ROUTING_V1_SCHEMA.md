# Verifiable-witness routing V1 schema specification

**Status:** developmental contract specification

**Runtime authority:** none

**Generation calls authorized:** none

This document fixes the input language that the developmental verifier and
deterministic solver must share. It is normative for V1 implementation but is
not a prospective experiment freeze.

## Encoding and loading

Problem and witness documents are UTF-8 JSON. Each loader must:

- reject malformed UTF-8 or JSON;
- reject duplicate object keys at every nesting level;
- reject `NaN`, `Infinity` and `-Infinity`;
- reject a problem document larger than 262,144 bytes;
- reject a witness document larger than 131,072 bytes; and
- require exact object field sets, with no ignored extension fields.

JSON numbers used by V1 are integers checked with `type(value) is int`, so a
Boolean never satisfies an integer field. No coercion, Unicode normalization,
case folding, default insertion or semantic repair is permitted.

Identifiers must match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. This ASCII-only rule
is deliberate: identifiers are protocol tokens, not human names.

## Problem document

The top-level object has exactly these fields:

```json
{
  "schema_version": "verifiable_assignment_problem_v1",
  "problem_id": "example-001",
  "entities": [],
  "slots": [],
  "fixed_assignments": [],
  "colocation_pairs": [],
  "separation_pairs": [],
  "coverage_requirements": []
}
```

All arrays are required even when empty. Array order does not change
feasibility semantics. The declared entity order controls canonical witness
output.

### Slots

`slots` contains between 1 and 64 objects with exactly:

```json
{"slot_id": "slot-a", "capacity": 3}
```

`slot_id` is a V1 identifier and must be unique. `capacity` is an integer from
0 through 128 inclusive.

### Entities

`entities` contains between 1 and 128 objects with exactly:

```json
{
  "entity_id": "entity-01",
  "eligible_slot_ids": ["slot-a", "slot-b"]
}
```

`entity_id` is a V1 identifier and must be unique. `eligible_slot_ids` contains
between 1 and 64 unique identifiers, each referencing a declared slot. The
listed order has no semantic effect.

### Fixed assignments

`fixed_assignments` contains at most 128 objects with exactly:

```json
{"entity_id": "entity-01", "slot_id": "slot-a"}
```

Both identifiers must resolve. The slot must be eligible for the entity. An
entity may occur in at most one fixed assignment.

### Pair constraints

`colocation_pairs` and `separation_pairs` each contain at most 512 objects with
exactly:

```json
{"left_entity_id": "entity-01", "right_entity_id": "entity-02"}
```

Both identifiers must resolve and must differ. Pair identity is unordered:
`(a, b)` and `(b, a)` are the same pair. A pair may occur only once within a
collection and must not occur in both collections.

For a colocation pair, both entities must be assigned to the same slot. For a
separation pair, they must be assigned to different slots.

### Coverage requirements

`coverage_requirements` contains at most 512 objects with exactly:

```json
{
  "coverage_id": "cover-east",
  "slot_ids": ["slot-a", "slot-b"],
  "minimum_assigned_entities": 4
}
```

`coverage_id` is a unique V1 identifier. `slot_ids` contains between 1 and 64
unique declared slot identifiers. `minimum_assigned_entities` is an integer
from 1 through 128 inclusive.

The constraint is satisfied when at least that many distinct entities are
assigned to any slot in `slot_ids`. Coverage requirements may overlap; an
entity can contribute to more than one requirement when its assigned slot is
listed by each.

## Problem validity versus feasibility

Schema and reference failures make a problem invalid. A structurally valid
problem may nevertheless be infeasible because its combined constraints have
no solution. The parser must not claim feasibility and must not silently drop
conflicting constraints.

The deterministic solver reports infeasibility separately. Prospective model
tasks, if ever authorized, must be generated and frozen under a separately
reviewed procedure that does not disclose or store an expected witness in the
candidate input.

## Problem identity

`problem_sha256` is the lowercase SHA-256 of the exact problem-file bytes as
loaded, including whitespace and final newline. It is not a hash of parsed or
re-serialized JSON. The verifier computes this value; neither the problem nor
the candidate defines it.

Any prompt renderer must receive the authenticated problem and computed hash.
Rendering must not add constraints, hints, a known solution or information
absent from the trusted document.

## Witness document

The top-level witness object has exactly:

```json
{
  "schema_version": "verifiable_assignment_witness_v1",
  "problem_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "assignments": [
    {"entity_id": "entity-01", "slot_id": "slot-a"}
  ]
}
```

`problem_sha256` must match `[0-9a-f]{64}` and equal the verifier-computed
digest. `assignments` contains between 1 and 128 objects, each with exactly
`entity_id` and `slot_id`.

Every declared entity must occur exactly once. No undeclared entity or slot is
permitted. Assignment order has no semantic effect. On PASS, the verifier
returns a fresh canonical witness ordered by the trusted problem's entity
array; it never returns unparsed candidate text.

## Verification order and stable outcomes

The verifier stops at the first failure in this order:

1. strict problem loading and problem-contract validation;
2. strict witness loading and exact witness fields;
3. witness schema and problem-hash identity;
4. assignment entry shape and identifier validity;
5. exact entity coverage and declared slot membership;
6. entity eligibility;
7. fixed assignments;
8. slot capacities;
9. colocation pairs;
10. separation pairs; and
11. coverage requirements.

The implementation must use stable machine-readable details. At minimum it
must distinguish:

- file, UTF-8 and JSON parsing failures;
- `DUPLICATE_JSON_KEY` and `NON_FINITE_JSON_CONSTANT`;
- problem schema, field-set, bound, identifier and reference failures;
- witness schema, field-set, hash and assignment-shape failures;
- missing, additional and duplicate entity assignments;
- unknown or ineligible slots;
- fixed-assignment, capacity, colocation, separation and coverage violations;
- `ALL_DECLARED_CONSTRAINTS_SATISFIED`; and
- deterministic-solver `SOLVED`, `INFEASIBLE` and `RESOURCE_LIMIT` outcomes.

Exact reason-code spelling beyond the named codes above is fixed by the first
implementation and its tests. Later changes must not collapse distinct
constraint failures into a generic schema PASS or FAIL.

## Solver boundary

The baseline solver consumes the same validated problem representation as the
verifier. It may return only:

- `SOLVED` with a witness that independently passes the verifier;
- `INFEASIBLE` after exhaustive bounded search establishes no witness; or
- `RESOURCE_LIMIT` when a predeclared node or time budget is exhausted.

`RESOURCE_LIMIT` must never be reported as infeasibility. Solver search order
must be deterministic, and node count plus monotonic elapsed time must be
recorded. The verifier itself must not call the solver.

## Non-claims

V1 verifies feasibility only within this explicit language. It does not verify
that the problem captures a real-world requirement, infer constraints from
natural language, certify optimality, assess fairness, or authorize local
model output. Runtime v0.3 remains unchanged and remote-authoritative.
