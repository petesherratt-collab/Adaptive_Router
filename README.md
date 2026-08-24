# Adaptive Router v0.1

A small Linux terminal experiment testing whether externally observable, deterministic runtime evidence can support local-to-remote model escalation. It routes a narrow set of mechanical tasks to Ollama, applies explicit health/runtime/validation gates, and sends other or rejected tasks to OpenRouter. Each request produces metadata-only JSONL telemetry.

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

Prompts and answers are not logged. `runs.jsonl` contains task class, input size, system/runtime measurements, validator state, route/reason, deterministic shadow selection, and the Ollama-reported residency of the configured local model. When Ollama supplies it, the loaded model size is recorded in bytes. Shadow execution defaults off and never affects the user-visible result. Remote fallback always receives the original prompt, not failed local output.

Rolling seven-day medians exclude hard-health rejections and local errors. They and Wilson 95% intervals are reported only as evidence; v0.1 never tunes or routes from aggregate statistics. Fewer than the configured 30 suitable observations produces `INSUFFICIENT_BASELINE_DATA` or `INSUFFICIENT_EVIDENCE`.

## Initial policy

Local eligible: `rewrite`, `summarise_short`, `extract_structured`, `format`.

Remote default: `code`, `research`, `unknown`.

Stable reasons: `LOCAL_ACCEPTED`, `REMOTE_DEFAULT_TASK`, `LOW_RAM`, `ACTIVE_SWAP_PRESSURE`, `LOCAL_TIMEOUT`, `LOCAL_ERROR`, `TTFT_EXCEEDED`, `GENERATION_TOO_SLOW`, `VALIDATOR_FAILED`, `REMOTE_ERROR`, and `SHADOW_SAMPLE`.

Before a local-eligible request, the router checks Ollama's local `/api/ps` endpoint. The minimum-available-RAM gate applies only when the configured model is not resident. Swap occupancy is logged but does not reject local inference by itself; swap-out activity observed during the fixed 0.1-second preflight sampling window does. If residency cannot be confirmed, the router conservatively treats the model as not resident.

After v0.1, hold thresholds steady and collect ordinary usage data. The next step is evaluating whether TTFT, throughput, health, and the observational probe explain outcomes—not feature expansion.
