# Adaptive Router v0.3

A small Linux terminal router for deterministic execution and remote-authoritative generative inference through OpenRouter. Ollama is retained as an opt-in, non-authoritative shadow measurement path. The runtime preserves the research instruments that established this safety boundary, and each request produces metadata-only JSONL telemetry.

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

Probe latency remains observational in v0.3. It does not influence routing decisions, and its predictive value has not been established.

Routing statistics must display both sample size and uncertainty. Categories with fewer than 30 observations are not treated as established evidence.

## Setup

Requires Python 3.11+. Ollama and its configured model are optional for tests but required for live local routing. This project does not install or download a model.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENROUTER_API_KEY` only in `.env`; do not commit `.env`. The checked-in remote default is `openai/gpt-5.6-luna`, the model used by the measured paired replay. Model names, retry limits, and routing thresholds in `config.json` are explicit operating settings, not scientific constants.

## Usage

```bash
python main.py
python main.py --prompt "Rewrite this paragraph..."
python main.py --request-json examples/runtime_request_deterministic.json
python main.py --request-json examples/runtime_request_structured_json.json
python main.py --request-json examples/runtime_request_classification.json
python main.py --diagnostics
python main.py --stats
python -m unittest discover -s tests -v
```

## Explicit runtime requests

`--request-json` accepts a strict `runtime_request_v1` document. The caller
declares a task class, the prompt, and one contract. Supported behavior is:

- `deterministic_executor`: execute one allowlisted operation in Python; call
  neither Ollama nor OpenRouter.
- `structured_json`, `json_format`, `bullet_format`, and
  `label_format`: route to OpenRouter and enforce the declared output shape
  on the final response.
- `classification_labels`: route to OpenRouter and enforce permitted-label
  membership, which cannot establish semantic correctness.

A malformed request is rejected before either provider is called. A valid
contract describes observable conformance, not truth: correctly typed JSON can
still contain wrong values. OpenRouter receives the original caller prompt; local shadow output is never
used as repair context or returned to the caller. A successful remote transport
response is checked against the declared contract; a nonconforming final
response is withheld and recorded as
`REMOTE_CONTRACT_FAILED`. OpenRouter retries are bounded and apply only to
timeouts, connection failures, HTTP 408/429, and HTTP 5xx. Authentication and
other client errors, plus malformed success responses, are not retried.

See the checked-in examples under `examples/`.

Prompts, answers, and contract source literals are not logged. `runs.jsonl` contains request mode, contract type, task class, input size, system/runtime measurements, local and remote validator states, route/reason, total route latency, deterministic shadow selection, and the Ollama-reported residency of the configured local model. When Ollama supplies it, the loaded model size is recorded in bytes. Shadow execution defaults off. When explicitly enabled, an eligible sampled
request is measured locally after the authoritative remote call; only
metadata and conformance status are logged. Shadow text is neither logged nor
returned, and a shadow failure cannot alter or withhold the remote result.

Rolling seven-day medians exclude hard-health rejections and local errors. They and Wilson 95% intervals are reported only as evidence; v0.3 never tunes or routes from aggregate statistics. Fewer than the configured 30 suitable observations produces `INSUFFICIENT_BASELINE_DATA` or `INSUFFICIENT_EVIDENCE`.

## Current safe policy

Deterministic executor requests bypass both models. Every generative request,
including legacy prompts and all generative contract types, is
remote-authoritative by default. `classification_labels` remains explicitly
remote-only because label membership is not semantic validation.

The checked-in `routing.allow_user_visible_local` setting is `false`. The old
local-first implementation remains behind that explicit operator override for
controlled comparison and rollback, but it is not the shipped policy.
`SAFE_REMOTE_POLICY` records requests kept remote by this boundary.

Optional local shadow execution requires `shadow.enabled` and
`shadow.execute`, plus deterministic sampling. It runs synchronously after the
remote result is fixed, so enabling it adds measurement latency. It never
changes the user-visible answer.

Before any local execution, the router checks Ollama's local `/api/ps`
endpoint. The minimum-available-RAM gate applies only when the configured model
is not resident. Swap occupancy is logged but does not reject local inference
by itself; swap-out activity observed during the fixed 0.1-second preflight
sampling window does. If residency cannot be confirmed, the router
conservatively treats the model as not resident.

## Current product direction

Runtime health signals and output contracts remain operational or conformance
checks, not correctness estimates. The prospective v0.2 runtime evaluation
produced 117/120 correct outputs overall and 87/90 on generative tasks. It
avoided 21 remote calls but accepted three repeated bullet-content errors;
the paired remote arm was correct on all 90 generative observations.

v0.3 therefore converts that measured result into a product boundary:
deterministic work executes in code, generative work is remote-authoritative,
and local candidates must be measured in shadow before any narrower capability
can earn user-visible authority.
