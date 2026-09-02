# Adaptive Router v0.2

A small Linux terminal router for deterministic execution, contract-gated Ollama inference, and OpenRouter escalation. It preserves the research instruments that established its current boundaries, but v0.2 begins turning those findings into a usable runtime. Each request produces metadata-only JSONL telemetry.

## Prospective deterministic-contract case study

A prospectively frozen experiment across Gemma 3 270M, 1B, and 4B found that
deterministic output contracts caught 144 of 175 false accepts admitted by the
legacy gate: 82.3%, with a task-cluster bootstrap 95% interval of 63.9%–96.7%.
No baseline-correct survivor was rejected. A separate label cohort demonstrates
the semantic boundary, while deterministic execution identifies work that
should bypass the model entirely.

Read the illustrated
[prospective contract validation V2 case study](PROSPECTIVE_CONTRACT_VALIDATION_V2_CASE_STUDY.md)
for the methodology, results, limitations, experiment lineage, and
reproducibility references.

## Out-of-sample case study

The first frozen out-of-sample validation rejected the current fine-grained
routing policy. Fine capability routing used 100 rather than 200 remote calls
and achieved 85.5% strict accuracy, outperforming coarse routing at 78.5%, but
fell 14.5 percentage points below always remote. The preregistered tolerance
allowed a maximum five-point loss.

Read the illustrated [`CASE_STUDY.md`](CASE_STUDY.md) for the research question,
method, negative result, limitations, and proposed accuracy–remote-capacity
experiments. The complete frozen result and procedural deviations remain in
[`OOS_VALIDATION_V1_AUDIT.md`](OOS_VALIDATION_V1_AUDIT.md).

## What this project does

It measures RAM, swap, load, time to first output, generation throughput, adapter failures, and task-specific deterministic validation. Classification is a small ruleset, not a difficulty estimate. Every gate has a stable reason code and no opaque score. Direct observations, deterministic derivations, and interpretations are kept separate.

## What it does not claim

It does not detect intelligence, directly measure semantic difficulty, guarantee answer correctness, infer model confidence, use an LLM judge, prove latency predicts correctness, or assume the SHA probe is useful. A normal, fast response can still be semantically wrong when no validator applies; that unresolved failure mode is intentionally visible.

Deterministic validators are task-specific. For many open-ended question-answering tasks no defensible generic deterministic correctness validator is currently implemented.

Probe latency is observational in v0.1. It is being tested as a possible explanatory signal and does not influence routing decisions.

The v0.1 workload probe is observational only. Its predictive value must be established empirically before it can influence routing.

Routing statistics must display both sample size and uncertainty. Categories with fewer than 30 observations are not treated as established evidence.

## Setup

Requires Python 3.11+. Ollama and its configured model are optional for tests but required for live local routing. This project does not install or download a model.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENROUTER_API_KEY` only in `.env`, and replace `CHANGE_ME` in `config.json` with the chosen remote model. Do not commit `.env`. Thresholds in `config.json` are experimental settings, not scientific constants.

## Usage

```bash
python main.py
python main.py --prompt "Rewrite this paragraph..."
python main.py --diagnostics
python main.py --stats
python -m unittest discover -s tests -v
```

## Explicit runtime requests

`--request-json` accepts a strict `runtime_request_v1` document. The caller
declares a task class, the prompt, and one contract. Supported behavior is:

- `deterministic_executor`: execute one allowlisted operation in Python; call
  neither Ollama nor OpenRouter.
- `structured_json` and `json_format`: try Ollama and accept only an exact
  key set with declared JSON value types.
- `bullet_format` and `label_format`: try Ollama and accept only the
  declared line shape.
- `classification_labels`: route directly to OpenRouter. Permitted-label
  membership cannot establish semantic correctness.

A malformed request is rejected before either provider is called. A valid
contract describes observable conformance, not truth: correctly typed JSON can
still contain wrong values. If a local output fails its contract, OpenRouter
receives the original prompt; the failed local output is never used as repair
context.

See the checked-in examples under `examples/`.

Prompts, answers, and contract source literals are not logged. `runs.jsonl` contains request mode, contract type, task class, input size, system/runtime measurements, validator state, route/reason, deterministic shadow selection, and the Ollama-reported residency of the configured local model. When Ollama supplies it, the loaded model size is recorded in bytes. Shadow execution defaults off and never affects the user-visible result. Remote fallback always receives the original prompt, not failed local output.

Rolling seven-day medians exclude hard-health rejections and local errors. They and Wilson 95% intervals are reported only as evidence; v0.1 never tunes or routes from aggregate statistics. Fewer than the configured 30 suitable observations produces `INSUFFICIENT_BASELINE_DATA` or `INSUFFICIENT_EVIDENCE`.

## Initial policy

Local eligible: `rewrite`, `summarise_short`, `extract_structured`, `format`.

Remote default: `code`, `research`, `unknown`.

Stable reasons: `LOCAL_ACCEPTED`, `REMOTE_DEFAULT_TASK`, `LOW_RAM`, `ACTIVE_SWAP_PRESSURE`, `LOCAL_TIMEOUT`, `LOCAL_ERROR`, `TTFT_EXCEEDED`, `GENERATION_TOO_SLOW`, `VALIDATOR_FAILED`, `REMOTE_ERROR`, and `SHADOW_SAMPLE`.

Before a local-eligible request, the router checks Ollama's local `/api/ps` endpoint. The minimum-available-RAM gate applies only when the configured model is not resident. Swap occupancy is logged but does not reject local inference by itself; swap-out activity observed during the fixed 0.1-second preflight sampling window does. If residency cannot be confirmed, the router conservatively treats the model as not resident.

## Current research direction

Runtime health signals remain useful for operational rejection, but the
out-of-sample failures show that they cannot predict many clean semantic and
schema errors. The next experiment will estimate accuracy under explicit
remote-call budgets, compare stronger local models, and separate
oracle-supplied capability labels from automatic prompt classification.
