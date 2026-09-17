"""Run the corrected fresh 20-variant three-model leakage bundle."""

from pathlib import Path

import run_benchmark_leakage_v2 as implementation


ROOT = Path(__file__).resolve().parent
implementation.PLAN_PATH = ROOT / "BENCHMARK_LEAKAGE_V2_CORRECTED_PLAN.md"
implementation.OUTPUT_PATH = ROOT / "benchmark_leakage_v2_corrected_runs.jsonl"
implementation.PARTIAL_PATH = Path(str(implementation.OUTPUT_PATH) + ".partial")


if __name__ == "__main__":
    import json
    print(json.dumps({"rows": implementation.run()}, sort_keys=True))
