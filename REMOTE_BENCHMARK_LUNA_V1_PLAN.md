# OpenRouter Luna Paired Benchmark v1 — Pre-run Plan

Date: 2026-08-25

## Purpose

Measure a fixed remote baseline against the same frozen 30-task benchmark used
for Gemma 3 270M Simulation Zero v2.

## Fixed design

- API gateway: OpenRouter
- Requested model: `openai/gpt-5.6-luna`
- Tasks: 30 frozen deterministic tasks
- Repetitions: 5
- Maximum scheduled requests: 150
- Temperature: 0
- Maximum completion tokens: 256
- Request timeout: 90 seconds
- Cumulative reported-cost stop: USD 0.10
- No LLM judge
- No semantic repair
- Same deterministic normalization and oracle as the local run
- Fixed task order from `benchmark.json`
- Full-response caching is not enabled
- Provider prompt-cache usage is recorded when reported
- OpenRouter routing metadata is requested and preserved

## Execution semantics

Each `(task_id, repetition)` receives at most one scheduled API request.

Successful responses, empty responses, HTTP failures, timeouts, filtering, and
other errors are each preserved as observations. Failed observations are not
automatically retried.

The JSONL file is flushed and synchronized after every observation. A resumed
run validates existing keys and requested-model identity, then skips completed
observations without duplication.

The runner stops before scheduling another request once accumulated reported
cost has reached USD 0.10. Request count and maximum completion length provide
additional containment. The earlier single smoke request is excluded.

## Recorded fields

Each observation preserves:

- task ID, class, and repetition
- requested and returned model
- request parameters
- benchmark SHA-256
- Git code revision
- raw and normalized output
- strict oracle result
- response and HTTP identifiers
- normalized and native finish reasons
- prompt, completion, reasoning, cached, cache-write, and total tokens
- reported OpenRouter cost
- OpenRouter routing metadata
- response-cache status
- total request latency
- success and error state

The API key is never written to an artifact.

## Primary analysis

Report the frozen strict-oracle result overall, per task class, and per task.

Compare it with the frozen Gemma 3 270M observations using:

- task success
- latency
- token usage
- reported remote cost
- empty and failed responses
- paired task-family routing replay using measured remote outcomes

The five `extract_person_2` observations remain strict-oracle failures if they
preserve the honorific. Any audited interpretation is reported separately and
does not replace the frozen result.

## Evidentiary limitations

OpenRouter is an intermediary and may route across provider infrastructure.
Returned model and exposed routing metadata will be recorded.

Five repetitions per task provide a small within-task sample. Temperature zero
does not guarantee byte-identical or deterministic provider execution.

This experiment measures this model, gateway, task suite, and execution window.
It does not establish general frontier-model performance.
