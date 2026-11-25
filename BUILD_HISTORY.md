# Adaptive Router build history

**Project path:** `/home/peter/adaptive-router`
**Updated:** 2026-09-22

This is the single history for Adaptive Router. It combines the narrative
project history (motivation, lessons, standing rules) with the dated engineering
record (what was built or measured, how it was verified, what remained
uncertain). It supersedes `ADAPTIVE_ROUTER_PROJECT_HISTORY.md`, whose full
content is preserved below.

Where an entry says **directly verified**, the claim comes from a command run
against this working tree for this record, and the command is named. Where it
says **reconstructed**, the claim comes from the superseded project history or
from telemetry written by an earlier session, and is not presented as a fresh
observation.

**Anchoring caveat.** Entries through the 2026-08-23 baseline predate valid
project-level Git history and remain anchored only to the command output named
in those entries. Later entries are anchored to Git commits and authenticated
artifact hashes where recorded. The later-resolution notes under the 2026-08-23
gotchas document when project-level version control and ignore rules were
established.

---

## Standing rules

Operative constraints, not history. Reconstructed from the project history and
carried forward unchanged.

1. **Do not move thresholds merely to make a preferred model pass.**
2. **Smallest model is not the goal; smallest adequate model is.**
3. **Local success means only that inference executed** unless quality is
   separately established.
4. **TTFT is not equivalent to intellectual task difficulty.**
5. **Warm and cold model behaviour must be distinguished.**
6. **Generation throughput may reveal hardware limits more clearly than TTFT.**
7. **Swap occupancy is not current memory pressure.**
8. **RAM gates should account for model residency.**
9. **A deterministic validator can reject a computationally healthy model for
   good reason.**
10. **Do not introduce an LLM judge merely because semantic validation is
    difficult.**
11. **The SHA probe remains observational** until it demonstrates predictive
    value.
12. **Do not assume local inference is more energy-efficient than datacentre
    inference. Measure it.**
13. **Use energy per successful task, not merely energy per request.**
14. **Routing overhead and failed local attempts count toward the true cost.**
15. **Keep observed facts, deterministic derivations, and interpretations
    explicitly separate.**
16. **Preserve failed hypotheses and negative results;** they are part of the
    instrument's history.

### Core methodological principle

Inherited from the earlier CCC work:

> Where ordinary deterministic code can make a decision from observable
> evidence, do not introduce an LLM judge.

Routing decisions should be inspectable, reproducible, and falsifiable. Always
distinguish **directly observed** facts, **deterministically derived** results,
and **inferences** about task difficulty or semantic quality. Do not quietly
turn an inference into telemetry.

---

## Project background

Reconstructed from the superseded project history.

### Purpose

Adaptive Router began as a small experimental deterministic local→remote LLM
router for a low-spec Linux laptop. The original motivation was **cost**: avoid
paying for expensive remote/frontier inference when a much smaller local model
can perform the task adequately.

It has since acquired a second, potentially more important research motivation:
**energy and computational right-sizing**. The emerging question is:

> Can deterministic routing assign each task to the smallest computational tier
> that can complete it adequately, reducing unnecessary compute, cost, and
> potentially energy consumption?

This remains an experimental harness, not a production gateway.

### Initial architecture

``` text
request
  ↓
deterministic task classification
  ↓
local model attempt
  ↓
runtime telemetry + deterministic validation
  ├── acceptable → return local answer
  └── unacceptable → escalate to remote model
```

Local inference uses Ollama. Remote inference is intended to use OpenRouter.
During early experimentation OpenRouter was deliberately left unconfigured so
that remote fallback could not hide mistakes in local routing.

### Hardware constraint

The development laptop is severely constrained: CPU-only, roughly 4 GB RAM,
roughly 511 MB swap, Ollama available locally. This constraint has been useful
experimentally because differences between model sizes become very visible.

### Routing signals

The harness developed deterministic telemetry including CPU load, available
RAM, RAM percentage, swap occupancy, current swap activity, SHA workload probe
latency, local model residency, model size, TTFT, total inference time,
generation tokens/sec, chars/sec, and the deterministic validator result. Every
routing decision has an explicit reason code.

### The validator problem

There is no honest generic deterministic validator for open-ended prose or
general question answering. Current validator states are `PASS`, `FAIL`, and
`NOT_APPLICABLE`. Do not solve this inconvenience by casually introducing an LLM
judge. The open research question remains:

> How far can deterministic routing get before subjective semantic quality
> becomes unavoidable?

### Energy reframing

The project began with radical API cost tiers in mind. The broader hypothesis is
now computational right-sizing:

> Frontier-scale computation should not be spent on tasks that a much smaller
> computational tier can perform adequately.

This is especially relevant to agentic systems. An apparently simple user
request such as email summarisation may generate many internal inference calls
for classification, extraction, summarisation, planning, and checking. Using a
frontier model for every internal operation can magnify unnecessary computation.

A future router could conceptually allocate across several tiers:

``` text
deterministic code
→ tiny model
→ small model
→ medium model
→ large model
→ frontier model
```

The agent determines **what work needs doing**; the router determines **how much
model capability each step deserves**.

**Energy gotcha: local does not automatically mean greener.** Do not equate
`local = low energy` with `remote = high energy`. An old CPU grinding
inefficiently for a long time could consume more energy per successful task than
highly optimised accelerator inference in a datacentre. The energy claim must be
measured rather than assumed. A better target metric is **energy per successful
task** rather than energy per request.

Likewise, energy savings at the task level do not automatically imply lower
total societal energy demand. Cheaper inference may induce more inference demand
(a rebound/Jevons effect). The defensible research hypothesis is narrower:

> For a fixed quality threshold, deterministic adaptive routing can reduce the
> computation and potentially the energy required per successfully completed AI
> task compared with always using a frontier model.

### Relationship to WayfinderRouter

WayfinderRouter reconnaissance found an existing deterministic local/cloud
router with TTFT, throughput, health signals, shadow routing, calibration,
Wilson intervals, and explicit evidence discipline. Its architecture differs
materially:

``` text
Wayfinder:
prompt evidence → deterministic complexity score → choose local/cloud
→ runtime telemetry manages deployment

Adaptive Router:
local attempt → observe actual runtime evidence → deterministic validation
→ accept or escalate
```

Do not fork Wayfinder. Keep this harness small. Useful concepts borrowed
include deterministic SHA-256 shadow sampling, explicit reason codes, bounded
evidence, minimum sample sizes before trusting rates, Wilson intervals,
abstention / `NOT_APPLICABLE`, and strict separation of observation from
inference.

---

## 2026-08-10 – 2026-08-18 — v0.1 harness and model tier experiments

**Reconstructed** from the superseded project history and from telemetry written
by those sessions. Figures below were not re-measured for this record.

### Objective

Establish whether a tiny local model on constrained CPU-only hardware can own
any task class outright, using deterministic gates and validators rather than a
difficulty estimate or an LLM judge.

### Changes

Built the v0.1 harness: deterministic classifier, Ollama local leg, OpenRouter
remote leg (intentionally unconfigured), system and runtime telemetry, health
gates, task-specific validators, deterministic shadow sampling, JSONL logging,
and a statistics reporter with minimum sample sizes and Wilson intervals.

### Verification

Model experiments, all reconstructed:

**Qwen3 4B** — `qwen3:4b` effectively froze the laptop. *Lesson:* a 4B model is
not a viable default local worker on this hardware.

**Qwen3 0.6B** — ran, but default reasoning/thinking produced a large reasoning
trace for a trivial rewrite. *Lesson:* reasoning mode can itself distort latency
measurements and waste computation on simple tasks.

**Gemma 3 1B** — noticeably better prose than the smallest models, but CPU
inference far too slow for interactive use.

``` text
cold: TTFT ~38.8 s | total ~127.3 s | TPS ~0.92
warm: TTFT ~24.3 s | total ~177.0 s | TPS ~0.91
```

Residency improved TTFT but did essentially nothing for sustained generation
throughput. *Lesson:* CPU generation speed, rather than model loading, is the
binding constraint for Gemma 1B on this laptop.

**Gemma 3 270M, cold** — controlled prompt
`Rewrite: The weather was bad but I went outside anyway.`

``` text
resident: false | TTFT 10.71 s | total 27.18 s | TPS 5.83
available RAM ~1756 MB | active swap: none
```

Escalated on `TTFT_EXCEEDED`. Roughly six times the generation throughput of 1B.

**Gemma 3 270M, warm/resident** — model preloaded into Ollama. Direct output for
the controlled rewrite included several alternatives claiming that it rained,
that the rain stopped, or that the weather stayed dry: altered or invented facts
rather than a faithful rewrite.

``` text
resident: true | model size ~326 MB | TTFT 1.75 s | total 15.82 s | TPS 6.18
active swap: none
```

Computational thresholds comfortably satisfied. The router nevertheless
escalated on `VALIDATOR_FAILED`, with `rewrite_shape_v1: FAIL`.

This is an important result: the model was fast enough, but its output was not
acceptable for the task. The subsequent remote execution failed only because the
OpenRouter key remained intentionally unconfigured.

### Decisions

**Smallest model is not the objective.** Do not optimise for *use the smallest
model*; optimise for *use the smallest model that reliably satisfies the task*.
A tiny model that consumes little compute but produces an unusable answer is not
efficient. If its failure causes retries or escalation, it may actually waste
computation. This distinction is central to both the cost and energy versions of
the project.

A useful conceptual decomposition:

``` text
execution_success
performance_acceptable
semantic_quality
routing_success
```

These are not the same thing. For the warm Gemma 270M rewrite experiment:

``` text
execution_success:       PASS
performance_acceptable:  PASS
validator:               FAIL
semantic_quality:        poor by human inspection
routing decision:        correctly escalated
```

**Emerging quality–compute frontier:**

``` text
Gemma 270M   computationally viable | ~6 tok/s warm | weak for open-ended rewriting
Gemma 1B     better language quality | ~0.91 tok/s  | too slow for interactive use
4B class     effectively unusable on this hardware
```

The useful question is therefore not which model is "best", but which **task
classes** each computational tier can own reliably. Likely candidates for 270M
testing include structured extraction, formatting, classification, and
mechanical transformations — attractive because deterministic validators can
often establish correctness.

**Do not** optimise the rewrite prompt or loosen thresholds to make Gemma 270M
pass. The warm 270M result has already established that the model is
computationally viable but unreliable for the controlled rewrite.

### Gotchas

#### 1. Swap occupancy is not swap pressure

- **Observed:** an early design treated absolute swap usage as a hard gate.
  **Source:** reconstructed.
- **Why surprising or dangerous:** Linux can retain old pages in swap after
  memory pressure has disappeared, so occupancy alone rejects local inference on
  a machine that is no longer under pressure.
- **Resolution or containment:** the router distinguishes swap occupancy from
  current swap activity. High historical occupancy alone does not block local
  inference; active swap-out pressure can.

#### 2. A universal RAM threshold ignores model residency

- **Observed:** a single available-RAM threshold was too crude. **Source:**
  reconstructed.
- **Why surprising or dangerous:** if a model is already resident, much of its
  loading cost has already been paid; rejecting it for falling below a *pre-load*
  threshold escalates work that would have run cheaply.
- **Resolution or containment:** the router checks Ollama residency and does not
  reject a resident model solely on available RAM. If residency cannot be
  confirmed, it conservatively treats the model as not resident.

#### 3. TTFT is not task difficulty

- **Observed:** cold model loading can dominate time-to-first-token. **Source:**
  reconstructed.
- **Why surprising or dangerous:** high TTFT could be misread as evidence that a
  task is intellectually difficult, turning an inference into telemetry.
- **Resolution or containment:** Ollama's separate load, prompt-evaluation,
  evaluation, and total durations are potentially more informative and should be
  preferred.

#### 4. The SHA probe may not matter

- **Observed:** the proof-of-work-style SHA probe was intended as an external
  measure of machine load. Ordinary system and Ollama telemetry have so far been
  more directly useful. **Source:** reconstructed.
- **Resolution or containment:** it remains logged but observational.
- **Open risk:** it must not influence routing unless evidence demonstrates
  predictive value.

---

## 2026-08-23 — Combine histories and record baseline state

### Objective

Merge the narrative project history into this build history so the project has a
single record, and capture the verified state of the harness before any further
experimental work, so that later threshold or validator changes have a fixed
point to be compared against.

No routing behaviour, threshold, validator, or configuration value was changed.

### Changes

**Directly verified:** created `BUILD_HISTORY.md` (this file), absorbing the full
content of `ADAPTIVE_ROUTER_PROJECT_HISTORY.md`, which was then removed. A copy
of the superseded file was retained outside the project at
`/tmp/claude-1000/-home-peters/2bec48f7-32ca-4696-8aa4-b762eb7e1148/scratchpad/ADAPTIVE_ROUTER_PROJECT_HISTORY.md.bak`.
No source file, test, or configuration value was created, modified, or deleted.

### Verification

**Directly verified**, from commands run on 2026-08-23 in
`/home/peters/adaptive-router`:

- `.venv/bin/python -m unittest discover -s tests` — 35 tests, OK, 0.190s.
- Source inventory: `local.py` 64, `main.py` 65, `probe.py` 10, `remote.py` 33,
  `router.py` 84, `shadow.py` 8, `stats.py` 70, `telemetry.py` 30,
  `validators.py` 57 lines. Seven test modules under `tests/`.
- `runs.jsonl` holds 32 records spanning `2026-08-10T21:01:44Z` to
  `2026-08-18T12:56:14Z`.

**Directly verified**, telemetry aggregates computed from those 32 records:

| Field | Distribution |
| --- | --- |
| `task_class` | `extract_structured` 18, `unknown` 8, `rewrite` 6 |
| `decision.route` | remote 20, local 12 |
| `decision.reason` | `REMOTE_ERROR` 20, `LOCAL_ACCEPTED` 12 |
| `decision.trigger` | `REMOTE_DEFAULT_TASK` 8, `TTFT_EXCEEDED` 5, `VALIDATOR_FAILED` 5, `LOW_RAM` 2, absent 12 |
| `validator` | `json_structure_v1` PASS 12 / FAIL 4, `rewrite_shape_v1` FAIL 1, `unsupported` NOT_APPLICABLE 15 |

Local inference was attempted in 22 of 32 runs.

**Directly verified**, configuration in force at the time of these runs, from
`config.json`: local `gemma3:270m` via Ollama at `http://localhost:11434`,
timeout 45s; remote model literal `CHANGE_ME` via OpenRouter, timeout 90s;
`minimum_available_ram_mb` 1500, `active_swap_out_pages_threshold` 0,
`maximum_ttft_ms` 8000, `minimum_generation_rate` 1.5,
`summarise_max_input_chars` 12000; shadow enabled with execute false at 0.05
sample rate; probe enabled at 50000 iterations; `minimum_evidence_count` 30 over
a 7-day baseline.

### Decisions

1. Maintain a single combined history in this file. This reverses the decision
   recorded earlier the same day to keep the narrative and engineering records
   separate; the operator directed the merge, and the superseded file was
   removed rather than left to diverge.
2. Record the baseline before changing anything, so that any later movement in
   pass rates can be attributed to a specific change rather than to drift.
3. Leave `remote.model` as `CHANGE_ME`. Per the project history this is
   deliberate: an unconfigured remote leg prevents remote fallback from masking
   local routing mistakes. The resulting `REMOTE_ERROR` on all 20 remote routes
   is expected behaviour, not a defect.
4. Do not treat the `json_structure_v1` 12/4 split as established evidence. At
   18 `extract_structured` observations it is below the project's own
   `minimum_evidence_count` of 30.

### Gotchas

#### 1. The project is not under version control

- **Observed:** `git status` in `/home/peters/adaptive-router` fails with
  `fatal: not a git repository (or any of the parent directories): .git`.
  `/home/peters/.git` exists but is an empty directory containing no Git
  objects, so the upward search finds nothing usable. **Source:** directly
  verified, 2026-08-23.
- **Why surprising or dangerous:** the environment banner for a session started
  in `/home/peters` can report the home directory as a Git repository on the
  strength of that empty stub. An operator may believe work is being tracked
  when no history is being recorded at all. Experimental telemetry in
  `runs.jsonl` cannot be tied to the code revision that produced it.
- **Diagnosis:** `ls -a /home/peters/.git` returns only `.` and `..`.
- **Resolution or containment:** none applied. Version control was raised and
  deferred by the operator; findings are to be recorded in this file and
  published to GitHub only when judged usable.
- **Open risk:** telemetry rows remain unattributable to a code revision, and a
  future `git init` run from `/home/peters` would silently adopt the empty stub
  as a home-directory repository.
- **Later resolution:** the project is now under Git/GitHub version control.

#### 2. A live API key sits beside an absent ignore file

- **Observed:** `.env` is present (20 bytes) alongside `.env.example`, and no
  `.gitignore` exists in the project. `.venv/` and `__pycache__/` are also
  present with no ignore rule. **Source:** directly verified, 2026-08-23.
- **Why surprising or dangerous:** the project's stated intent is to publish to
  GitHub once findings are usable. A first `git add .` at that moment would
  stage the OpenRouter key, and the README's instruction not to commit `.env` is
  not currently enforced by anything mechanical.
- **Diagnosis:** directory listing shows `.env` with no sibling `.gitignore`.
- **Resolution or containment:** none applied yet. A `.gitignore` covering
  `.env`, `.venv/`, and `__pycache__/` must be written before the first
  `git add` in this project, not after.
- **Open risk:** the sequencing depends on remembering it at commit time.
- **Later resolution:** `.gitignore` now protects `.env`, virtual environments,
  caches, and run logs.

#### 3. Remote-route reason codes overwrite their trigger

- **Observed:** in all 20 remote routes, `decision.reason` is `REMOTE_ERROR`
  while the originating gate is preserved separately in `decision.trigger`.
  **Source:** directly verified from `runs.jsonl`, 2026-08-23.
- **Why surprising or dangerous:** counting `decision.reason` alone across the
  current log makes every escalation look like a remote transport failure and
  makes the local gates appear never to have fired. The routing signal of
  interest lives in `decision.trigger`.
- **Diagnosis:** `router.py` sets `final_reason` to `REMOTE_ERROR` when the
  remote call fails, retaining the initiating reason under `trigger`.
- **Resolution or containment:** analysis of escalation causes must read
  `decision.trigger`, falling back to `decision.reason` only for local routes,
  where `trigger` is absent by design (12 of 32 records).
- **Open risk:** any future summary that groups by `reason` will misreport
  escalation causes for as long as the remote leg stays unconfigured.

---

## 2026-08-24 — Simulation Zero v1 — ProDesk / Gemma 3 270M

### Environment

- Host: HP ProDesk 400 G2.5 SFF, Linux Mint
- Model: `gemma3:270m` via Ollama
- Model resident during measured run
- Benchmark: 10 deterministic tasks × 3 repetitions = 30 observations
- No LLM judge
- Corrected benchmark/oracle frozen before execution
- Full pre-run test suite: 45 passed, 6 subtests passed
- `py_compile` passed
- `git diff --check` passed

### Results

- Overall: 17/30 oracle-correct (56.7%)
- `extract_person`: 3/3
- `extract_event`: 3/3
- `extract_order`: 3/3
- `classify_sentiment`: 3/3
- `classify_priority`: 2/3
- `format_json`: 3/3
- `format_bullets`: 0/3
- `format_labels`: 0/3
- `transform_reverse`: 0/3
- `transform_slug`: 0/3

### Important observation

`classify_priority`'s failure was inspected directly:

- rep 1 raw `"High\n"` → normalized `"high"` → PASS
- rep 2 raw `"High\n"` → normalized `"high"` → PASS
- rep 3 raw `"Low"` → normalized `"low"` → FAIL

Therefore this is an observed model failure, not a normalization/oracle failure.

### Performance observation

Warm resident inference on the ProDesk showed TTFT in the inspected tail
roughly 40–130 ms and generation roughly 60–80 tok/s. Do not generalize these
figures beyond the inspected records; calculate full-run statistics separately.

### Preserved evidence

`benchmark_runs_prodesk_simzero_v1.jsonl`

SHA-256:
`802003f86282bef7b8a918b3d05b0f9f34749bb70bd6da12d7413a1a8afe8670`

### Interpretation

The 270M model shows a strongly task-dependent capability boundary. It was
perfect on the three structured-extraction tasks and JSON formatting, nearly
perfect on classification, but failed every observed exact bullet,
label-formatting, character-reversal, and slug-transformation task. Do not
infer general task-class capability from 3 repetitions per task.

## Open questions carried forward

**Immediate.** Gemma 270M is fast enough when resident but failed the rewrite
validator. Which narrow, deterministically verifiable task classes can it
reliably own on this hardware? Answer experimentally before changing the
architecture. `extract_structured` is nearest to answerable, needing 12 further
observations to reach the minimum evidence count of 30.

**Next experimental direction.** A small benchmark across narrow task classes
with deterministic validators — JSON extraction, classification, formatting,
mechanical transformation, and short summarisation where an objective constraint
can be checked. For each model/task pair record runtime telemetry, validator
result, and a human verdict of good / usable / bad. Do not automate
routing-table learning yet; first establis
---

## 2026-08-25 — Simulation Zero v2 result and failure audit

### Environment and design

- Host: HP ProDesk 400 G2.5 SFF, Linux Mint
- Model: `gemma3:270m` via Ollama
- Benchmark: 30 deterministic tasks × 5 repetitions = 150 observations
- Model resident during the measured run
- Remote fallback deliberately unavailable
- No LLM judge or semantic output repair
- Benchmark and oracle frozen before execution
- Pre-run verification: 46 tests passed, 6 subtests passed
- `py_compile` and `git diff --check` passed

### Frozen strict-oracle result

- Overall: 66/150 = 44.0%
- Structured extraction: 35/45 = 77.8%
- Classification: 16/30 = 53.3%
- Formatting: 15/45 = 33.3%
- Transformation: 0/30
- Empty outputs: 2

Median measured performance:

- TTFT: 42.699 ms
- Total time: 262.133 ms
- Generation rate: 56.510 tokens/s

This performance is dramatically faster than the earlier low-resource laptop
condition. Deployment performance and task capability must therefore be treated
as separate dimensions.

### Fine-grained capability boundary

The aggregate task classes concealed sharp differences:

- Sentiment classification: 15/15
- Priority classification: 1/15
- JSON formatting: 15/15
- Markdown bullets and key:value labels: 0/30
- Deterministic transformations: 0/30

Seven extraction tasks achieved 5/5. Two initially recorded 0/5.

### Post-run failure audit

The frozen benchmark result was not changed.

`extract_person_2` accounted for five recorded failures. Every output preserved
the source value `Dr. Grace Hopper`, while the oracle expected `Grace Hopper`.
Because the prompt did not instruct removal of honorifics, these five failures
were classified as benchmark/specification defects rather than model-capability
failures.

The separate post-hoc specification-adjusted interpretation is therefore:

- Overall: 71/150 = 47.3%
- Structured extraction: 40/45 = 88.9%

These adjusted figures do not replace the frozen strict-oracle result.

`extract_event_2` was a genuine systematic failure: all five outputs selected
the explicitly irrelevant calendar header instead of the event description.

Representative inspection confirmed genuine exact-instruction failures across
bullet formatting, key:value labels, and all six deterministic transformation
tasks. The two empty generations were correctly represented with unavailable
TTFT and tokens-per-second values.

Priority classification produced strong observed failures, especially for the
face-valid low- and high-priority examples. However, future benchmarks must
define an operational severity rubric rather than relying only on intuitive
low/medium/high semantics.

No normalization, oracle-implementation, or telemetry defect was demonstrated
by the audit.

### Preserved evidence

`benchmark_runs_simzero_v2.jsonl`

- Bytes: 80,476
- SHA-256:
  `5637130c56894a0263c534bb87c5037901f0e535df28e658f68d5e85c03f7f6e`

`benchmark_summary_simzero_v2.json`

- Bytes: 4,086
- SHA-256:
  `ab878c4e4320c602da41c0e16f0ed8341f0f6e23e8c372883708bf23b71346b3`

The independent audit interpretation is recorded in
`SIMULATION_ZERO_V2_AUDIT.md`.

### Resolution of the previous immediate question

The v2 experiment supplies the requested minimum evidence for several narrow
task capabilities. Gemma 3 270M is a credible local candidate for exact JSON
formatting, sentiment classification, and many structured-extraction patterns.
It is not supported for priority classification, bullet/label formatting, or
deterministic string transformations.

This is a capability map, not a scalar easy-to-hard hierarchy and not yet a
production routing policy.

### Next experiment

Proceed to an offline routing-policy simulation using the frozen empirical
observations. Compare:

1. always local
2. always remote/frontier
3. coarse task-class routing
4. fine-grained empirical capability routing

Measure task success, unnecessary escalations, missed escalations, latency,
monetary cost, and a clearly labelled compute/energy proxy. Do not yet build a
learned or agentic router.

---

## 2026-08-25 — Routing Simulation Zero v1

The first offline routing-policy replay was completed over the 150 frozen
Simulation Zero v2 observations. No local or remote model was called.

Four deterministic policies were compared:

1. always local
2. always remote
3. coarse task-class routing
4. fine capability-family routing

Coarse and fine routing each sent 75/150 observations remotely. Under the frozen
strict interpretation, fine routing retained 65 local passes versus 51 for
coarse routing, reduced missed escalations from 24 to 10, and reduced
unnecessary escalations from 15 to 1.

Under the audited interpretation, fine routing retained 70 local passes versus
56 for coarse routing, reduced missed escalations from 19 to 5, and again
reduced unnecessary escalations from 15 to 1.

Remote success was not measured. Sensitivity analysis used explicitly
counterfactual uniform remote-success assumptions of 80%, 90%, 95%, and 100%.
No monetary cost, remote latency, compute, or energy result was claimed.
Remote-call count is a routing-volume proxy only.

The fine policy was designed after inspecting the same benchmark. The result is
therefore an in-sample replay, not evidence of out-of-sample generalization.

Result document: `ROUTING_SIMULATION_ZERO_V1.md`

- SHA-256:
  `a701d1a9c14f11201fb469e629136fb15f1861d56615d92709ea2a6bdf376f23`

The next evidentiary step is a paired remote benchmark on the same frozen tasks,
followed by replay using measured task-dependent remote outcomes rather than a
uniform assumed success rate.
## 2026-08-25 — Measured OpenRouter Luna baseline

A paired remote benchmark was completed over the same frozen 30 tasks × 5
repetitions used for Gemma 3 270M Simulation Zero v2.

### Frozen execution

- Gateway: OpenRouter
- Requested and returned model: `openai/gpt-5.6-luna`
- Code revision:
  `a844984b1141c67ac499f5d48dac0872248994d3`
- Temperature: 0
- Maximum completion tokens: 256
- No automatic retries
- Reported cost stop: USD 0.10
- 150 unique observations recorded

### Frozen strict result

- Overall: 128/150 = 85.3%
- Structured extraction: 38/45 = 84.4%
- Classification: 25/30 = 83.3%
- Formatting: 35/45 = 77.8%
- Transformation: 30/30 = 100%
- Successful responses: 148/150
- Empty outputs: 2
- Median request time: 1,847.455 ms
- Total reported cost: USD 0.005432
- Total tokens: 9,280

All 148 successful responses were directly routed through OpenRouter region
`LHR`, selected OpenAI on attempt 1, and returned
`openai/gpt-5.6-luna`. No cached or cache-write tokens were reported.

### Failure audit

The frozen result was not changed.

The two empty observations were a `ConnectionError` and `ReadTimeout`, both on
`extract_person_2`. They were retained without retry as availability failures.

Fifteen successful strict failures were classified as specification defects:

- five correct `extract_event_2` outputs differed only in unrequested
  capitalization;
- five `format_labels_contact` outputs followed the prompt's literal
  `key:value` syntax while the oracle silently required spaces;
- five `format_labels_ticket` outputs used the supplied human-readable label
  while the oracle silently required lowercase snake case.

Five `classify_priority_medium` outputs remain indeterminate because no
operational priority rubric was supplied.

Separate post-hoc interpretations:

- specification-adjusted: 143/150 = 95.3%
- specification-adjusted excluding the five indeterminate observations:
  143/145 = 98.6%
