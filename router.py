import json
import os
from pathlib import Path
import re
import uuid
from datetime import datetime, timezone
import local, remote
from probe import run_probe
from shadow import should_shadow
from telemetry import collect_system_metrics, system_is_healthy
from validators import validate

LOCAL_ALLOWED = {"rewrite", "summarise_short", "extract_structured", "format"}
LOCAL_ACCEPTED, REMOTE_DEFAULT_TASK, LOW_RAM, ACTIVE_SWAP_PRESSURE, LOCAL_TIMEOUT, LOCAL_ERROR, TTFT_EXCEEDED, GENERATION_TOO_SLOW, VALIDATOR_FAILED, REMOTE_ERROR, SHADOW_SAMPLE = (
    "LOCAL_ACCEPTED", "REMOTE_DEFAULT_TASK", "LOW_RAM", "ACTIVE_SWAP_PRESSURE", "LOCAL_TIMEOUT", "LOCAL_ERROR",
    "TTFT_EXCEEDED", "GENERATION_TOO_SLOW", "VALIDATOR_FAILED", "REMOTE_ERROR", "SHADOW_SAMPLE")
REASON_CODES = frozenset((LOCAL_ACCEPTED, REMOTE_DEFAULT_TASK, LOW_RAM, ACTIVE_SWAP_PRESSURE, LOCAL_TIMEOUT,
                          LOCAL_ERROR, TTFT_EXCEEDED, GENERATION_TOO_SLOW, VALIDATOR_FAILED,
                          REMOTE_ERROR, SHADOW_SAMPLE))


def classify(prompt, config):
    low = prompt.strip().lower()
    def has_command_prefix(*commands):
        return any(re.match(rf"^{re.escape(command)}(?=\s|:|$)", low) for command in commands)

    if has_command_prefix("rewrite", "rephrase", "polish"): return "rewrite"
    if has_command_prefix("summarise", "summarize") and len(prompt) <= config["routing"]["summarise_max_input_chars"]: return "summarise_short"
    if "json" in low and re.search(r"extract|schema|required keys?", low): return "extract_structured"
    if has_command_prefix("format", "convert", "transform") or "format as" in low: return "format"
    if re.search(r"\b(code|python|javascript|function|program|debug|sql)\b", low): return "code"
    if re.search(r"\b(current|latest|search|web|research)\b", low): return "research"
    return "unknown"


class Router:
    def __init__(self, config, log_path="runs.jsonl", local_fn=local.generate, remote_fn=remote.generate,
                 metrics_fn=collect_system_metrics, probe_fn=run_probe,
                 residency_fn=local.model_residency, api_key=None):
        self.config, self.log_path = config, Path(log_path)
        self.local_fn, self.remote_fn = local_fn, remote_fn
        self.metrics_fn, self.probe_fn, self.residency_fn = metrics_fn, probe_fn, residency_fn
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")

    def route(self, prompt):
        request_id, task = str(uuid.uuid4()), classify(prompt, self.config)
        metrics = self.metrics_fn()
        probe_ms = self.probe_fn(self.config["probe"]["iterations"]) if self.config["probe"]["enabled"] else None
        shadow_cfg = self.config["shadow"]
        selected = shadow_cfg["enabled"] and should_shadow(request_id, shadow_cfg["sample_rate"], shadow_cfg["salt"])
        record = {"request_id": request_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                  "task_class": task, "input_chars": len(prompt), "system": metrics, "probe_ms": probe_ms,
                  "local_model_resident": False, "local_model_size_bytes": None,
                  "local": {"attempted": False}, "validator": {"name": "unsupported", "status": "NOT_APPLICABLE"},
                  "shadow": {"selected": selected, "executed": False}}
        if task not in LOCAL_ALLOWED: return self._remote(prompt, record, REMOTE_DEFAULT_TASK)
        residency = self.residency_fn(self.config["local"])
        record["local_model_resident"] = residency["resident"]
        record["local_model_size_bytes"] = residency.get("size_bytes")
        healthy, health_reason = system_is_healthy(metrics, self.config, residency["resident"])
        if not healthy: return self._remote(prompt, record, health_reason)
        result = self.local_fn(prompt, self.config["local"]); record["local"] = {"attempted": True, **result.metadata()}
        if not result.success: return self._remote(prompt, record, LOCAL_TIMEOUT if result.error == LOCAL_TIMEOUT else LOCAL_ERROR)
        if result.ttft_ms is not None and result.ttft_ms > self.config["routing"]["maximum_ttft_ms"]:
            return self._remote(prompt, record, TTFT_EXCEEDED)
        if result.tokens_per_second is not None and result.tokens_per_second < self.config["routing"]["minimum_generation_rate"]:
            return self._remote(prompt, record, GENERATION_TOO_SLOW)
        check = validate(task, prompt, result.text); record["validator"] = check.__dict__
        if check.status == "FAIL": return self._remote(prompt, record, VALIDATOR_FAILED)
        record["decision"] = {"route": "local", "reason": LOCAL_ACCEPTED}; self._log(record)
        return {"text": result.text, "route": "local", "reason": LOCAL_ACCEPTED, "local": result, "remote": None}

    def _remote(self, original_prompt, record, reason):
        result = self.remote_fn(original_prompt, self.config["remote"], self.api_key)
        record["remote"] = result.metadata()
        final_reason = reason if result.success else REMOTE_ERROR
        record["decision"] = {"route": "remote", "reason": final_reason, "trigger": reason}
        self._log(record)
        return {"text": result.text, "route": "remote", "reason": final_reason, "trigger": reason,
                "local": None, "remote": result}

    def _log(self, record):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle: handle.write(json.dumps(record, separators=(",", ":")) + "\n")
