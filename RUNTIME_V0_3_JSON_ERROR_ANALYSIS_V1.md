# Runtime v0.3 structural-JSON error analysis V1

**Status:** RETROSPECTIVE ONLY  
**Candidate screen:** NO_RULE_CANDIDATE  
**Sealed V2 decision:** DO_NOT_PROMOTE

## Observations

The local provider completed all 120 observations across 40 task clusters. It was oracle-correct on 16/120 rows. The structural contract passed 39 rows, including 23 semantic errors.

| Stratum | Correct | Contract PASS | Accepted errors |
|---|---:|---:|---:|
| flat_scalar | 7/30 | 13/30 | 6 |
| record_selection | 0/30 | 9/30 | 9 |
| type_boundary | 9/30 | 12/30 | 3 |
| nested_collection | 0/30 | 5/30 | 5 |

## Deterministic derivations

Primary error classes count each row once. Leaf-difference counts may count more than one path per row.

```json
{
  "leaf_difference_counts": {
    "array_length": 4,
    "container_type": 38,
    "missing_member": 24,
    "scalar_type": 40,
    "scalar_value": 85,
    "unexpected_member": 9
  },
  "primary_class_counts": {
    "container_type": 23,
    "exact": 16,
    "member_set": 21,
    "scalar_type": 33,
    "scalar_value": 18,
    "unparseable_candidate": 9
  },
  "task_patterns": {
    "candidate_uniqueness": {
      "1": 33,
      "2": 7
    },
    "contract_patterns": {
      "mixed_contract_status": 2,
      "unanimous_fail": 26,
      "unanimous_pass": 12
    },
    "correctness_patterns": {
      "mixed_correctness": 1,
      "unanimous_correct": 5,
      "unanimous_error": 34
    }
  }
}
```

Every predeclared subgroup is present in the JSON and CSV outputs. No deployable subgroup passed the frozen candidate screen.

## Candidate hypotheses

- **MODEL_CHANGE_CANDIDATE:** Gemma 3 270M is inadequate for this structural-JSON distribution. V2 does not validate any replacement model.
No validator-change candidate is established: this analysis does not specify and test an oracle-free deterministic check that both rejects an accepted error and retains a correct local PASS.

Neither hypothesis changes the shipped remote-authoritative policy.

## Prohibited claims

- This retrospective analysis does not validate a successor router.
- Contract PASS does not establish semantic correctness.
- Favorable V2 subgroups do not authorize local serving.

## Gotchas

The dataset contains 120 rows but only 40 task clusters. Three repetitions do not create 120 independent tasks. Exhaustively printing subgroup results limits cherry-picking but does not remove post-selection bias.

A fast local arm is not automatically useful: rejected local calls add latency before fallback, while accepted semantic errors remove correctness.