- successful unambiguous observations after adjustment: 143/143

These do not replace the frozen 128/150 result.

Result audit: `REMOTE_BENCHMARK_LUNA_V1_AUDIT.md`

- SHA-256:
  `bda54936fdff880dfd96a018c9716d205a8f12862a3a2f139b2532b699e994ed`

### Next analysis

Replay always-local, always-remote, coarse-class, and fine-capability policies
using paired measured local and remote outcomes. Retain both strict and audited
interpretations. Do not use the earlier uniform remote-success assumption as
the principal result.
## 2026-08-25 — Measured paired routing simulation v1

The four routing policies were replayed over 150 exactly paired local and remote
observations. This replaced the earlier hypothetical remote-success assumptions
with measured Gemma 3 270M and GPT-5.6 Luna outcomes.

### Strict replay

| Policy | Passes | Remote calls | Reported remote cost |
|---|---:|---:|---:|
| Always local | 66/150 | 0 | $0 |
| Always remote | 128/150 | 150 | $0.005432 |
| Coarse class | 116/150 | 75 | $0.0027282 |
| Fine capability | 125/150 | 75 | $0.0024892 |

### Audited replay

| Policy | Passes | Remote calls |
|---|---:|---:|
| Always local | 71/150 | 0 |
| Always remote | 143/150 | 150 |
| Coarse class | 131/150 | 75 |
| Fine capability | 140/150 | 75 |

Fine routing used 50% fewer remote calls than always remote while remaining two
percentage points behind its success rate under both interpretations.

Relative to always remote, fine routing reduced:

- reported remote cost by approximately 54.2%;
- median selected time from 1,847.455 ms to 990.314 ms;
- summed selected work from 438.850 s to 204.695 s.

At the same 75-call remote budget, fine routing exceeded coarse routing by nine
passes under both interpretations and reduced unnecessary escalations from 15
to 1.

The fine policy selected neither of the two measured remote transport failures.
Under the audited interpretation, always remote produced two harmful
escalations because the paired local observations passed while the remote calls
failed.

No energy reduction is claimed because neither local electricity nor remote
energy consumption was measured.

This remains an in-sample replay: the fine capability map was designed after
inspecting the local benchmark. The next experiment must evaluate the frozen
policy on a newly specified out-of-sample suite.

Result document: `ROUTING_SIMULATION_PAIRED_V1.md`

- SHA-256:
  `52813cdfcd0f09b2dc33a2e1d7c81fa1613fba0e8758363219762d178b92e7da`

---

## 2026-08-26 — Out-of-sample paired routing validation v1

### Preregistered design

A genuinely new benchmark was frozen before model execution:

- 40 new tasks
- 7 explicit capability families
- 5 repetitions per task and model
- 200 local observations
- 200 remote observations
- 200 paired `(task_id, repetition)` keys
- deterministic strict oracle
- no LLM judge or semantic repair

The frozen fine policy routed structured extraction, sentiment, and JSON
formatting locally. Priority, Markdown bullets, key/value labels, and
deterministic transformations were routed remotely.

The primary descriptive criterion required:

1. exactly 100 rather than 200 remote calls; and
2. a fine-routing strict pass rate no more than five percentage points below
   always remote.

### Frozen evidence

Benchmark:

- `benchmark_oos_v1.json`
- SHA-256:
  `6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295`

Execution runner:

- revision:
  `50387be90fca40cf6f3f9467106a09abdc9a3c71`

Local observations:

- `benchmark_runs_oos_local_v1.jsonl`
- 200 observations
- SHA-256:
  `425fa9328781ff2e53f69ce0a054531e106be3a6ed1380c148e35ec3d47c8ca0`

Remote observations:

- `benchmark_runs_oos_openrouter_luna_v1.jsonl`
- 200 observations
- SHA-256:
  `cd2029a23d73bbef0287b3028d3c97b9ecad44613f091448972bdd551398caae`

Both evidence files contain the same 200 unique paired keys and record the same
benchmark hash and execution-runner revision.

### Strict result

| Policy | Passes | Pass rate | Remote calls |
|---|---:|---:|---:|
| Always local | 78/200 | 39.0% | 0 |
| Always remote | 200/200 | 100.0% | 200 |
| Coarse task class | 157/200 | 78.5% | 100 |
| Fine capability | 171/200 | 85.5% | 100 |

Fine routing halved remote calls but lost 14.5 percentage points relative to
always remote. It therefore failed the preregistered five-point tolerance.

The paired task-cluster bootstrap sensitivity analysis used all five
repetitions within each sampled task:

- samples: 6,000
- seed: `20260826`
- fine minus always-remote estimate: -14.5 percentage points
- percentile 95% interval: [-25.0, -5.5] percentage points

This is not a formal non-inferiority result.

### Capability-family result

| Capability family | Local | Remote |
|---|---:|---:|
| Structured extraction | 40/50 | 50/50 |
| Sentiment | 10/25 | 25/25 |
| JSON formatting | 21/25 | 25/25 |
| Priority | 7/25 | 25/25 |
| Markdown bullets | 0/25 | 25/25 |
| Key/value labels | 0/25 | 25/25 |
| Transformation | 0/25 | 25/25 |

Fine routing improved on coarse routing by 14 observations, showing that
fine-grained capability distinctions generalized better than broad task
classes. However, the earlier sentiment result did not generalize: only 10 of
25 new sentiment observations passed locally.

### Failure audit

The fine policy incurred 29 misses:

- 15 sentiment-label failures
- 10 structured-extraction schema/type failures
- 4 JSON numeric-type failures

The prompts contained explicit rubrics, required keys, and numeric-type
instructions. Inspection found no defensible specification, normalization,
oracle, transport, or instrumentation correction.

Accordingly, the audited interpretation equals the frozen strict result.

All 16 empty local outputs occurred in Markdown-bullet or transformation
tasks, which the fine policy routed remotely. OpenRouter Luna returned 200
successful responses, 200 strict passes, and no empty outputs.

The complete audit is preserved in `OOS_VALIDATION_V1_AUDIT.md`.

### Cost and latency observations

Reported OpenRouter cost:

- always remote: USD 0.00664640
- fine routing: USD 0.00321820
- reduction: approximately 51.6%

Measured median selected total time:

- always remote: 1,690.078 ms
- fine routing: 1,115.469 ms

Summed sequential selected work:

- always remote: 476,651.369 ms
- fine routing: 327,977.701 ms

These are not direct energy measurements. No energy reduction is inferred.

### Disclosed procedural deviations

The OOS-specific analysis code was not committed before model execution,
although the suite, routing policy, execution runner, validators, and tests
were committed.

The preregistration required a fixed bootstrap seed but omitted the numeric
value. The date-derived seed `20260826` was selected after data collection.

Neither deviation changed the frozen observations or strict point estimates,
but the analysis must not be described as fully code-preregistered.

### Conclusion and next direction

The fixed fine capability policy is rejected as sufficiently reliable under
the preregistered criterion.

The result demonstrates three important points:

1. routing at capability-family level outperforms routing at broad task-class
   level;
2. strong in-sample performance can fail to generalize even for apparently
   narrow deterministic tasks;
3. a routing policy needs uncertainty, evidence thresholds, and
   within-family heterogeneity rather than a permanent binary capability map.

The next experiment should not immediately redefine the policy around these
40 observed tasks. First quantify task-level uncertainty and compare
conservative evidence-thresholded routing rules using nested or additional
held-out data.

## 2026-08-27 — The production validator was weaker than the benchmark oracle

### Category

`INSTRUMENTATION ISSUE`, in the live routing gate rather than in the
benchmark. No model-capability conclusion changes. No frozen evidence,
benchmark specification, oracle, or analysis output is modified by this
entry or by the accompanying code change.

### What was found

Replaying the frozen out-of-sample local outputs through the *live router's*
`validators.validate` showed that `json_structure_v1` returned `PASS` on all
10 structured-extraction observations that the benchmark oracle recorded as
strict failures.

The cause was a silent degradation. The required-key extractor was:

``` text
(?:required keys?|keys?)\s*[:=]\s*([\w, ]+)
```

The frozen prompts say `Required keys exactly: city, temperature_c,
condition`. The word `exactly` sits between `keys` and the colon, so the
pattern captured nothing, `required` became `[]`, and the key check was
skipped entirely. The validator then fell through to "did this parse as
JSON" and reported `PASS`.

The defect is not principally the regex. It is that a validator could
report `PASS` on a materially weaker guarantee than its name asserted, and
left no trace of having done so: `detail` was `None` on the pass path, so
no run log could distinguish "three required keys checked" from "no keys
checked".

This is the exact failure the project's measurement rules exist to prevent:

> Never allow a weak validator to support a stronger claim than it measures.

### Why the benchmark did not catch it

The benchmark oracle compares against frozen expected values and never
calls `validators.validate`. The live router calls `validators.validate`
and never sees an expected value. The two paths had drifted apart with no
test comparing them. The 200 OOS observations therefore measured a
validation layer the router does not use.

### Second finding: inconsistent fence normalization

`extract_structured` stripped one outer ```json fence; the `format` JSON
path called bare `json.loads`. Consequently `oos_json_server` was rejected
by the live validator — but for the wrong reason. The fence broke the
parse; the actual defect was the port emitted as the string `"8443"`. The
same output unfenced passed.

### Changes made

1. `required_keys()` separates *declaration* from *extraction*. A prompt
   that mentions keys but whose key list cannot be parsed now fails closed
   with the explicit reason `REQUIRED_KEYS_UNPARSED` and escalates, rather
   than passing on a degraded check.
2. Every applicable pass records the keys actually checked
   (`CHECKED_KEYS=...` plus a `checked_keys` field), and a pass on a prompt
   with no key specification is labelled `NO_KEY_SPECIFICATION`.
3. One outer JSON fence is now stripped identically on both the
   `extract_structured` and `format` JSON paths.
4. `MISSING_REQUIRED_KEYS` names the missing keys, and a non-object JSON
   value under a key requirement gets its own `NOT_A_JSON_OBJECT` code.
5. `ValidationResult` carries `value_types_checked`, which is `False`
   everywhere, because no current validator has an explicit deterministic
   schema.
6. `_normalize_structured_json` is retained as an alias with identical
   behaviour so the frozen benchmark harness is untouched.
7. Regression tests in `tests/test_validator_scope.py` use the verbatim
   frozen prompts and outputs for `temperature`/`temperature_c`, numeric
   `42`, and numeric `8443`.

### Measured effect, including the part that got worse

Against the frozen local evidence, false accepts among observations the
fine policy routed locally:

``` text
before: 10   (5 oos_extract_weather, 5 oos_extract_device)
after:   9   (5 oos_extract_device, 4 oos_json_server)
```

Newly rejected correct outputs: 0.

The five `oos_extract_weather` false accepts are genuinely fixed: the wrong
key name is now caught. The four `oos_json_server` observations moved the
other way. They were previously rejected only because the fence broke the
parse. Removing that accident exposes that the validator never had any
means of catching a string-typed port.

The headline count barely moves, and that is the honest result. The
underlying limitation — no value-type checking — is unchanged and was never
fixable without a schema. What changed is that the validator no longer
claims more than it checked. A `PASS` that was silently worthless is now
either a `FAIL` or a `PASS` that discloses its own scope.

### Standing consequence

The remaining nine are all value-type defects. Closing them requires an
explicit deterministic schema per task, supplied to the validator rather
than inferred from prompt prose. Until such a schema exists, a local
`LOCAL_ACCEPTED` on a structured-extraction task establishes required-key
presence and JSON syntax only, and must not be read as task correctness.

Recorded gap, not yet addressed: `router.classify()` has no `classification`
task class, so `validate()` returns `NOT_APPLICABLE` for sentiment and
priority prompts. The capability family with the worst measured local
performance currently has no deterministic gate at all.

---

## 2026-08-27 – 2026-08-28 — Local Model Scaling comparison v1

### Objective and frozen design

Measure how capability and latency changed from Gemma 3 270M to 1B and 4B on
the same frozen out-of-sample suite, without changing tasks, repetitions,
strict oracle, routing thresholds, or post-generation gate definitions.

- Benchmark: 40 tasks × 5 repetitions = 200 observations per model
- Frozen 270M baseline: 200 observations
- New execution: 1B and 4B, 200 observations each
- Total comparison: 600 observations
- No LLM judge, semantic repair, or retry
- Benchmark SHA-256:
  `6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295`
- Plan SHA-256:
  `97359083cc1f4b2352ea383e02076cc8ba6170336499d745be4f15742bf98363`
- Pre-execution amendment SHA-256:
  `f10c2a890a8e543e97bb80f53a8dabcbe3d5633caeafc40fe3cfef8bcbace71f`

The execution package was committed at `2538ac9` before either new model run.
The six canonical evidence and analysis outputs were committed together at
`8a8b459`. The independent audit was later merged through PR #2.

### Strict result

| Model | Strict passes | Pass rate | Change from 270M |
|---|---:|---:|---:|
| Gemma 3 270M | 78/200 | 39.0% | baseline |
| Gemma 3 1B | 99/200 | 49.5% | +10.5 percentage points |
| Gemma 3 4B | 158/200 | 79.0% | +40.0 percentage points |

Paired against 270M, 1B gained 41 passes and lost 20, for a net gain of 21.
4B gained 94 and lost 14, for a net gain of 80. The improvement was therefore
large but not monotonic at every paired observation or task.

### Post-generation gate result

| Model | Gate survivors | False accepts | Correct outputs rejected |
|---|---:|---:|---:|
| Gemma 3 270M | 176/200 | 98 | 0 |
| Gemma 3 1B | 198/200 | 100 | 1 |
| Gemma 3 4B | 196/200 | 42 | 4 |

The larger model materially improved strict correctness, but the live gates
did not establish correctness. At 4B they still accepted 42 strict failures
and rejected four correct outputs. The validators were principally
shape/health gates, and some frozen task classes had no applicable validator.

Resident 4B median latency was approximately 4.27 seconds. This establishes a
real local accuracy–latency frontier on the measured ProDesk, not a universal
model-size rule and not an energy result.

### Preserved outputs

| Artifact | SHA-256 |
|---|---|
| `benchmark_runs_scaling_gemma3_1b_v1.jsonl` | `a3bde560ccf875658f9129c3eaa321b51c6c29f3f5a7096d9a97eca070310622` |
| `benchmark_summary_scaling_gemma3_1b_v1.json` | `bcddf854832a83ca6a04d2dbc633877cadea68567d7b934b900a4172cccc58ab` |
| `benchmark_runs_scaling_gemma3_4b_v1.jsonl` | `c0576396252f39523840ca1d970648a84ec03960ca746451a10c0ef83b6cb676` |
| `benchmark_summary_scaling_gemma3_4b_v1.json` | `1cc8daec80df9d443f39d2d95040bcfe325dc91a0531ecf1cd9dacf16159d4a3` |
| `local_model_scaling_v1.json` | `e93fc2be593256ffce0e7f5dcd587a21c7916d6611651dc1c626c285beb7e0ca` |
| `local_model_scaling_v1.csv` | `24c2bcec0110475f033329015d4fbca051116af1656ca83f61dbe320d62371ab` |

Audit: `LOCAL_MODEL_SCALING_V1_AUDIT.md`

- SHA-256:
  `ed70eb18229c2a5aadab1999ae5855406ff202ccea026ff0372311409608f1ee`

### Decision

Do not choose a local tier from model accuracy alone. Model capability,
resident latency, gate coverage, and the cost of false acceptance are separate
axes. The immediate problem exposed by scaling was validator capability, not
the absence of another model size.

---

## 2026-08-28 – 2026-08-31 — Validator Contract Replay v1

### Objective and scope

Retrospectively replay all 600 frozen local observations through explicit
deterministic task contracts and ask how many baseline false accepts those
contracts would have caught. No model or network call was made.

The experiment deliberately separated:

1. raw contract conformance;
2. operational baseline/counterfactual gate survival; and
3. frozen-oracle correctness.

The contracts could not receive expected answers, oracle correctness,
normalized output, or recorded benchmark-validator results.

### Frozen chain

| Role | Commit |
|---|---|
| Plan | `99927cf` |
| Implementation, contracts and tests | `c1fb5e0` |
| Canonical JSON/CSV results | `0cbb019` |
| Audit | `36c332b` |
| Merge to main | `b8286b8` |

| Artifact | SHA-256 |
|---|---|
| Plan | `ac7cb2ee4b47ee07c4a0a63b122d56ce47d49dffb88ff82e19fd9a32d638edf0` |
| Contract file | `ea585eaf7775426ca9d58e8b8276a7bc18d7789545f84bb370aae6ac4ce6a1f0` |
| Canonical JSON | `45c4a04438adc1761de54f130b231b562c5b60c14fcfd9a75c3f90b7761a05ed` |
| Canonical CSV | `d33b0e92f7984893f4ea936d18a960ae35bbbc51a1cdaabc559bc086d4a33ad0` |
| Audit | `68bdf9f47b76938ac56b2bb02dc4f754158cc2d8ca7374b4dfc3465df0280f42` |

### Result

| Scope | Baseline false accepts | Caught | Remaining | Newly rejected correct |
|---|---:|---:|---:|---:|
| Gemma 3 270M | 98 | 61 | 37 | 0 |
| Gemma 3 1B | 100 | 79 | 21 | 2 |
| Gemma 3 4B | 42 | 27 | 15 | 10 |
| **Overall** | **240** | **167** | **73** | **12** |

The contracts caught 167 of 240 retained baseline false accepts (69.6%).
Counterfactual survivors fell from 570 to 391 and counterfactual false accepts
fell from 240 to 73. No incorrect observation rejected by the baseline gate
was newly admitted.

### What the aggregate concealed

**Classification.** All 150 sentiment/priority outputs used permitted labels,
but 56 were oracle-incorrect. Permitted-label conformance is not semantic
correctness. These 56 cases account for most of the 73 remaining false
accepts.

**Ambiguous server port.** The frozen `oos_json_server` contract accepted both
numeric `8443` and string `"8443"`, because the prompt did not specify the JSON
type. Nine false accepts therefore remained across the three models, including
all five 4B observations. Tightening the type after seeing the outcomes would
reverse the frozen `TYPE_UNSPECIFIED_BY_PROMPT` ruling.

**Transformations.** Executable exact contracts caught all 62 baseline false
accepts in the transformation family, but also rejected all 12 newly rejected
correct outputs. Each differed from the computed result only by one trailing
newline. The strict raw-output contract and the benchmark oracle had different
whitespace semantics.

### Interpretation boundaries and procedural disclosure

The contracts were designed after the model evidence existed, although the
plan and contract file were frozen and hashed before the canonical replay.
The 69.6% catch rate is therefore retrospective evidence about these 600
observations, not an unbiased prospective estimate for unseen work.

A discarded pre-commit test version briefly exercised internal write mode
against the real frozen evidence using temporary paths. No canonical output
was retained from that execution. The canonical result was produced only
after implementation commit `c1fb5e0`; the deviation is disclosed in the
audit rather than omitted.

Audit: `VALIDATOR_CONTRACT_REPLAY_V1_AUDIT.md`

### Decision and next boundary

Explicit deterministic contracts materially improve acceptance reliability
where the task supplies checkable structure or an executable operation. They
do not solve semantic classification, and exact contracts can reject correct
outputs when their normalization differs from the benchmark.

The next capability claim must be prospective: freeze contracts before
collecting a fresh suite. Classification needs either a separately evaluated
deterministic semantic classifier or escalation; permitted-label validation
alone must never be presented as correctness. Any numeric-only server-port
contract belongs in a successor specification rather than a post-hoc change.

---

## 2026-08-31 – 2026-09-01 — Prospective Contract Validation v1/v2

### Objective

Test prospectively specified deterministic output contracts as an additional
gate on top of the Adaptive Router's legacy validator and telemetry gate.

The primary question was:

> When the legacy router gate accepts an LLM output that is actually wrong,
> how often can a deterministic contract catch that false accept?

Unlike Validator Contract Replay v1, the tasks, prompts, contracts,
implementation and analysis procedure were frozen before the canonical V2
model outputs existed.

The experiment used:

* Gemma 3 270M, 1B and 4B
* 40 tasks per model
* 5 repetitions per task
* 200 observations per model
* 600 observations overall
* temperature 0
* maximum 256 output tokens
* no retries
* no prompt repair
* no skipped failures
* no model or stratum interleaving

The four cohorts were:

1. A — structural schema;
2. B — format conformance;
3. C — label conformance, reported separately; and
4. D — deterministic execution, reported separately as bypassable work.

The primary A+B estimand contained 20 tasks × 5 repetitions × 3 models =
300 observations.

### V1 execution incident

V1 was halted after completing the 270M stratum because the frozen runner
contained a protocol-instrument contradiction.

Every standalone model invocation required all canonical output paths to be
absent. The subsequent 1B invocation therefore failed because the legitimate
completed 270M files already existed.

V1 was formally classified:

> PARTIAL / EXECUTION HALTED DUE TO FROZEN PROTOCOL-INSTRUMENT CONTRADICTION

The completed V1 270M evidence was sealed and retained. It was not used to
tune V2.

V2 used new task IDs, prompts, literals and oracle values.

### V2 state-machine correction

V2 replaced the contradictory preflight with a frozen monotonic state machine:

```text
EMPTY
  ->
270M_COMPLETE
  ->
1B_COMPLETE
  ->
4B_COMPLETE
  ->
