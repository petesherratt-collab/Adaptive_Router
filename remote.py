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

    def metadata(self):
        data = asdict(self); data.pop("text")
        return data


def generate(prompt, config, api_key, session=requests):
    started = time.perf_counter()
    if not api_key:
        return RemoteResult(False, error="OPENROUTER_KEY_MISSING", model=config["model"])
    try:
        response = session.post(config["base_url"].rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": config["model"], "messages": [{"role": "user", "content": prompt}]},
            timeout=config["timeout_seconds"])
        response.raise_for_status(); body = response.json()
        return RemoteResult(True, body["choices"][0]["message"]["content"],
                            (time.perf_counter()-started)*1000, body.get("model", config["model"]))
    except Exception as exc:
        return RemoteResult(False, total_ms=(time.perf_counter()-started)*1000,
                            model=config["model"], error=type(exc).__name__)
