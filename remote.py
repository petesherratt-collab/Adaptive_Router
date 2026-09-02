from dataclasses import asdict, dataclass
import time

import requests


RETRYABLE_STATUS_CODES = frozenset({408, 429})
OPENROUTER_KEY_MISSING = "OPENROUTER_KEY_MISSING"
OPENROUTER_CONFIG_ERROR = "OPENROUTER_CONFIG_ERROR"
OPENROUTER_TIMEOUT = "OPENROUTER_TIMEOUT"
OPENROUTER_CONNECTION_ERROR = "OPENROUTER_CONNECTION_ERROR"
OPENROUTER_REQUEST_ERROR = "OPENROUTER_REQUEST_ERROR"
OPENROUTER_RESPONSE_INVALID = "OPENROUTER_RESPONSE_INVALID"
OPENROUTER_ERROR = "OPENROUTER_ERROR"


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
    attempt_count: int = 0
    retry_count: int = 0

    def metadata(self):
        data = asdict(self)
        data.pop("text")
        return data


def _retryable_status(status_code):
    return status_code in RETRYABLE_STATUS_CODES or (
        isinstance(status_code, int) and 500 <= status_code <= 599
    )


def _retry_configuration(config):
    maximum_attempts = config.get("maximum_attempts", 1)
    backoff_seconds = config.get("retry_backoff_seconds", 0.0)
    if (
        type(maximum_attempts) is not int
        or maximum_attempts < 1
        or type(backoff_seconds) not in (int, float)
        or backoff_seconds < 0
    ):
        raise ValueError(OPENROUTER_CONFIG_ERROR)
    return maximum_attempts, float(backoff_seconds)


def _error_code(exc, status_code):
    if isinstance(exc, requests.Timeout):
        return OPENROUTER_TIMEOUT
    if isinstance(exc, requests.ConnectionError):
        return OPENROUTER_CONNECTION_ERROR
    if isinstance(exc, requests.HTTPError) and status_code is not None:
        return f"OPENROUTER_HTTP_{status_code}"
    if isinstance(exc, requests.RequestException):
        return OPENROUTER_REQUEST_ERROR
    if isinstance(exc, (KeyError, IndexError, TypeError, ValueError)):
        return OPENROUTER_RESPONSE_INVALID
    return OPENROUTER_ERROR


def _should_retry(exc, status_code):
    return isinstance(exc, (requests.Timeout, requests.ConnectionError)) or (
        isinstance(exc, requests.HTTPError) and _retryable_status(status_code)
    )


def generate(prompt, config, api_key, session=requests, sleep_fn=time.sleep):
    started = time.perf_counter()

    if not api_key:
        return RemoteResult(
            False,
            error=OPENROUTER_KEY_MISSING,
            model=config["model"],
        )

    try:
        maximum_attempts, backoff_seconds = _retry_configuration(config)
    except (KeyError, TypeError, ValueError):
        return RemoteResult(
            False,
            error=OPENROUTER_CONFIG_ERROR,
            model=config.get("model"),
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

    url = config["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Metadata": "enabled",
    }

    for attempt in range(1, maximum_attempts + 1):
        response = None
        try:
            response = session.post(
                url,
                headers=headers,
                json=payload,
                timeout=config["timeout_seconds"],
            )
            response.raise_for_status()
            body = response.json()

            choices = body["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError("missing choices")
            choice = choices[0]
            if not isinstance(choice, dict):
                raise ValueError("invalid choice")
            message = choice.get("message") or {}
            if not isinstance(message, dict):
                raise ValueError("invalid message")
            content = message.get("content")
            if not isinstance(content, str) or not content:
                raise ValueError("empty content")

            usage = body.get("usage") or {}
            if not isinstance(usage, dict):
                raise ValueError("invalid usage")
            prompt_details = usage.get("prompt_tokens_details") or {}
            completion_details = usage.get("completion_tokens_details") or {}
            if not isinstance(prompt_details, dict) or not isinstance(
                completion_details, dict
            ):
                raise ValueError("invalid token details")
            response_headers = getattr(response, "headers", {}) or {}

            return RemoteResult(
                True,
                text=content,
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
                attempt_count=attempt,
                retry_count=attempt - 1,
            )
        except Exception as exc:
            status_code = getattr(response, "status_code", None)
            if attempt < maximum_attempts and _should_retry(exc, status_code):
                sleep_fn(backoff_seconds * attempt)
                continue
            return RemoteResult(
                False,
                total_ms=(time.perf_counter() - started) * 1000,
                model=config.get("model"),
                status_code=status_code,
                error=_error_code(exc, status_code),
                attempt_count=attempt,
                retry_count=attempt - 1,
            )

    raise AssertionError("unreachable")