ANALYZED
```

Before a later stratum could run:

* every previous stratum had to exist;
* every previous stratum had to authenticate;
* completed strata were immutable;
* current and future outputs had to be absent; and
* partial files blocked execution.

A completed canonical stratum could not be overwritten, appended, resumed or
rerun.

The real canonical experiment successfully traversed:

```text
EMPTY -> 270M_COMPLETE -> 1B_COMPLETE -> 4B_COMPLETE -> ANALYZED
```

The specific V1 failure mode was therefore eliminated prospectively rather
than repaired after observing V2 results.

Focused V2 tests passed 23/23. The synthetic dry-run produced 600 rows while
making zero generation requests and creating zero canonical outputs. The
critical synthetic transition from `270M_COMPLETE` to the 1B preflight passed.

### Frozen chain

| Role                           | Commit                                     |
| ------------------------------ | ------------------------------------------ |
| V1 design freeze               | `9021d4b2c51d05f247c7d3f04c087a62ad789d03` |
| V1 implementation freeze       | `34f5f1f3451524325d98fb8d672fd03baebb8747` |
| V1 halted results and incident | `5837f2a8b8bd0ead1a21b9af231d8ecfec2902db` |
| V2 design freeze               | `d7de1d5eeab6c3a3fc58554c46e1fa68388c0136` |
| V2 implementation freeze       | `fb2d68f3c18dc080f276151386b8a92878701c91` |
| V2 canonical results freeze    | `e84a7a21d9e492d4e562d2ef9f4973caef8c2136` |

V2 frozen design hashes:

| Artifact                                     | SHA-256                                                            |
| -------------------------------------------- | ------------------------------------------------------------------ |
| `PROSPECTIVE_CONTRACT_VALIDATION_V2_PLAN.md` | `5eb789d210360e5ade44755cfdc3a1e54f3f67f08d95f3f11a66da33a0a62528` |
| `benchmark_prospective_contract_v2.json`     | `9932a510ed5592801b8a2bc3ab4cc3dbbebd3042a3b434fe6d683e48daf50e27` |
| `validator_contracts_prospective_v2.json`    | `cfbb36c1d9c3dc2ecc755348ffc9e4ca620d56220501b0879580a0f4d6868007` |

### Primary result

All 300 primary generations completed successfully.

| Stage                         | Accepted | Correct | Incorrect |
| ----------------------------- | -------: | ------: | --------: |
| Legacy baseline gate          |      274 |      99 |       175 |
| After deterministic contracts |      130 |      99 |        31 |

The prospective contracts caught 144 of the 175 baseline false accepts:

```text
144 / 175 = 82.2857%
```

Primary false-accept catch rate:

```text
82.3%
```

No baseline-correct survivor was rejected:

```text
0 / 99
```

No incorrect output rejected by the baseline gate was newly admitted.

The wrong-answer share among accepted outputs fell from:

```text
175 / 274 = 63.9%
```

to:

```text
31 / 130 = 23.8%
```

### Frozen bootstrap

The analysis used a deterministic 10,000-draw task-cluster bootstrap:

* namespace: `prospective_contract_validation_v2`
* seed: `20260901`
* 20 primary tasks sampled with replacement
* all five repetitions and all three model strata carried together
* SHA-256 counter sampler
* Hyndman-Fan Type 7 percentiles
* 2.5% and 97.5% bounds

The 95% interval for the primary false-accept catch rate was:

```text
63.9%–96.7%
```

All 10,000 draws were defined.

The historical retrospective result of 69.6% lies inside this interval.
The prospective experiment therefore supports replication of a large
false-accept reduction. It does not establish superiority, equivalence or
non-inferiority relative to the retrospective result.

### Result by model

| Model        | Primary correctness | Baseline false accepts | Caught | Remaining | Catch rate | Correct rejected |
| ------------ | ------------------: | ---------------------: | -----: | --------: | ---------: | ---------------: |
| Gemma 3 270M |              10/100 |                     80 |     70 |        10 |      87.5% |                0 |
| Gemma 3 1B   |              25/100 |                     65 |     49 |        16 |      75.4% |                0 |
| Gemma 3 4B   |              70/100 |                     30 |     25 |         5 |      83.3% |                0 |

Increasing model size materially reduced the underlying error burden:

```text
270M: 10% correct
1B:   25% correct
4B:   70% correct
```

Deterministic contracts nevertheless caught false accepts at all three model
sizes.

No model-specific significance test was preregistered. The differences between
the three catch rates must not be described as statistically meaningful without
a new explicitly defined analysis.

### Result by primary contract type

| Contract type   | Baseline false accepts | Caught | Catch rate |
| --------------- | ---------------------: | -----: | ---------: |
| Bullet format   |                     45 |     45 |       100% |
| Label format    |                     60 |     59 |     98.33% |
| JSON format     |                     35 |     25 |     71.43% |
| Structured JSON |                     35 |     15 |     42.86% |

By primary cohort:

| Cohort             | Baseline false accepts | Caught | Remaining | Catch rate |
| ------------------ | ---------------------: | -----: | --------: | ---------: |
| Format conformance |                    105 |    104 |         1 |     99.05% |
| Structural schema  |                     70 |     40 |        30 |     57.14% |

The contracts were strongest when incorrect output created an observable
format or structural violation. They were weaker when an incorrect answer
could still satisfy the declared schema.

No baseline-correct survivor was rejected in any primary contract type.

### C — semantic boundary

Label conformance was reported separately from the primary result.

| Observations | Oracle-correct | Baseline false accepts | Caught | Remaining |
| -----------: | -------------: | ---------------------: | -----: | --------: |
|          150 |            100 |                     50 |      5 |        45 |

Catch rate:

```text
5 / 50 = 10%
```

All 45 remaining errors were wrong-but-permitted labels.

A permitted-label contract can establish whether an output belongs to the
allowed label set. It cannot establish which permitted label is semantically
correct.

This was an intended boundary condition and prevents the primary finding from
being presented as a general solution to semantic correctness.

### D — deterministic bypass

Deterministic execution was also reported separately from the primary result.

| Observations | Oracle-correct | Baseline false accepts | Caught | Remaining |
| -----------: | -------------: | ---------------------: | -----: | --------: |
|          150 |             15 |                    135 |    135 |         0 |

By construction, the deterministic executor and oracle compute the same
function, so their exact agreement carries no information about validator
effectiveness. The cohort demonstrates that these mechanical transformations
are executable in code and should bypass generative inference.

D must not be folded into the primary contract-validator headline.

### Preserved canonical V2 outputs

| Artifact                                                     | SHA-256                                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------------ |
| `benchmark_prospective_contract_v2_gemma3_270m.jsonl`        | `ff99425c76877758971784db03b9943c49ee9aa94b03034b112bfeb74ad2ef1e` |
| `benchmark_prospective_contract_v2_gemma3_270m_summary.json` | `bc79ab6594b85e81319fda75a6a6c7832740997d423c7d042b58d74adb1d2d6b` |
| `benchmark_prospective_contract_v2_gemma3_1b.jsonl`          | `51ef79b72e4ac02d2aa12b039c606550978dc87d8df15069a9f6a93356ab7052` |
| `benchmark_prospective_contract_v2_gemma3_1b_summary.json`   | `a5c80d6c2b5780f5296309df3766c97f755ca43487df2cedcec4091376bdff90` |
| `benchmark_prospective_contract_v2_gemma3_4b.jsonl`          | `a9102caa11242cb275f3956e26daddd0e3be5f6f2fbae47533c8375289de9c18` |
| `benchmark_prospective_contract_v2_gemma3_4b_summary.json`   | `e95efa983d4e0f6fc3db4cf23633062b517b4fbe60aa7a3fa8a7845045f3b8ca` |
| `prospective_contract_validation_v2_analysis.json`           | `c6d5dda2398072ee1f6c8ab0a539672ee321edf0d7013b80202ffb6c0379e159` |
| `prospective_contract_validation_v2_analysis.csv`            | `a8f35a6ddd4dfddeb4ceecc1da8894c6e49e1b4e0db37b1935a07d9910a1c995` |

These canonical artifacts are sealed. They must not be modified or rerun.

### Architectural interpretation

The experiment supports a three-layer Adaptive Router architecture:

1. **Model capability** reduces how often the model is wrong.
2. **Deterministic contracts** reduce how often observable wrong outputs are
   accepted.
3. **Deterministic execution** bypasses the model for work ordinary code can
   perform exactly.

Increasing model capability and deterministic contract validation are
complementary controls. Neither substitutes for the other.

### Interpretation boundaries

The experiment does not establish that:

* contracts make outputs 82.3% correct;
* deterministic contracts solve semantic correctness;
* the prospective result is significantly better than the historical 69.6%;
* model-specific catch rates differ significantly;
* zero observed correct rejections proves that the true rejection rate is zero;
* contracts reduce cost or energy per successful task; or
* the router can yet select the best contract for arbitrary unseen work.

The evidence is limited to three sizes of one local model family, 20 primary
constructed tasks, five repetitions per task and temperature-zero generation.
The task-cluster interval is consequently broad.

### Decision and next phase

Prospective Contract Validation V2 is complete.

No further canonical model execution is required, and no canonical evidence or
analysis artifact is to be changed.

The next phase is public research communication:

* concise methodology;
* experiment lineage;
* result graphs;
* architectural implications;
* semantic-boundary and deterministic-bypass findings;
* limitations; and
* reproducibility references.

A self-contained public case-study draft has been prepared outside the
canonical experiment. It is not part of the V2 evidence freeze. Before any
repository or public release, every displayed count, percentage, interval,
filename and hash must be checked byte-for-byte against the sealed canonical
analysis artifacts.

No new model experiment should begin until its intended research question has
been explicitly defined.

---

## 2026-09-02 — Repository repair and measured paired routing replay v1

### V1 regression repair

An external repository review reproduced all published Prospective Contract
Validation V2 headline figures from the raw JSONL, then identified one
permanent failure in the full test suite.

The V1 dry-run test still expected a successful empty-output preflight after
the halted 270M evidence had been sealed in the repository. The frozen V1
runner correctly refused those existing canonical paths, so the test encoded
the same protocol-instrument contradiction documented in
`PROSPECTIVE_CONTRACT_VALIDATION_V1_EXECUTION_INCIDENT.md`.

PR #7 replaced that impossible expectation with a regression test asserting
that:

- the sealed V1 270M evidence blocks the superseded dry run;
- both canonical filenames appear in the failure; and
- no generation request occurs.

The repair did not modify V1 semantics or any sealed evidence. The same PR
tightened the public V2 case study by stating that Cohort D executor/oracle
agreement is exact by construction, identifying structured JSON as the source
of 20 of 31 remaining primary false accepts, and qualifying the 0/99 observed
correct-rejection result.

Merge commit: `857d6db`

Full repository result after the repair: 256 tests passed.

### Measured replay objective

Replace Routing Simulation Zero v1's uniform assumed remote-success rates with
the 150 paired outcomes actually measured for Gemma 3 270M and OpenRouter Luna.
No model or network request was made.

| Input | SHA-256 |
|---|---|
| `benchmark_runs_simzero_v2.jsonl` | `5637130c56894a0263c534bb87c5037901f0e535df28e658f68d5e85c03f7f6e` |
| `benchmark_runs_openrouter_luna_v1.jsonl` | `341d203f34f3789e489329030895970e719483334e42d2ac144080516e3c0405` |

All 150 task/repetition keys paired exactly. The committed implementation used
for canonical output was `773a63333bfcce031b991ae24ebc3615cf60b6ff`.
The two result files were committed together at `120df2b`.

### Paired overlap

| Interpretation | Both correct | Local only | Remote only | Neither | Oracle selector ceiling |
|---|---:|---:|---:|---:|---:|
| Strict | 66 | 0 | 62 | 22 | 128/150 |
| Audited | 69 | 2 | 74 | 5 | 145/150 |

Under the strict oracle, local correctness was a subset of remote correctness.
The two audited local-only observations corresponded to remote transport
failures, not a demonstrated local capability advantage.

### Policy result

| Interpretation | Policy | Passes | Remote calls | Reported remote cost | Median selected time |
|---|---|---:|---:|---:|---:|
| Strict | Always local | 66/150 | 0 | $0 | 262.133 ms |
| Strict | Always remote | 128/150 | 150 | $0.0054320 | 1,847.455 ms |
| Strict | Coarse class | 116/150 | 75 | $0.0027282 | 966.929 ms |
| Strict | Fine capability | 125/150 | 75 | $0.0024892 | 990.314 ms |
| Audited | Always local | 71/150 | 0 | $0 | 262.133 ms |
| Audited | Always remote | 143/150 | 150 | $0.0054320 | 1,847.455 ms |
| Audited | Coarse class | 131/150 | 75 | $0.0027282 | 966.929 ms |
| Audited | Fine capability | 140/150 | 75 | $0.0024892 | 990.314 ms |

At the same 75-call budget, fine routing gained nine passes over coarse routing
under both interpretations. Relative to always remote, fine routing used 50%
fewer remote calls, reduced recorded remote cost by approximately 54.2%, and
lost three passes, or 2.0 percentage points.

The latency values replay one selected route and do not represent a live
local-first fallback. Reported OpenRouter cost is not an energy measurement.

### Preserved outputs

| Artifact | SHA-256 |
|---|---|
| `routing_simulation_measured_v1.json` | `8eb3a3514e544d10594bf0fd82223293347340c4619400acaa7e9e20a41622ed` |
| `routing_simulation_measured_v1.csv` | `8e2d6ef34678840390bd7ca36e7c163644e6fa634d33b3427731455eb2713d53` |

Result document: `ROUTING_SIMULATION_MEASURED_V1.md`

### Decision

The measured replay is promising enough to continue but does not validate the
270M fine policy for deployment. It is in-sample with respect to local
capability selection and omits the later scaling, contract, and deterministic
executor components.

The next product phase is an explicit end-to-end router design combining direct
deterministic execution, an empirically selected local tier, task contracts,
OpenRouter escalation, and defined remote failure handling. That complete
policy requires a fresh prospective evaluation of final user-visible outcomes.
---

## 2026-09-02 — Runtime v0.2 contract-routing product slice

### Objective

Turn the accumulated routing, scaling, contract-validation and deterministic-
executor evidence into a first usable runtime slice. This was product
implementation, not a new benchmark and not a claim that the complete router
policy is deployment-ready.

Branch: `feature/runtime-v0.2-contract-routing`

Base commit: `e986714`

### Implemented boundary

- Added strict `runtime_request_v1` request documents.
- Added exact-key and declared-type JSON contracts, bullet and label-format
  contracts, and remote-only classification-label contracts.
- Added allowlisted deterministic operations that bypass both Ollama and
  OpenRouter.
- Changed legacy validation to fail closed: `NOT_APPLICABLE` now escalates
  instead of accepting local output.
- Applied explicit contracts to final successful remote responses as well as
  local responses. A nonconforming final response is withheld under
  `REMOTE_CONTRACT_FAILED`.
- Added bounded OpenRouter retries for timeouts, connection failures, HTTP
  408/429 and HTTP 5xx. Authentication/client failures and malformed success
  responses are not retried.
- Changed the checked-in remote model from the unusable `CHANGE_ME` placeholder
  to the measured `openai/gpt-5.6-luna` model.
- Aligned live Ollama generation with the frozen prospective settings:
  temperature zero, 256 maximum output tokens and persistent residency.
- Aligned JSON outer-fence normalization with Prospective Contract Validation
  V2.
- Added end-to-end `decision.total_ms` telemetry without logging prompts,
  answers or deterministic source literals.

### Verification

Final pre-PR local result:

```text
14 focused runtime-contract tests passed
295 full repository tests passed
suite_exit=0
```

The seven pre-existing untracked audit/review artifacts were not staged,
modified or deleted.

### Bounded live smoke observations

These were ordinary live checks against the development branch. Their
`runs.jsonl` records remain local and uncommitted; they are not canonical
benchmark evidence.

| Path | Visible result | Route/provider time | Cost | Interpretation |
|---|---|---:|---:|---|
| Legacy unknown prompt | exact requested text | Luna 1,410 ms | $0.0000194 | Direct remote path, one attempt |
| Initial structured request | correct remote JSON after local parse rejection | local 7,085 ms + remote 2,271 ms | $0.0000418 | Safety worked, but local-first fallback imposed at least 9.36 s provider time |
| Aligned structured request | fenced JSON with `name` and `count` | 714 ms end to end; local 569 ms | $0 | Local contract path, no remote call |
| Classification contract | `positive` | 1,445 ms end to end; Luna 1,306 ms | $0.0000128 | Direct remote; final label-membership contract passed |

The aligned structured output visibly matched the supplied example, but the
runtime gate established only exact keys and JSON value types. It did not
establish semantic truth. Likewise, label membership does not establish that
the selected label is semantically correct.

The large difference between the two local structured runs is not attributed
to one cause. Residency/warm state, generation settings and contract
normalization changed between them. These smokes were not a controlled paired
experiment.

### Development incidents before merge

One remote edit inserted a literal `\\n` into Python source and prevented the
new modules from importing. Focused execution exposed it; commit `c5e7f2e`
restored valid syntax.

End-to-end latency instrumentation initially referenced `time.perf_counter()`
without importing `time`. The live request aborted before metrics collection,
model calls or logging. Commit `17d6a77` added the import, and router tests
require `decision.total_ms` on every recorded route.

A new regression test then showed that uppercase permitted-label declarations
were not rejected by the request schema. Commits `0af6d17` and `49e80ab`
closed that boundary and added malformed nested-value cases.

None of these defects reached `main`, altered sealed evidence or produced a
canonical result.

### Decision and next boundary

Runtime v0.2 now demonstrates three functioning user-visible paths:
deterministic execution, contract-gated local inference and contract-checked
OpenRouter routing. The slice is suitable for pull-request review.

It is not yet a validated adaptive policy. In particular, structured JSON can
contain semantically wrong but schema-conforming values, and local-first
fallback can be much slower than direct remote routing. After merge, the next
phase must define and freeze the automatic pre-routing policy, then evaluate
the assembled runtime prospectively on fresh tasks. Percentages from earlier
unpaired suites must not be combined as if they were observations from this
runtime.

---

## 2026-09-02 – 2026-09-03 — Runtime v0.2 prospective evaluation v1

### Objective and frozen boundary

Evaluate the released v0.2 product runtime end to end on fresh,
deterministically scored requests. The primary question was whether the
assembled runtime returned correct final user-visible results while reducing
OpenRouter use relative to always-remote execution.

The suite contained 40 tasks with three repetitions each:

| Cohort | Tasks | Runtime observations | Runtime path |
|---|---:|---:|---|
| Deterministic | 10 | 30 | Python executor; neither provider |
| Structural JSON | 12 | 36 | Local first; contract-gated fallback |
| Line format | 8 | 24 | Local first; contract-gated fallback |
| Classification | 10 | 30 | Direct OpenRouter |
| **Total** | **40** | **120** | |

Each of the 90 generative observations retained one local and one remote
provider output. The actual runtime output supplied an arm where possible and
only the missing provider arm was run as a control. Canonical execution
therefore made exactly 90 logical Ollama calls, 90 logical OpenRouter calls and
30 deterministic executions. There were no experiment-level retries,
replacement tasks or skipped failures.

Frozen identities:

| Item | Identity |
|---|---|
| Released runtime | tag `v0.2.0`, commit `307a47389fea10df38623bc2f238a14a11081269` |
| Execution implementation | `18b04a27a64dbd8fffa841d36be9394285562610` |
| Local model | `gemma3:270m`, Q8_0 digest `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be` |
| Remote model | `openai/gpt-5.6-luna` |
| Plan SHA-256 | `d051be7261d708d3adef7f807b8899ca02b88c11531e4f9b3e28eb4ef3c3de98` |
| Benchmark SHA-256 | `384a64905d6bee062a51444442752737911d2c5c5b96a14eba0164a35c7c8acb` |
| Config SHA-256 | `0ca3fb1cae7ae78798ff9566f72fe3a70bf45c0d5f184acc1360ee96c0d44522` |

Before execution, 22 focused tests and all 317 repository tests passed. The
synthetic dry run exercised all 120 observations, 90 synthetic local calls and
90 synthetic remote calls while making zero provider requests and creating
zero repository outputs. The metadata-only preflight authenticated the
revision, input hashes, provider identities and empty output state without
making a generation request.

### Canonical execution

The one-shot execution completed successfully with exit status zero:

| Measure | Result |
|---|---:|
| Runtime observations | 120 |
| Final outputs correct | 117/120 |
| Accepted errors | 3 |
| Withheld outputs | 0 |
| Local logical calls | 90 |
| Remote logical calls | 90 |
| Remote HTTP attempts | 90 |
| Internal remote retries | 0 |
| Total reported remote-control cost | USD 0.0032856 |

The evidence was committed at `8509d2b`; the canonical analysis was committed
separately at `487e6b3`.

### Generative policy result

The 30 deterministic observations were all correct and made no provider call.
They demonstrate the released bypass path, not model routing or validator
effectiveness.

For the 90 generative observations:

| Policy or provider | Correct | Remote calls | Median time |
|---|---:|---:|---:|
| Released v0.2 runtime | 87/90 | 69 | 2,316.095 ms |
| Paired always local | 36/90 | 0 | 539.214 ms |
| Paired always remote | 90/90 | 90 | 1,948.776 ms |

Provider overlap was:

| Both correct | Local only | Remote only | Neither |
|---:|---:|---:|---:|
| 36 | 0 | 54 | 0 |

Local correctness was therefore a strict subset of remote correctness in this
suite. The runtime avoided 21 remote calls but lost three correct results
relative to always remote. The task-cluster bootstrap used 10,000 frozen
SHA-256-defined draws with zero undefined draws. Its 95% interval was 90%–100%
for runtime correctness and -10 to 0 percentage points for runtime minus
always-remote correctness.

Actual runtime remote calls reported USD 0.0024438, USD 0.0008418 less than
the paired always-remote total, a reduction of approximately 25.6%. This is
reported provider cost only. Local energy and local monetary cost were not
measured.

The runtime median was about 367 ms slower than the paired direct-remote
median. This is consistent with local-first failures paying local work before
fallback, but the difference between medians is descriptive and is not a
paired latency estimate.

### Where the policy worked and failed

| Cohort | Runtime correct | Local accepted | Remote calls | Accepted errors |
|---|---:|---:|---:|---:|
| Structural JSON | 36/36 | 18 | 18 | 0 |
| Line format | 21/24 | 3 | 21 | 3 |
| Classification | 30/30 | 0 | 30 | 0 |

All three accepted errors were `bullet_format` outputs. The local provider
was oracle-incorrect on all 24 line-format observations, but three wrong bullet
outputs passed the deterministic shape contract and were returned. The
`label_format` gate rejected all 12 local outputs and escalated them.

Structural JSON was the only measured local-first cohort that saved remote
calls without losing correctness: 18 of 36 outputs were accepted locally and
all 36 final results were correct. This does not establish semantic JSON
correctness generally; the contracts can still accept wrong values that have
the declared keys and types.

Classification routed directly remote and was correct on all 30 observations.
Although the paired local control happened to be correct on 18, label
membership cannot determine which permitted label is semantically correct, so
the runtime did not use those local outputs.

### Preserved artifacts

| Artifact | SHA-256 |
|---|---|
| `runtime_v0_2_prospective_v1_runs.jsonl` | `a4554f6df094f05a7a4dbd19e260f60a09d6a725405117f8585343b1e6a9f3c5` |
| `runtime_v0_2_prospective_v1_router_telemetry.jsonl` | `ff8088c218ec261c3d51789207b9ec2ab70415384533ae8dee93c23f3c6fe6e6` |
| `runtime_v0_2_prospective_v1_summary.json` | `4157d30e5e92cc495d4aa6309565a06c50d4e2d1cbf1f3435fac8d49f4e979db` |
| `runtime_v0_2_prospective_v1_analysis.json` | `b901a005e0e6e760e41648a194f8c8be659de218b9caef8a51ba114e83b5b848` |
| `runtime_v0_2_prospective_v1_analysis.csv` | `7d5504530d2f2840544f351458b162fb004d59a39d065f8c468fd7f052ce87b9` |

These outputs are sealed and must not be modified, regenerated or used to tune
a claim about this same prospective suite.

### Procedural disclosures

Before the first provider request, an accidental command-output footer was
removed from the plan, an incorrect frozen config hash caused a fail-closed
test and was corrected, and metadata preflight environment loading was fixed.
Focused regression tests were added. None of these pre-execution incidents
created canonical output or called a provider.

After evidence was sealed, the analysis program was invoked without
`--write` under the mistaken assumption that this was a dry run. That
invocation actually created the two canonical analysis files. A subsequent
`--write` invocation correctly refused to overwrite them with
`ANALYSIS_ALREADY_EXISTS`. The files from the first successful invocation
were retained, hashed and committed without regeneration.

After the canonical outputs were committed, the full repository suite exposed
a lifecycle regression in
`test_metadata_preflight_makes_no_generation_request`. The test still required
the execution preflight to report `EMPTY`, although the now-sealed evidence
correctly makes that state impossible. PR #10 had already been opened when the
failure was observed. The test was split into a mocked-empty positive report
test and a repository-state regression test proving that sealed evidence raises
`OUTPUT_STATE_NOT_EMPTY` before model metadata lookup or either provider
generation function. The runner and all canonical artifacts remained
unchanged.

### Decision and next boundary

Runtime v0.2 is functioning software, but this prospective result does not
validate its local-first policy as a generally preferable default. In this
suite it exchanged three correct answers and higher median latency for 21
avoided remote calls and about USD 0.00084 in reported API cost.

No v0.2 thresholds, prompts or contracts are changed from these same outcomes.
A successor v0.3 should preserve deterministic bypass, retain direct remote
routing for semantic classification, and prevent unproven local acceptances
from reaching users. Candidate local paths should begin in shadow mode and
earn task-specific authority prospectively. The first concrete safety change
is to remove `bullet_format` from user-visible local acceptance; all measured
local bullet outputs were wrong despite three passing the shape contract.

Structural JSON remains a candidate for narrowly bounded local use because it
saved 18 remote calls without an observed final error here, but its contracts
establish shape and declared types rather than semantic truth. It requires
additional prospective evidence before a broader deployment claim.

---

## 2026-09-03 – 2026-09-06 — Runtime v0.3 safe-routing product boundary

### Objective

Convert the prospective v0.2 result into a safer default product policy. The
v0.2 runtime avoided 21 of 90 generative remote calls but returned three local
bullet-content errors that the shape contract accepted. The paired remote arm
was correct on all 90 generative observations. v0.3 therefore treats contract
conformance as a necessary output check, not sufficient authority to expose an
unproven local generation.

Branch: `feature/runtime-v0.3-safe-routing`

Base commit: `21d4b9f`

### Implemented boundary

- Generative runtime contracts now route to OpenRouter by default.
- Legacy tasks that were formerly local eligible also route remote under the
  checked-in policy.
- Deterministic executor requests continue to bypass both providers.
- `classification_labels` remains explicitly remote-only.
- Added stable reason `SAFE_REMOTE_POLICY` for generative requests retained on
  the authoritative remote path.
- Added `routing.allow_user_visible_local`, defaulting to `false`. The old
  local-first path remains available only as an explicit operator override for
  controlled comparison and rollback.
- Implemented actual opt-in shadow execution. A request must be selected by the
  deterministic sampler and both `shadow.enabled` and `shadow.execute` must
  be true.
- The remote result is fixed before shadow execution. Shadow output is never
  returned, supplied to OpenRouter, or written to telemetry. Only provider
  metadata and contract-conformance status are retained.
- Shadow failure or nonconformance cannot change or withhold the authoritative
  remote result.
- Local health and residency gates still apply before an enabled shadow model
  call. Shadow execution is synchronous and therefore adds measurement latency
  when enabled; it remains disabled in the checked-in configuration.

### Frozen-config lifecycle repair

The released v0.2 prospective instrument authenticated the mutable live
`config.json` directly. Adding the v0.3 policy field would therefore have made
the historical full-suite hash test fail even though the sealed evidence was
unchanged.

The exact v0.2 configuration bytes were preserved as
`config_runtime_v0_2_prospective_v1.json`. The historical instrument now
authenticates that immutable snapshot under the original SHA-256
`0ca3fb1cae7ae78798ff9566f72fe3a70bf45c0d5f184acc1360ee96c0d44522`.
No plan, benchmark, evidence, summary, or analysis artifact was modified.

The first full v0.3 suite then exposed a second compatibility boundary:
the preserved v0.2 file correctly omitted the new flag, while the v0.3 router
correctly interprets an absent flag as fail-safe remote-only. The historical
synthetic replay consequently made 90 remote calls instead of reproducing
v0.2's expected 30. The v0.2 runner now adds
`allow_user_visible_local=true` only to its in-memory replay configuration
after reading the authenticated bytes. A focused regression test requires both
the absent field in the frozen file and the explicit compatibility value in
memory. This changes neither the frozen hash nor production v0.3 policy.

### Bounded live smoke observations

These checks used the development branch and are not canonical benchmark
evidence.

| Path | Outcome | Provider behavior | End-to-end time |
|---|---|---|---:|
| Structured JSON, shipped configuration | Remote JSON passed exact-key/type contract | Remote authoritative; local not attempted; shadow not selected | 2,395.695 ms |
| Structured JSON, temporary forced shadow sample | Remote JSON remained authoritative; local shadow also passed shape/type contract | One remote call and one local shadow call; no shadow text logged | 3,591.143 ms |

The forced shadow observation recorded a resident 325,666,733-byte local model,
228.110 ms TTFT, 674.402 ms local total time and 53.509 tokens/second. Those
figures describe one warm live observation and establish no latency or
correctness distribution.

Both outputs visibly matched the example answer. The validators established
only exact JSON keys and declared value types; they did not establish semantic
truth.

### Final pre-PR verification

```text
24 focused v0.2 prospective compatibility tests passed
324 full repository tests passed
suite_exit=0
```

The preserved v0.2 configuration retained SHA-256
`0ca3fb1cae7ae78798ff9566f72fe3a70bf45c0d5f184acc1360ee96c0d44522`.
`git diff --check` passed. The seven pre-existing untracked audit and review
artifacts were not staged, modified or deleted.

### Decision and next boundary

v0.3 is a safety correction, not evidence that adaptive routing is solved.
The shipped runtime now provides useful deterministic execution and
contract-checked remote generation without exposing local candidates that have
not earned authority.

The next experimental step is prospective shadow collection on explicitly
defined task families. Any future user-visible local route must be justified by
fresh, paired evidence with task-specific correctness oracles, false-accept
limits, latency and cost accounting, and a precommitted promotion rule. Shape
contracts alone cannot promote a capability.

---

## 2026-09-08 — Runtime v0.3 structural-JSON shadow evaluation V1 halted

### Objective

Prospectively test whether `gemma3:270m` could earn narrowly bounded
user-visible authority for structural JSON while released runtime v0.3
continued to return the OpenRouter result. The frozen suite specified 40 fresh
tasks, three repetitions, paired remote and local-shadow arms, exact recursive
JSON oracles, and a zero-local-accepted-error promotion rule.

Branch: `experiment/runtime-v0.3-shadow-json-v1`

Design freeze: `2ad263e249b06127267e041fe51cd1a73250bf1d`

Execution implementation: `560be38853aeae60b1fdc4e04bf8d5c3436dfde6`

### Pre-execution verification

Nineteen focused tests and all 343 repository tests passed. The synthetic dry
run completed all 120 observations with 10,000 bootstrap draws, made zero
provider network requests, and created no repository output. Metadata preflight
authenticated the frozen plan, benchmark, config, implementation revision,
local model, remote model, and empty output state.

### Execution incident

The one-shot provider execution halted at observation 48 with
`PROVIDER_ARM_FAILURE`. It retained 47 completed paired rows and 48 router
telemetry rows. The failed observation was `select_06`, repetition 3.

The authoritative remote arm received HTTP 200 but recorded
`OPENROUTER_RESPONSE_INVALID`, with one attempt and no retry. The response ID,
finish reasons, usage, cost, and router metadata were absent. This establishes a
runtime response-schema failure but does not identify whether OpenRouter, an
upstream provider, an intermediary, or an unhandled legitimate response variant
was responsible.

The local shadow arm completed successfully and passed its structural contract.
The router nevertheless recorded `REMOTE_ERROR` and did not substitute the
shadow output. This is the intended remote-authoritative safety behavior.

Partial evidence was preserved at
`9dd9952ca9498f82d2e380b5e256bada6aafa3e9`:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `runtime_v0_3_shadow_json_v1_runs.jsonl.partial` | 47 | `a0611b82b1e28ccb992158631c7a15a5877b6b46dfa8b6323a0f8e3ab038ecf5` |
| `runtime_v0_3_shadow_json_v1_router_telemetry.jsonl.partial` | 48 | `0a087031de14ea823ba8f5ccd33e4be48fb8c388a0485a319df7a5871da4b289` |

No canonical result or analysis files were created. The partials were not
deleted, repaired, resumed, or promoted to canonical evidence.

### Decision and next boundary

V1 is **incomplete and promotion is blocked** under its precommitted stop rule.
The 47 completed rows are diagnostic evidence, not the planned 120-observation
effectiveness estimate. No local-model promotion or rejection claim is made
from them.

A successor must be a separately frozen V2 with fresh tasks. Its plan must
decide prospectively how malformed HTTP-200 remote responses are handled and
should consider a canonical failure manifest. V1 must not be rerun or resumed.
See `RUNTIME_V0_3_SHADOW_JSON_V1_EXECUTION_INCIDENT.md`.


## 2026-09-08 — Runtime v0.3 structural-JSON shadow V2 framing reconciliation

### Scope

After the V2 runner and analyzer were implemented but before any provider
generation request, a second framing review identified useful clarifications
around logical calls, HTTP attempts, fallback latency, and missing cost
metadata. Two attempted executions stopped at frozen-plan authentication after
the plan had been modified locally; both stopped before model or provider
generation. The uncommitted review was preserved at SHA-256
`16ce80fe9cc12b25f8cc38046238f462ef4d39fba77f27e2fac60fd097455256`
before the tracked files were restored.

### Reconciliation

- Completed evidence now requires exactly 120 local and 120 remote logical
  calls. Remote HTTP attempts are separately reconciled from `attempt_count`
  and must total 120..240; `retry_count` must equal `attempt_count - 1`.
- Counterfactual local-first latency is calculated per observation. A local
  contract pass uses local latency; a local failure or rejection uses local plus
  remote latency to represent sequential fallback.
- Promotion retains the authoritative remote-provider median as its latency
  comparator. Actual runtime latency includes synchronous shadow measurement
  overhead and is reported descriptively rather than used as the baseline.
- Successful remote results require finite reported cost. A failed provider
  result may have unavailable cost, as occurred in V1; it remains a measured
  outcome but consumes a frozen conservative USD 0.001 reserve. Reported and
  reserved costs remain separate, and their sum governs the USD 0.03 stop rule.
- Provider and decision latencies must be finite, non-negative, non-Boolean
  numbers. Primary denominators, logical calls, HTTP attempts, and analysis
  input artifacts are explicit.

### Gotchas

Making null cost fatal would have recreated the V1 failure mode for an
`OPENROUTER_RESPONSE_INVALID` result. Treating it as zero would instead make
the spending limit unenforceable. The conservative reserve preserves the
service outcome without granting free budget. Comparing local-first fallback
against end-to-end shadow runtime would also favor promotion because that
runtime deliberately pays for both arms; the remote-provider arm is the cleaner
deployable baseline.

The reconciled plan SHA-256 is
`d33b1c4c611b815313d8b27fcd04ec29a4fbc62465e7ed80f30564c12af441a3`.
Focused compilation, 27 V2 tests, and the synthetic 120-observation dry run
passed without network requests or repository outputs. Full-suite and live
preflight verification remain required before execution.

## 2026-09-08 — Runtime v0.3 structural-JSON shadow V2 result

### Scope and execution

V2 was a separately frozen, one-shot prospective evaluation of the released
remote-authoritative v0.3 runtime and a non-authoritative local shadow. It used
40 fresh structural-JSON tasks across four predeclared strata, with three
repetitions each: 120 ordered observations and one paired local and remote
logical call per observation.

Before execution, 27 focused V2 tests and all 370 repository tests passed. The
synthetic dry run completed 120 observations with 10,000 bootstrap draws,
made zero provider network requests, and created no repository outputs.
Metadata preflight authenticated the plan, benchmark, config, implementation
revision, both model identities, and an empty output state.

The single sealed provider execution completed successfully. It captured 120
runs and 120 router telemetry rows, exactly 120 local logical calls, exactly 120
remote logical calls, and 120 remote HTTP attempts. All local calls completed.
The remote arm completed 118 calls successfully and retained two
`OPENROUTER_RESPONSE_INVALID` outcomes rather than aborting the experiment.
Both unreported failed-call costs consumed the frozen USD 0.001 reserve.

Execution evidence was committed at
`803d71d`:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `runtime_v0_3_shadow_json_v2_runs.jsonl` | 120 | `1b846bb04cbf335d8bce8b37e5d94cb509a4a06f9a476408023ee7cf80060702` |
| `runtime_v0_3_shadow_json_v2_router_telemetry.jsonl` | 120 | `333a073ab9c50aaa4aafed2f1bc09e65bff49fa7bf45960db016d50a1ae16ba6` |
| `runtime_v0_3_shadow_json_v2_summary.json` | — | `d2a1a1f1d007ebb226f1fadb3df63e7e8248d0ff7514414b35fdec5bfd5c2a6e` |

The authenticated analysis was committed at
`9929c39`:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `runtime_v0_3_shadow_json_v2_analysis.json` | — | `b4a93b8ecee9dc45d17dc281c903cd5a1629ef7f95edc42433562438e0393160` |
| `runtime_v0_3_shadow_json_v2_analysis.csv` | 6 | `196d9d7f31192dd150c77e244e22e3beda32e104021b10421e4e58573cd2b09b` |

Frozen identities:

| Input | SHA-256 |
|---|---|
| Plan | `d33b1c4c611b815313d8b27fcd04ec29a4fbc62465e7ed80f30564c12af441a3` |
| Benchmark | `b160537b15f25941227d9381c0bee625f2af8ed385463b1608a6568f1079e278` |
| Config | `36df214e322b8148614e0ac8289ddb77779e326e06d91e3780ea39b87bd01657` |
| Implementation | `ca9f915d4f25b25113faa11ef33d8b2db903a679` |

### Primary result

The precommitted decision is **`DO_NOT_PROMOTE`**.

The authoritative runtime was correct on 105/120 observations (87.5%). The
local arm was correct on 16/120 (13.3%). A local-first counterfactual that
accepted every local contract PASS and otherwise fell back to remote was
correct on 83/120 (69.2%), 22 fewer correct observations than the released
runtime.

The local contract passed 39 outputs, but 23 of those accepted outputs were
wrong: an accepted-error rate of 23/39 (59.0%). Its exact one-sided 95%
Clopper-Pearson upper bound was 72.3%, far above the precommitted 5% ceiling.
The counterfactual avoided 39 remote logical calls; the task-cluster bootstrap
95% interval was 23..57, and the point estimate did not reach the required 60.
The bootstrap 95% interval for counterfactual-minus-runtime correctness rate
was -30.8 to -7.5 percentage points.

Median measured latencies were 992.9 ms for the paired local arm, 2916.0 ms
for the remote provider arm, 3610.4 ms for deployable sequential local-first
fallback, and 4202.3 ms for the actual synchronous-shadow runtime. The
counterfactual therefore failed its deployable comparison with direct remote
service even though it was faster than the deliberately two-arm shadow
runtime.

Reported remote cost was USD 0.0109828. Two remote failures had no reported
cost and consumed USD 0.002 of frozen conservative reserve, for USD 0.0129828
total budget accounting, below the USD 0.03 ceiling.

### Stratum results

| Stratum | Remote correct | Local correct | Local PASS | Accepted errors | Counterfactual correct |
|---|---:|---:|---:|---:|---:|
| Flat scalar | 30/30 | 7/30 | 13/30 | 6 | 24/30 |
| Nested collection | 19/30 | 0/30 | 5/30 | 5 | 15/30 |
| Record selection | 27/30 | 0/30 | 9/30 | 9 | 18/30 |
| Type boundary | 29/30 | 9/30 | 12/30 | 3 | 26/30 |
| **Overall** | **105/120** | **16/120** | **39/120** | **23** | **83/120** |

The local model produced no correct answer in either nested collection or
record selection. Every locally correct result was also remotely correct:
overlap was 16 both-correct, zero local-only, 89 remote-only, and 15 neither.
There is no measured correctness niche in this suite where local rescued a
remote error.

### Promotion criteria

Only evidence completeness and absence of instrumentation/execution failure
passed. Six substantive criteria failed:

- local accepted errors were 23 rather than zero;
- local contract passes were 39 rather than at least 60;
- the accepted-error upper bound was 72.3% rather than at most 5%;
- counterfactual correctness was 83 rather than at least the runtime's 105;
- avoided remote calls were 39 rather than at least 60; and
- counterfactual median request latency was 3610.4 ms rather than at most the
  2916.0 ms remote-provider median.

### Decision and runtime boundary

Structural-JSON local authority remains disabled. The released v0.3
remote-authoritative policy is retained for these generative contracts. Local
shadow measurement may continue for research, but local contract conformance
must not be treated as evidence of semantic correctness or as authorization to
serve the local result.

This does not establish that local routing is impossible. It establishes that
this model, validator, task distribution, and local-PASS policy do not meet the
frozen promotion standard. A successor must change and freeze a substantive
candidate before collecting fresh evidence; it must not tune a decision rule on
these V2 outcomes and present that reuse as prospective validation.

### Gotchas

V2's most important success is methodological rather than promotional. The V1
malformed HTTP-200 condition recurred twice, but the prospectively defined V2
failure representation retained both outcomes and allowed the sealed suite to
complete without treating unknown cost as zero.

The superficially attractive 992.9 ms local-arm median is not a deployable
request-latency result. Because 81 observations would reject or fail local,
real local-first fallback waits for local before remote; its median was 3610.4
ms, slower than direct remote. Likewise, 39 contract passes are not 39 safe
savings: 23 were semantic errors. The experiment again demonstrates that
structural validity and semantic correctness are different quantities.

## 2026-09-08 — Runtime v0.3 structural-JSON retrospective error analysis V1

### Scope and authentication

After V2 rejected local authority, a separate retrospective protocol examined
why the local model failed and whether any deployable, oracle-free subgroup
deserved a fresh prospective test. The protocol had no promotion authority,
forbade provider generation requests and runtime-policy changes, and fixed the
input hashes, recursive error taxonomy, task-cluster treatment, exhaustive
subgroup inventory, and candidate screen before implementation.

The analyzer authenticated the frozen protocol and all five committed V2
inputs, then re-ran the sealed V2 analysis and required exact agreement. It
reconciled all 120 observations, 40 task IDs, three repetitions per task,
contracts, strata, telemetry, model identity, ordering, and published totals.
The analysis made zero provider network requests and did not mutate the sealed
V2 evidence.

Implementation and tests were committed at `b1073b2` and `33ce24d`. Fourteen
focused tests initially covered hash failure, duplicate JSON keys, recursive
JSON Pointer classification, primary-class precedence, task clustering,
subgroup exhaustiveness, candidate-screen success and failure fixtures,
oracle-feature exclusion, dry-run immutability, and output non-overwrite. All
384 repository tests then passed on the execution host.

### Error structure

The local provider completed all 120 calls, but only 16 outputs were
oracle-correct. The structural contract passed 39 outputs: 16 correct and 23
incorrect. It rejected 81 outputs, all of which were incorrect. Contract PASS
therefore preserved every correct local result in this suite but did not
separate safe from unsafe accepted outputs.

Mutually exclusive primary row classes were:

| Primary class | Rows |
|---|---:|
| Exact | 16 |
| Scalar type | 33 |
| Container type | 23 |
| Member set | 21 |
| Scalar value | 18 |
| Unparseable candidate | 9 |

Recursive comparison recorded every value-free JSON Pointer difference. Leaf
counts were 85 scalar-value differences, 40 scalar-type differences, 38
container-type differences, 24 missing members, 9 unexpected members, and 4
array-length differences. Leaf totals exceed erroneous rows because one output
may differ at several paths.

Failure was predominantly stable rather than repetition noise. Of the 40 task
clusters, 34 were wrong in all three repetitions, five were correct in all
three, and one had mixed correctness. Canonical local output was identical
across all three repetitions for 33 tasks and had two variants for seven.

### Exhaustive subgroup screen

The analyzer printed all 42 predeclared subgroup rules:

- contract PASS alone;
- four contract-PASS single-stratum rules;
- all 15 non-empty contract-PASS stratum allowlists;
- four pre-output stratum rules;
- 17 declared contract-signature groups; and
- one explicitly non-deployable three-repetition unanimity rule.

Every subgroup was labelled retrospective and reported accepted rows, distinct
task clusters, accepted errors, exact one-sided uncertainty, avoided calls, and
counterfactual correctness. None had zero accepted errors, so no subgroup could
pass even the first substantive safety boundary. The frozen result was
**`NO_RULE_CANDIDATE`**.

The permitted interpretation is **`MODEL_CHANGE_CANDIDATE`**: Gemma 3 270M is
inadequate on this distribution, without evidence that any particular
replacement will succeed. No validator-change candidate was claimed because no
specified oracle-free deterministic check was tested that both rejected an
accepted error and retained a correct PASS. No deterministic-executor claim was
generalized from the templated benchmark.

### Canonical artifacts

The canonical offline outputs were committed at `a439e61`:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `runtime_v0_3_json_error_analysis_v1.json` | — | `2201a4eab785393754f0ca768566eba060c7ccab3f8d72d28c932b87b3dcd973` |
| `runtime_v0_3_json_error_analysis_v1.csv` | 83 | `fa672ca460adc0b58053f5c66a4734065c3df99f41c26afb2be4b8406df7f241` |
| `RUNTIME_V0_3_JSON_ERROR_ANALYSIS_V1.md` | 78 | `e7e8680742479cc49ba27ccb5fe547eae2852aec1297abaf37b20987b0b953c2` |

The JSON contains all 120 value-free row classifications, task summaries,
authenticated overlap totals, and the complete subgroup inventory. The CSV
contains 40 task rows and 42 subgroup rows plus its header. The Markdown report
separates observations, deterministic derivations, candidate hypotheses, and
prohibited claims.

### Decision and next boundary

This analysis closes the current 270M structural-JSON local-authority line. It
does not rescue V2, alter v0.3, or authorize a tuned routing rule. A successor
experiment must freeze a substantively changed candidate—most plausibly a
different local model—against fresh tasks before collecting outcomes.

### Gotchas

The 120 rows represent only 40 independent task clusters. Treating repetitions
as independent tasks would exaggerate the apparent evidence. Exhaustively
reporting subgroup combinations prevents selective omission but cannot remove
the post-selection bias of a retrospective search.

The first artifact commit followed a `git diff --cached --check` warning about
two Markdown hard-break spaces because the shell sequence did not stop on the
non-zero check. The generator, regression test, and committed report were
corrected in `8baa252`, `b97b7be`, and `6cd8716`. Fifteen focused tests then
passed, `git diff --check` was silent, and the corrected Markdown hash above was
verified. Future multi-command release sequences should stop explicitly when a
verification command fails rather than relying on visual inspection of output.

## 2026-09-09 — Runtime v0.3 structural-JSON 1B shadow V1 frozen

### Scope

The sealed 270M V2 result and retrospective error review supported a model-change hypothesis but no deployable rule. A successor prospective experiment was therefore frozen for `gemma3:1b` while leaving runtime v0.3 remote-authoritative and live `config.json` unchanged.

The model identity was captured from Ollama's local metadata API: digest `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc`, 999.89M parameters, Q4_K_M, and package size 815319791 bytes. Metadata collection made no generation request.

### Frozen artifacts

- `benchmark_runtime_v0_3_shadow_json_1b_v1.json`: 40 fresh tasks, three repetitions, 120 observations, with ten tasks in each of the four established structural-JSON strata. Exact task identifiers, prompts, and complete expected JSON objects were checked against shadow V1 and V2. SHA-256: `54fd3f5c253dbe0bf7b558c8cba807bfc341c48187df04a2815ec5153b1a60d1`.
- `config_runtime_v0_3_shadow_json_1b_v1.json`: experiment-only remote-authoritative configuration with 1B shadow execution at sample rate 1.0. SHA-256: `0285d0b79dba88c2f6714b1c9742910fd9508b24115e4defa3ee65df87a4192c`.
- `RUNTIME_V0_3_SHADOW_JSON_1B_V1_PLAN.md`: prospective protocol frozen before implementation or provider execution. SHA-256: `a608ac5b5a5d77061992c75a44425428aa05dbce90b1e1e6a2467da050ec0ee1`.

### Decision boundary

Promotion requires zero local accepted errors, at least 60 local contract passes, an exact one-sided 95% accepted-error upper bound no greater than 0.05, counterfactual correctness no worse than actual runtime, at least 60 avoided remote logical calls, and counterfactual request median latency no worse than actual runtime request latency. All 120 paired observations and their budgets, identities, and telemetry must authenticate.

The experiment screens 1B independently. Because it does not pair 1B and 270M on the same fresh tasks, it cannot support a causal model-size comparison. It does not validate retrospective V2 subgroups or alter the shipped policy.

### Gotchas

The 1B model's larger package and slower likely inference do not count against it until measured under the frozen latency rule; assumed performance must not leak into implementation or task replacement. Conversely, improved conformance would not be enough: contract PASS remains distinct from recursive semantic correctness.

## 2026-09-09 — Runtime v0.3 structural-JSON 1B shadow V1 result

### Execution and authentication

The prospective 1B shadow experiment completed all 120 ordered observations
against the frozen 40-task benchmark with three repetitions per task. The
released runtime remained remote-authoritative while `gemma3:1b` executed as
a non-serving shadow arm. All 120 remote logical calls and all 120 local logical
calls completed successfully. The remote arm used 120 HTTP attempts with no
retries or provider failures.

Before execution, 28 focused tests and all 413 repository tests passed. Dry-run
and preflight made zero provider generation requests, reported empty output
state, and authenticated the frozen benchmark, config, plan, implementation,
and local model identity. A copied benchmark-date check initially caused
`BENCHMARK_IDENTITY_MISMATCH`; commit `7beda34` corrected the adapter from
the inherited 2026-09-08 date to the frozen 2026-09-09 date without changing
the plan, benchmark, config, or collected evidence.

Execution evidence was committed at `f06cc46`:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `runtime_v0_3_shadow_json_1b_v1_runs.jsonl` | 120 | `6fc99afd2ee7be1f3ecabef728dd561d6280dc441860db0560f0e27c731d2e52` |
| `runtime_v0_3_shadow_json_1b_v1_router_telemetry.jsonl` | 120 | `28192c78b1fba0979478b0281e8e20f8e7085dac413cbb11bdd66e995d3cf03a` |
| `runtime_v0_3_shadow_json_1b_v1_summary.json` | — | `973fddf899148b059c4cebc243ec38f457b30fbd3bde0a7e93dd1c42f5e70b87` |

The authenticated analysis was committed at `503adea`:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `runtime_v0_3_shadow_json_1b_v1_analysis.json` | — | `55a0f7bfae13cc3990193fe9e3d1a5ffa34dbdd7d936ac3831c1e78d31fa0966` |
| `runtime_v0_3_shadow_json_1b_v1_analysis.csv` | 6 | `025f402bf18e0acad2f93061e0845314ead53db231dd46db4f9ae3987072161d` |

Frozen identities were plan
`a608ac5b5a5d77061992c75a44425428aa05dbce90b1e1e6a2467da050ec0ee1`,
benchmark
`54fd3f5c253dbe0bf7b558c8cba807bfc341c48187df04a2815ec5153b1a60d1`,
config
`0285d0b79dba88c2f6714b1c9742910fd9508b24115e4defa3ee65df87a4192c`,
and implementation
`7beda3493e70a5b3719a67d6ae06be06a794174c`.

### Primary result

The precommitted decision is **`DO_NOT_PROMOTE`**.

The authoritative runtime was correct on 105/120 observations (87.5%). The
local 1B arm was correct on 43/120 (35.8%). A local-first counterfactual that
served every local contract PASS and otherwise fell back to remote was correct
on 88/120 (73.3%), 17 fewer correct observations than the released runtime.

The local contract passed exactly 60 outputs, meeting the minimum volume
threshold, but 17 of those accepted outputs were wrong. The accepted-error rate
was 17/60 (28.3%), and its exact one-sided 95% Clopper-Pearson upper bound was
39.4%, far above the precommitted 5% ceiling. The counterfactual avoided exactly
60 remote logical calls; its task-cluster bootstrap 95% interval was 42..78.
The bootstrap 95% interval for counterfactual-minus-runtime correctness rate
was -25.0 to -5.0 percentage points.

Median measured latencies were 3173.0 ms for the paired local arm, 2509.0 ms
for the remote provider arm, 4874.6 ms for deployable sequential local-first
fallback, and 5855.8 ms for the actual synchronous-shadow runtime. The frozen
comparison with actual runtime request latency therefore passed, but it did not
offset the safety and correctness failures.

Reported remote cost was USD 0.0117774. No remote result required reserved
failure cost, and total accounting remained below the USD 0.03 ceiling.

### Stratum results

| Stratum | Remote correct | Local correct | Local PASS | Accepted errors | Counterfactual correct |
|---|---:|---:|---:|---:|---:|
| Flat scalar | 30/30 | 12/30 | 19/30 | 7 | 23/30 |
| Nested collection | 18/30 | 3/30 | 9/30 | 6 | 12/30 |
| Record selection | 27/30 | 12/30 | 15/30 | 3 | 24/30 |
| Type boundary | 30/30 | 16/30 | 17/30 | 1 | 29/30 |
| **Overall** | **105/120** | **43/120** | **60/120** | **17** | **88/120** |

Every locally correct result was also remotely correct. Overlap was 43
both-correct, zero local-only, 62 remote-only, and 15 neither. The experiment
therefore found no measured observation where local authority rescued a remote
error.

### Promotion criteria and decision

Evidence completeness, absence of instrumentation or execution failure, at
least 60 local contract passes, at least 60 avoided remote calls, and the
frozen request-latency comparison passed. Three substantive criteria failed:

- local accepted errors were 17 rather than zero;
- the accepted-error upper bound was 39.4% rather than at most 5%; and
- counterfactual correctness was 88 rather than at least the runtime's 105.

Structural-JSON local authority remains disabled. Runtime v0.3 remains
remote-authoritative for these contracts. The 1B model improved the independent
screen enough to reach the volume thresholds, but structural conformance still
did not provide a safe semantic routing boundary.

### Gotchas

The 1B and 270M experiments used different fresh task sets. The higher 1B local
correct count and contract-PASS count are descriptively encouraging, but they
cannot be attributed causally to model size. A direct model comparison would
require a separately frozen paired design.

The lower counterfactual median than the synchronous-shadow runtime does not
mean local-first was faster than direct remote service: the remote provider-arm
median was 2509.0 ms. More importantly, 17 of the 60 apparent remote-call
savings would have served semantically wrong local outputs. Meeting the savings
count exactly did not make those savings safe.

## 2026-09-09 — Source-aware JSON verifier V1 developmental candidate

### Research decision

The structural-JSON local-authority line based only on exact keys and declared
types is closed for now. Runtime v0.3 remains remote-authoritative, and a 4B
prospective shadow run is deferred. The 1B result showed that increased
contract-PASS volume did not provide a safe semantic boundary: 17 of 60
contract-accepted outputs were wrong, and no local-only correct observation was
measured.

The next candidate changes the acceptance mechanism rather than merely the
model size. `source_aware_json.py` is an offline proof-carrying extraction
prototype. In its deliberately narrow V1 scope, the caller authenticates UTF-8
source bytes, declares ordered record boundaries, supplies a selector literal
that must identify exactly one record, and declares flat scalar output keys and
types. An untrusted candidate supplies field byte spans. Deterministic code
checks that every span lies in the selected record and reconstructs the output
from the source bytes.

### Boundary

This component is not integrated into `runtime_contracts.py`, `router.py` or
`config.json`. It has no promotion authority, makes no provider request, and
does not alter or rerun sealed evidence. A PASS establishes bounded source
grounding and record consistency, not arbitrary semantic correctness.

The full protocol and limitations are recorded in
`SOURCE_AWARE_JSON_VERIFIER_V1_PLAN.md`. Synthetic adversarial tests cover
fabrication, wrong-record selection, cross-record splicing, proof-set drift,
type substitution, selector ambiguity, malformed spans, UTF-8 boundaries,
nested values, duplicate JSON keys and source authentication.

Developmental review also preserves an executable negative boundary. When two
same-typed values are swapped between output fields but both cited spans are
authentic and inside the selected record, V1 accepts them. Source occurrence is
therefore stronger than shape/type conformance but is still not field-role
correctness. V1 does not justify a prospective model experiment or a runtime
integration.

### Verification

- `python -m unittest tests.test_source_aware_json -v` — 20 tests passed.
- `python -m unittest discover -s tests` — 433 tests passed.
- `python -m py_compile source_aware_json.py tests/test_source_aware_json.py`
  passed.
- `git diff --check` passed.
- No provider generation request was made.

| Artifact | SHA-256 |
|---|---|
| `SOURCE_AWARE_JSON_VERIFIER_V1_PLAN.md` | `a25c0bbc1cb546a280d0036fced154088dec090d29f423e782408fb9fd82d492` |
| `source_aware_json.py` | `4e747b30d769837d70043636726ddddb045953bc7f2121e5f3d4ac8006b05dbd` |
| `tests/test_source_aware_json.py` | `fccb7d1b4309d60cec40f7476fec99e872a6573b028d84c78b3e111f746bc23e` |

The first local commit command followed a successful hash check with
`git diff --cached --check`, which correctly reported four Markdown hard-break
spaces. Because the shell sequence did not stop on that non-zero exit, it
created an unpushed commit. The whitespace and plan hash were corrected, the
checks were rerun with explicit stop-on-error behavior, and the unpushed commit
was amended before publication. No provider call, sealed-artifact change or
runtime-policy change occurred.

### Next boundary

Before any prospective model experiment, review whether the trusted record
segmentation and selector already make the workload deterministically
executable. The same-type field-role limitation means further constraints are
required; if those constraints identify the field values mechanically, route
the work to deterministic code rather than an LLM. Only if a nontrivial and
deterministically verifiable model role remains should a successor be frozen on
fresh tasks and compare deployable local-first latency with direct remote
service.

---

## 2026-09-22 — Initial research-cycle endpoint

The initial local-authority research cycle is closed. Runtime v0.3 remains remote-authoritative for generative work, deterministic operations continue to bypass models, and local generation retains no user-visible authority.

The decisive 1B shadow experiment met its volume and potential-savings thresholds but failed safety and correctness: 43/120 local correct, 60/120 contract passes, 17 accepted errors, a 39.4% one-sided accepted-error upper bound, and an 88/120 local-first counterfactual against 105/120 for the runtime. Its 4874.6 ms deployable median also exceeded the 2509.0 ms direct remote median. Every locally correct observation was also remotely correct.

No 4B structural-JSON promotion experiment will be started in this cycle. Source-aware verification remains a negative boundary, and the documentation-only verifiable-witness design remains paused without implementation or promotion authority.

The diverged leakage investigation is preserved at `preserve/local-main-leakage-2026-09-20` (`d2cccad`) and was not merged into canonical history. The bundle SHA-256 is `214d3c81c6b9b42126d90fbc55f3aa15defa12e18d97bca3d2e201cd1e76f675`; the untracked-artifact archive SHA-256 is `f42c40cc87404c0355c60322bf3cfeff63e9d6f9cc76c882d286f9d37dd128f8`.

This endpoint is documentation only. It changes no runtime source, configuration, sealed benchmark, evidence or analysis; makes no provider request; and grants no new authority. Full reasoning and reopening conditions are recorded in `RESEARCH_ENDPOINT_2026-09-22.md`.

---

## 2026-11-15 — Fast path V1 developmental build

The project is reopened on a substantively different question from the closed
local-authority cycle. The objective is answer time for repeated single-step
tasks; cost is dropped as a parameter. Deterministic code is the fast route,
several remote models are raced for everything else, and code written on the
fly must pass an execution-only gate before it serves an answer. Runtime v0.3
and its remote-authoritative policy are unchanged; `router.py` and
`config.json` were not edited.

### Added

- `sandbox.py`: static screen plus restricted subprocess execution.
- `fast_path.py`: request schema, shape store, model race, agreement examples,
  background synthesis, promotion gate, audit and demotion.
- `main.py`: `--fast-request-json` and `--fast-status`.
- `config_fast_path.json`: separate from `config.json`, which sealed runners read.
- `vendor/ccc_code_items.py`: the 16 CCC code items, vendored byte-identical
  from `petesherratt-collab/jev-ccc-probe` at `c5ba7e3` and hash-pinned.
- `fast_path_gold_items_v1.py`: 28 fresh items to the same recipe. Draft, not
  frozen. Expected values were written from the specifications, not derived
  from the references.
- `evaluate_fast_path_gate.py`, `fast_path_gate_dev_v1.json`,
  `fast_path_gate_fresh_v1.json`: provider-free gate measurement.
- `run_fast_path_gold.py`: collector for model and synthesiser fail rates. Not run.

### Design decisions

- The routing decision is a lookup, never a model call, so nothing slow sits
  in front of the answer.
- The first parseable racer wins; agreement is evaluated afterwards and only
  feeds learning.
- Following the CCC finding that a judge shown a conclusion tends to adopt it,
  no model judges a candidate function and the synthesiser never sees examples.
- Caller-supplied examples outrank model agreement. Two contradictory
  model-agreement examples cancel.
- A provider failure during synthesis does not consume a bounded attempt.

### Gate measurement

Mean share of k-example subsets that accepted the single-bug variant:
development set 50.5%, 21.2%, 3.8% for k = 1, 2, 3; fresh set 66.5%, 42.4%,
25.7%, 14.5%, 7.3%, 3.0%, 0.8%, 0.0% for k = 1 to 8. No reference was
rejected. Zero at the top of each range is forced by construction. The
default `min_gate_examples` was raised from 4 to 8 after the fresh result; it
is an operating setting, not a validated threshold.

### Verification

- `python -m unittest discover -s tests` — 472 tests passed.
- `python fast_path_gold_items_v1.py` — self-verify passed for 28 items.
- `git diff --check` passed.
- No provider generation request was made. OpenRouter was not reachable from
  the build environment and no key was present.

### Next boundary

Review and freeze the fresh bank, choose the race roster, then run
`run_fast_path_gold.py` once to obtain per-model fail rates, the rate at which
two models agree on a wrong answer, and the synthesiser's fail rate. An
answer-time comparison against direct single-model service needs its own
frozen plan with repeated task shapes.

---

## 2026-11-16 — Fast path development gold run

First provider run on the fast-path line, made from a cloud session through a
dedicated `adaptive-router` environment. Status: development only. The bank
`fast_path_gold_items_v1.py` (SHA-256 `c14f31f7…e0b921`) had not been reviewed
or frozen and the roster was chosen on the day, so nothing here is a
prospective result.

Roster: `openai/gpt-5.6-luna`, `openai/gpt-6-luna`,
`anthropic/claude-haiku-5.5`, `google/gemini-3.8-flash`,
`deepseek/deepseek-v4.1-flash`; synthesis by `openai/gpt-6-luna`. 1,255 answer
calls and 28 synthesis calls, no retries, no provider failures on synthesis.

- Wrong or unusable answers per model out of 251: 3, 3, 84, 5, 10 in roster
  order. 77 of the 84 and 9 of the 10 were unparseable or empty responses.
- Unanimous valid answers: 240 cases, all correct. Non-unanimous: 11.
- Replayed fastest-valid race: median 716 ms, 90th percentile 1053 ms, one
  wrong answer. Best accurate single model: median 1049 ms.
- Synthesis: 27 of 28 gold-correct. The failure (`slugify`, missing
  `import re`) fails all examples and is rejected by the gate.

Artifacts: `fast_path_gold_dev_run_v1.jsonl`,
`fast_path_gold_dev_run_v1_summary.json`. `config_fast_path.json` now carries
the roster. No runtime v0.3 source or sealed artifact changed.

---

## 2026-11-16 — Answer prompt revision and timing plan draft

The development run showed that most unusable answers were format failures:
one model reasoned in prose before its answer, and two returned empty content
when reasoning consumed the 256-token limit.

- `build_answer_prompt` now lists each argument on its own line and requires a
  final `ANSWER: <JSON>` line. `parse_answer` reads the last `ANSWER:` line, or
  a reply that is a single JSON value. It never extracts a value from prose.
- `fast_path.answer_max_tokens` (1024) replaces the inherited 256 for answers.
- Tuning used only the vendored CCC items, 60 cases by five models. Wrong or
  unusable answers: 7 of 300 before, 0 of 300 after. Median latencies did not
  rise materially. The 28-item bank was not re-run.
- `run_fast_path_gold.py` now records the answer token limit and a hash of the
  answer prompt template in its header.
- `FAST_PATH_TIMING_V1_PLAN.md` drafts a three-arm timing experiment. It is
  not frozen and authorizes nothing. Both existing banks are development
  evidence, so it requires a new benchmark.

Verification: full unit suite passed; `git diff --check` passed.

---

## 2026-11-16 — Fast-path timing V1 freeze

The timing experiment is frozen before any provider call against its
benchmark. The owner accepted the proposed workload size, criteria and
arrival assumption in session. The 30-shape benchmark was written by the
assistant and was not reviewed by the owner before the freeze.

Added: `fast_path_timing_bench_v1.py` (30 shapes, 30 seeded requests each, no
overlap with either earlier bank), `run_fast_path_timing_v1.py`,
`analyze_fast_path_timing_v1.py`, `tests/test_fast_path_timing.py`, a
`synthesis_enabled` setting for the race-only arm and `FastPathRouter.close`.

A live smoke test on three development-bank shapes with 12 requests each
completed without error: two shapes were promoted at request index 7 and then
served from code at a median of 28 ms; the third reached only 7 agreed
examples because the five models were not unanimous on 5 of 12 requests.
That output is not evidence for this experiment and was not committed.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_timing_bench_v1.py` | `e36398997f733a6deaf611e1f7541572ab4f39e68e1f983546c0044dd552848d` |
| `config_fast_path.json` | `1f14f980657cc059a3ad5955fe30fb7e13f4b924fbdf341057c9501c016d986f` |
| `fast_path.py` | `b6f4c739fdd17911daf85a85bc424ecb19faccfd16310b917014c15b97060ea2` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `remote.py` | `4efc49ab45e68d09f026e75fca9e3aff2780fac8682b3b27f7fa983eda51afc2` |
| `run_fast_path_timing_v1.py` | `68c96d073103a29e7d857a0141ad096b0c4962dd36e4b3d8751b4888e191fe64` |
| `analyze_fast_path_timing_v1.py` | `b8175ab605d53390c03567fc6e3f3f351a726748617aea6929a5026aa87cc1e8` |
| `FAST_PATH_TIMING_V1_PLAN.md` | `011887d3686609ecbe360a5b82844979e3cee920349a41929009906c86c7b313` |

