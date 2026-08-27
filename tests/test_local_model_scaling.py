import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import run_local_model_scaling as scaling


REVISION = "0123456789abcdef"

TASK = {
    "task_id": "scaling_test",
    "task_class": "format",
    "capability_family": "json_format",
    "normalization": "text",
    "prompt": "Output only: ok",
    "expected": "ok",
}


def local_result(text="ok"):
    return SimpleNamespace(
        success=True,
        text=text,
        ttft_ms=10.0,
        total_ms=20.0,
        tokens_per_second=50.0,
        error=None,
    )


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return FakeResponse(self.payload)


class LocalModelScalingTests(unittest.TestCase):
    def test_model_order_and_exact_identities_are_frozen(self):
        self.assertEqual(
            scaling.MODEL_ORDER,
            ("gemma3:1b", "gemma3:4b"),
        )
        self.assertEqual(
            scaling.MODEL_SPECS["gemma3:1b"]["digest"],
            (
                "8648f39daa8fbf5b18c7b4e6a8fb4990"
                "c692751d49917417b8842ca5758e7ffc"
            ),
        )
        self.assertEqual(
            scaling.MODEL_SPECS["gemma3:4b"]["digest"],
            (
                "a2af6cc3eb7fa8be8504abaf9b04e88f"
                "17a119ec3f04a3addf55f92841195f5a"
            ),
        )

    def test_outputs_cannot_collide_with_frozen_oos_files(self):
        frozen = {
            scaling.oos.LOCAL_OUTPUT.resolve(),
            scaling.oos.LOCAL_SUMMARY.resolve(),
            scaling.oos.REMOTE_OUTPUT.resolve(),
            scaling.oos.REMOTE_SUMMARY.resolve(),
        }
        scaling_paths = {
            spec[key].resolve()
            for spec in scaling.MODEL_SPECS.values()
            for key in ("output", "summary")
        }

        self.assertTrue(frozen.isdisjoint(scaling_paths))
        self.assertEqual(len(scaling_paths), 4)

    def test_fetch_installed_identity_normalizes_tags_response(self):
        spec = scaling.MODEL_SPECS["gemma3:1b"]
        session = FakeSession({
            "models": [{
                "name": spec["name"],
                "digest": spec["digest"],
                "size": spec["package_size_bytes"],
                "details": {
                    "parameter_size": spec["parameter_size"],
                    "quantization_level": (
                        spec["quantization_level"]
                    ),
                    "format": spec["format"],
                    "family": spec["family"],
                },
            }],
        })

        actual = scaling.fetch_installed_identity(
            spec["name"],
            "http://localhost:11434",
            session=session,
        )

        self.assertEqual(actual, scaling.public_identity(spec))
        self.assertEqual(
            session.calls,
            [("http://localhost:11434/api/tags", 5)],
        )

    def test_missing_installed_model_is_rejected(self):
        session = FakeSession({"models": []})

        with self.assertRaisesRegex(ValueError, "not installed"):
            scaling.fetch_installed_identity(
                "gemma3:1b",
                "http://localhost:11434",
                session=session,
            )

    def test_identity_mismatch_is_rejected(self):
        spec = scaling.MODEL_SPECS["gemma3:1b"]
        changed = scaling.public_identity(spec)
        changed["digest"] = "wrong"

        with self.assertRaisesRegex(
            ValueError,
            "identity mismatch",
        ):
            scaling.verify_installed_identity(changed, spec)

    def test_existing_record_requires_comparison_identity(self):
        spec = scaling.MODEL_SPECS["gemma3:1b"]
        record = {
            "task_id": TASK["task_id"],
            "rep": 1,
            "task_class": TASK["task_class"],
            "capability_family": TASK["capability_family"],
            "provider": "ollama",
            "requested_model": spec["name"],
            "returned_model": spec["name"],
            "benchmark_sha256": scaling.oos.BENCHMARK_SHA256,
            "code_revision": REVISION,
            "comparison_id": "wrong",
            "model_identity": scaling.public_identity(spec),
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            path.write_text(
                json.dumps(record) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "comparison_id",
            ):
                scaling.load_existing(
                    path,
                    [TASK],
                    spec,
                    REVISION,
                )

    def test_summary_separates_residency_states_and_sizes(self):
        spec = scaling.MODEL_SPECS["gemma3:1b"]
        base = {
            "task_id": TASK["task_id"],
            "task_class": TASK["task_class"],
            "capability_family": TASK["capability_family"],
            "provider": "ollama",
            "requested_model": spec["name"],
            "returned_model": spec["name"],
            "raw_output": "ok",
            "oracle_correct": True,
            "success": True,
            "error": None,
            "ttft_ms": 10.0,
            "total_ms": 20.0,
            "tokens_per_second": 50.0,
        }
        resident = {
            **base,
            "rep": 1,
            "model_residency": {
                "resident": True,
                "size_bytes": 700,
            },
        }
        nonresident = {
            **base,
            "rep": 2,
            "ttft_ms": 100.0,
            "total_ms": 200.0,
            "model_residency": {
                "resident": False,
                "size_bytes": None,
            },
        }
        unknown = {
            **base,
            "rep": 3,
            "model_residency": {
                "resident": None,
                "size_bytes": None,
            },
        }

        summary = scaling.make_summary(
            [resident, nonresident, unknown],
            spec,
        )

        self.assertEqual(summary["resident_observation_count"], 1)
        self.assertEqual(
            summary["nonresident_observation_count"],
            1,
        )
        self.assertEqual(
            summary["unknown_residency_observation_count"],
            1,
        )
        self.assertEqual(summary["resident_median_total_ms"], 20.0)
        self.assertEqual(
            summary["nonresident_median_total_ms"],
            200.0,
        )
        self.assertEqual(summary["resident_sizes_bytes"], [700])

    def test_run_writes_identity_and_safely_resumes(self):
        original = scaling.MODEL_SPECS["gemma3:1b"]
        calls = []

        with tempfile.TemporaryDirectory() as directory:
            spec = copy.copy(original)
            spec["output"] = Path(directory) / "runs.jsonl"
            spec["summary"] = Path(directory) / "summary.json"

            def fake_generate(prompt, config):
                calls.append((prompt, config["model"]))
                return local_result()

            with (
                patch.object(
                    scaling.oos,
                    "OBSERVATION_COUNT",
                    2,
                ),
                patch.object(
                    scaling.oos,
                    "REPS",
                    2,
                ),
                patch.object(
                    scaling.oos,
                    "code_revision",
                    return_value=REVISION,
                ),
            ):
                summary = scaling.run_model(
                    [TASK],
                    spec,
                    {
                        "model": spec["name"],
                        "base_url": "http://localhost:11434",
                    },
                    generate_fn=fake_generate,
                    residency_fn=lambda config: {
                        "resident": True,
                        "size_bytes": 700,
                    },
                    identity_fn=lambda model, base_url: (
                        scaling.public_identity(spec)
                    ),
                )

                first_call_count = len(calls)

                repeated = scaling.run_model(
                    [TASK],
                    spec,
                    {
                        "model": spec["name"],
                        "base_url": "http://localhost:11434",
                    },
                    generate_fn=fake_generate,
                    residency_fn=lambda config: {
                        "resident": True,
                        "size_bytes": 700,
                    },
                    identity_fn=lambda model, base_url: (
                        scaling.public_identity(spec)
                    ),
                )

            self.assertEqual(first_call_count, 2)
            self.assertEqual(len(calls), 2)
            self.assertEqual(summary, repeated)
            self.assertEqual(summary["pass_count"], 2)

            records = [
                json.loads(line)
                for line in spec["output"].read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(len(records), 2)
            self.assertTrue(all(
                record["comparison_id"]
                == scaling.COMPARISON_ID
                for record in records
            ))
            self.assertTrue(all(
                record["model_identity"]
                == scaling.public_identity(spec)
                for record in records
            ))

    def test_wrong_configuration_makes_no_identity_request(self):
        spec = scaling.MODEL_SPECS["gemma3:1b"]
        identity_calls = []

        with self.assertRaisesRegex(
            ValueError,
            "configuration",
        ):
            scaling.run_model(
                [TASK],
                spec,
                {
                    "model": "wrong",
                    "base_url": "http://localhost:11434",
                },
                identity_fn=lambda *args: identity_calls.append(args),
            )

        self.assertEqual(identity_calls, [])

    def test_4b_order_gate_precedes_identity_and_generation(self):
        spec = scaling.MODEL_SPECS["gemma3:4b"]
        identity_calls = []
        generation_calls = []

        with (
            patch.object(
                scaling.oos,
                "code_revision",
                return_value=REVISION,
            ),
            patch.object(
                scaling,
                "require_completed_1b",
                side_effect=RuntimeError("1B required"),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "1B required",
            ):
                scaling.run_model(
                    [TASK],
                    spec,
                    {
                        "model": spec["name"],
                        "base_url": "http://localhost:11434",
                    },
                    generate_fn=lambda *args: (
                        generation_calls.append(args)
                    ),
                    identity_fn=lambda *args: (
                        identity_calls.append(args)
                    ),
                )

        self.assertEqual(identity_calls, [])
        self.assertEqual(generation_calls, [])

    def test_existing_mismatched_summary_is_rejected(self):
        spec = scaling.MODEL_SPECS["gemma3:1b"]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            path.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "does not match",
            ):
                scaling.verify_existing_summary(
                    path,
                    {"expected": True},
                )


if __name__ == "__main__":
    unittest.main()
