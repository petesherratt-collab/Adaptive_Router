import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_oos_validation as analysis


def record(
    task_id,
    rep,
    family,
    task_class,
    provider,
    model,
    correct,
    *,
    success=True,
    total_ms=10.0,
    cost=None,
):
    return {
        "task_id": task_id,
        "rep": rep,
        "task_class": task_class,
        "capability_family": family,
        "provider": provider,
        "requested_model": model,
        "benchmark_sha256": analysis.BENCHMARK_SHA256,
        "code_revision": analysis.RUNNER_REVISION,
        "oracle_correct": correct,
        "success": success,
        "total_ms": total_ms,
        "cost": cost,
    }


def paired(
    task_id,
    rep,
    family,
    task_class,
    local_correct,
    remote_correct,
    *,
    local_success=True,
    remote_success=True,
    local_ms=10.0,
    remote_ms=100.0,
    remote_cost=0.01,
):
    local = record(
        task_id,
        rep,
        family,
        task_class,
        "ollama",
        analysis.LOCAL_MODEL,
        local_correct,
        success=local_success,
        total_ms=local_ms,
    )
    remote = record(
        task_id,
        rep,
        family,
        task_class,
        "openrouter",
        analysis.REMOTE_MODEL,
        remote_correct,
        success=remote_success,
        total_ms=remote_ms,
        cost=remote_cost,
    )
    return local, remote