Verification: full unit suite passed; `python fast_path_timing_bench_v1.py`
self-verify passed; `git diff --check` passed.

---

## 2026-11-16 — Fast-path timing V1 primary result

The frozen primary run completed in one attempt with no early stop, no
incident and no unanswered request in any arm. Frozen-criteria decision:
`SUPPORTED`.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. Direct | 824/900 | 1198 | 3205 | 1651 |
| B. Race only | 884/900 | 864 | 1125 | 891 |
| C. Fast path | 892/900 | 30 | 961 | 290 |

- Time ratio C/A 0.0254, shape-cluster bootstrap 95% interval 0.0238 to 0.0267.
- Correctness C minus A +0.0756, interval +0.0378 to +0.1189.
- 30 of 30 shapes promoted on the first synthesis attempt; promotion index
  median 7, maximum 16. Zero gold-wrong functions, zero demotions, zero wrong
  stored examples, zero wrong code-served answers out of 629.
- Fast-path model-route requests: 271, of which 8 wrong, in three shapes.
- Arm A errors were concentrated in counting and arithmetic shapes.
- Race winners in arm B: `claude-haiku-5.5` 585, `deepseek-v4.1-flash` 275,
  `gpt-5.6-luna` 39, `gemini-3.8-flash` 1.
- Background learning in arm C totalled about 1,166 s, untimed by design.

