import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_local_model_scaling as analysis


TASK = {
    "task_id": "task",
    "task_class": "format",
    "capability_family": "json_format",
    "normalization": "text",
    "prompt": "Output only: ok",
    "expected": "ok",
}

JSON_TASK = {
    **TASK,
    "task_id": "json_task",
    "prompt": "Format as JSON",
}


def record(
    rep,
    correct,
    model="gemma3:270m",
    resident=True,
    total_ms=20.0,
    ttft_ms=None,
    tokens_per_second=50.0,
    success=True,
    raw_output=None,
    task=TASK,
):
    if ttft_ms is None:
        ttft_ms = total_ms / 2
    if raw_output is None:
        raw_output = "ok" if correct else "wrong"
    return {
        "task_id": task["task_id"],
        "rep": rep,
        "task_class": task["task_class"],
        "capability_family": task["capability_family"],
        "provider": "ollama",
        "requested_model": model,
        "returned_model": model,
        "benchmark_sha256": analysis.oos.BENCHMARK_SHA256,
        "raw_output": raw_output,
        "oracle_correct": correct,
        "success": success,
        "error": None if success else "error",
        "ttft_ms": ttft_ms,
        "total_ms": total_ms,
        "tokens_per_second": tokens_per_second,
        "model_residency": {
            "resident": resident,
            "size_bytes": 700 if resident else None,
        },
    }


