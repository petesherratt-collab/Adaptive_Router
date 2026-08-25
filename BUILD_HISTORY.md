# Adaptive Router build history

**Project path:** `/home/peters/adaptive-router`
**Updated:** 2026-08-23

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

**Anchoring caveat.** The companion Personal Watchdog log anchors verified
claims to Git commit hashes. This project is not under version control (see
2026-08-23, Gotcha 1), so verification here anchors only to command output at a
stated time. That establishes that a check passed; it does not establish which
revision of the code it passed against. Treat every "directly verified" claim
below as scoped to the working tree as it stood at the timestamp of its entry.

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