Limits: 30 task clusters; constructed pure-function tasks; benchmark not
owner-reviewed before the freeze; favourable arrival model. The benchmark is
now used; later runs on it are descriptive sensitivity runs only.

| Artifact | SHA-256 |
|---|---|
| `fast_path_timing_v1_primary.jsonl` | `e47435883c4004e282ffa69c410388f23904dbcb6ec543bf5bea5daf0d4002db` |
| `fast_path_timing_v1_primary_analysis.json` | `328e98481cc42ce29a0648ff2493e7c1d3311e5f4ae116dce8943d780af25a0a` |

---

## 2026-11-16 — Timing V1 sensitivity: immediate arrival

`run_fast_path_timing_v1.py` gained `--arrival immediate`, which stops
draining background learning between requests and records the gap since the
previous request of the same arm. The default is unchanged. The runner and
analysis hashes therefore differ from the freeze entry; the primary evidence
was produced by the frozen versions and re-analyses to the same figures.

One descriptive run on the already-used benchmark, label `arrival_immediate`:

- Fast path: 892/900 correct, median 33 ms, mean 337 ms, 573 code-served.
- Direct: 815/900 correct (22 unanswered), median 1233 ms. Race: 882/900, 853 ms.
- Ratio C/A 0.0265 (interval 0.0245 to 0.0280); correctness +0.0856.
- First code-served index: median 10, range 9 to 19 (primary: median 8, max 17).
- 30 of 30 promoted first attempt; no wrong function, example or demotion.
- Gap between consecutive fast-path requests: median 2.2 s, 10th pct 0 s.

Not a prospective result. Arrival faster than about two seconds is untested.

| Artifact | SHA-256 |
|---|---|
| `fast_path_timing_v1_arrival_immediate.jsonl` | `b8814cfbf2531467cf22d15cd653729953137b25df2b27b54c2653ed1bcc414b` |
| `fast_path_timing_v1_arrival_immediate_analysis.json` | `4e8a31650452dcd262b4981c99eec2daeefb7300b0e5079255928138e0e633e4` |

---

## 2026-11-16 — Timing V1 `min_gate_examples=4` run invalidated

The second sensitivity run lost its provider partway: the OpenRouter account
ran out of credits and returned HTTP 402. The direct arm is missing 451 of 900
answers, so no comparison from this run is valid. Details, the limited
descriptive reading and follow-up are in
`FAST_PATH_TIMING_V1_GATE4_EXECUTION_INCIDENT.md`. The evidence file is kept
unaltered. Provider calls on this line are paused until credit is added.

---

## 2026-11-16 — Runner hardening and `min_gate_examples=4` rerun

After the credit incident `run_fast_path_timing_v1.py` gained a
`ProviderMonitor`: it tallies provider errors, stops at once on HTTP 401 or
402, and stops when more than half of the last 100 calls fail. Direct-arm rows
record their error and the footer carries the tally. A stopped run keeps its
`.partial` name with status `PROVIDER_FAILURE_STOP`.

The owner added credit and the run was repeated from the start, label
`min_gate_examples_4_rerun`. 6,545 provider calls, 13 invalid responses, no
unanswered request in any arm.

- Fast path: 895/900 correct, median 31 ms, mean 158 ms, 768 code-served.
- Direct: 829/900, median 1183 ms. Race only: 884/900, median 844 ms.
- Ratio C/A 0.0260 (interval 0.0241 to 0.0270); correctness +0.0733.
- First code-served index: median 4, latest 8 (primary: 8 and 17).
- 30 of 30 promoted first attempt; no wrong function, example or demotion.
- All 5 wrong fast-path answers came from the model race.

No synthesised function was wrong in any run so far, so these runs do not
test the gate's ability to reject one. Descriptive only.

| Artifact | SHA-256 |
|---|---|
| `fast_path_timing_v1_gate4_rerun.jsonl` | `e50063042646580aa47906ee64b7354ead13b6f6aa588d7d3352f541cd984816` |
| `fast_path_timing_v1_gate4_rerun_analysis.json` | `aa75436f8dd8eb92de4f41dc69494790f7a90415b471560ed32be3e1a985eecf` |

---

## 2026-11-16 — Fast-path timing V2 (harder shapes) freeze

The V1 runs never produced a wrong synthesised function, so they could not
exercise the gate or the audit. `fast_path_timing_bench_v2_hard.py` adds 20
error-prone shapes and `FAST_PATH_TIMING_V2_HARD_PLAN.md` freezes one primary
run on them under the V1 rules and criteria. No provider call has touched
this benchmark. The benchmark was not owner-reviewed before the freeze.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_timing_bench_v2_hard.py` | `54abf8668ef51d5a9acf8d11366102b9b086a72bb5497339129e33cf9f4446a9` |
| `fast_path_timing_bench_v1.py` | `e36398997f733a6deaf611e1f7541572ab4f39e68e1f983546c0044dd552848d` |
| `config_fast_path.json` | `1f14f980657cc059a3ad5955fe30fb7e13f4b924fbdf341057c9501c016d986f` |
| `fast_path.py` | `b6f4c739fdd17911daf85a85bc424ecb19faccfd16310b917014c15b97060ea2` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `remote.py` | `4efc49ab45e68d09f026e75fca9e3aff2780fac8682b3b27f7fa983eda51afc2` |
| `run_fast_path_timing_v1.py` | `afe13bde696a309dd29a97378f9883104cd9fae9a346c1c4cfc855e30d55a2bf` |
| `analyze_fast_path_timing_v1.py` | `b01b8fab99b0f3724d7789bf2caa87e51e59137e6da49dc50fd998e792523b9a` |
| `FAST_PATH_TIMING_V2_HARD_PLAN.md` | `94d17a7d64f40939988d59e077a6a03eba71d762b3699f9e81e17cce781f6601` |

Verification: full unit suite passed; benchmark self-verify and standard
library cross-checks passed; `git diff --check` passed.

---

## 2026-11-16 — Fast-path timing V2 (harder shapes) result

The frozen run completed in one attempt: 4,766 provider calls, 61 invalid
responses, no early stop. Frozen-criteria decision: `SUPPORTED`.

| Arm | Correct | Median ms | 90th pct ms | Mean ms |
|---|---:|---:|---:|---:|
| A. Direct | 571/600 (2 unanswered) | 2964 | 4951 | 2987 |
| B. Race only | 593/600 | 1161 | 2157 | 1344 |
| C. Fast path | 598/600 | 32 | 1660 | 458 |

- Ratio C/A 0.0109 (interval 0.0094 to 0.0147); correctness +0.045
  (interval +0.020 to +0.075).
- 20 of 20 shapes promoted; promotion index median 7, latest 14 (`luhn_valid`,
  8 disagreements). 418 code-served answers, none wrong. No wrong stored
  example, no demotion. Both wrong fast-path answers came from the race.

Readings fixed in advance:

- First synthesised function gold-wrong and rejected by the gate: one,
  `eval_expression`, a syntax error rejected statically; the retry passed.
- Gold-wrong function promoted: one, `number_to_words`. It returns '' for 0.
  It differs from the reference on exactly 1 of the 10,000 inputs in range.
  It passed the gate on 8 examples and was never demoted. Wrong answers
  served: 0, because 0 was not in the request stream.
- Shapes never promoted: none.

No gate failure as the plan defines it. The latent fault shows the limit of
example-based promotion and of auditing only the inputs that arrive.

| Artifact | SHA-256 |
|---|---|
| `fast_path_timing_v2_hard_primary.jsonl` | `550c110445435754eeb39ba5ef45a6933dedb41db6889157ca207486fa6b36eb` |
| `fast_path_timing_v2_hard_primary_analysis.json` | `c69166f9e581b4213753cf84f4d8493df77966e69074de238bc7593edb19915e` |

---

## 2026-11-16 — Boundary probing before promotion

Chosen by the owner over an independent-implementation comparison, as the
response to the latent `number_to_words` fault promoted in the V2 run.

Added to `fast_path.py`: `build_probe_prompt`, `parse_probes`,
`propose_probes`, `answer_probes` and a probe step that runs once per shape
before the first synthesis attempt. New settings: `probe_enabled`,
`probe_model` (`google/gemini-3.8-flash`), `max_probes` (12),
`probe_max_tokens` (4096). Probe examples carry source `probe_agreement`.
`run_fast_path_timing_v1.py` now verifies stored examples against the
reference directly, because probe inputs lie outside the request stream.
`evaluate_fast_path_probes.py` measures probing on items with a buggy variant.

Results, all descriptive:

- Replay of the promoted wrong function: 12 probes proposed, 12 agreed, wrong
  function rejected on input 0, reference passed all 12.
- First 44-item evaluation invalid: 18 probe replies truncated at 1,024
  tokens. Kept as `fast_path_probe_eval_v1.jsonl`.
- Second 44-item evaluation: 516 probes, 502 agreed, 14 disputed. Buggy
  variants rejected 42 of 44. One accepted because no probe exposed an
  order-dependent fault; one untested because the probe reply was unusable.
  One reference rejected, `caesar_decode`, where the vendored reference
  shifts uppercase letters contrary to its specification.
- After that run an unparseable probe reply is retried once.

| Artifact | SHA-256 |
|---|---|
| `fast_path_probe_eval_v2.jsonl` | `3b2b6743286adb1304c146c6895a7d98fc8aad60c2ceaffb81fadb98487f6670` |
| `fast_path_probe_eval_v1.jsonl` | `a2a2a8537c45f090a006a2fd933a02e047cd84c3b444992d66cedf5aac519489` |
| `fast_path_probe_case_number_to_words_result.jsonl` | `fd79903ba58e452e70618ae2b6f1280f974584c26c2f7ade531c45f3b425024c` |

---

## 2026-11-16 — Harder benchmark with probing enabled (descriptive)

Label `probes_enabled`, benchmark already used once. 5,925 provider calls, 62
invalid responses, no unanswered request.

| Arm | Correct | Median ms | Mean ms |
|---|---:|---:|---:|
| A. Direct | 572/600 | 2791 | 2800 |
| B. Race only | 595/600 | 1166 | 1340 |
| C. Fast path | 598/600 | 33 | 437 |

- 20 of 20 shapes promoted on the first attempt, gate examples 18 to 20.
  Promotion index median 7, latest 12. First code-served index median 8.
- Every promoted function gold-correct. No demotion.
- Probes: 240 proposed, 234 unanimous, 6 disputed, 0 wrong against the
  reference, 0 outside the reference's domain.
- 425 code-served answers, none wrong. Background work about 1,443 s.
- No synthesised function was wrong in this run, so no probe rejection
  occurred; the run shows probing did not obstruct promotion or answer time.

| Artifact | SHA-256 |
|---|---|
| `fast_path_timing_v2_hard_probes.jsonl` | `796c59372613fc27ecbf0b3c7f6d142e2d2fd20272437ff1f61797733a806fa5` |
| `fast_path_timing_v2_hard_probes_analysis.json` | `4b45ee0ce969eb8da690e9ae8184bad0974ee2939b1ecdf9709ce17adef66181` |

---

## 2026-11-16 — Multi-step jobs, first build

The owner chose to move from single-step tasks to multi-step jobs. The first
stage keeps the plan in the caller's hands: the orchestrator executes a
declared plan and decides nothing except, by lookup, whether a step can be
answered by promoted code. A model-written plan is deferred.

Added: `pipeline.py` (job schema, validation, concurrent step execution,
metadata-only job log), `tests/test_pipeline.py`, `main.py --job-json`,
`examples/fast_path_job_ticket_triage.json`, and a `learn` argument to
`FastPathRouter.handle` so judgement steps are raced without being stored.

Reasoning for the two step kinds: a whole job that is a pure function would
simply be promoted as one function by the single-step fast path. Decomposition
earns its place only for mixed jobs, where some steps need a model and the
rest can go down to code. Letting a judgement step learn would invite a
keyword heuristic that reproduces a handful of examples; declaring the kind
prevents that. Discovering the kind automatically is not attempted.

Change to learning: `probe_after_examples` (3) lets the probe step run before
`min_gate_examples` arrived examples exist, with probe answers counting toward
the minimum. Found in the first live demonstration, where a rule over twelve
possible inputs reached only seven distinct examples in sixteen jobs and was
never promoted. This changes single-step behaviour too; the recorded timing
runs predate it.

Live demonstration (no gold, not evidence): 16 ticket-triage jobs. Jobs 1 to 3
ran every step on the race, 2.3 to 2.8 s. From job 4 all three function steps
ran as code and jobs took 0.86 to 1.66 s. One synthesised function was
rejected by the gate and its retry promoted, in the earlier of two demo runs.

Verification: full unit suite passed; `git diff --check` passed.

---

## 2026-11-16 — Fast-path jobs V1 freeze

`FAST_PATH_JOBS_V1_PLAN.md` freezes one four-arm run on
`fast_path_jobs_bench_v1.py`: 12 mixed job shapes, 20 jobs each, gold by
construction. Arms: one direct whole-job call, a whole-job race, the step
pipeline on the race, and the step pipeline over the fast path.

Added: `pipeline.build_job_prompt`, `FastPathRouter.race_prompt`,
`run_fast_path_jobs_v1.py`, `analyze_fast_path_jobs_v1.py`,
`tests/test_fast_path_jobs.py`. No provider call has touched the benchmark.
A live smoke test used one six-job shape outside it and is not evidence.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_jobs_bench_v1.py` | `68e092a8990939b876baabb7a4c611bae7ac07c1558b977d95cfd0dfa4fd13b4` |
| `config_fast_path.json` | `39cf0ef944193465e62c08001b423220b37a738a2ee9fddd7e28b9c0c32e7cc6` |
| `fast_path.py` | `bfae3e002d5ab8ebe23b1c5fa020e023fdc17fefde09fcf33f59e109bc331623` |
| `pipeline.py` | `bca87fc09cb826de1b6e5376b4eb38102ac0d5f5025662181d87bb472eed679d` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `remote.py` | `4efc49ab45e68d09f026e75fca9e3aff2780fac8682b3b27f7fa983eda51afc2` |
| `run_fast_path_timing_v1.py` | `c1c242d8da450dd037848596648b0ec763f737ef957ddc0e22f703d7aea61ea5` |
| `run_fast_path_jobs_v1.py` | `f7398118495f8db27e902848cabd05e9e03f59389ef55666d85e74e010743289` |
| `analyze_fast_path_timing_v1.py` | `b01b8fab99b0f3724d7789bf2caa87e51e59137e6da49dc50fd998e792523b9a` |
| `analyze_fast_path_jobs_v1.py` | `68cd5ff613647929428e2e8ac9bdb1aea959e47711cd4d8ac01997e079e78004` |
| `FAST_PATH_JOBS_V1_PLAN.md` | `8a32094866ce0995390a0fef1462ac45d98bbb600cf66c62c72b32b66879745b` |

Verification: full unit suite passed; benchmark self-verify passed;
`git diff --check` passed.

---

## 2026-11-16 — Fast-path jobs V1 result

The frozen run completed in one attempt: 10,708 provider calls, 8 invalid
responses, no unanswered job. Frozen-criteria decision: `NOT_SUPPORTED`.

| Arm | Correct | Median ms | Mean ms |
|---|---:|---:|---:|
| A. Direct whole job | 234/240 | 2218 | 2269 |
| R. Whole-job race | 238/240 | 1233 | 1240 |
| B. Pipeline, race only | 238/240 | 2616 | 2614 |
| C. Pipeline, fast path | 240/240 | 1115 | 1402 |

- C/A time ratio 0.502, interval 0.416 to 0.784: fails the 0.75 limit.
  Correctness C minus A +0.025, interval 0.000 to +0.054: meets the margin.
- C/R 0.904 (0.800 to 1.284), correctness +0.008. B/A 1.179 (1.010 to 1.533).
  R/A 0.556 (0.469 to 0.740).
- Arm C steps: 447 function steps on code (median 26 ms, 0 wrong), 133
  function steps on the race (0 wrong), 380 judgement steps (0 wrong).
  Arm B: 4 wrong function steps of 580, 0 wrong judgement steps of 380.
- 27 of 29 function steps promoted, 0 gold-wrong, 0 demotions, 0 wrong
  examples, 0 judgement shapes stored.
- Not promoted: `store_aisle.aisle` (3 examples) and `greeting.hello` (4):
  domains smaller than `min_gate_examples`.
- Fixed-in-advance shapes: `dial_code` C median 1847 ms against R 1165 ms;
  `triple_code` C 1108 ms against R 1341 ms, and correct 20/20 against 18/20.
- After the fifth job of each shape, medians were A 2205, R 1220, B 2620,
  C 1050 ms.

Reading: decomposition without code is a cost; with code it roughly halves
time against one model but does not beat a whole-job race on this workload.
A fixed minimum example count cannot be met by a function whose whole domain
is smaller than that count.

| Artifact | SHA-256 |
|---|---|
| `fast_path_jobs_v1_primary.jsonl` | `a9b35987181a775c74ebadcf61280313bc9a88a0bd810cb6fc63efcde5eb30f5` |
| `fast_path_jobs_v1_primary_analysis.json` | `ed636371abc96d88aee1f7ce3a66d9198a655830c6e506e70ac71d7ed4cca349` |

---

## 2026-11-17 — Saturation rule and jobs V1 rerun

`fast_path.py` gained `_gate_minimum`: a shape whose last `saturation_window`
agreed inputs were all already stored may go to synthesis, and pass the gate,
with as few as `saturation_min_examples` examples. Each agreed observation
updates `repeat_streak`. Settings 5 and 2. Promotions under the rule carry
`gate.saturated`.

Descriptive rerun of jobs V1, label `saturation`: 10,700 provider calls, 8
invalid responses, no unanswered job. Correct A 233, R 239, B 240, C 240 of
240; medians 2205, 1071, 2266, 963 ms. C/A 0.437 (0.381 to 0.568); C/R 0.900
(0.797 to 1.298). 28 of 29 function steps promoted, all gold-correct; two
under saturation. `shipping_estimate.zone` was not promoted: one probe
example, unanimous across five models, contradicts the reference, and both
synthesis attempts were rejected at 12 of 13 examples. One wrong stored
example in total. The runner now records wrong examples with the reference
value.

| Artifact | SHA-256 |
|---|---|
| `fast_path_jobs_v1_saturation.jsonl` | `fecc89582efef69ececedb5437178e36dd45a18ea1557f03da730744da56a129` |
| `fast_path_jobs_v1_saturation_analysis.json` | `a52be2a75b5284f4b171ace998b81e5c83b89c3b4abfa5a091ee213dc673eb04` |

---

## 2026-11-17 — Fast-path jobs V2 (larger jobs) freeze

`FAST_PATH_JOBS_V2_LARGE_PLAN.md` freezes one four-arm run on
`fast_path_jobs_bench_v2_large.py`: 7 job shapes of 7 steps each, 15 jobs per
shape, long structured inputs. The primary comparison is the step pipeline
over the fast path against the whole-job race, the arm it could not beat in
V1. Settings changes since jobs V1: `answer_max_tokens` 1024 to 4096 for every
arm, and the saturation rule enabled. `analyze_fast_path_jobs_v1.py` gained
`--baseline` and `--time-limit`. No provider call has touched this benchmark.
Provider credit at the freeze: about $16.70.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_jobs_bench_v2_large.py` | `0821ca5e659feaa0980daef76d31117332ab643ab193bfc0f19cf15b12726f3e` |
| `fast_path_jobs_bench_v1.py` | `68e092a8990939b876baabb7a4c611bae7ac07c1558b977d95cfd0dfa4fd13b4` |
| `config_fast_path.json` | `7713a63fad7297eb16192b97500b52dbd0400cecb5476f52d7dbad110dc2494c` |
| `fast_path.py` | `5ec148e775d334871f20e9bccfb7b919c4a150e73679b39339f2272e21c64a04` |
| `pipeline.py` | `bca87fc09cb826de1b6e5376b4eb38102ac0d5f5025662181d87bb472eed679d` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `remote.py` | `4efc49ab45e68d09f026e75fca9e3aff2780fac8682b3b27f7fa983eda51afc2` |
| `run_fast_path_timing_v1.py` | `c1c242d8da450dd037848596648b0ec763f737ef957ddc0e22f703d7aea61ea5` |
| `run_fast_path_jobs_v1.py` | `3a06f6a10e00169adae33ac43c4a669e333785968b9ae6de3426e05382d2b109` |
| `analyze_fast_path_timing_v1.py` | `b01b8fab99b0f3724d7789bf2caa87e51e59137e6da49dc50fd998e792523b9a` |
| `analyze_fast_path_jobs_v1.py` | `46aaf4797fc1844c9b084737604334ba284cc8ddcc1a97737be831a3e74268e7` |
| `FAST_PATH_JOBS_V2_LARGE_PLAN.md` | `ebde07340a4fedcc1fdd2f0deab9561303905e6fefcb9fdbe3c1f2de0c0bba57` |

Verification: full unit suite passed; benchmark self-verify passed;
`git diff --check` passed.

---

## 2026-11-17 — Fast-path jobs V2 (larger jobs) result

The frozen run completed in one attempt: 8,357 provider calls, 20 invalid
responses, no unanswered job. Decision under the frozen criteria, arm C
against arm R: `SUPPORTED`.

| Arm | Correct | Median ms | Mean ms |
|---|---:|---:|---:|
| A. Direct whole job | 99/105 | 3786 | 3969 |
| R. Whole-job race | 105/105 | 2791 | 2800 |
| B. Pipeline, race only | 104/105 | 5317 | 5531 |
| C. Pipeline, fast path | 105/105 | 1129 | 2155 |

- C/R 0.405 (0.340 to 0.877); correctness 0.000 (0.000 to 0.000).
- C/A 0.298 (0.228 to 0.660); +0.057. R/A 0.737. B/A 1.405 (1.087 to 1.812).
- Arm A errors: `stock_reorder` 5, `grade_report` 1. Arm B: one wrong job,
  first wrong step a function step on the race.
- 39 of 41 function steps promoted. `thread_digest.span`: both synthesised
  functions rejected by the gate. `stock_reorder.order_line`: one unanimous
  example in fifteen jobs, never synthesised.
- `log_triage.worst` is reported gold-wrong by the analysis; it fails only the
  benchmark's hand-written tests, whose log lines lack the 'HH:MM:SS' field the
  specification requires. It matched gold on every stream input.
- Three wrong stored examples, all probe answers where the reference is
  weaker than or silent relative to the specification: a negative amount in
  `invoice_audit.summary`, a quoted CSV field in `order_batch.rows`, a hyphen
  in a name in `meeting_actions.actions`. In that step one synthesis attempt
  was rejected at 13 of 14 before a later one was promoted; which example it
  failed was not recorded.

| Artifact | SHA-256 |
|---|---|
| `fast_path_jobs_v2_large_primary.jsonl` | `0e42c2f0c90dbefb0cc78061b3f45ee0b32ba347e0fef566f927582871de77c6` |
| `fast_path_jobs_v2_large_primary_analysis.json` | `845504cdf1b601a00fd5693a0225520fae8a5bbcf965e31976e7ce34e855b777` |

---

## 2026-11-17 — The router writes its own plans: build and freeze

The owner chose model-written plans as the next step. `planner.py` adds a
`PlanningRouter`: whole-task racing until a template has `plan_examples`
agreed answers, a planner model writing a step plan from the description and
input names, adoption only when the plan reproduces every agreed answer in a
trial run through the step pipeline, and an audit that drops a plan when a
fresh race agrees on something else. `FastPathRouter.start_prompt_race`
exposes every racer's answer. New settings: `planner_model`
(`openai/gpt-6-luna`), `planner_max_tokens` 8192, `plan_examples` 3,
`max_plan_attempts` 2, `plan_audit_rate` 0.1.

`fast_path_planned_bench_v1.py` gives each of the seven large-job shapes one
plain-language description. A live smoke run on two shapes, seven jobs each,
adopted a plan for both on the first attempt; every answer in every arm but one
direct call was correct. Not evidence.

`FAST_PATH_PLANNED_V1_PLAN.md` freezes one descriptive run. Provider credit at
the freeze: about $11.60.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_planned_bench_v1.py` | `f45bae98a0d8b305ece27c5d831f4db09190d7327ad6d96933d3e8502132dda2` |
| `fast_path_jobs_bench_v2_large.py` | `0821ca5e659feaa0980daef76d31117332ab643ab193bfc0f19cf15b12726f3e` |
| `config_fast_path.json` | `ce3fb332fa510b89fa0db96087f2850b5fbf79e1540d8c6a07a51893893c9a4a` |
| `fast_path.py` | `b51396aac1deb7a14fdb12dfb365065f5e9099e21e7f4640e0d24ca08cc88302` |
| `pipeline.py` | `bca87fc09cb826de1b6e5376b4eb38102ac0d5f5025662181d87bb472eed679d` |
| `planner.py` | `9f9236703e29acf82912f6c081a2c0fa678cc03b4d641a71d099c827cda44139` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `remote.py` | `4efc49ab45e68d09f026e75fca9e3aff2780fac8682b3b27f7fa983eda51afc2` |
| `run_fast_path_planned_v1.py` | `d5d24d842885037df4dc6464c7641db73b9dca69ac7770371647d4513951de0d` |
| `analyze_fast_path_planned_v1.py` | `5c57588248bbaa6358262b95c9383654d9db9d590f3396486688533852dc4d99` |
| `FAST_PATH_PLANNED_V1_PLAN.md` | `e15a816f68e86d7abd4b6a49906c0b1467a9cdde2a369efb443d253240b8fc8d` |

