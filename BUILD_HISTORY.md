# Adaptive Router build history

**Project path:** `/home/peter/adaptive-router`
**Updated:** 2026-08-31

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