class LocalModelScalingAnalysisTests(unittest.TestCase):
    def test_frozen_analysis_identities(self):
        self.assertEqual(
            analysis.ANALYSIS_ID,
            "local_model_scaling_v1_strict",
        )
        self.assertEqual(
            analysis.MODEL_ORDER,
            ("gemma3:270m", "gemma3:1b", "gemma3:4b"),
        )
        self.assertEqual(
            analysis.PLAN_SHA256,
            (
                "97359083cc1f4b2352ea383e02076cc8"
                "ba6170336499d745be4f15742bf98363"
            ),
        )
        self.assertEqual(
            analysis.AMENDMENT_SHA256,
            (
                "f10c2a890a8e543e97bb80f53a8dabc"
                "be3d5633caeafc40fe3cfef8bcbace71f"
            ),
        )
        self.assertEqual(analysis.MAXIMUM_TTFT_MS, 8000)
        self.assertEqual(analysis.MINIMUM_GENERATION_RATE, 1.5)
        self.assertEqual(
            analysis.BASELINE_SHA256,
            (
                "425fa9328781ff2e53f69ce0a054531e"
                "106be3a6ed1380c148e35ec3d47c8ca0"
            ),
        )

    def test_validate_keys_accepts_exact_paired_set(self):
        records = [record(1, True), record(2, False)]
        with (
            patch.object(analysis.oos, "OBSERVATION_COUNT", 2),
            patch.object(analysis.oos, "REPS", 2),
        ):
            analysis.validate_keys(records, [TASK])

    def test_validate_keys_rejects_duplicate(self):
        records = [record(1, True), record(1, False)]
        with (
            patch.object(analysis.oos, "OBSERVATION_COUNT", 2),
            patch.object(analysis.oos, "REPS", 2),
        ):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                analysis.validate_keys(records, [TASK])

    def test_validate_keys_rejects_incomplete_set(self):
        with (
            patch.object(analysis.oos, "OBSERVATION_COUNT", 2),
            patch.object(analysis.oos, "REPS", 2),
        ):
            with self.assertRaisesRegex(ValueError, "expected 2"):
                analysis.validate_keys([record(1, True)], [TASK])

    def test_baseline_hash_mismatch_is_rejected_first(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(analysis.oos, "file_sha256", return_value="wrong"),
        ):
            path = Path(directory) / "baseline.jsonl"
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "270M evidence SHA-256"):
                analysis.load_baseline([TASK], path)

    def test_gate_order_and_exact_boundaries(self):
        failed = record(
            1,
            False,
            success=False,
            ttft_ms=9000.0,
            tokens_per_second=1.0,
        )
        self.assertEqual(
            analysis.post_generation_gate(failed, TASK),
            "GENERATION_FAILED",
        )

        at_ttft_boundary = record(1, True, ttft_ms=8000.0)
        self.assertEqual(
            analysis.post_generation_gate(at_ttft_boundary, TASK),
            "SURVIVED",
        )
        over_ttft_boundary = record(1, True, ttft_ms=8000.001)
        self.assertEqual(
            analysis.post_generation_gate(over_ttft_boundary, TASK),
            "TTFT_EXCEEDED",
        )

        at_rate_boundary = record(1, True, tokens_per_second=1.5)
        self.assertEqual(
            analysis.post_generation_gate(at_rate_boundary, TASK),
            "SURVIVED",
        )
        below_rate_boundary = record(1, True, tokens_per_second=1.499)
        self.assertEqual(
            analysis.post_generation_gate(below_rate_boundary, TASK),
            "GENERATION_TOO_SLOW",
        )

    def test_validator_failure_and_not_applicable_semantics(self):
        malformed_json = record(
            1,
            False,
            raw_output="not json",
            task=JSON_TASK,
        )
        self.assertEqual(
            analysis.post_generation_gate(malformed_json, JSON_TASK),
            "VALIDATOR_FAILED",
        )

        not_applicable = record(1, False, raw_output="wrong")
        self.assertEqual(
            analysis.post_generation_gate(not_applicable, TASK),
            "SURVIVED",
        )

    def test_missing_telemetry_matches_live_router(self):
        missing = record(1, False)
        missing["ttft_ms"] = None
        missing["tokens_per_second"] = None
        self.assertEqual(
            analysis.post_generation_gate(missing, TASK),
            "SURVIVED",
        )
        metrics = analysis.gate_metrics([missing], [TASK])
        self.assertEqual(metrics["missing_ttft_count"], 1)
        self.assertEqual(metrics["missing_throughput_count"], 1)
        self.assertEqual(metrics["false_accept_count"], 1)

    def test_gate_metrics_count_false_accepts_and_rejected_correct(self):
        records = [
            record(1, True),
            record(2, False),
            record(3, True, ttft_ms=9000.0),
            record(4, False, success=False),
        ]
        result = analysis.gate_metrics(records, [TASK])
        self.assertEqual(result["observation_count"], 4)
        self.assertEqual(result["survivor_count"], 2)
        self.assertEqual(result["survivor_rate"], 0.5)
        self.assertEqual(result["strict_pass_count_among_survivors"], 1)
        self.assertEqual(result["strict_pass_rate_among_survivors"], 0.5)
        self.assertEqual(result["false_accept_count"], 1)
        self.assertEqual(result["rejected_correct_count"], 1)
        self.assertEqual(result["first_outcome_counts"]["SURVIVED"], 2)
        self.assertEqual(result["first_outcome_counts"]["TTFT_EXCEEDED"], 1)
        self.assertEqual(
            result["first_outcome_counts"]["GENERATION_FAILED"], 1
        )

    def test_gate_metrics_reject_unknown_task(self):
        unknown = record(1, True)
        unknown["task_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unknown task_id"):
            analysis.gate_metrics([unknown], [TASK])

    def test_paired_comparison_counts_gains_and_losses(self):
        baseline = [
            record(1, True),
            record(2, False),
            record(3, True),
            record(4, False),
        ]
        candidate = [
            record(1, True, "gemma3:1b"),
            record(2, True, "gemma3:1b"),
            record(3, False, "gemma3:1b"),
            record(4, False, "gemma3:1b"),
        ]
        result = analysis.paired_comparison(baseline, candidate)
        self.assertEqual(result["baseline_passes"], 2)
        self.assertEqual(result["candidate_passes"], 2)
        self.assertEqual(result["pass_difference"], 0)
        self.assertEqual(result["pass_rate_difference"], 0.0)
        self.assertEqual(result["gained_passes"], 1)
        self.assertEqual(result["lost_passes"], 1)
        self.assertEqual(result["both_pass"], 1)
        self.assertEqual(result["both_fail"], 1)

    def test_paired_comparison_rejects_key_mismatch(self):
        baseline = [record(1, True)]
        candidate = [record(2, True, "gemma3:1b")]
        with self.assertRaisesRegex(ValueError, "paired key set"):
            analysis.paired_comparison(baseline, candidate)

    def test_model_metrics_separate_resident_timing_and_gates(self):
        records = [
            record(1, True, resident=True, total_ms=20.0),
            record(2, False, resident=False, total_ms=200.0),
        ]
        result = analysis.model_metrics(
            records,
            analysis.BASELINE_IDENTITY,
            [TASK],
        )
        self.assertEqual(result["pass_count"], 1)
        self.assertEqual(result["pass_rate"], 0.5)
        self.assertEqual(
            result["residency"]["resident_observation_count"], 1
        )
        self.assertEqual(
            result["residency"]["nonresident_observation_count"], 1
        )
        self.assertEqual(
            result["residency"]["resident_timing"]["median_total_ms"],
            20.0,
        )
        self.assertEqual(
            result["residency"]["nonresident_timing"]["median_total_ms"],
            200.0,
        )
        gates = result["post_generation_gate_simulation"]
        self.assertEqual(gates["overall"]["survivor_count"], 2)
        self.assertEqual(
            gates["residency"]["resident"]["observation_count"], 1
        )
        self.assertEqual(
            gates["residency"]["nonresident"]["observation_count"], 1
        )
        self.assertEqual(
            gates["residency"]["unknown"]["observation_count"], 0
        )

    def test_csv_is_deterministic_and_uses_lf(self):
        models = {}
        for model in analysis.MODEL_ORDER:
            models[model] = {
                "observation_count": 2,
                "pass_count": 1,
                "pass_rate": 0.5,
                "timing": {
                    "median_ttft_ms": 10.0,
                    "median_total_ms": 20.0,
                    "median_tokens_per_second": 50.0,
                },
                "per_family": {
                    "json_format": {
                        "observation_count": 2,
                        "pass_count": 1,
                        "pass_rate": 0.5,
                    }
                },
            }
        document = {"models": models}
        first = analysis.render_csv(document)
        second = analysis.render_csv(document)
        self.assertEqual(first, second)
        self.assertNotIn("\r\n", first)
        self.assertTrue(first.endswith("\n"))
        rows = list(csv.DictReader(io.StringIO(first)))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["model"], "gemma3:270m")
        self.assertEqual(rows[0]["scope"], "overall")

    def test_writer_refuses_if_either_output_exists(self):
        document = {
            "models": {
                model: {
                    "observation_count": 0,
                    "pass_count": 0,
                    "pass_rate": None,
                    "timing": {
                        "median_ttft_ms": None,
                        "median_total_ms": None,
                        "median_tokens_per_second": None,
                    },
                    "per_family": {},
                }
                for model in analysis.MODEL_ORDER
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "analysis.json"
            csv_path = Path(directory) / "analysis.csv"
            json_path.write_text("{}\n", encoding="utf-8")
            with (
                patch.object(analysis, "JSON_OUTPUT", json_path),
                patch.object(analysis, "CSV_OUTPUT", csv_path),
            ):
                with self.assertRaisesRegex(
                    FileExistsError, "refusing to overwrite"
                ):
                    analysis.write_outputs(document)
            self.assertFalse(csv_path.exists())

    def test_writer_creates_both_outputs_with_lf(self):
        models = {}
        for model in analysis.MODEL_ORDER:
            models[model] = {
                "observation_count": 1,
                "pass_count": 1,
                "pass_rate": 1.0,
                "timing": {
                    "median_ttft_ms": 10.0,
                    "median_total_ms": 20.0,
                    "median_tokens_per_second": 50.0,
                },
                "per_family": {},
            }
        document = {"analysis_id": analysis.ANALYSIS_ID, "models": models}
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "analysis.json"
            csv_path = Path(directory) / "analysis.csv"
            with (
                patch.object(analysis, "JSON_OUTPUT", json_path),
                patch.object(analysis, "CSV_OUTPUT", csv_path),
            ):
                analysis.write_outputs(document)
            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertNotIn(b"\r\n", json_path.read_bytes())
            self.assertNotIn(b"\r\n", csv_path.read_bytes())
            self.assertTrue(json_path.read_bytes().endswith(b"\n"))
            self.assertTrue(csv_path.read_bytes().endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
