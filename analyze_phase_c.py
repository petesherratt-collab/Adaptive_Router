"""Phase C analysis: the frozen write-once comparisons, overall and per job family.

    python analyze_phase_c.py fast_path_phase_c_v1.jsonl --output fast_path_phase_c_v1_analysis.json

Uses analyze_write_once_v1.analyse for the whole run (primary arm P), then repeats the
P-against-R and Q-against-R pairs on the one-reading and many-reading shapes of
fast_path_planned_bench_v7 separately, with the same shape-cluster bootstrap.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyze_fast_path_planned_v1 import pair
from analyze_fast_path_timing_v1 import BOOTSTRAP_REPLICATES, by_shape, load
import analyze_write_once_v1
from fast_path_planned_bench_v7 import FAMILY


def by_family(jobs, replicates=BOOTSTRAP_REPLICATES):
    out = {}
    for family in ("one", "many"):
        rows = [r for r in jobs if FAMILY.get(r["shape"]) == family]
        grouped = by_shape(rows)
        present = {r["arm"] for r in rows}
        out[family] = {
            "shapes": sorted(grouped),
            "arms": analyze_write_once_v1.arm_table(rows),
            "p_vs_r": pair(grouped, "P", "R", replicates) if {"P", "R"} <= present else None,
            "q_vs_r": pair(grouped, "Q", "R", replicates) if {"Q", "R"} <= present else None,
            "q_vs_p": pair(grouped, "Q", "P", replicates) if {"Q", "P"} <= present else None,
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("observations")
    parser.add_argument("--output")
    args = parser.parse_args()
    kinds = load(args.observations)
    result = analyze_write_once_v1.analyse(kinds, primary_arm="P")
    if result.get("status") == "COMPLETED":
        result["by_family"] = by_family(kinds.get("job", []))
    text = json.dumps(result, indent=1)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
