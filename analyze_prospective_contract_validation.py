"""Analyze authenticated prospective evidence without generating model output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import prospective_contract_validation as pcv


def load_rows(path: Path, model: str, task_inventory):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank evidence line: {path}:{line_number}")
            try:
                rows.append(pcv._strict_json_loads(line))
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid evidence JSON: {path}:{line_number}") from exc
    pcv.validate_result_rows(rows, task_inventory, model)
    return rows


def load_all_rows(task_inventory):
    rows = []
    for model in pcv.MODEL_ORDER:
        rows.extend(load_rows(pcv.EVIDENCE_PATHS[model], model, task_inventory))
    return rows


def analyze(write=False):
    suite, task_inventory, contracts = pcv.load_frozen_inputs()
    rows = load_all_rows(task_inventory)
    report = pcv.analyze_rows(rows, task_inventory, contracts, pcv.implementation_revision())
    if write:
        pcv.atomic_write_json(pcv.ANALYSIS_JSON_PATH, report)
        pcv.atomic_write_text(pcv.ANALYSIS_CSV_PATH, pcv.render_csv(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    report = analyze(write=args.write)
    print(json.dumps({"status": "PASS", "write": args.write, "observation_count": len(pcv.MODEL_ORDER) * pcv.OBSERVATIONS_PER_MODEL}, sort_keys=True))
    return report


if __name__ == "__main__":
    main()