class OOSAnalysisTests(unittest.TestCase):
    def test_fine_policy_uses_capability_family(self):
        local_families = {
            "structured_extraction",
            "sentiment",
            "json_format",
        }
        remote_families = {
            "priority",
            "markdown_bullets",
            "key_value_labels",
            "transformation",
        }

        for family in local_families:
            with self.subTest(family=family):
                self.assertEqual(
                    analysis.route(
                        "fine_capability",
                        {
                            "capability_family": family,
                            "task_class": "format",
                        },
                    ),
                    "local",
                )

        for family in remote_families:
            with self.subTest(family=family):
                self.assertEqual(
                    analysis.route(
                        "fine_capability",
                        {
                            "capability_family": family,
                            "task_class": "classification",
                        },
                    ),
                    "remote",
                )

    def test_coarse_policy_uses_task_class_only(self):
        self.assertEqual(
            analysis.route(
                "coarse_class",
                {
                    "task_class": "extract_structured",
                    "capability_family": "transformation",
                },
            ),
            "local",
        )
        self.assertEqual(
            analysis.route(
                "coarse_class",
                {
                    "task_class": "classification",
                    "capability_family": "priority",
                },
            ),
            "local",
        )
        self.assertEqual(
            analysis.route(
                "coarse_class",
                {
                    "task_class": "format",
                    "capability_family": "sentiment",
                },
            ),
            "remote",
        )

    def test_remote_cost_is_counted_exactly_once(self):
        pairs = [
            paired(
                "task",
                1,
                "priority",
                "classification",
                False,
                True,
                remote_cost=0.25,
            )
        ]

        result = analysis.simulate(
            pairs,
            "always_remote",
        )

        self.assertEqual(result["remote_calls"], 1)
        self.assertEqual(
            result["remote_calls_with_reported_cost"],
            1,
        )
        self.assertAlmostEqual(
            result["reported_remote_cost"],
            0.25,
        )

    def test_escalation_categories_and_ceiling(self):
        pairs = [
            paired(
                "missed",
                1,
                "sentiment",
                "classification",
                False,
                True,
            ),
            paired(
                "unnecessary",
                1,
                "priority",
                "classification",
                True,
                True,
                remote_cost=0.10,
            ),
            paired(
                "harmful",
                1,
                "transformation",
                "transform",
                True,
                False,
                remote_cost=0.20,
            ),
            paired(
                "unrecoverable",
                1,
                "json_format",
                "format",
                False,
                False,
            ),
        ]

        result = analysis.simulate(
            pairs,
            "fine_capability",
        )

        self.assertEqual(result["selected_passes"], 1)
        self.assertEqual(result["local_calls"], 2)
        self.assertEqual(result["remote_calls"], 2)
        self.assertEqual(result["beneficial_escalations"], 0)
        self.assertEqual(result["missed_escalations"], 1)
        self.assertEqual(
            result["unnecessary_escalations"],
            2,
        )
        self.assertEqual(result["harmful_escalations"], 1)
        self.assertEqual(
            result["unrecoverable_local_failures"],
            1,
        )
        self.assertEqual(result["oracle_ceiling_passes"], 3)
        self.assertAlmostEqual(
            result["reported_remote_cost"],
            0.30,
        )

    def test_always_remote_records_beneficial_escalation(self):
        result = analysis.simulate(
            [
                paired(
                    "task",
                    1,
                    "sentiment",
                    "classification",
                    False,
                    True,
                )
            ],
            "always_remote",
        )

        self.assertEqual(
            result["beneficial_escalations"],
            1,
        )
        self.assertEqual(result["selected_passes"], 1)

    def test_selected_transport_failure_is_retained(self):
        result = analysis.simulate(
            [
                paired(
                    "task",
                    1,
                    "priority",
                    "classification",
                    False,
                    False,
                    remote_success=False,
                )
            ],
            "always_remote",
        )

        self.assertEqual(
            result["selected_transport_failures"],
            1,
        )
        self.assertEqual(result["selected_passes"], 0)

    def test_pairing_rejects_key_mismatch(self):
        local = [
            paired(
                "local-task",
                rep,
                "sentiment",
                "classification",
                True,
                True,
            )[0]
            for rep in (1, 2)
        ]
        remote = [
            paired(
                "remote-task",
                rep,
                "sentiment",
                "classification",
                True,
                True,
            )[1]
            for rep in (1, 2)
        ]

        with (
            patch.object(analysis, "OBSERVATIONS", 2),
            patch.object(analysis, "TASKS", 1),
            patch.object(analysis, "REPS", 2),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "paired key sets differ",
            ):
                analysis.pair_records(local, remote)

    def test_identity_validation_rejects_mutations(self):
        records = [
            paired(
                "task",
                rep,
                "sentiment",
                "classification",
                True,
                True,
            )[0]
            for rep in (1, 2)
        ]

        cases = [
            ("benchmark_sha256", "wrong", "SHA-256"),
            ("code_revision", "wrong", "revision"),
            ("provider", "wrong", "provider"),
            ("requested_model", "wrong", "model"),
        ]

        for field, value, message in cases:
            with self.subTest(field=field):
                mutated = [
                    dict(item) for item in records
                ]
                mutated[0][field] = value

                with (
                    patch.object(
                        analysis,
                        "OBSERVATIONS",
                        2,
                    ),
                    patch.object(
                        analysis,
                        "TASKS",
                        1,
                    ),
                    patch.object(
                        analysis,
                        "REPS",
                        2,
                    ),
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        message,
                    ):
                        analysis.validate_identity(
                            mutated,
                            "local",
                            "ollama",
                            analysis.LOCAL_MODEL,
                        )

    def test_percentile_uses_linear_interpolation(self):
        values = [0.0, 1.0, 2.0, 3.0]
        self.assertEqual(
            analysis.percentile(values, 0.0),
            0.0,
        )
        self.assertEqual(
            analysis.percentile(values, 1.0),
            3.0,
        )
        self.assertAlmostEqual(
            analysis.percentile(values, 0.5),
            1.5,
        )

    def test_cluster_bootstrap_is_deterministic(self):
        pairs = []

        for rep in (1, 2):
            pairs.append(
                paired(
                    "task-a",
                    rep,
                    "sentiment",
                    "classification",
                    True,
                    True,
                )
            )
            pairs.append(
                paired(
                    "task-b",
                    rep,
                    "json_format",
                    "format",
                    False,
                    True,
                )
            )

        with (
            patch.object(analysis, "TASKS", 2),
            patch.object(analysis, "REPS", 2),
        ):
            first = analysis.cluster_bootstrap(
                pairs,
                samples=100,
                seed=123,
            )
            second = analysis.cluster_bootstrap(
                pairs,
                samples=100,
                seed=123,
            )

        self.assertEqual(first, second)
        self.assertEqual(first["samples"], 100)
        self.assertEqual(first["seed"], 123)
        self.assertEqual(first["estimate"], -0.5)
        self.assertEqual(
            first["repetitions_retained_per_task"],
            2,
        )

    def test_cluster_validation_retains_all_repetitions(self):
        pairs = [
            paired(
                "task-a",
                1,
                "sentiment",
                "classification",
                True,
                True,
            ),
            paired(
                "task-b",
                1,
                "json_format",
                "format",
                True,
                True,
            ),
            paired(
                "task-b",
                2,
                "json_format",
                "format",
                True,
                True,
            ),
        ]

        with (
            patch.object(analysis, "TASKS", 2),
            patch.object(analysis, "REPS", 2),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "incomplete repetition cluster",
            ):
                analysis.group_pairs_by_task(pairs)

    def test_output_writers_refuse_overwrite_and_use_lf(self):
        rows = [{
            "policy": "always_local",
            "selected_passes": 1,
        }]
        document = {"result": "test"}

        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "result.csv"
            json_path = Path(directory) / "result.json"

            analysis.write_csv(rows, csv_path)
            analysis.write_json(document, json_path)

            self.assertNotIn(b"\r\n", csv_path.read_bytes())

            with csv_path.open(
                encoding="utf-8",
                newline="",
            ) as handle:
                parsed = list(csv.DictReader(handle))
            self.assertEqual(len(parsed), 1)

            with self.assertRaises(FileExistsError):
                analysis.write_csv(rows, csv_path)
            with self.assertRaises(FileExistsError):
                analysis.write_json(document, json_path)

    def test_deviations_and_seed_are_explicit(self):
        self.assertEqual(
            analysis.BOOTSTRAP_SEED,
            20260826,
        )
        joined = " ".join(analysis.ANALYSIS_DEVIATIONS)
        self.assertIn(
            "not committed before model execution",
            joined,
        )
        self.assertIn(
            "did not record its numeric value",
            joined,
        )


if __name__ == "__main__":
    unittest.main()
