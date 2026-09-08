# Runtime v0.3 Structural-JSON Shadow Evaluation V1 — Execution Incident

Date: 2026-09-08
Branch: `experiment/runtime-v0.3-shadow-json-v1`

## Classification

**INCOMPLETE / PROVIDER ARM FAILURE / PROMOTION BLOCKED**

Runtime v0.3 remained remote-authoritative. The partial run is not characterized
as a completed evaluation, and no effectiveness or promotion conclusion is
drawn from its 47 completed observations.

## Frozen identities

- Runtime release: `v0.3.0`
- Runtime commit: `f67273d04ef9b8a3964ed4371390808bf6ba8ffe`
- Design freeze: `2ad263e249b06127267e041fe51cd1a73250bf1d`
- Execution implementation: `560be38853aeae60b1fdc4e04bf8d5c3436dfde6`
- Preserved partial-evidence commit:
  `9dd9952ca9498f82d2e380b5e256bada6aafa3e9`
- Plan SHA-256:
  `acfa8f12d585a7d817afc09dec632c7346c29582b10e4fd477c9337c516eb0ed`
- Benchmark SHA-256:
  `76378d8bdeba1facb3f43f41186b2e31f091d8baea7550f10c54d42803ed0f93`
- Config SHA-256:
  `36df214e322b8148614e0ac8289ddb77779e326e06d91e3780ea39b87bd01657`

## Pre-execution verification

Before the provider run:

- 19 focused experiment tests passed;
- all 343 repository tests passed;
- the synthetic 120-observation dry run passed;
- the dry run made zero provider network requests and created no repository
  outputs; and
- metadata preflight authenticated the frozen inputs, implementation revision,
  local model identity, remote model identity, and empty output state.

## Halted execution

The one-shot command was:

```text
./.venv/bin/python run_runtime_v0_3_shadow_json_v1.py --execute
```

It exited with status 1 and:

```text
runtime_v0_3_shadow_json_v1.FrozenDesignError: PROVIDER_ARM_FAILURE
```

The retained state contains:

| Item | Count |
|---|---:|
| Completed paired run rows | 47 |
| Router telemetry rows | 48 |
| Failed observation | 48 |
| Failed task | `select_06` |
| Failed repetition | 3 |

The preceding completed row was `select_06`, repetition 2.

## Failure record

The authoritative remote arm for observation 48 recorded:

- HTTP status: 200;
- runtime error: `OPENROUTER_RESPONSE_INVALID`;
- logical attempt count: 1;
- retry count: 0;
- response ID, finish reasons, token counts, cost, and router metadata: absent.

This establishes that the received success response did not satisfy the
runtime's expected OpenRouter response structure. The retained telemetry does
not establish whether the cause originated in OpenRouter, an upstream provider,
an intermediary, or an unhandled but legitimate response variant. It is
therefore classified at the observed runtime boundary rather than attributed
to a party.

The local shadow arm for the same observation executed successfully. It was
resident, completed in 815.624 ms, and passed `structured_json_v1`. That
contract result establishes declared shape and types only; the incomplete
observation was never sealed as a paired scored row.

The router recorded `REMOTE_ERROR` with trigger `SAFE_REMOTE_POLICY`. It did
not return or substitute the local shadow output. This is the intended v0.3
safety behavior.

## Preserved evidence

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `runtime_v0_3_shadow_json_v1_runs.jsonl.partial` | 47 | `a0611b82b1e28ccb992158631c7a15a5877b6b46dfa8b6323a0f8e3ab038ecf5` |
| `runtime_v0_3_shadow_json_v1_router_telemetry.jsonl.partial` | 48 | `0a087031de14ea823ba8f5ccd33e4be48fb8c388a0485a319df7a5871da4b289` |

No canonical runs, telemetry, summary, analysis JSON, or analysis CSV was
created. The partial files were committed without deletion, repair, resumption,
or conversion into canonical outputs.

## Decision

The frozen plan states that a provider error or missing arm makes the run
incomplete and blocks promotion. Runtime v0.3 Structural-JSON Shadow Evaluation
V1 therefore has no promotion decision beyond **PROMOTION BLOCKED:
INCOMPLETE**.

The 47 paired rows may support failure diagnosis, but they must not be reported
as the precommitted 120-observation effectiveness estimate. In particular, the
successful local shadow at the failed observation cannot replace the missing
authoritative arm.

## Successor boundary

Any further prospective test must be a separately named and frozen V2. It must
use fresh tasks because V1 outcomes have now been observed. Before execution,
V2 should explicitly decide whether malformed HTTP-200 provider responses
remain non-retryable, become bounded retry cases, or terminate with a canonical
failure manifest. V1 itself must not be resumed or silently repaired.
