# Measured Paired Routing Replay v1

Date: 2026-09-02

## Purpose

Replace the uniform remote-success assumptions in Routing Simulation Zero v1
with observation-level outcomes measured from the paired Gemma 3 270M and
OpenRouter Luna runs.

This is an offline replay. It made no model or API request and did not modify
either frozen evidence file.

## Authenticated inputs

| Source | Observations | SHA-256 |
|---|---:|---|
| `benchmark_runs_simzero_v2.jsonl` | 150 | `5637130c56894a0263c534bb87c5037901f0e535df28e658f68d5e85c03f7f6e` |
| `benchmark_runs_openrouter_luna_v1.jsonl` | 150 | `341d203f34f3789e489329030895970e719483334e42d2ac144080516e3c0405` |

All 150 `(task_id, repetition)` keys paired exactly, with matching task
classes.

The committed implementation used to produce the canonical outputs was
`773a63333bfcce031b991ae24ebc3615cf60b6ff`. The result files were committed
at `120df2b`.

## Policies replayed

The four policies are unchanged from Routing Simulation Zero v1:

- **Always local:** send every task to Gemma 3 270M.
- **Always remote:** send every task to OpenRouter Luna.
- **Coarse class:** keep structured extraction and classification local; send
  formatting and transformation remotely.
- **Fine capability:** keep structured extraction, sentiment classification,
  and JSON formatting local; send priority classification, bullet formatting,
  label formatting, and transformations remotely.

Each policy chooses one route before generation. This replay does not model a
local-first attempt followed by remote fallback.

## Interpretation layers

The strict interpretation uses the frozen `oracle_correct` values without
adjustment.

The audited interpretation applies only the previously documented
specification rulings:

- local `extract_person_2` observations are treated as correct;
- remote `extract_event_2`, `format_labels_contact`, and
  `format_labels_ticket` observations are treated as correct; and
- remote `classify_priority_medium` remains incorrect because the task lacked
  an operational priority rubric.

The audited interpretation does not replace the strict result.

## Paired outcome overlap

| Interpretation | Both correct | Local only | Remote only | Neither | Oracle selector ceiling |
|---|---:|---:|---:|---:|---:|
| Strict | 66 | 0 | 62 | 22 | 128/150 |
| Audited | 69 | 2 | 74 | 5 | 145/150 |

Under the strict oracle, every local success was also a remote success.
Therefore, even an outcome-aware selector could not exceed always remote on
this frozen strict sample.

Under the audited interpretation, the two local-only successes were
`extract_person_2` repetitions for which the remote request produced a
transport failure. They show availability complementarity rather than a
demonstrated local capability advantage.

## Measured replay result

### Strict

| Policy | Passes | Pass rate | Remote calls | Reported remote cost | Median selected time |
|---|---:|---:|---:|---:|---:|
| Always local | 66/150 | 44.0% | 0 | $0 | 262.133 ms |
| Always remote | 128/150 | 85.3% | 150 | $0.0054320 | 1,847.455 ms |
| Coarse class | 116/150 | 77.3% | 75 | $0.0027282 | 966.929 ms |
| Fine capability | 125/150 | 83.3% | 75 | $0.0024892 | 990.314 ms |

### Audited

| Policy | Passes | Pass rate | Remote calls | Reported remote cost | Median selected time |
|---|---:|---:|---:|---:|---:|
| Always local | 71/150 | 47.3% | 0 | $0 | 262.133 ms |
| Always remote | 143/150 | 95.3% | 150 | $0.0054320 | 1,847.455 ms |
| Coarse class | 131/150 | 87.3% | 75 | $0.0027282 | 966.929 ms |
| Fine capability | 140/150 | 93.3% | 75 | $0.0024892 | 990.314 ms |

At the same 75-call remote budget, fine capability gained nine passes over
coarse routing under both interpretations.

Relative to always remote, fine capability:

- saved 75 remote calls, a 50% reduction;
- reduced recorded remote cost by $0.0029428, or approximately 54.2%;
- reduced replayed median selected time from 1,847.455 ms to 990.314 ms,
  approximately 46.4%; and
- lost three passes, or 2.0 percentage points, under both interpretations.

The cost reduction exceeds the call reduction because the remotely selected
task mixture was cheaper than the full benchmark mixture.

## Interpretation

This replay replaces the earlier hypothetical uniform remote-success rate with
measured task-dependent outcomes. It establishes a concrete trade-off on this
frozen sample: the fine policy retained 125 of 128 strict always-remote passes
while using half as many remote calls.

It does not validate that policy for deployment. The fine capability map was
designed after inspecting the local benchmark, although it predates the paired
remote evidence. The analysis is consequently in-sample with respect to local
capability selection.

The result also concerns Gemma 3 270M. It does not incorporate the later 1B
and 4B scaling evidence, prospective contracts, or deterministic executor.
Those components were measured on different suites and cannot be combined by
pretending their observations are paired.

## Product implications

The result is promising enough to continue, but not sufficient to ship the
fine policy unchanged.

A usable successor should combine:

1. direct deterministic execution for executable operations;
2. an empirically selected local model tier;
3. explicit task contracts where the requested output is checkable;
4. remote escalation for contract failure and unsupported semantic work; and
5. an explicit retry/failure policy for the remote path.

That complete router must then be tested prospectively on fresh tasks and
scored on final user-visible outcomes, remote calls, latency, reported cost,
and failure handling.

## Boundaries

- This is a replay of one selected route, not a live end-to-end router run.
- Median selected time does not include orchestration overhead or sequential
  local-then-remote fallback.
- Reported cost is the OpenRouter cost field preserved in the remote evidence;
  it is not an energy or compute measurement.
- No retry, output-contract fallback, or deterministic executor is simulated.
- The 150 observations are repetitions of 30 constructed tasks, not a
  production workload distribution.
- No uncertainty interval or prospective acceptance threshold was specified
  for this descriptive replay.

## Preserved outputs

| Artifact | SHA-256 |
|---|---|
| `routing_simulation_measured_v1.json` | `8eb3a3514e544d10594bf0fd82223293347340c4619400acaa7e9e20a41622ed` |
| `routing_simulation_measured_v1.csv` | `8e2d6ef34678840390bd7ca36e7c163644e6fa634d33b3427731455eb2713d53` |

The JSON is the canonical machine-readable analysis. The CSV is a flat
eight-row policy view. Neither source evidence file was modified.
