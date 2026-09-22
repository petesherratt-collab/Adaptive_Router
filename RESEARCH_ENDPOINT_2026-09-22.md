# Adaptive Router initial research-cycle endpoint

**Date:** 2026-09-22

**Canonical baseline:** `2ae3d10`

**Runtime policy:** v0.3 remote-authoritative

**Local generative authority:** disabled

## Endpoint

The initial local-authority research cycle is complete.

The project began with a practical hypothesis: deterministic routing might send narrow tasks to the smallest adequate local model and reduce remote use without materially reducing correctness.

The evidence supports only part of that architecture. Deterministic execution is useful when code completely defines the result. Deterministic contracts reject many observable format, type and structural failures. Runtime telemetry can determine whether local inference is operationally viable.

None of those mechanisms established a sufficiently safe semantic boundary for serving the tested local generative outputs. Runtime v0.3 therefore remains remote-authoritative, and the current promotion programme ends without promoting a local model.

This is a bounded negative result, not a universal impossibility claim.

## Terminal claim

> For the tested hardware, Gemma 3 candidates, constructed task families and deterministic acceptance mechanisms, local generative authority did not preserve the correctness of the remote-authoritative runtime under the prospectively frozen promotion rules.

The project does not claim that every local model is inadequate, that remote models are always correct, or that routing can never reduce cost. It makes no energy claim because electricity consumption was not directly measured.

## Decisive 1B result

The separately frozen Gemma 3 1B experiment used 40 fresh tasks with three repetitions, producing 120 observations.

| Measure | Result |
|---|---:|
| Runtime/remote correct | 105/120 |
| Local correct | 43/120 |
| Local contract passes | 60/120 |
| Errors among contract passes | 17/60 |
| One-sided 95% accepted-error upper bound | 39.4% |
| Local-first counterfactual correct | 88/120 |
| Potential remote calls avoided | 60 |
| Local-first counterfactual median | 4874.6 ms |
| Direct remote provider median | 2509.0 ms |
| Decision | `DO_NOT_PROMOTE` |

The experiment reached its frozen volume and potential-savings thresholds but failed its safety and correctness thresholds. Every locally correct observation was also remotely correct: 43 both-correct, zero local-only, 62 remote-only and 15 neither.

The earlier 270M experiment used different fresh tasks. The two results do not establish a causal model-size comparison.

## What remains useful

- Deterministic operations should bypass models when code completely defines success.
- Contracts remain useful conformance controls, but a correctly shaped value can still be semantically wrong.
- Runtime health signals measure operational viability, not answer correctness.
- Local shadow execution remains available for measurement without serving its output.
- Verifiable witnesses may exhibit a real find-versus-check asymmetry, but no useful nontrivial model workload has yet been demonstrated.

## Closed and paused lines

The following work is closed for this research cycle:

- structural-JSON authority based on exact keys and declared types;
- retrospective subgroup tuning over sealed evidence;
- a 4B run whose only substantive change would be model size; and
- further provider calls intended merely to find a passing model.

Source-aware byte-span verification established provenance and record membership but accepted same-typed field-role swaps. It remains a documented negative boundary, not a promotion candidate.

The verifiable-witness design is preserved on `experiment/verifiable-witness-routing-v1` at `d2174f1`. It has no implementation, model evidence, runtime authority or promotion authority.

## Standing product

- Allowlisted deterministic operations bypass both providers.
- Generative work remains remote-authoritative.
- Final remote output is checked against its declared observable contract.
- Local Ollama execution remains optional and non-authoritative.
- Shadow output is neither returned nor used to repair the remote answer.

The checked-in `routing.allow_user_visible_local` setting remains `false`.

## Preservation

The diverged leakage investigation remains unmerged at `preserve/local-main-leakage-2026-09-20`, commit `d2cccad`.

| Archive | SHA-256 |
|---|---|
| `local-main-leakage.bundle` | `214d3c81c6b9b42126d90fbc55f3aa15defa12e18d97bca3d2e201cd1e76f675` |
| `untracked-leakage-artifacts.tar.gz` | `f42c40cc87404c0355c60322bf3cfeff63e9d6f9cc76c882d286f9d37dd128f8` |

The seven unrelated persistent untracked files in the primary worktree remain untouched.

## Conditions for reopening

A successor requires a substantively new question and a separately reviewed prospective freeze. It must use fresh identical instances across arms, include a deterministic baseline, completely specify the bounded correctness claim, and freeze promotion and stop rules before generation.

Energy claims require direct documented power measurement. A model-search role must survive comparison with ordinary deterministic code. Retrospective rules derived from sealed outcomes must not be described as prospectively validated.

## Final status

The project ends this research cycle with a functioning conservative runtime, a preserved chain of negative and boundary evidence, and no promoted local generative authority.

The failed promotion is the result, not unfinished business.
