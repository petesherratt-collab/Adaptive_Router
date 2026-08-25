# OpenRouter Luna Paired Benchmark v1 — Result and Audit

Date: 2026-08-25

## Frozen execution identity

- Requested model: `openai/gpt-5.6-luna`
- API gateway: OpenRouter
- Code revision:
  `a844984b1141c67ac499f5d48dac0872248994d3`
- Benchmark SHA-256:
  `57f5fe930c4309efd09cf2cc6d5b21f97b4d67e0c74f83ae148035f6b23ff5a7`
- Tasks: 30
- Repetitions: 5
- Scheduled observations: 150
- Temperature: 0
- Maximum completion tokens: 256
- No automatic retries
- Earlier smoke request excluded

All 150 observations recorded the same code revision, benchmark hash,
requested-model identity, and returned-model identity.

## Preserved evidence

`benchmark_runs_openrouter_luna_v1.jsonl`

- Observations: 150
- SHA-256:
  `341d203f34f3789e489329030895970e719483334e42d2ac144080516e3c0405`

`benchmark_summary_openrouter_luna_v1.json`

- SHA-256:
  `2a29d0c4883c1393225309fb27f5c25038df1d0ccd87a4df0fecf6211a76101f`

The raw JSONL was not altered during the audit.

## Frozen strict-oracle result

- Overall: 128/150 = 85.3%
- Structured extraction: 38/45 = 84.4%
- Classification: 25/30 = 83.3%
- Formatting: 35/45 = 77.8%
- Transformation: 30/30 = 100%
- Successful API responses: 148/150 = 98.7%
- Empty outputs: 2

The frozen result remains unchanged.

## Usage and cost

- Prompt tokens: 5,704
- Completion tokens: 3,576
- Reasoning tokens: 1,470
- Total tokens: 9,280
- Reported cached tokens: 0
- Reported cache-write tokens: 0
- Total reported cost: USD 0.005432
- Median total request time: 1,847.455 ms

TTFT and tokens-per-second were not measured for the non-streaming remote
requests.

## Routing metadata

Routing metadata was returned for all 148 successful responses:

- strategy: `direct` in 148/148
- region: `LHR` in 148/148
- selected provider: OpenAI in 148/148
- attempt: 1 in 148/148
- BYOK: false in 148/148
- returned model: `openai/gpt-5.6-luna` in 148/148

No routing metadata was returned for the two client-level failures.

The client did not enable OpenRouter full-response caching. OpenRouter did not
return a response-cache status header, and reported prompt cached-token and
cache-write-token totals were both zero.

## Failure audit

### Transport failures: 2

`extract_person_2` repetitions 3 and 5 produced no model response:

- one `ConnectionError`
- one `ReadTimeout`

Both observations were retained as strict-oracle failures. Neither was retried.
The other three `extract_person_2` repetitions passed the strict oracle.

These are availability failures, not demonstrated model-capability failures.

### `extract_event_2`: 5 specification/case defects

All five responses extracted the correct event, date, and city:

```json
{"event":"Product launch briefing","date":"2026-09-14","city":"Edinburgh"}