Verification: full unit suite passed (536 tests); description self-verify
passed; `git diff --check` passed.

---

## 2026-11-17 — Planned jobs V1 result

The frozen descriptive run completed in one attempt: 3,489 provider calls, 5
invalid responses, no unanswered job. Decision, C against R: `NOT_SUPPORTED`.

| Arm | Correct | Median ms | Mean ms |
|---|---:|---:|---:|
| A. Direct | 96/105 | 3823 | 3962 |
| R. Whole-task race | 103/105 | 2528 | 2504 |
| C. Planning router | 105/105 | 1986 | 1999 |

- C/R 0.786 (0.466 to 1.000): upper bound not below 1.0. C minus R +0.019
  (0.000 to +0.038). C/A 0.520 (0.310 to 0.668), +0.086.
- Plans adopted for 6 of 7 shapes, first plan-served job index 3 or 4.
  Attempts: 6 adopted, 2 rejected by trial (1/3 and 0/3 matched), 2 invalid.
- `order_batch`: both plans refused as `INVALID_STEP_TASK:INVALID_SIGNATURE`.
  The plan text was not kept, so which signature failed is unknown.
- Arm C routes: 69 jobs on a plan (median 1553 ms, all correct), 36 on the
  race (median 2768 ms, all correct). After adoption, medians A 3823, R 2422,
  C 1553 ms.
- Plan steps: 19 function (16 promoted), 7 judgement. Step executions:
  181 function on code, 36 function on the race, 80 judgement. No wrong job
  example, no plan demotion.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v1.jsonl` | `4c462b877dfb4129289e1dff877f9678bd54eebc4458c608d6f4be663a8d83a1` |
| `fast_path_planned_v1_analysis.json` | `913cda0eed7f53654084dc5f4830ab8aad408ae2c559a6050e8a79167a72d25d` |

---

## 2026-11-17 — Planner fixes and rerun authorised

At the owner's request: signature tidying and one retry with the refusal reason
in `planner.py` (`normalise_signature`, `plan_retries`), refused and rejected
plans kept in the record, and `plan_examples` lowered from 3 to 2. Recorded as
amendment 1 to `FAST_PATH_PLANNED_V1_PLAN.md`. Full suite passed (539 tests).
Credit before the rerun: about $9.45.

| Changed file | SHA-256 |
|---|---|
| `config_fast_path.json` | `b3ca27f9c3e828074293a51cc5a1530e73302998998a8d084dbcb99fef9cf06a` |
| `planner.py` | `8366396755502fcd320ffa6a22860afdb0ab5d5dd1375e051eb53a05aaa986a5` |
| `FAST_PATH_PLANNED_V1_PLAN.md` | `38a2e1a14014fa7791391cde991ee3f9c83acdd0dd9780627ace3c44a8193f5e` |

---

## 2026-11-17 — Planned jobs V1 rerun with fixes

Label `planned_v1_fixes`: 3,060 provider calls, 2 invalid responses, no
unanswered job. Decision: `NOT_SUPPORTED`.

| Arm | Correct | Median ms | Mean ms |
|---|---:|---:|---:|
| A. Direct | 101/105 | 3736 | 3941 |
| R. Whole-task race | 102/105 | 2391 | 2419 |
| C. Planning router | 103/105 | 2009 | 2249 |

- C/R 0.841 (0.716 to 1.087); C minus R +0.010 (-0.019 to +0.038).
- 8 plan attempts, all adopted on first try (one shape twice, after an audit
  demotion). No refused plan, so the validator fix and retry were not used.
- Plan steps 16 function (12 promoted), 8 judgement. Step executions: 130
  function on code, 80 function on the race, 101 judgement.
- Arm C routes: 88 plan jobs (87 correct, median 1862 ms), 17 race jobs
  (16 correct, median 2487 ms). After adoption: A 3709, R 2391, C 1867 ms.
- Wrong in C: `meeting_actions` job 0 on the race (overdue count 2 for 4);
  `invoice_audit` job 5 on a plan, final model step returned null. The audit
  then dropped that plan; a second plan was adopted.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v1_fixes.jsonl` | `c3b5a6c06db7198bc5bd107bbd4cc975683543d88119efbd4089932d8d6a75a2` |
| `fast_path_planned_v1_fixes_analysis.json` | `e8c413b24886d668478d1f8afc34ce7638dc70d52fc83c965a239e24541f08c5` |

---

## 2026-11-17 — Planner steering and speed feedback

The owner asked to steer the planner to smaller steps and asked whether any
feedback mechanism existed. Until now feedback covered correctness only (the
plan trial and the audit). Added: small-step guidance in `build_plan_prompt`;
`build_refine_prompt` and `PlanningRouter._maybe_refine`, which after
`refine_after_jobs` plan-served jobs reports to the planner which function
steps became code and which are still on the models, and adopts a revised plan
only if it passes the trial. Refinement attempts carry `kind: refine` and do
not count toward `max_plan_attempts`. Recorded as amendment 2. Full suite
passed. Credit before the run: about $7.05.

| Changed file | SHA-256 |
|---|---|
| `config_fast_path.json` | `64b85380071e693613b97697d31a48111ceab67fd0a9de5f907f520be124cca9` |
| `planner.py` | `06e432f3159fb0bd76c568ca2e163c9d143e7b2eae93979e2b7831fe7c7f7231` |
| `FAST_PATH_PLANNED_V1_PLAN.md` | `c499d3c22ddced01be3e183e01ae6eb65d301cb77a09cb322b3b085c46726262` |

---

## 2026-11-17 — Planned jobs V1, third run: steering and speed feedback

Label `planned_v1_steer`: 9,088 provider calls, 4 invalid responses, 26 HTTP
429 responses, no unanswered job. Decision: `NOT_SUPPORTED`.

| Arm | Correct | Median ms | Mean ms |
|---|---:|---:|---:|
| A. Direct | 95/105 | 3675 | 3904 |
| R. Whole-task race | 104/105 | 2429 | 2435 |
| C. Planning router | 105/105 | 1370 | 2225 |

- C/R 0.564 (0.397 to 1.091); C minus R +0.010 (0.000 to +0.029).
  C/A 0.373 (0.249 to 0.713).
- 13 plan attempts: 12 adopted, 1 rejected by trial (meeting_actions, 1 of 2).
  5 of them were speed refinements, all adopted, each after 4 jobs.
- Final plans: 83 function steps (79 promoted), 8 judgement. Step executions:
  768 function on code, 168 function on the race, 101 judgement.
- Last five jobs per shape: medians A 3723, R 2375, C 969 ms.
- `order_batch` C median 3900 ms against R 2683 ms: a 16-step plan with three
  function steps never promoted.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v1_steer.jsonl` | `b3f728f19cd548383af279e7826edd29ed7addfc8734ee75ee8335dbfa52ff05` |
| `fast_path_planned_v1_steer_analysis.json` | `9e912b76017943b20bc99fbd86d793af0b61607cc03a0cbe3883b96571ce0dbb` |

---

## 2026-11-17 — Planned jobs V2 freeze: prospective test on fresh jobs

The owner added credit and asked to continue. `fast_path_planned_bench_v2.py`
adds 7 new job shapes with plain-language descriptions and reference
functions qualified by hand-worked tests. `FAST_PATH_PLANNED_V2_PLAN.md`
freezes one prospective run of the planning router (steering and speed
feedback on) against the whole-task race. No provider call has touched these
jobs.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_planned_bench_v2.py` | `a48b7995948e089d53ca40cf8b241e6111e78c273f5fa39853c742250091b4fb` |
| `config_fast_path.json` | `64b85380071e693613b97697d31a48111ceab67fd0a9de5f907f520be124cca9` |
| `fast_path.py` | `b51396aac1deb7a14fdb12dfb365065f5e9099e21e7f4640e0d24ca08cc88302` |
| `pipeline.py` | `bca87fc09cb826de1b6e5376b4eb38102ac0d5f5025662181d87bb472eed679d` |
| `planner.py` | `06e432f3159fb0bd76c568ca2e163c9d143e7b2eae93979e2b7831fe7c7f7231` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `remote.py` | `4efc49ab45e68d09f026e75fca9e3aff2780fac8682b3b27f7fa983eda51afc2` |
| `run_fast_path_planned_v1.py` | `d5d24d842885037df4dc6464c7641db73b9dca69ac7770371647d4513951de0d` |
| `analyze_fast_path_planned_v1.py` | `5c57588248bbaa6358262b95c9383654d9db9d590f3396486688533852dc4d99` |
| `FAST_PATH_PLANNED_V2_PLAN.md` | `274701454f923abf1e9ef14e695c00c102043100fa0275554c03698fbc8ba1af` |

Verification: full unit suite passed; benchmark self-verify passed.

---

## 2026-11-17 — Planned jobs V2 result: supported on fresh jobs

The frozen prospective run completed in one attempt: 8,061 provider calls, 11
invalid responses, no unanswered job. Decision: `SUPPORTED`.

| Arm | Correct | Median ms | Mean ms |
|---|---:|---:|---:|
| A. Direct | 98/105 | 4275 | 4355 |
| R. Whole-task race | 102/105 | 2469 | 2552 |
| C. Planning router | 104/105 | 1534 | 2090 |

- C/R 0.621 (0.412 to 0.919); C minus R +0.019 (-0.019 to +0.067).
  C/A 0.359 (0.229 to 0.587); +0.057.
- 13 plan attempts: 12 adopted, 1 rejected (playlist refinement, 0 of 2).
  Six were speed refinements. No plan demotion, no wrong job example.
- Plan-served jobs 84, all correct, median 1261 ms. Race-served 21, 20
  correct (pick_list job 1 wrong).
- First plan-served job index: 2 for four shapes, 3 for two, 7 for
  timesheet (5 whole-task disagreements delayed its examples).
- Final plans: 74 function steps (70 promoted), 7 judgement. Step executions:
  689 function on code, 152 function on the race, 84 judgement.
- Last five jobs per shape: A 4623, R 2486, C 1063 ms.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_primary.jsonl` | `58419c3b641273822f1f819655c587323985239af8dd46bd01f8f246993f8139` |
| `fast_path_planned_v2_primary_analysis.json` | `062baa8b50c49431c45d6e4d1d8e6feb93f8effd881af8469ec7d4a310e9fbf2` |

---

## 2026-11-17 — Majority agreement, usage metering, immediate arrival

The owner asked to work through the listed next steps in order. Step 1 (real
tasks) waits on tasks from the owner; steps 2 and 3 start now.

- `PlanningRouter._agreement` takes an optional minimum: with
  `job_agreement_min` set, an answer given by at least that many racers, and by
  more than any other answer, counts as agreed. Default `null` keeps
  unanimity.
- `run_fast_path_planned_v1.py` wraps each arm's provider calls in a
  `UsageMeter` and writes calls and tokens per arm to each shape summary; the
  analysis sums them. `--arrival immediate` stops draining background work
  between jobs.
- Follow-up runs recorded in `FAST_PATH_PLANNED_V2_PLAN.md`.

Full suite passed (549 tests).

| Changed file | SHA-256 |
|---|---|
| `config_fast_path.json` | `0943897831b3793de717042cbda97a4470d49c327821ed079f7c97ac349bf41a` |
| `planner.py` | `98e5917acce35e5fbdef78d30b0904c1e1f2c18d370d5aca35ba4725fb73ce4e` |
| `run_fast_path_planned_v1.py` | `c27f73ab4e5f4fe9e751e7842848c612de2212c1e1b761ec4e17a149e9270f78` |
| `analyze_fast_path_planned_v1.py` | `644089f209b8eec130d250a2631f91c49e1f3a057f477120bd9b054afe964c4a` |
| `FAST_PATH_PLANNED_V2_PLAN.md` | `360a1786e7e0132b40724ba353645ca96585efa970f12e8221d385fe6137c85b` |

---

## 2026-11-17 — Follow-up 1: majority agreement (descriptive)

Label `majority`, `job_agreement_min` 4: 9,592 provider calls, no unanswered
job. Correct A 96, R 100, C 105 of 105. Medians A 4090, R 2585, C 1865 ms.
C/R 0.721 (0.472 to 1.024); C minus R +0.048 (+0.019 to +0.086).

- First plan job index 2 for five shapes, 3 for two; `timesheet` 2 (job 3)
  against 7 (job 8) under unanimity. No wrong job example, no demotion.
- 14 plan attempts: 12 adopted, 2 rejected (one first plan, one refinement).
- Final plans: 86 function steps (83 promoted), 7 judgement.
- Usage per arm: A 105 calls, 50,566 prompt and 27,932 completion tokens;
  R 525 calls, 281,442 and 358,348; C 8,962 calls, 2,020,135 and 1,393,248.
- Last five jobs per shape: A 3908, R 2641, C 967 ms.

Decision for follow-up 2: keep `job_agreement_min` 4, which brought plans
earlier with no observed safety cost.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_majority.jsonl` | `acf2741db820ff701f382ac6e1c317a60f5dc5cb4a17e69fa2264ae9fd46e477` |
| `fast_path_planned_v2_majority_analysis.json` | `416c0c875508cb688e2f97e2dd51a51d93753f172bdcd81b0650cd5fb656e2bd` |

---

## 2026-11-17 — Follow-up 2: back-to-back arrival (descriptive)

Label `immediate`, `job_agreement_min` 4, `--arrival immediate`: 7,266 provider
calls, 7 HTTP 429 and 3 invalid responses, no unanswered job.

- Correct A 96, R 100, C 99 of 105. Medians A 4074, R 2579, C 3117 ms;
  C 90th percentile 14,150 ms. C/R 1.209 (1.053 to 1.568); C minus R -0.010
  (-0.086 to +0.057). Both criteria fail.
- Arm C routes: 44 plan jobs (43 correct, median 6581 ms), 61 race jobs
  (56 correct). First plan job index 5 to 13; `expense_claims` none.
- 14 plan attempts: 10 adopted, 4 rejected. Final plans 78 function steps,
  36 promoted. Step executions: 127 function on code, 251 on the race.
- First wrong plan-served answer of any run: `bank_statement` job index 9.
- Usage: A 105 calls, R 525, C 6,636 (1,713,420 prompt and 1,279,034
  completion tokens).

Finding: adoption is gated on correctness only. Under live arrival a plan is
adopted while most of its steps are still raced one by one, which makes jobs
slower than a single whole-task race.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_immediate.jsonl` | `84642a8fe9f752f82b3998c36e5943c5aefd672193da75f45fa8485ac2d6d2a1` |
| `fast_path_planned_v2_immediate_analysis.json` | `db532fa5af5310d86dab9d62180e77f9a63c37ce983a64a45d4d29bfab0723d8` |

---

## 2026-11-17 — Shadow plans: go live only when fast

The owner chose to test a fix for the back-to-back result. `PlanningRouter`
now adopts a plan in shadow mode when `plan_shadow` is set: the whole-task race
keeps answering, `_shadow` runs the plan on each live job's inputs off the
answer path, drops the plan on an agreed mismatch, and switches it live once
its last `plan_live_window` runs each beat `plan_live_ratio` times the median
race time recorded for the template. Refinement counts shadow runs as uses.
Shape summaries record the plan's mode and shadow timings. Full suite passed
(552 tests). Credit before the run: about $11.85.

| Changed file | SHA-256 |
|---|---|
| `config_fast_path.json` | `eff69a362c563b90abce44cd08e442cac38beb0df66f9aa898e35573c1c1b066` |
| `planner.py` | `8e76fbb9146c106d61f9c4884fa75db7969349f5188980734952215451959f00` |
| `run_fast_path_planned_v1.py` | `6aeca26a05da142d6d7efe4400b805127f1bdc4cfe5bc550cd3c7d118efdc9f2` |
| `FAST_PATH_PLANNED_V2_PLAN.md` | `74b138f3b7f80426ba0b54da58cf77c9e3a83d00fbee078fa0787797c650a612` |

---

## 2026-11-17 — Follow-up 3: shadow plans under back-to-back arrival

Label `shadow`: 7,946 provider calls, 108 HTTP 429 and 12 invalid responses,
no unanswered job. Correct A 98, R 101, C 98 of 105. Medians A 4020, R 2451,
C 2834 ms; C 90th percentile 13,753 ms. C/R 1.157 (1.065 to 1.279); C minus R
-0.029 (-0.067 to 0.000).

- All 105 arm-C jobs answered by the race; no plan reached live mode.
  Recorded shadow-run times 6.2 to 43.4 s; race medians per shape 2.2 to
  4.5 s. One plan dropped on a shadow mismatch (`playlist`).
- 14 plan attempts: 12 adopted into shadow, 2 refinements rejected. Final
  plans 87 function steps, 30 promoted.
- Last five jobs per shape: A 4147, R 2506, C 7967 ms.
- Cause found in code: `FastPathRouter._models` is one pool used by the live
  race and by all background work, so background calls delay live ones.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_shadow.jsonl` | `1759f1f78dd41e9f2c88921840a1658f860ff8fda26d98d3605790dedb71bd5b` |
| `fast_path_planned_v2_shadow_analysis.json` | `7d8ba0651ceab2b9addb08e9e0822dcf8de88edc5acb95234f8c7d01d1c5b775` |

---

## 2026-11-17 — Live/background isolation and the real-tasks format (no provider calls)

The owner chose to keep the remaining credit (about $7.65) for a test on real
tasks. Meanwhile, two fixes for the second back-to-back flaw, tested against
fake models only:

- `FastPathRouter` has a separate background model pool
  (`background_model_workers`, default as large as the live pool) and a
  `background_context`; everything submitted through `_submit` runs in it.
  `pipeline.Orchestrator(background=True)` runs a job's steps on the
  background pool. `PlanningRouter` uses such an orchestrator for plan trials
  and shadow runs, and runs its own background work in the same context. A
  test checks that whole-task answers run on live threads and every step run
  on background threads.
- `PlanningRouter` allows one shadow run per task at a time; a run that would
  queue is skipped and counted in `shadow_skipped`.

These are not yet measured on live traffic.

For the owner's tasks: `real_tasks/` with a README describing the JSON format,
a made-up `example_invoice_check.json`, and `fast_path_real_bench.py`, which
loads every non-example file as a job shape for the planned-jobs runner and
explains format errors. Full suite passed.

| Changed file | SHA-256 |
|---|---|
| `fast_path.py` | `fe034b1b0fc35799017548e5dd7d9f090659676e756c32af9153b962d4f956f2` |
| `pipeline.py` | `fecc96aee7349fbf2229dad47207c7467a76c884fec281dd596d35185f528e83` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `fast_path_real_bench.py` | `cb24a842075f25b52d4fd601be560f88b7f150ab85f769e544c1a182c5471425` |
| `real_tasks/README.md` | `c6ec342711818564d90ed4e4e1adb003ea4fc2acafe205c60d73e7df58351e9c` |
| `real_tasks/example_invoice_check.json` | `5a9940bddd45ba86f013aa70f8a56e2dede4ee13cb00f14b670e71bc8bdcd1bd` |

---

## 2026-11-17 — Ceiling arm, frozen before its run

The owner pointed out that no run had a code-only arm and specified a ceiling
arm: hand-written code for the mechanical work, reading steps raced as arm C
races its judgement steps, drained arrival, per-arm metering, and the reading
of a perfect score stated in advance. Added `fast_path_ceiling_v1.py`
(reading steps for the seven fresh shapes) and arm D in
`run_fast_path_planned_v1.py` (`--ceiling`) and in the analysis
(`ceiling`: reading accuracy, C against D, medians of the first three and the
later jobs). Recorded as follow-up 4 in `FAST_PATH_PLANNED_V2_PLAN.md`. The
owner chose a full paired run (about $4 of $7.65). Full suite passed.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_ceiling_v1.py` | `a166f9e727199adffc9bb6ecf9137f28732c74c0375c7f21c291ba14c6c669e7` |
| `run_fast_path_planned_v1.py` | `47ae8affb3032d303bced2227b32a90885521661729a579ac558b9b33d58522d` |
| `analyze_fast_path_planned_v1.py` | `e9f83ace806fd733628076e6382ddb3fd08bdb0701788ab5aff7a16dfb5453d9` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `fast_path.py` | `fe034b1b0fc35799017548e5dd7d9f090659676e756c32af9153b962d4f956f2` |
| `pipeline.py` | `fecc96aee7349fbf2229dad47207c7467a76c884fec281dd596d35185f528e83` |
| `config_fast_path.json` | `eff69a362c563b90abce44cd08e442cac38beb0df66f9aa898e35573c1c1b066` |
| `FAST_PATH_PLANNED_V2_PLAN.md` | `347ca922f14c51d948bda3682bb00050997da80ec426db8a056c036eaa6decd8` |

---

## 2026-11-17 — Follow-up 4: ceiling arm result

Label `ceiling`: 9,337 provider calls, 8 invalid responses, no unanswered job.

| Arm | Correct | Median ms | Calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|
| A | 96/105 | 3891 | 105 | 50,566 | 28,193 |
| R | 98/105 | 2360 | 525 | 281,438 | 362,227 |
| C | 104/105 | 2146 | 8,182 | 1,833,042 | 1,290,226 |
| D | 105/105 | 834 | 525 | 91,516 | 18,679 |

- D reading steps correct 105/105. C/D 2.574 (1.590 to 3.534).
- Medians, first three jobs per shape: R 2385, C 2533, D 834; later jobs:
  R 2347, C 1956, D 838; last five: A 3908, R 2491, C 1198, D 870.
- Arm C, same settings as the frozen run: C/R 0.909 (0.535 to 1.245);
  correctness +0.057 (+0.010 to +0.133). All 7 shapes planned; 13 attempts all
  adopted; 80 function steps, 72 promoted. One wrong C answer, from the race.
- Not recorded as a decision: the frozen run's decision stands, and this
  descriptive re-run shows its time margin varies widely between runs.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_ceiling.jsonl` | `b708475aa1d2f8c6989791cdd53269935e788bb8980b503cbfaa62001e5840a7` |
| `fast_path_planned_v2_ceiling_analysis.json` | `f37b88d4a74ef0b10233655a29f4c655162b28576f330b88061c38f78ab81afc` |

---

## 2026-11-17 — Follow-up 5 authorised: isolation fixes under live traffic

The owner asked for both the real-task test and a live run of the isolation
fixes. The real-task test waits on tasks from the owner. Follow-up 5 recorded
in `FAST_PATH_PLANNED_V2_PLAN.md`. Credit before the run: about $20.95.

| File | SHA-256 |
|---|---|
| `fast_path.py` | `fe034b1b0fc35799017548e5dd7d9f090659676e756c32af9153b962d4f956f2` |
| `pipeline.py` | `fecc96aee7349fbf2229dad47207c7467a76c884fec281dd596d35185f528e83` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `config_fast_path.json` | `eff69a362c563b90abce44cd08e442cac38beb0df66f9aa898e35573c1c1b066` |
| `run_fast_path_planned_v1.py` | `47ae8affb3032d303bced2227b32a90885521661729a579ac558b9b33d58522d` |
| `FAST_PATH_PLANNED_V2_PLAN.md` | `42726e1a0475dfdcc41fc492651cd0cac5d7466dd734a4c9d8cca1843b453468` |

---

## 2026-11-17 — Follow-up 5: isolation fixes under live traffic

Label `isolated`: 6,660 provider calls, 6 invalid responses, no HTTP 429, no
unanswered job. Correct A 102, R 101, C 103, D 105. Medians A 3620, R 2448,
C 2432, D 838 ms. C/R 0.993 (0.963 to 1.075); correctness +0.019 (-0.019 to
+0.067). D reading 105/105; C/D 2.903.

- All 105 arm-C jobs answered by the race; C race-route median 2432 ms against
  R 2448 ms. Last five jobs per shape: R 2432, C 2386 ms.
- 11 plan attempts, all adopted into shadow; one dropped on a shadow mismatch
  (`playlist`). Six shadow runs finished in total, 4.9 to 47.2 s; none went
  live. 74 function steps, 38 promoted.
- Usage: C 5,505 calls (1,403,966 prompt and 1,158,966 completion tokens).

