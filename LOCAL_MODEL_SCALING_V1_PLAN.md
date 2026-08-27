# Local Model Scaling Comparison v1 — Pre-run Plan

Date: 2026-08-27

## Purpose

Measure how three specific Gemma 3 Ollama packages perform on the same frozen
deterministic task suite and fixed CPU-only hardware.

This is a frozen-suite regression comparison. It is not a new out-of-sample
validation and does not independently test the external validity of the task
suite.

## Research question

On the existing HP ProDesk, does moving from the Gemma 3 270M package to the 1B
or 4B package produce a useful local accuracy–latency frontier?

## Fixed hardware

- Machine: HP ProDesk 400 G2.5 SFF
- CPU: Intel Core i3-4160T at 3.10 GHz
- Physical cores: 2
- Hardware threads: 4
- RAM: 15 GiB reported
- Swap: 2 GiB
- GPU acceleration: none
- Ollama version: 0.32.15

No hardware change is permitted between model runs.

## Frozen model identities

### Gemma 3 270M

- Ollama name: `gemma3:270m`
- Parameters: 268.10M
- Quantization: Q8_0
- Format: GGUF
- Package size: 291,554,930 bytes
- Digest:
  `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be`

### Gemma 3 1B

- Ollama name: `gemma3:1b`
- Parameters: 999.89M
- Quantization: Q4_K_M
- Format: GGUF
- Package size: 815,319,791 bytes
- Digest:
  `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc`

### Gemma 3 4B

- Ollama name: `gemma3:4b`
- Parameters: 4.3B
- Quantization: Q4_K_M
- Format: GGUF
- Package size: 3,338,801,804 bytes
- Digest:
  `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`

These are comparisons between exact distributed packages. Quantization is not
held constant: 270M uses Q8_0 while 1B and 4B use Q4_K_M. Results must not be
attributed to parameter count alone.

## Frozen benchmark

Reuse without modification:

- suite: `oos_validation_v1`
- file: `benchmark_oos_v1.json`
- tasks: 40
- repetitions: 5
- observations per model: 200
- benchmark SHA-256:
  `6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295`

Prompts, expected outputs, normalizations, validators, task classes and
capability-family labels must remain unchanged.

## Evidence

The existing 270M evidence is reused without modification:

- `benchmark_runs_oos_local_v1.jsonl`
- 200 observations
- SHA-256:
  `425fa9328781ff2e53f69ce0a054531e106be3a6ed1380c148e35ec3d47c8ca0`

New model-specific evidence files will be:

- `benchmark_runs_scaling_gemma3_1b_v1.jsonl`
- `benchmark_summary_scaling_gemma3_1b_v1.json`
- `benchmark_runs_scaling_gemma3_4b_v1.jsonl`
- `benchmark_summary_scaling_gemma3_4b_v1.json`

Existing evidence or summary files must never be overwritten. Safe resume may
append only missing `(task_id, repetition)` keys after verifying benchmark,
model, digest and code-revision identities.

## Execution

Each new model receives:

- the same 40 tasks;
- five repetitions per task;
- 200 scheduled observations;
- the existing Ollama streaming generation path;
- no automatic retries;
- no prompt repair;
- no post-run normalization changes;
- deterministic validators only;
- no LLM judge.

Run the complete 1B evidence collection before the complete 4B collection.
Model order is therefore fixed as 1B, then 4B.

The runner must verify the installed model digest before making the first model
request. Every observation must record requested model, exact digest,
parameter size, quantization, package size, benchmark hash, code revision,
pre-request residency, timing, raw output and validator result.

## Residency and timing

The first request after loading a model may include cold-load time. Later
requests are expected to be resident but this is verified per observation.

Report separately:

- all-observation median TTFT and total time;
- resident-only median TTFT and total time;
- non-resident observation count and timing;
- median tokens per second;
- model-reported resident size;
- empty-output and error counts.

Swap occupancy is not treated as active swap pressure. No energy claim may be
made from latency, RAM, model size or remote-call avoidance.

## Strict outcomes

For each model report:

- overall strict pass count and rate;
- pass count and rate by capability family;
- pass count and rate by task;
- successful-response count;
- empty-output count;
- error count;
- exact paired difference against the frozen 270M observations.

The primary descriptive comparison is overall strict accuracy.

Secondary comparisons are:

- structured extraction;
- sentiment;
- JSON formatting;
- priority;
- Markdown bullets;
- key/value labels;
- transformation;
- resident-only latency and throughput.

No minimum success threshold is declared. This is a comparative mapping
experiment, not a deployment acceptance test.

## Qualification disclosure

Before preregistration, both 1B and 4B received a small number of manual
qualification prompts. These covered:

- one explicit positive-sentiment item;
- numeric JSON value `42`;
- exact key `temperature_c` with numeric value `18`;
- numeric port `8443`.

The 1B model failed two numeric-type qualifications. The 4B model passed all
four qualifications. The 4B model showed approximately 23.56 seconds cold
latency and 0.88 seconds warm latency for the sentiment prompt.

These observations motivated inclusion of the models and mean this experiment
must not be described as a pristine out-of-sample model comparison. No prompts,
validators or policies may be changed in response to qualification results.

## Interpretation boundaries

The experiment may establish performance of these exact packages on this exact
suite and hardware.

It does not establish:

- production-distribution performance;
- automatic routing of arbitrary prompts;
- performance of other quantizations or model families;
- parameter-count causality;
- energy savings;
- performance on other machines;
- future remote-inference prices or capacity;
- that a model should be deployed without task-specific validation.

## Stop conditions

Stop before execution if:

- the benchmark hash differs;
- a model digest differs;
- model order changes;
- tests fail;
- the scaling runner or analysis is not committed;
- an intended evidence or summary file already exists;
- output paths could collide with frozen OOS evidence;
- the working tree contains tracked changes.

During execution, retain errors and empty outputs and do not retry them.
