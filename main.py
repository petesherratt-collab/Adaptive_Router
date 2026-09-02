import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from local import model_residency
from probe import run_probe
from router import Router
from runtime_contracts import RuntimeContractError, load_runtime_request
from stats import read_runs, render_report
from telemetry import collect_system_metrics


ROOT = Path(__file__).resolve().parent


def load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def diagnostics(config):
    try:
        response = requests.get(
            config["local"]["base_url"].rstrip("/") + "/api/tags", timeout=2
        )
        reachable = response.ok
        models = (
            [model.get("name") for model in response.json().get("models", [])]
            if reachable
            else []
        )
    except requests.RequestException:
        reachable, models = False, []

    residency = model_residency(config["local"])
    resident_size = (
        f"{residency['size_bytes']} bytes"
        if residency["size_bytes"] is not None
        else "not reported"
    )
    metrics = collect_system_metrics()
    return "\n".join(
        [
            f"Ollama reachable: {'yes' if reachable else 'no'}",
            (
                "Local model available: "
                f"{'yes' if config['local']['model'] in models else 'no'}"
            ),
            f"Local model resident: {'yes' if residency['resident'] else 'no'}",
            f"Resident model size: {resident_size}",
            (
                "OpenRouter key configured: "
                f"{'yes' if os.getenv('OPENROUTER_API_KEY') else 'no'}"
            ),
            f"RAM available: {metrics['available_ram_mb']:.0f} MB",
            (
                f"Swap occupancy: {metrics['swap_used_mb']:.0f} MB "
                f"({metrics['swap_percent']:.1f}%)"
            ),
            (
                "Swap activity "
                f"({metrics['swap_activity_sample_seconds']:.1f}s): "
                f"in {metrics['swap_in_bytes']} bytes/"
                f"{metrics['swap_in_pages']} pages, "
                f"out {metrics['swap_out_bytes']} bytes/"
                f"{metrics['swap_out_pages']} pages"
            ),
            f"probe time: {run_probe(config['probe']['iterations']):.3f} ms",
            f"runs logged: {len(read_runs(ROOT / 'runs.jsonl'))}",
        ]
    )


def show(result):
    print(f"[route: {result['route'].upper()}]")
    if result["route"] == "remote" and not result["remote"].success:
        print(
            f"[initial decision: {result['trigger']}]\n"
            f"[remote failure: {result['remote'].error}]"
        )
    else:
        print(f"[reason: {result['reason']}]")
    if result["local"]:
        local_result = result["local"]
        rate = (
            f"{local_result.tokens_per_second:.1f} tok/s"
            if local_result.tokens_per_second is not None
            else f"{local_result.chars_per_second:.1f} chars/s"
        )
        print(f"[ttft: {(local_result.ttft_ms or 0) / 1000:.1f}s | {rate}]")
    print("\n" + (result["text"] or "No answer was returned."))


def build_parser():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stats", action="store_true")
    mode.add_argument("--diagnostics", action="store_true")
    mode.add_argument("--prompt")
    mode.add_argument(
        "--request-json",
        metavar="PATH",
        help="route one explicit runtime_request_v1 JSON document",
    )
    return parser


def main():
    load_dotenv(ROOT / ".env")
    config = load_config()
    parser = build_parser()
    args = parser.parse_args()

    if args.stats:
        print(render_report(read_runs(ROOT / "runs.jsonl"), config))
        return
    if args.diagnostics:
        print(diagnostics(config))
        return

    router = Router(config, ROOT / "runs.jsonl")
    if args.request_json:
        try:
            request = load_runtime_request(args.request_json)
        except RuntimeContractError as exc:
            parser.error(f"invalid runtime request: {exc}")
        show(router.route_request(request))
        return
    if args.prompt:
        show(router.route(args.prompt))
        return

    print(
        "Adaptive Router v0.2\n"
        f"Local: {config['local']['model']} via Ollama\n"
        f"Remote: {config['remote']['model']} via OpenRouter\n"
    )
    while True:
        try:
            prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt:
            show(router.route(prompt))
            print()


if __name__ == "__main__":
    main()