Reading: the pool separation removed the slowdown of the live path seen in
follow-up 3. Within 15 back-to-back jobs per shape, learning does not finish,
so the shadow rule never lets a plan serve.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_isolated.jsonl` | `1bea144dbcab2988276bbc10bde692b6318952477cb897ea96fcd585c27233e1` |
| `fast_path_planned_v2_isolated_analysis.json` | `dc7e98daa6d7f08adf2628a8140d2c29ba7afaa80020720dd7638821e7ae50f8` |

---

## 2026-11-17 — Write-up and spreadsheet brought up to date; follow-up 6 recorded

The owner has no real tasks to supply, so the real-task test is dropped. The
shared write-up gained a section on live traffic and the ceiling and corrected
limits; the spreadsheet gained five follow-up rows and a Ceiling sheet.
`run_fast_path_planned_v1.py` now takes several `--set` overrides and
`--jobs N`. Follow-up 6 (`long_stream`) recorded before its run. Credit
before the run: about $17.40.

| File | SHA-256 |
|---|---|
| `run_fast_path_planned_v1.py` | `53676003b38dcc69536957ffc7c3bb79515c75da06cd7ea7276fceb204c4a7e1` |
| `config_fast_path.json` | `eff69a362c563b90abce44cd08e442cac38beb0df66f9aa898e35573c1c1b066` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `fast_path.py` | `fe034b1b0fc35799017548e5dd7d9f090659676e756c32af9153b962d4f956f2` |
| `FAST_PATH_PLANNED_V2_PLAN.md` | `fb200f5655592fe5d6bcaa505740eb60ab755b3d9549096e0b9185510d1ee01a` |

---

## 2026-11-17 — Follow-up 6: long stream, cheaper learning

Label `long_stream`: four shapes, 40 jobs each, back to back, `max_probes` 4,
`job_agreement_min` 4, shadow plans, separate pools, ceiling arm. 7,025
provider calls, 7 invalid responses, no unanswered job.

| Arm | Correct | Median ms | Calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|
| A | 143/160 | 4014 | 160 | 81,152 | 47,835 |
| R | 149/160 | 2755 | 800 | 449,463 | 604,715 |
| C | 151/160 | 2239 | 5,265 | 1,451,151 | 1,221,962 |
| D | 160/160 | 836 | 800 | 140,799 | 30,938 |

- Live from job index 19 (`timesheet`, after 6 shadow runs), 24
  (`survey_scores`, after 3), 33 (`shipment_tracking`, after 12).
  `expense_claims` stayed in shadow: 17 of 20 function steps promoted, shadow
  runs 2.8 to 15.2 s against a race median of 2651 ms.
- Arm C routes: 44 plan jobs (43 correct, median 1602 ms), 116 race jobs
  (108 correct, median 2661 ms). After each shape went live: C 1678, 1789,
  845 ms; R 3110, 3261, 1900 ms; D 836, 819, 831 ms.
- C/R 0.813 (0.696 to 1.000); C minus R +0.012 (0.000 to +0.037).
  D reading 160/160; C/D 2.678.
- 9 plan attempts: 6 adopted, 3 rejected (1 plan, 2 refinements).

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_long.jsonl` | `844adab42aada6d993f03a276a5d9ab75c4b68e5bf8d037636834fdcafe4cc6c` |
| `fast_path_planned_v2_long_analysis.json` | `5c6d921486826f87ea02d5c07631ee6ace1ee0e9814823e0d24a62e5daf47fe7` |

---

## 2026-11-17 — Follow-up 7 frozen: cheaper learning (handoff item 1)

New session, working through the handoff's open items in order at the owner's
request. `FastPathRouter` gains an optional `learning_models` roster: function
steps learned in the background (step races in plan trials and shadow runs,
and probe answers) ask only these models; live answers, live plan steps and
judgement steps keep the full roster. Default `null` keeps earlier behaviour.
`UsageMeter` now meters calls and tokens by purpose, and the analysis reports
them. Full suite passed (562 tests). Recorded as follow-up 7 in
`FAST_PATH_PLANNED_V2_PLAN.md`. Credit before the run: about $13.25.

| File | SHA-256 |
|---|---|
| `fast_path.py` | `01262b2e97fc24c494340a4224e81782ca85eae88510219d9d171b90ad087d89` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `pipeline.py` | `fecc96aee7349fbf2229dad47207c7467a76c884fec281dd596d35185f528e83` |
| `config_fast_path.json` | `785e0a8b2ba76b6be33d5ebdfb2c4b3533f27b70cbd16a77ef9bd9c01b3f42df` |
| `run_fast_path_planned_v1.py` | `e6696d96bfd20d1278b1ea98e58055fcde34b9f49ab10dc716b35548a3d684ce` |
| `analyze_fast_path_planned_v1.py` | `7f8c08f7b4eebddbb7c46be623be2e1456f36140b2161d3daea51a9ea7cf497e` |
| `FAST_PATH_PLANNED_V2_PLAN.md` | `e43d80fd7cb1e73b73dda43f198d1068c11d4c07e1aa96413e4f3c143222c2d9` |

---

## 2026-11-17 — Planned jobs V3 stage 1 frozen: new shapes and code-only rules, before any text exists

Handoff items 2 and 4 share one benchmark (`FAST_PATH_PLANNED_V3_PLAN.md`):
8 new, more varied job shapes, and keyword reading rules for a code-only arm,
written from the descriptions alone. Recorded here before the reading texts
are generated, so the rules cannot have been fitted to them. Follow-up 7 was
running meanwhile; nothing here touches its files.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_planned_bench_v3.py` | `5248a055c80d11e9d55b3280102ac23dd844d055fdd4476597386e7a4fbfbc70` |
| `fast_path_code_only_v1.py` | `843a14b6496b675c01ea8f1f43a9c1916209142a93bd6c63ca3dea7bc101a9f5` |
| `fast_path_ceiling_v3.py` | `4420adde077c3d03c186f207a6b77f6d71c05a937d5c6360cd9806a90a6959a6` |
| `make_bench_v3_prose.py` | `ac306989534241c9f413f870596520193bbb9159ed60011396cfa7cafebed868` |
| `FAST_PATH_PLANNED_V3_PLAN.md` | `e19b8177286dd2ee196342082ea2d94d02994489eaada0e01792e45f04e46809` |

---

## 2026-11-17 — Follow-up 7: cheaper learning with a two-model learning roster

Label `lean_learning`: as follow-up 6 plus `learning_models`
`["google/gemini-3.8-flash", "openai/gpt-5.6-luna"]`. 4,866 provider calls
(follow-up 6: 7,025), 3 HTTP 429 and 2 invalid responses, no unanswered job.

| Arm | Correct | Median ms | Calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|
| A | 143/160 | 3631 | 160 | 81,152 | 47,431 |
| R | 148/160 | 2830 | 800 | 449,450 | 604,161 |
| C | 148/160 | 2759 | 3,106 | 951,053 | 1,100,486 |
| D | 160/160 | 854 | 800 | 140,795 | 30,229 |

- Arm C by purpose: whole-task races 720 calls, step and probe answers 2,217,
  probe proposals 74, synthesis 85, plans 10. Learning calls (everything but
  the whole-task race) about 2,386, against an estimated 4,660 in follow-up 6
  (not metered by purpose; its 116 race-routed jobs and a few audits account
  for about 600 of its 5,265 calls).
- Money did not fall: about $4.45 for this run against about $4.15 for
  follow-up 6. The learning pair includes the roster's most expensive model
  per token (`google/gemini-3.8-flash`, $0.75 and $3.75 per million prompt and
  completion tokens; `openai/gpt-6-luna` and `anthropic/claude-haiku-5.5` are
  $0.10 and $0.50), so fewer calls did not mean less spend. Cost is not an
  objective, but the remaining credit is a limit.
- Plans live: `expense_claims` from job index 30 (after 9 shadow runs, all
  15 function steps promoted; it never went live in follow-up 6),
  `survey_scores` from job index 34 (after 13). `shipment_tracking` stayed in shadow
  (25 of 26 function steps promoted; the unpromoted `action` step kept shadow
  runs at 2.1 to 4.4 s against a race median of 2.0 s). `timesheet` lost its
  plan to a shadow mismatch and had no attempts left. 16 plan-served jobs (all
  correct, median 1029 ms) against 44 in follow-up 6.
- C/R 0.975 (0.936 to 1.034); C minus R 0.000 (-0.050 to +0.038). Wrong job
  examples 0. D reading 160/160.

Reading: the learning roster cut learning calls by about half, as intended,
but neither time nor money improved in this run. Which plans the planner
writes, and whether one step resists promotion, varied more between the two
runs than anything the roster changed. One run per setting cannot separate
the two. A cheaper pair by price (for example `openai/gpt-6-luna` with
`deepseek/deepseek-v4.1-flash`, 240 of 251 agreed in the development data,
1 agreed and wrong) is untested.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v2_lean.jsonl` | `ad843e7d6aa69c10b862c52c289604854abe19893f222f6b4b1055d49bd58a11` |
| `fast_path_planned_v2_lean_analysis.json` | `c1cf18797b379ae53ad9dd2fd0c4955d47e8ec78c4fa7bfc352cce8644d8ee71` |

---

## 2026-11-17 — V3 reading texts generated and hand-checked (before any rule is scored)

`make_bench_v3_prose.py` (hash above) wrote 12 texts per label, 324 in all,
with one call per shape to `mistralai/mistral-large-4-0`. The assistant read
every text against its planted label before any rule or model saw it:
none excluded, 7 borderline texts kept with reasons (recorded in the file).
The sensor notes all name their site outright, and the delivery notes mostly
name a city and postcode; the urgency, department, diet, issue, request and
formality texts mostly do not use the label word.

| File | SHA-256 |
|---|---|
| `fast_path_planned_bench_v3_prose.json` | `efaf393f643cb108d10ecd0bd170856f5cf5149a249c01a5c6341044b9005cf4` |

---

## 2026-11-17 — Code-only rules scored on unseen text; V3 run frozen (stage 2)

Handoff item 2. `score_code_only_v1.py` scored the frozen keyword rules on the
hand-checked texts, with no provider call: 293 of 324 distinct texts (90.4%),
220 of 240 jobs on the 30-job stream. Perfect on urgency and site, weakest on
library requests (39/48) and diets (29/36). Details in `code_only_v1_scores.json`
and `FAST_PATH_PLANNED_V3_PLAN.md`.

Runner and analysis gain arm E (code only: rules plus reference code, no
model, never metered) and its summary (reading accuracy per shape; R, C and D
against E). Stage 2 of `FAST_PATH_PLANNED_V3_PLAN.md` frozen: 8 shapes, 20
jobs each, arms A, R, C, D, E, drained arrival, plans live on adoption. Full
suite passed (568 tests). Credit at the freeze: about $8.75.

| Frozen file | SHA-256 |
|---|---|
| `fast_path.py` | `01262b2e97fc24c494340a4224e81782ca85eae88510219d9d171b90ad087d89` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `pipeline.py` | `fecc96aee7349fbf2229dad47207c7467a76c884fec281dd596d35185f528e83` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `remote.py` | `4efc49ab45e68d09f026e75fca9e3aff2780fac8682b3b27f7fa983eda51afc2` |
| `config_fast_path.json` | `785e0a8b2ba76b6be33d5ebdfb2c4b3533f27b70cbd16a77ef9bd9c01b3f42df` |
| `run_fast_path_planned_v1.py` | `6913fe3d017e0a9ba31f27ad37a29bd3295833439f036db8bc6697d6f20fe44e` |
| `analyze_fast_path_planned_v1.py` | `548f0ab690bd0b5cfcf16b2a72a11e15daa9010c56aaed449d1106c6525792d3` |
| `fast_path_planned_bench_v3.py` | `5248a055c80d11e9d55b3280102ac23dd844d055fdd4476597386e7a4fbfbc70` |
| `fast_path_planned_bench_v3_prose.json` | `efaf393f643cb108d10ecd0bd170856f5cf5149a249c01a5c6341044b9005cf4` |
| `fast_path_ceiling_v3.py` | `4420adde077c3d03c186f207a6b77f6d71c05a937d5c6360cd9806a90a6959a6` |
| `fast_path_code_only_v1.py` | `843a14b6496b675c01ea8f1f43a9c1916209142a93bd6c63ca3dea7bc101a9f5` |
| `score_code_only_v1.py` | `77140d74e9838a11c80e643453490b7ffc8573e8d749abc31be0fe4946fa7088` |
| `code_only_v1_scores.json` | `690ca3e75ff2c9142781976a2bec4816042f22130fcf695b550f726c444e5c3f` |
| `FAST_PATH_PLANNED_V3_PLAN.md` | `468c2348cd0b51cb37cef479ec123c57ef78948e32185f13cc4774861abb1514` |

---

## 2026-11-17 — Planned jobs V3 primary result (prospective; handoff items 2 and 4)

Label `v3_primary`: 8 fresh shapes, 20 jobs each, arms A, R, C, D, E, drained
arrival, plans live on adoption. 10,153 provider calls, 14 invalid responses,
no unanswered job. Cost about $2.43.

| Arm | Correct | Median ms | Last five ms | Calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|---:|
| A | 153/160 | 3086 | 3210 | 160 | 68,026 | 28,327 |
| R | 155/160 | 1957 | 1834 | 800 | 375,371 | 420,438 |
| C | 158/160 | 2078 | 1186 | 8,393 | 1,833,375 | 1,185,950 |
| D | 160/160 | 872 | 870 | 800 | 154,682 | 40,847 |
| E | 148/160 | 0.16 | 0.15 | 0 | 0 | 0 |

**Primary decision: NOT SUPPORTED.** C/R 1.062 (0.684 to 1.440): the time
criterion fails. C minus R +0.019 (+0.006 to +0.037): the correctness
criterion holds.

- Plans adopted for 7 of 8 shapes, all from job index 2; 126 plan-served jobs,
  all correct (median 1861 ms). `fleet_fuel` had both plans rejected and ran
  on the race throughout (its two wrong C answers came from the race). 15 plan
  attempts: 12 adopted, 3 rejected. 70 function steps, 62 promoted. No wrong
  job example, no demotion.
- Shapes where C was slower than R, with the reason in their records:
  `library_loans` (3343 against 2036 ms; three date-arithmetic steps,
  `overdue`, `days`, `most_title`, never promoted and raced in a chain),
  `room_bookings` (2264 against 1885; three floor-lookup steps unpromoted),
  `fleet_fuel` (no plan), and `ticket_queue` and `event_rsvps` before their
  steps were promoted. Where every step was promoted, C ran at about 0.8 to
  1.1 s against the race's 1.6 to 2.7 s.
- Ceiling: D reading 160/160; C/D 2.38 (1.54 to 3.33).
- Code-only test (fixed in advance): E 148/160, exactly as stage 1 predicted.
  C minus E +0.063 (+0.013 to +0.113): **C beats code**. D minus E +0.075
  (+0.038 to +0.119): **models read better than the rules**. R minus E +0.044
  (-0.006 to +0.094): the race does **not** clear the bar. E is about 10,000
  times faster than any model arm.

| Artifact | SHA-256 |
|---|---|
| `fast_path_planned_v3_primary.jsonl` | `0c9a5b7835e658c6d9fade95c3929aefc479839acbb3ab8455f4629fe356fb57` |
| `fast_path_planned_v3_primary_analysis.json` | `2af7cea26a5e75b1508169ad63c389a59ae392237ca47c16e3040a87cac0e67d` |

---

## 2026-11-18 — Write-once arm frozen (next step 1 of 3)

At the owner's request (credit topped up to about $10.50), the competitor the
planning router has to beat: `write_once.py`, a router that has one model
write the whole job once and keeps it only if it reproduces two agreed answers.
The runner gains arm W and `--arms`; `analyze_write_once_v1.py` analyses it.
Full suite passed. Plan: `FAST_PATH_WRITE_ONCE_V1_PLAN.md`.

| Frozen file | SHA-256 |
|---|---|
| `write_once.py` | `4f222c320a16269357d5aa45fa11a7e7f08edf196496b2aab026fe4e911f0ce2` |
| `run_fast_path_planned_v1.py` | `3f27601a162bfe3ed8e5ff59ce7f11e6054126ef864fdf3fe3759f520a864751` |
| `analyze_write_once_v1.py` | `a4eaf4b591bdabe17cf571d1328bd402fb5c2406ed2820e5d249867c7267f3df` |
| `analyze_fast_path_planned_v1.py` | `ac7a63d137d0f2eb21923e26e1bcd7738bda574b54f2d7288708a0c934d230a5` |
| `config_fast_path.json` | `785e0a8b2ba76b6be33d5ebdfb2c4b3533f27b70cbd16a77ef9bd9c01b3f42df` |
| `fast_path.py` | `01262b2e97fc24c494340a4224e81782ca85eae88510219d9d171b90ad087d89` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `sandbox.py` | `b132f5d8175e60916baa0550c09d2f5d34e247e99bd390eee07510f596a9dcff` |
| `fast_path_planned_bench_v3.py` | `5248a055c80d11e9d55b3280102ac23dd844d055fdd4476597386e7a4fbfbc70` |
| `fast_path_planned_bench_v3_prose.json` | `efaf393f643cb108d10ecd0bd170856f5cf5149a249c01a5c6341044b9005cf4` |
| `fast_path_ceiling_v3.py` | `4420adde077c3d03c186f207a6b77f6d71c05a937d5c6360cd9806a90a6959a6` |
| `fast_path_code_only_v1.py` | `843a14b6496b675c01ea8f1f43a9c1916209142a93bd6c63ca3dea7bc101a9f5` |
| `FAST_PATH_WRITE_ONCE_V1_PLAN.md` | `bd40c172c69c19b40591e83a736a702f8ee31617d2dbfe61922450edd0b792a1` |

---

## 2026-11-18 — Write-once arm result (descriptive)

Label `write_once_v1`: V3 jobs (8 shapes, 20 each), arms R, D, E, W, drained.
2,548 provider calls, 3 invalid responses, no unanswered job. Cost about $1.23.

| Arm | Correct | Median ms | Last five ms | Calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|---:|
| R | 155/160 | 1963 | 1866 | 800 | 374,422 | 415,263 |
| D | 160/160 | 925 | 925 | 800 | 154,688 | 45,288 |
| E | 148/160 | 0.17 | 0.17 | 0 | 0 | 0 |
| W | 156/160 | 1018 | 1002 | 948 | 227,352 | 147,728 |
| C (V3 primary, other run) | 158/160 | 2078 | 1186 | 8,393 | 1,833,375 | 1,185,950 |

- **Every shape adopted a program at its first attempt**, at job index 2
  (four shapes), 3 (two), 4 and 5. Each program had one reading step and 16
  to 50 lines of code. No demotion. 134 program-served jobs, 133 correct
  (median 977 ms); the one wrong answer was a reading, not code: the
  borderline `recipe_scaling` text flagged in the hand check ("No steak or
  salmon...") read as 'any' under the program's own, vaguer reading spec.
  The three other wrong W answers came from the race before adoption.
- W/R 0.519 (0.423 to 0.613); W minus R +0.006 (-0.013 to +0.025).
  W/D 1.10 (1.05 to 1.22); W minus D -0.025 (-0.050 to -0.006).
  W minus E +0.050 (-0.006 to +0.106).
- Against the planning router on the same jobs (other run, descriptive): W
  answered faster (1018 against 2078 ms median), went to code on every shape
  where C left `fleet_fuel` unplanned and three shapes with unpromoted steps,
  and made 948 calls against 8,393.

Reading: writing the job once, checked against two agreed answers, beat
learning it step by step on every measure except a small correctness margin,
and came within 10% of the hand-written ceiling. The planning router's
step-by-step learning is not justified on jobs like these.

| Artifact | SHA-256 |
|---|---|
| `fast_path_write_once_v1.jsonl` | `a3415cfecea27dcf7ccc726b0ed61d0d7f6f5a6c11442d11cd8e10545815ee82` |
| `fast_path_write_once_v1_analysis.json` | `5dcff012e82474c5a625c91b411ae6d00f981c4e57c2a09636924e89c4fd2151` |

---

## 2026-11-18 — Repair V1 frozen (next step 2 of 3)

`repair_attempts` (default 0) and per-step learning diagnostics, tested with
fake models; full suite passed. Plan: `FAST_PATH_REPAIR_V1_PLAN.md`.

| Frozen file | SHA-256 |
|---|---|
| `fast_path.py` | `753fef2c26534cabd0f6efbc7a2da0baf64b0ba3e2ac2572e2cd4217e2886caa` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `pipeline.py` | `fecc96aee7349fbf2229dad47207c7467a76c884fec281dd596d35185f528e83` |
| `config_fast_path.json` | `6d994e62ef672619a88aeb909032ea9681766decf274152e2b64d99d027cda10` |
| `run_fast_path_planned_v1.py` | `949b6dae148988ab4d55a8394aac1c343c29b2ccb0b082a01e744a99151541c7` |
| `FAST_PATH_REPAIR_V1_PLAN.md` | `7a1c0af0ef0a668468a87cffb193d27a2225d90d198ee79b7824478d1bf9742c` |

---

## 2026-11-18 — Repair V1 result (descriptive)

Label `repair_v1`: `library_loans`, `room_bookings`, `event_rsvps`, 20 jobs
each, arms R and C, `repair_attempts` 1. 4,375 provider calls, 6 invalid
responses. Cost about $1.47.

| Shape | C median (this run) | C median (V3 primary) | R median | C promoted |
|---|---:|---:|---:|---:|
| `library_loans` | 983 | 3343 | 2062 | 10/10 |
| `room_bookings` | 1434 | 2264 | 1920 | 11/12 |
| `event_rsvps` | 1826 | 1795 | 1793 | 11/12 |

- **Why steps stay on the models** (new diagnostics): each stuck step had
  plenty of agreed examples (28, with 12 agreed probes and no racer
  disagreement) and failed the gate on mismatches: 12 of 15 and 12 of 16
  examples matched on both blind attempts.
- **The repair did not help.** Two repairs were tried
  (`room_duration_pairs`, `maybe_entries`); shown two failing cases, the
  rewritten code matched fewer examples (6 of 17 and 10 of 17). Neither was
  promoted. No repair was needed in `library_loans`.
- The speed gains against the V3 primary run come from the planner writing
  different plans this time (every `library_loans` step was promoted), not
  from repair. Run-to-run variation in plans again dominates.
- All 60 C answers and all 60 R answers correct.

Reading: the stuck steps return structured values (lists of pairs or rows)
whose exact form the racers agree on but the code writer does not reproduce
from the spec. The fix would lie in the plan's step specs or in agreeing on a
canonical form, not in showing failures to the code writer. Given the
write-once result, this line is not worth pursuing further now.

| Artifact | SHA-256 |
|---|---|
| `fast_path_repair_v1.jsonl` | `59ae3d512287e934e14e7088be503382d27114f120f981aeb852ea2e08082f7c` |
| `fast_path_repair_v1_analysis.json` | `d31a159f21e2d3d393eedaea30ad464298040585ecc99e221a8e68e6b43978dd` |

---

## 2026-11-18 — Write-once V2 stage 1 frozen: unseen jobs and rules before any text exists

At the owner's request (estimated cost about $5.20 of $7.80). Plan:
`FAST_PATH_WRITE_ONCE_V2_PLAN.md`.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_planned_bench_v4.py` | `7bdc4dc5a86c3e1710e3076c9ccf8f87fd7236ec6cd5851995caf550cfe2679d` |
| `fast_path_code_only_v2.py` | `37be79b8d1ff4bc45cb49e623612a280f3c658ba745e86bf27a4a0709c993ae2` |
| `fast_path_ceiling_v4.py` | `bcab5bb6034e1849397ad116d8e39030cc06673a749ff0691a8373c2bce61e82` |
| `make_bench_v4_prose.py` | `0a6a4b5080b9bda60858b56532757a94cb7f87252d526f5a9096a7c58b578f01` |
| `FAST_PATH_WRITE_ONCE_V2_PLAN.md` | `81c5829758ad8fbee89ba77399972b7542d75f80f8ce8ade15ed63d176b93dc9` |

Amendment before any text was kept: the first generation stopped at
`energy_meter` on a provider failure (`OPENROUTER_RESPONSE_INVALID`) and,
by design, saved nothing; the three shapes it had received were never read.
`make_bench_v4_prose.py` now retries a failed call (up to three attempts)
instead of stopping. The prompt is unchanged. New hash: `25f1ab5b6a1c8dbfa8c392e409f68669d386a662d04e50a7ef8d3b1f30c4ffc2`.

V4 texts generated (12 per label, 360 in all) and hand-checked before any
rule or model read them: 1 excluded (`flight_delays` information[3], which
fits rebook too), 2 borderline kept with reasons.

| File | SHA-256 |
|---|---|
| `fast_path_planned_bench_v4_prose.json` | `8b12829bdf1e69825d610c06940eaf6f7ede074b2894c47b843b4399ff3d4b7d` |

---

## 2026-11-18 — Write-once V2 stage 2 frozen

Rules v2 scored offline: 308/359 texts, 127/160 stream labels. Runs frozen in
`FAST_PATH_WRITE_ONCE_V2_PLAN.md`; the analysis gains a decision for W
against R and W/C, C/R pairs. Credit at the freeze: about $7.75.

| Frozen file | SHA-256 |
|---|---|
| `write_once.py` | `4f222c320a16269357d5aa45fa11a7e7f08edf196496b2aab026fe4e911f0ce2` |
| `run_fast_path_planned_v1.py` | `949b6dae148988ab4d55a8394aac1c343c29b2ccb0b082a01e744a99151541c7` |
| `analyze_write_once_v1.py` | `766c1365f4e2e1c8e5d552bcd6c4e9689ffd8fb5e2445c3adbc80700a150670f` |
| `config_fast_path.json` | `6d994e62ef672619a88aeb909032ea9681766decf274152e2b64d99d027cda10` |
| `fast_path.py` | `753fef2c26534cabd0f6efbc7a2da0baf64b0ba3e2ac2572e2cd4217e2886caa` |
| `planner.py` | `941d7f2baaa04caa7f92b5ae369760e3a10f6a0acdf2e925c87b6807aa3dccb3` |
| `fast_path_planned_bench_v4.py` | `7bdc4dc5a86c3e1710e3076c9ccf8f87fd7236ec6cd5851995caf550cfe2679d` |
| `fast_path_planned_bench_v4_prose.json` | `8b12829bdf1e69825d610c06940eaf6f7ede074b2894c47b843b4399ff3d4b7d` |
| `fast_path_ceiling_v4.py` | `bcab5bb6034e1849397ad116d8e39030cc06673a749ff0691a8373c2bce61e82` |
| `fast_path_code_only_v2.py` | `37be79b8d1ff4bc45cb49e623612a280f3c658ba745e86bf27a4a0709c993ae2` |
| `FAST_PATH_WRITE_ONCE_V2_PLAN.md` | `3b413a2b037f3accb4ce57e6e77dc53c5a3deafae21596c8e76019550558a7ec` |

---

## 2026-11-18 — Write-once V2 run 1 result (prospective)

Label `write_once_v2_primary`: V4 jobs (8 unseen shapes, 20 each), arms R, C,
D, E, W, drained. 14,206 provider calls, 40 invalid responses, no unanswered
job. **Cost about $5.62, against an estimate of $3.80** (arm C made 11,627
calls).

| Arm | Correct | Median ms | Last five ms | Calls |
|---|---:|---:|---:|---:|
| R | 153/160 | 2296 | 2416 | 800 |
| C | 150/160 | 1753 | 1074 | 11,627 |
| D | 159/160 | 912 | 926 | 800 |
| E | 127/160 | 0.14 | 0.16 | 0 |
| W | 151/160 | 963 | 910 | 979 |

**Primary decision: NOT SUPPORTED.** W/R 0.419 (0.352 to 0.468): the time
criterion holds. W minus R -0.013 (-0.100 to +0.050): the correctness
criterion fails.

- W adopted a program for every shape at its first attempt (job index 2 or
  3). 139 program-served jobs, 132 correct. Of the 7 wrong: 5 were code, all
  in `wine_orders`, where the program rounded the discounted value instead
  of the discount, which differs only when the discount ends in exactly half
  a cent, a case neither trial example contained. An audit caught the first
  such program and dropped it; the second had the same fault. 2 were
  readings (a cot request, a conference-room note), under the program's own
  reading specs.
- C's plans made the same rounding error on the same `wine_orders` jobs
  (C 14/20 there). The whole-task race got all 20 right.
- W against C: 0.55 of C's time (0.42 to 0.80), correctness +0.006 (0.000 to
  +0.019), with 1/12 of the calls. C against R: 0.76 (0.48 to 0.99),
  correctness -0.019 (-0.106 to +0.044).
- W against D: 1.06 of the ceiling's time (0.99 to 1.12), -0.050 (-0.125 to
  0.000). W and C against E: W +0.150 (-0.025 to +0.319); neither interval is
  wholly above zero, because the rules were right on `wine_orders` where the
  code-based arms were not.

Reading: on unseen jobs writing the job once was again about twice as fast as
the race and beat step learning on time, calls and correctness, but code
checked against two agreed answers can carry an edge-case rule error that the
race does not make. The two-example trial is too thin for rounding rules; the
probes the fast path uses for single steps would be the natural guard.

| Artifact | SHA-256 |
|---|---|
| `fast_path_write_once_v2_primary.jsonl` | `9223f62d65cd58aac9c43c1d89965da514c30ad2016ce2b6b2e2c3cebb40092e` |
| `fast_path_write_once_v2_primary_analysis.json` | `951ff93341bbe09b1c0abfaae39b223bf95efc64c84200102398682f710a91d4` |

---

## 2026-11-18 — Write-once V3 stage 1 frozen: probes and fresh unseen jobs

Owner topped up to about $13 and chose: edge-case probes for write-once
(`program_probes`, arm P in the runner), then a fresh prospective test with
jobs drained and back to back. Estimated cost about $4.20. Full suite passed.
Plan: `FAST_PATH_WRITE_ONCE_V3_PLAN.md`.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_planned_bench_v5.py` | `917d653eac9cdd9b07b6b9509af298b4ae00e04e878fdf8551fe341dbbf44c55` |
| `fast_path_ceiling_v5.py` | `9e74e0302fff403da8c00ac6d1b35faec3edbd3ad96ea50f797fd687e8ebe620` |
| `make_bench_v5_prose.py` | `6a4143b8d034e9c83570bbc9732d21f46631e37a7390d4f78dfcd31ce42e15d1` |
| `write_once.py` | `a9add6feeab325a90b7c9c9afc79b0d819d11f98ef9405c4fcaf8c4772a62d7f` |
| `FAST_PATH_WRITE_ONCE_V3_PLAN.md` | `96e824456c8c3ce0724a5c839026b5ab4b0e549057609d4b6484e41164f56886` |

---

## 2026-11-18 — Write-once V3: texts hand-checked; runs frozen

V5 texts generated (324) and hand-checked before any model read them: 3
excluded, 4 borderline kept. Runs frozen in `FAST_PATH_WRITE_ONCE_V3_PLAN.md`.
Credit at the freeze: about $11.90.

| Frozen file | SHA-256 |
|---|---|
| `write_once.py` | `a9add6feeab325a90b7c9c9afc79b0d819d11f98ef9405c4fcaf8c4772a62d7f` |
| `run_fast_path_planned_v1.py` | `40c154947af6d6a8c62f25230f70e2cc99e2d1fa5b515fe6f4a4690fc646e30a` |
| `analyze_write_once_v1.py` | `4f52663c636a2d17a76bbc1edf9da6dde1e49ba102e94e5ac1e7e97353946cbf` |
| `config_fast_path.json` | `6d994e62ef672619a88aeb909032ea9681766decf274152e2b64d99d027cda10` |
| `fast_path.py` | `753fef2c26534cabd0f6efbc7a2da0baf64b0ba3e2ac2572e2cd4217e2886caa` |
| `fast_path_planned_bench_v5.py` | `917d653eac9cdd9b07b6b9509af298b4ae00e04e878fdf8551fe341dbbf44c55` |
| `fast_path_planned_bench_v5_prose.json` | `408e3b4b22cae81fda3246b7cce7a6059ea3f500c938d601dc5f1be43d1fd5a4` |
| `fast_path_ceiling_v5.py` | `9e74e0302fff403da8c00ac6d1b35faec3edbd3ad96ea50f797fd687e8ebe620` |
| `FAST_PATH_WRITE_ONCE_V3_PLAN.md` | `40cf04c1428e0635b3cfe1318808c3d05923ae515c19c65fbbdefb494b417e12` |

---

## 2026-11-18 — Write-once V3 run 1 result (prospective)

Label `write_once_v3_primary`: V5 jobs (8 unseen shapes, 30 each), arms R, D, W,
P (write once with 6 edge-case probes), drained. 5,651 provider calls, 2
invalid responses. Cost about $2.34.

| Arm | Correct | Median ms | Calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|
| R | 233/240 | 1925 | 1,200 | 519,379 | 556,581 |
| D | 240/240 | 931 | 1,200 | 229,928 | 74,583 |
| W | 240/240 | 948 | 1,385 | 312,361 | 159,795 |
| P | 238/240 | 961 | 1,866 | 451,967 | 266,605 |

**Primary decision: SUPPORTED.** P/R 0.499 (0.449 to 0.577); P minus R +0.021
(0.000 to +0.054).

- P adopted a program for every shape at its first attempt (job index 2, and
  4 for `shared_bills`). 222 program-served jobs, all correct; its two wrong
  answers came from the race before adoption. Probes: 48 proposed, 46 agreed
  by the racers, **0 failed**: no program was rejected by a probe.
- W (no probes) was also right on all 240 jobs; two of its first programs
  (`train_fares`, `reading_challenge`) failed the two-example trial and the
  second attempts were adopted. W/R 0.493 (0.456 to 0.529), +0.029 (+0.004 to
  +0.063).
- P against W: time 1.01 (0.96 to 1.12), correctness -0.008 (-0.025 to 0.000),
  about 35% more calls. P against D: 1.03 (0.98 to 1.14).

Reading: on fresh unseen jobs written with rounding, tie and threshold rules,
writing the job once was twice as fast as the race, at least as accurate, and
level with the hand-written ceiling. The probes caught nothing here, so this
run shows they are cheap, not that they help; the V4 rounding failure remains
their only motivating case.

| Artifact | SHA-256 |
|---|---|
| `fast_path_write_once_v3_primary.jsonl` | `76081c55e7814211f0c9081f4e766b0fbf7841bad5718eadf2354f7519b8c4db` |
| `fast_path_write_once_v3_primary_analysis.json` | `81fa6f983f79fe6bc3a560f7eda06db971ca8ea27194f551468bab0df33bd9da` |

---

## 2026-11-18 — Write-once V3 run 2: jobs back to back (descriptive)

Label `write_once_v3_immediate`: the same V5 jobs, arms R and P,
`--arrival immediate`. 3,036 provider calls, 2 invalid responses. Cost about
$2.11.

| Arm | Correct | Median ms | Last five ms | Calls |
|---|---:|---:|---:|---:|
| R | 239/240 | 1966 | 1889 | 1,200 |
| P | 237/240 | 1273 | 931 | 1,836 |

- P/R 0.647 (0.536 to 0.743); P minus R -0.008 (-0.017 to 0.000).
- Programs went live at job index 10 to 21 (median 13), against 2 to 4 with
  drained arrival: writing a program, trying it and running its probes takes
  longer than ten jobs arriving back to back. Until then the race answered.
- 129 program-served jobs, all correct (median 914 ms against the race's 2,015
  ms over the same jobs); the 3 wrong P answers came from the race. Probes:
  47 agreed, 0 failed.

Reading: under live traffic write-once still saves about a third of the time
over 30 jobs, and once live it runs at the ceiling's speed. Its start-up cost
is a fixed delay of about a dozen jobs, far shorter than the planning
router's 20 to 35 jobs, or never, in follow-ups 5 to 7.

| Artifact | SHA-256 |
|---|---|
| `fast_path_write_once_v3_immediate.jsonl` | `d0d63ebb366187b8a0f8369a191df4a1e3938f2e28431ab8c906a35005e5c84e` |
| `fast_path_write_once_v3_immediate_analysis.json` | `b6d19846fb7561793213740b89dbfa352b84eccebd62add2c672037e00b0fc3c` |

---

## 2026-11-18 — Write-once becomes the multi-step path (no provider calls)

At the owner's request (steps 1 to 3, with the planner on hard jobs; balance
about $17.39):

