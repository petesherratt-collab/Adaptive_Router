"""V2 analyzer: authenticate all immutable strata, then analyze once."""

from __future__ import annotations

import argparse
import json

import prospective_contract_validation_v2 as pcv


def analyze(write=False):
    suite, inventory, contracts = pcv.load_frozen_inputs()
    pre = pcv.preflight_analysis(inventory, pcv.ROOT)
    report = pcv.analyze_rows(pre["rows"], inventory, contracts, pre["revision"], pre["prior_stratum_sha256"])
    if write:
        paths = pcv.v2_paths()
        pcv.atomic_write_json(paths["analysis_json"], report)
        pcv.atomic_write_text(paths["analysis_csv"], pcv.render_csv(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    report = analyze(args.write)
    print(json.dumps({"status":"PASS","write":args.write,"observation_count":report["primary"]["overall"]["observation_count"] + report["label_conformance"]["overall"]["observation_count"] + report["deterministic_executor"]["overall"]["observation_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
