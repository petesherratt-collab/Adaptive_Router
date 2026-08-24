import argparse
import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from local import model_residency
from probe import run_probe
from router import Router
from stats import read_runs, render_report
from telemetry import collect_system_metrics

ROOT = Path(__file__).resolve().parent


def load_config(): return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def diagnostics(config):
    try:
        response = requests.get(config["local"]["base_url"].rstrip("/") + "/api/tags", timeout=2)
        reachable = response.ok; models = [m.get("name") for m in response.json().get("models", [])] if reachable else []
    except requests.RequestException: reachable, models = False, []
    residency = model_residency(config["local"])
    resident_size = f"{residency['size_bytes']} bytes" if residency["size_bytes"] is not None else "not reported"
    metrics = collect_system_metrics()
    return "\n".join([f"Ollama reachable: {'yes' if reachable else 'no'}",
        f"Local model available: {'yes' if config['local']['model'] in models else 'no'}",
        f"Local model resident: {'yes' if residency['resident'] else 'no'}",
        f"Resident model size: {resident_size}",
        f"OpenRouter key configured: {'yes' if os.getenv('OPENROUTER_API_KEY') else 'no'}",
        f"RAM available: {metrics['available_ram_mb']:.0f} MB",
        f"Swap occupancy: {metrics['swap_used_mb']:.0f} MB ({metrics['swap_percent']:.1f}%)",
        f"Swap activity ({metrics['swap_activity_sample_seconds']:.1f}s): in {metrics['swap_in_bytes']} bytes/{metrics['swap_in_pages']} pages, out {metrics['swap_out_bytes']} bytes/{metrics['swap_out_pages']} pages",
        f"probe time: {run_probe(config['probe']['iterations']):.3f} ms", f"runs logged: {len(read_runs(ROOT/'runs.jsonl'))}"])


def show(result):
    print(f"[route: {result['route'].upper()}]")
    if result["route"] == "remote" and not result["remote"].success:
        print(f"[initial decision: {result['trigger']}]\n[remote failure: {result['remote'].error}]")
    else:
        print(f"[reason: {result['reason']}]")
    if result["local"]:
        local = result["local"]; rate = f"{local.tokens_per_second:.1f} tok/s" if local.tokens_per_second is not None else f"{local.chars_per_second:.1f} chars/s"
        print(f"[ttft: {(local.ttft_ms or 0)/1000:.1f}s | {rate}]")
    print("\n" + (result["text"] or "No answer was returned."))


def main():
    load_dotenv(ROOT / ".env"); config = load_config()
    parser = argparse.ArgumentParser(); parser.add_argument("--stats", action="store_true"); parser.add_argument("--diagnostics", action="store_true"); parser.add_argument("--prompt")
    args = parser.parse_args()
    if args.stats: print(render_report(read_runs(ROOT/"runs.jsonl"), config)); return
    if args.diagnostics: print(diagnostics(config)); return
    router = Router(config, ROOT/"runs.jsonl")
    if args.prompt: show(router.route(args.prompt)); return
    print(f"Adaptive Router v0.1\nLocal: {config['local']['model']} via Ollama\nRemote: {config['remote']['model']} via OpenRouter\n")
    while True:
        try: prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt): print(); break
        if prompt: show(router.route(prompt)); print()


if __name__ == "__main__": main()