- `write_once.py`: programs and templates kept on disk (`store_dir`); readings
  may be made on every item of a list of texts or of a text field of a list of
  objects (`"each": true`, `"field"`), giving a list of labels; optional
  `write_early`: the first program is written and probed when a template is
  first seen, in parallel with the race, and tried on the examples as soon as
  they exist. Default behaviour otherwise unchanged.
- `main.py --task-json PATH` answers a plain-language `fast_path_task_v1`
  document through `WriteOnceRouter` (programs in `fast_path_programs/`).
- `config_fast_path.json`: `program_probes` 6 (probes on by default),
  `write_early` false until tested.
- `planner.py` marked superseded; kept for the record and for jobs a model
  cannot write whole.
- The runner pins arm W to no probes and no early writing, so earlier runs
  remain comparable, and gains arm Q (`--early`: probes plus early writing).

Full suite passed.

---

## 2026-11-18 — Hard jobs V1 stage 1 frozen, before any text exists

Plan: `FAST_PATH_HARD_JOBS_V1_PLAN.md`. The runner's ceiling arm reads every
item of a list when the reading has an `item_field`. Full suite passed.

| Frozen file | SHA-256 |
|---|---|
| `fast_path_planned_bench_v6.py` | `c4250db625cdce4dbd385314163ec0fcfc096666c27cba5bc8c67f61159f196d` |
| `fast_path_ceiling_v6.py` | `20fda45f20174a57dc9e3cbfd15130a6d8a8601054a9fec4f215e59d14a24084` |
| `make_bench_v6_prose.py` | `e7d3d885d45e52b17ad259184948de63df7b1d041f5afcf9f0c9b97f0b4ef498` |
| `write_once.py` | `16dbbae4096222fe95fb1633a1695e3556b31f7f643b72a16aa64111c769c1bd` |
| `run_fast_path_planned_v1.py` | `3e8741cc2701aa89eda9a94594a98fc3316fab0914c8e08dc6d6d0967f1944df` |
| `FAST_PATH_HARD_JOBS_V1_PLAN.md` | `51ea61289d06b139da5c24fa88534e676831ad977d23e81a3292f87a1fb0a68b` |

Amendment before any V6 text was kept: generation stopped at `menu_check`
after three `OPENROUTER_RESPONSE_INVALID` replies. The raw reply showed why:
the writer now reasons before answering and ran out of its 8,192-token limit
with no text. `make_bench_v6_prose.py` now allows 32,000 tokens and 600 s
per call and saves each finished shape to a `.partial` file so a failure
loses nothing. The four shapes received before the stop were never read and
were discarded. The prompt is unchanged. New hash: `bdb51a320dc06bd1b32c1db58bb0281bb5df70db947286a6eceb6f17330da2ba`.

---

## 2026-11-18 — Hard jobs V1: texts hand-checked; runs frozen

V6 texts generated (336) and hand-checked before any model read them: 13
excluded (two-allergen dishes), 4 borderline kept. Runs frozen in
`FAST_PATH_HARD_JOBS_V1_PLAN.md`. Credit at the freeze: about $17.

| Frozen file | SHA-256 |
|---|---|
| `write_once.py` | `16dbbae4096222fe95fb1633a1695e3556b31f7f643b72a16aa64111c769c1bd` |
| `run_fast_path_planned_v1.py` | `3e8741cc2701aa89eda9a94594a98fc3316fab0914c8e08dc6d6d0967f1944df` |
| `analyze_write_once_v1.py` | `8db4c3af8d0cac541af6dcc8806b56da042e2d440e7fbfe9480051be27ed1cfc` |
| `config_fast_path.json` | `2b94990b93115c29f80ca8035518f396d186dba1a8d353b2546d56d55c599577` |
| `fast_path.py` | `753fef2c26534cabd0f6efbc7a2da0baf64b0ba3e2ac2572e2cd4217e2886caa` |
| `planner.py` | `b1a43bc1efee80936362e291cd31369d039c948ead3b1acbd9deb66fc4cf8e2d` |
| `pipeline.py` | `fecc96aee7349fbf2229dad47207c7467a76c884fec281dd596d35185f528e83` |
| `fast_path_planned_bench_v6.py` | `c4250db625cdce4dbd385314163ec0fcfc096666c27cba5bc8c67f61159f196d` |
| `fast_path_planned_bench_v6_prose.json` | `7e0ada753a1f1bbf589739d9fec3a640e81d2ec2eacb6a698f18a8c8a51ca1cb` |
| `fast_path_ceiling_v6.py` | `20fda45f20174a57dc9e3cbfd15130a6d8a8601054a9fec4f215e59d14a24084` |
| `FAST_PATH_HARD_JOBS_V1_PLAN.md` | `1ac6a9fa516e5b9b69dfe8a4c2f7e91dae579a501e4b5fc417185a13933e72ea` |

---

## 2026-11-18 — Hard jobs V1 run A result (prospective)

Label `hard_v1_primary`: V6 jobs (8 shapes, 20 each, about 7.4 readings per
job), arms R, C, D, P, drained. 30,807 provider calls, 208 invalid responses.
**Cost about $12.90, against an estimate of $6** (arm C: 18,178 calls and
8.4 million tokens). Run B is not started; the owner is asked first.

| Arm | Correct | Median ms | 90th pct ms | Calls |
|---|---:|---:|---:|---:|
| R | 143/160 | 2245 | 3202 | 800 |
| C | 108/160 | 2891 | 19741 | 18,178 |
| D | 140/160 | 1806 | 3130 | 5,895 |
| P | 143/160 | 2492 | 3941 | 5,934 |

**Primary decision: NOT SUPPORTED.** P/R 1.110 (1.017 to 1.195): slower than
the race. P minus R 0.000 (-0.038 to +0.038): the correctness bound also fails.

- **The planning router did not win where it was expected to: it did worst.**
  C against P: correctness -0.219 (-0.388 to -0.075), time 1.16 (0.93 to
  5.56), with three times P's calls. Its plans were wrong on most jobs of
  `applicant_screen` (6/20), `expense_lines` (9/20) and `review_digest`
  (16/20), and its unpromoted steps gave 12 to 18 s medians on three shapes.
- **Why write-once lost time here:** each reading of each item is its own
  race, run in parallel, so a job waits for the slowest of about seven races;
  the whole-task race waits for one. With one reading per job (V3 to V5) this
  did not arise. P was 1.38 times the ceiling's time even though both read
  per item: P also waited on the race before adoption and on program checks.
- Write-once adopted programs for 7 of 8 shapes (job index 2 to 4);
  `expense_lines` had both programs rejected on the trial and ran on the race
  throughout. 117 program-served jobs, 106 correct; most wrong answers were in
  `incident_log`, which every arm found hard (R 7/20, D 8/20, P 8/20, C 6/20):
  one misread severity among about seven notes flips the escalation rule.
- Probes ran only where some input is not read (3 shapes); none failed.

Reading: on jobs with many readings per job, writing the job once keeps its
accuracy but loses its speed advantage, because per-item reading races add a
max-of-N wait. Step-by-step planning does not help; it is the least accurate
and by far the most expensive arm. Batching a job's readings into one call is
the obvious next fix.

| Artifact | SHA-256 |
|---|---|
| `fast_path_hard_v1_primary.jsonl` | `8b772f509b9f5866205a91a603c4bb844b6e041b1a9ba03cd514fdcccd7634fc` |
| `fast_path_hard_v1_primary_analysis.json` | `8399c67bbcff543a6e23842cee47474e100fc8055cb7d90076834b4d2cb3f5ac` |

---

## 2026-11-20 — Reading fixes for many-reading jobs (no provider calls)

At the owner's request, the three open items from the hard-jobs result, all
opt-in settings of `WriteOnceRouter` (defaults unchanged), tested with fake
models only:

- `batch_readings`: a reading over a list is one race whose answer is a list
  of labels; an answer of the wrong length or with an unknown label is not
  used and the race waits for the next. Aim: remove the wait for the slowest
  of about seven per-item races.
- `uncertainty_gate`: readings and whole-task answers wait for a second valid
  answer and are flagged `uncertain` when the two differ (or only one comes).
  The answer is still returned; the flag goes with it.
- `adaptive_width` (`{"width": 2, "after": 5}`): after five races of a reading
  in which every valid answer agreed, race only the two models that won it
  most often; any disagreement restores the full roster. Idea from the SAGE
  preprint as summarised in the RAG survey the owner shared; not verified
  against the paper.

The runner gains arm B (`--fixes`: write once with probes plus all three) and
records each answer's `uncertain` flag; the analysis reports B against R and
P and accuracy of flagged against unflagged answers. Pull requests opened for
both repositories (Adaptive_Router #19, evolab #1). Full suite passed (618
tests).

---

## 2026-11-20 — Reading fixes V1 frozen

Plan: `FAST_PATH_READING_FIXES_V1_PLAN.md`. Credit at the freeze: about $14.20.

| Frozen file | SHA-256 |
|---|---|
| `write_once.py` | `a131c3afe9eb3407cc67f14915ab0d1920f11fee86542ae66072d64c0bab4ba1` |
| `run_fast_path_planned_v1.py` | `cb5052f891bba36b1e1ae7b2e75593102d0b16807204bfe4ad455c2278a274a1` |
| `analyze_write_once_v1.py` | `5db4340d3b6a9b29ace42df11fed5e25c78b036c5e984314d2f0db6358f82f2a` |
| `config_fast_path.json` | `2b94990b93115c29f80ca8035518f396d186dba1a8d353b2546d56d55c599577` |
| `fast_path.py` | `753fef2c26534cabd0f6efbc7a2da0baf64b0ba3e2ac2572e2cd4217e2886caa` |
| `fast_path_planned_bench_v6.py` | `c4250db625cdce4dbd385314163ec0fcfc096666c27cba5bc8c67f61159f196d` |
| `fast_path_planned_bench_v6_prose.json` | `7e0ada753a1f1bbf589739d9fec3a640e81d2ec2eacb6a698f18a8c8a51ca1cb` |
| `FAST_PATH_READING_FIXES_V1_PLAN.md` | `2b19740dfc253faf71b3e7480b2e8736d1a95f788d1146d37fec5382d1ed153d` |

---

## 2026-11-20 — Reading fixes V1 result (descriptive)

Label `reading_fixes_v1`: V6 hard jobs (8 shapes, 20 each), arms R, P, B,
drained. 7,502 provider calls, 10 invalid responses. Cost about $2.97
(estimate $6).

| Arm | Correct | Median ms | 90th pct ms | Calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|---:|
| R | 144/160 | 2261 | 3030 | 800 | 413,521 | 448,822 |
| P | 147/160 | 2595 | 4223 | 5,862 | 1,335,069 | 623,493 |
| B | 138/160 | 2289 | 3564 | 840 | 359,045 | 311,282 |

- **Speed and calls:** B used 840 calls against P's 5,862 (a seventh) and
  cut P's time to 0.88 (0.73 to 1.10), but was no faster than the race: B/R
  1.01 (0.79 to 1.27). The speed advantage is not restored.
- **Accuracy fell:** B minus R -0.038 (-0.088 to -0.006); B minus P -0.056
  (-0.156 to +0.019). Most of the loss is `incident_log` (B 4/20, P 11/20,
  R 8/20) and `expense_lines` (B 17, P 20): reading all items in one call,
  or on two models, reads severities less well than racing each item. This run
  cannot separate batching from the narrower race.
- **The uncertainty flag works:** 17 of B's answers were flagged and only 3
  of those were right (18%); unflagged answers were right 135 of 143 times
  (94%). The flag caught 14 of B's 22 wrong answers (64%).
- Programs adopted: B 8 of 8 shapes (one invalid first program); P 7 of 8
  (`menu_check` rejected twice).

Reading: batching and narrow races make write-once cheap on many-reading jobs
but cost accuracy and do not beat the race on time. The uncertainty gate is
the useful part: it separates answers that are almost always right from ones
that are mostly wrong.

| Artifact | SHA-256 |
|---|---|
| `fast_path_reading_fixes_v1.jsonl` | `9fd275219631ea37ee68b7b201614594ca8d53c955d37822218df9c67cbe2e4c` |
| `fast_path_reading_fixes_v1_analysis.json` | `4025ba86ccc29d08dade79070043e185b7a8a6ab7ac552b8c3e7ebdf4432782a` |

---

## 2026-11-21 — Real task V1 frozen: the owner's bank transactions

First run on real work. Plan: `REAL_BANK_V1_PLAN.md`. The export itself is not
committed; its SHA-256 is recorded so the run can be tied to it:
`07f1d2eb3aef7abcc02ad7010b629017774d85aa4cab5884770f2eb1b08b8e46`. `.gitignore` gains `real_tasks/private/`.

| Frozen file | SHA-256 |
|---|---|
| `real_bank_categorise_v1.py` | `984df867d1755491cb1649d30ba5fc837ec181d0378aea1a03df655792e80e39` |
| `REAL_BANK_V1_PLAN.md` | `8fa76cec0e441d195b3b9e05d1e7a944008713932c25f41b13348b9ed4baea00` |
| `fast_path.py` | `753fef2c26534cabd0f6efbc7a2da0baf64b0ba3e2ac2572e2cd4217e2886caa` |
| `config_fast_path.json` | `2b94990b93115c29f80ca8035518f396d186dba1a8d353b2546d56d55c599577` |

---

## 2026-11-21 — Real task V1 result: bank transaction categories

475 provider calls, all titles answered. Cost about $0.25. Test: 1,934
transactions from 2026-03-01, scored against Monzo's own category.

| Arm | Correct | Accuracy | Transactions needing a model | Mean time per transaction |
|---|---:|---:|---:|---:|
| E. Code only (training table, unseen to `general`) | 1,636 | 84.6% | 0 | 0 ms |
| M. Models only (race per merchant) | 1,230 | 63.6% | 1,934 | 1,070 ms |
| H. Hybrid (table, unseen merchants to the race) | 1,836 | 94.9% | 303 | 200 ms |
| H2. Hybrid that keeps learning | 1,820 | 94.1% | 59 | 39 ms |

- **Code first, models for the new, wins**: the hybrids beat code alone by
  about 10 points and models alone by about 31, and need a model for 3% (H2)
  to 16% (H) of transactions.
- Models alone are poor here because the categories follow Monzo's and the
  owner's filing conventions, which a merchant's name does not reveal: the
  largest disagreements were entertainment read as transport (241
  transactions), eating out as general (197) and entertainment as eating out
  (123). On merchants unseen in training the race was right for 208 of 303
  transactions (69%), still far better than the code-only fallback.
- The racers all agreed on 68 of the 95 merchants. Median race 1.2 s.
- Prediction held except the order of the hybrids: H2 was 16 transactions
  behind H, because a merchant's first Monzo category, which H2 then reuses,
  was sometimes not its usual one.

Only aggregate figures are committed (`real_bank_v1_summary.json`, no
merchant names); per-merchant detail is in the git-ignored
`real_tasks/private/`.

| Artifact | SHA-256 |
|---|---|
| `real_bank_v1_summary.json` | `91eb2e26f00fc2ab3e06c46cdfd0c2769c35f4f8d863fd2219a8fe0fb94c6e8c` |

---

## 2026-11-25 — Decision rules, answer cache, flag fallback (no provider calls)

- `fast_path.decide()`: the rules "first" and "majority". With majority, a tie or any
  dissent is flagged.
- `write_once` gains two settings:
  - `decision: "majority"`, for readings and whole-task races;
  - `flag_fallback`: a flagged program answer is served from a decided whole-task
    race.
- `answer_cache`: serves an exact input's agreed answer without a race. It is off by
  default.
- The runner gains arms F and M (`--flagged`), and the analysis gains F and M
  comparisons and a fallback summary.
- Tests: 637 pass.

Reason: the change-signals labeller (the owner's real daily task, restarted 2026-11-25)
showed one fast outlier model creating a "sell" label that four of five models rejected.

## 2026-11-25 — Flag fallback V1 frozen (Phase B)

Plan: `FAST_PATH_FLAG_FALLBACK_V1_PLAN.md`. Credit at the freeze: $10.85.

| Frozen file | SHA-256 |
|---|---|
| `write_once.py` | `aea8eb0fb4476b9094a1387b66f602044cafb293b8e771b8d042132f6c85c116` |
| `run_fast_path_planned_v1.py` | `621501e9978fc4340652a476c5011595c2348b63f1c48f714009f00b04023158` |
| `analyze_write_once_v1.py` | `7645a4d4be8897633e9404fb2f5dbb1ff7837a78d3b8d903c835fc4e0084932c` |
| `config_fast_path.json` | `b1a26ee68d335790895d1913ab9fc8ed2ef009465e67e9768f8588b5d44cd54b` |
| `fast_path.py` | `d02ccdff7d5440e9bb9ac385df5d5f75c9f3872032e5884786732b1ea6d560a1` |
| `fast_path_planned_bench_v6.py` | `c4250db625cdce4dbd385314163ec0fcfc096666c27cba5bc8c67f61159f196d` |
| `fast_path_planned_bench_v6_prose.json` | `7e0ada753a1f1bbf589739d9fec3a640e81d2ec2eacb6a698f18a8c8a51ca1cb` |
| `FAST_PATH_FLAG_FALLBACK_V1_PLAN.md` | `4d71ed42cb8a694a4485916ebacbc800b5546ceddfb47e48b2eb7186e9c1b7a0` |

## 2026-11-25 — Flag fallback V1 result (descriptive)

Label `flag_fallback_v1`: V6 hard jobs (8 shapes, 20 each), arms R, F and M, drained.
14,331 provider calls, 8 invalid responses. Cost about $4.30 (estimate $6.20).
Credit left: $6.55.

| Arm | Correct | Median ms | 90th pct ms | Calls |
|---|---:|---:|---:|---:|
| R | 140/160 | 2279 | 2944 | 800 |
| F | 147/160 | 3237 | 5605 | 6,663 |
| M | 148/160 | 8447 | 16975 | 6,868 |

- **F against R, served accuracy:** +4.4 points (+1.2 to +8.7). The frozen criterion
  (lower bound above −2 points) is **met**.
- **F against R, time:** 1.42 (1.29 to 1.61). F is slower.
- **F's fallback:** 9 of 140 program answers were flagged (6.4%). The fallback got 5 of
  9 right; the program would have got the same 5. Median 30 s. Unflagged program
  answers were right 126 of 131 times (96%).
- **M against R:** +5.0 points (+0.6 to +9.4), at 3.7 times R's time. M's flag:
  unflagged 119/122 right, flagged 29/38.

Reading: the flag filters well and the program is accurate. A majority re-decision of
flagged answers adds time but not accuracy on these jobs. Majority suits one-off
judgement steps, not every reading.

| Artifact | SHA-256 |
|---|---|
| `fast_path_flag_fallback_v1.jsonl` | `a62bfbf8dc8f544e0e60e72fe87c0999a663bb99f11c7bf9b0850edebd316c4f` |
| `fast_path_flag_fallback_v1_analysis.json` | `9817a71aef82486a17a0c25c927fef10d88fb817bea77a5488d8f08720108f57` |

## 2026-11-25 — Needs review and race alongside (no provider calls)

- `write_once` gains two options:
  - `flag_fallback: "review"`: a flagged answer is returned marked `needs_review`,
    with no retry.
  - `race_alongside`: the whole-task race and the program start together, and the
    first trusted answer is served. Trusted means an unflagged program answer, or two
    racing models agreeing.
- The runner gains arm S (`--alongside`).
- Tests: 655 pass.

## 2026-11-25 — Race alongside V1 frozen

Plan: `FAST_PATH_ALONGSIDE_V1_PLAN.md`. Credit at the freeze: $26.53.

| Frozen file | SHA-256 |
|---|---|
| `write_once.py` | `ab65b4dc3bdf8bddbdc2696cf4f795b59159b99c4d1c0d105dcf94441da3d5c1` |
| `run_fast_path_planned_v1.py` | `0b59e4e1a5b5d39d643c672dc9a8af385c578aa0582579f300bc79126d2dffc2` |
| `analyze_write_once_v1.py` | `fd085da9c3ed9f1edd5fe19cf4b40f22e3094080eddb83f0c69cfe553fbbd6ac` |
| `config_fast_path.json` | `b1a26ee68d335790895d1913ab9fc8ed2ef009465e67e9768f8588b5d44cd54b` |
| `fast_path.py` | `d02ccdff7d5440e9bb9ac385df5d5f75c9f3872032e5884786732b1ea6d560a1` |
| `fast_path_planned_bench_v6.py` | `c4250db625cdce4dbd385314163ec0fcfc096666c27cba5bc8c67f61159f196d` |
| `fast_path_planned_bench_v6_prose.json` | `7e0ada753a1f1bbf589739d9fec3a640e81d2ec2eacb6a698f18a8c8a51ca1cb` |
| `FAST_PATH_ALONGSIDE_V1_PLAN.md` | `ae25e42658ff6f4439327c174f2830cd44c26c1c41ba2855acfd2f6616264384` |
