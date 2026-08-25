from dataclasses import asdict, dataclass
import time

import requests


@dataclass
class RemoteResult:
    success: bool
    text: str = ""
    total_ms: float | None = None
    model: str | None = None
    error: str | None = None
    response_id: str | None = None
    status_code: int | None = None
    finish_reason: str | None = None
    native_finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    cost: float | None = None
    router_metadata: dict | None = None
    cache_status: str | None = None

    def metadata(self):
        data = asdict(self)
        data.pop("text")
        return data


def generate(prompt, config, api_key, session=requests):
    started = time.perf_counter()

    if not api_key:
        return RemoteResult(
            False,
            error="OPENROUTER_KEY_MISSING",
            model=config["model"],
        )

    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    if "temperature" in config:
        payload["temperature"] = config["temperature"]

    if "max_tokens" in config:
        payload["max_tokens"] = config["max_tokens"]

    response = None

    try:
        response = session.post(
            config["base_url"].rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-OpenRouter-Metadata": "enabled",
            },
            json=payload,
            timeout=config["timeout_seconds"],
        )
        response.raise_for_status()
        body = response.json()

        choice = body["choices"][0]
        message = choice.get("message") or {}
        usage = body.get("usage") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        response_headers = getattr(response, "headers", {}) or {}

        return RemoteResult(
            True,
            text=message.get("content") or "",
            total_ms=(time.perf_counter() - started) * 1000,
            model=body.get("model", config["model"]),
            response_id=body.get("id"),
            status_code=getattr(response, "status_code", None),
            finish_reason=choice.get("finish_reason"),
            native_finish_reason=choice.get("native_finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            reasoning_tokens=completion_details.get("reasoning_tokens"),
            cached_tokens=prompt_details.get("cached_tokens"),
            cache_write_tokens=prompt_details.get("cache_write_tokens"),
            cost=usage.get("cost"),
            router_metadata=body.get("openrouter_metadata"),
            cache_status=response_headers.get(
                "X-OpenRouter-Cache-Status"
            ),
        )

    except Exception as exc:
        return RemoteResult(
            False,
            total_ms=(time.perf_counter() - started) * 1000,
            model=config["model"],
            status_code=getattr(response, "status_code", None),
            error=type(exc).__name__,
        )
