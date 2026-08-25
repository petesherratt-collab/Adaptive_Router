from dataclasses import asdict, dataclass
import json
import time
import requests


def model_residency(config, session=requests):
    """Return whether Ollama reports the configured model as currently loaded."""
    try:
        response = session.get(
            config["base_url"].rstrip("/") + "/api/ps",
            timeout=min(config.get("timeout_seconds", 2), 2),
        )
        response.raise_for_status()
        configured_model = config["model"]
        for model in response.json().get("models", []):
            if configured_model in (model.get("name"), model.get("model")):
                return {"resident": True, "size_bytes": model.get("size")}
    except (requests.RequestException, ValueError, TypeError):
        pass
    return {"resident": False, "size_bytes": None}


@dataclass
class LocalResult:
    success: bool
    text: str = ""
    ttft_ms: float | None = None
    total_ms: float | None = None
    tokens_per_second: float | None = None
    chars_per_second: float | None = None
    eval_count: int | None = None
    eval_duration: int | None = None
    error: str | None = None

    def metadata(self):
        data = asdict(self); data.pop("text")
        return data


def generate(prompt, config, session=requests):
    started, first, chunks, final = time.perf_counter(), None, [], {}
    try:
        response = session.post(config["base_url"].rstrip("/") + "/api/generate",
            json={"model": config["model"], "prompt": prompt, "stream": True},
            timeout=config["timeout_seconds"], stream=True)
        response.raise_for_status()
        for line in response.iter_lines():
            if not line: continue
            item = json.loads(line)
            text = item.get("response", "")
            if text and first is None: first = time.perf_counter()
            chunks.append(text)
            if item.get("done"): final = item
        completed, text = time.perf_counter(), "".join(chunks)
        total = (completed - started) * 1000
        count, duration = final.get("eval_count"), final.get("eval_duration")
        tps = count / (duration / 1e9) if text and count and duration else None
        cps = len(text) / (total / 1000) if total > 0 else None
        return LocalResult(True, text, (first-started)*1000 if first else None, total, tps, cps, count, duration)
    except requests.Timeout:
        return LocalResult(False, total_ms=(time.perf_counter()-started)*1000, error="LOCAL_TIMEOUT")
    except Exception as exc:
        return LocalResult(False, total_ms=(time.perf_counter()-started)*1000, error=type(exc).__name__)
