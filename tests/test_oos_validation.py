import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import run_oos_validation as oos


REVISION = "0123456789abcdef"
TASK = {
    "task_id": "oos_test",
    "task_class": "format",
    "capability_family": "json_format",
    "normalization": "text",
    "prompt": "Output only: ok",
    "expected": "ok",
}


def result_local(text="ok"):
    return SimpleNamespace(
        success=True,
        text=text,
        ttft_ms=10.0,
        total_ms=20.0,
        tokens_per_second=50.0,
        error=None,
    )


def result_remote(text="ok", cost=0.001):
    return SimpleNamespace(
        success=True,
        text=text,
        model=oos.REMOTE_MODEL,
        response_id="response-1",
        status_code=200,
        finish_reason="stop",
        native_finish_reason="completed",
        prompt_tokens=10,
        completion_tokens=2,
        total_tokens=12,
        reasoning_tokens=0,
        cached_tokens=0,
        cache_write_tokens=0,
        cost=cost,
        router_metadata={"strategy": "direct"},
        cache_status=None,
        total_ms=100.0,
        error=None,
    )


def existing_record(
    rep=1,
    provider="ollama",
    model=oos.LOCAL_MODEL,
    revision=REVISION,
    benchmark_hash=oos.BENCHMARK_SHA256,
    cost=None,
):
    return {
        "task_id": TASK["task_id"],
        "rep": rep,
        "task_class": TASK["task_class"],
        "capability_family": TASK["capability_family"],
        "provider": provider,
        "requested_model": model,
        "returned_model": model,
        "benchmark_sha256": benchmark_hash,
        "code_revision": revision,
        "raw_output": "ok",
        "normalized_output": "ok",
        "oracle_correct": True,
        "validator": {
            "name": "benchmark_oracle_v2",
            "status": "PASS",
            "detail": None,
        },
        "validator_status": "PASS",
        "total_ms": 20.0,
        "success": True,
        "error": None,
        "cost": cost,
    }


def write_jsonl(path, records):
    Path(path).write_text(
        "".join(
            json.dumps(record, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


class OOSValidationTests(unittest.TestCase):
    def test_frozen_suite_loads(self):
        document = oos.load_suite()
        self.assertEqual(document["suite_id"], oos.SUITE_ID)
        self.assertEqual(len(document["tasks"]), 40)

    def test_expected_key_count_is_two_hundred(self):
        tasks = oos.load_suite()["tasks"]
        self.assertEqual(len(oos.expected_keys(tasks)), 200)

    def test_execution_flags_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            oos.main([
                "--execute-local",
                "--execute-remote",
            ])

    def test_existing_evidence_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            path.write_text("{broken\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "invalid JSON",
            ):
                oos.load_existing(
                    path,
                    [TASK],
                    "ollama",
                    oos.LOCAL_MODEL,
                    REVISION,
                )

    def test_existing_evidence_rejects_duplicate_key(self):
        record = existing_record()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            write_jsonl(path, [record, record])

            with self.assertRaisesRegex(
                ValueError,
                "duplicate",
            ):
                oos.load_existing(
                    path,
                    [TASK],
                    "ollama",
                    oos.LOCAL_MODEL,
                    REVISION,
                )

    def test_existing_evidence_rejects_identity_mismatches(self):
        cases = [
            (
                {"provider": "openrouter"},
                "wrong provider",
            ),
            (
                {"requested_model": "another-model"},
                "wrong model",
            ),
            (
                {"benchmark_sha256": "wrong"},
                "wrong benchmark",
            ),
            (
                {"code_revision": "wrong"},
                "another code revision",
            ),
            (
                {"capability_family": "priority"},
                "metadata mismatch",
            ),
        ]

        for changes, message in cases:
            with self.subTest(changes=changes):
                record = existing_record()
                record.update(changes)

                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "runs.jsonl"
                    write_jsonl(path, [record])

                    with self.assertRaisesRegex(
                        ValueError,
                        message,
                    ):
                        oos.load_existing(
                            path,
                            [TASK],
                            "ollama",
                            oos.LOCAL_MODEL,
                            REVISION,
                        )

    def test_local_resume_skips_completed_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "local.jsonl"
            summary = Path(directory) / "local-summary.json"
            write_jsonl(output, [existing_record(rep=1)])

            calls = []

            def fake_generate(prompt, config):
                calls.append((prompt, config["model"]))
                return result_local()

            with (
                patch.object(
                    oos,
                    "OBSERVATION_COUNT",
                    5,
                ),
                patch.object(
                    oos,
                    "code_revision",
                    return_value=REVISION,
                ),
            ):
                result = oos.run_local(
                    [TASK],
                    {"model": oos.LOCAL_MODEL},
                    output,
                    summary,
                    generate_fn=fake_generate,
                    residency_fn=lambda config: {
                        "resident": True,
                        "size_bytes": 1,
                    },
                )

            self.assertEqual(len(calls), 4)
            self.assertEqual(result["observation_count"], 5)
            self.assertEqual(result["pass_count"], 5)
            self.assertEqual(
                len(output.read_text(
                    encoding="utf-8"
                ).splitlines()),
                5,
            )

    def test_remote_resume_and_cost_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "remote.jsonl"
            summary = Path(directory) / "remote-summary.json"
            calls = []

            def fake_generate(prompt, config, api_key):
                calls.append((prompt, config["model"], api_key))
                return result_remote()

            with (
                patch.object(
                    oos,
                    "OBSERVATION_COUNT",
                    5,
                ),
                patch.object(
                    oos,
                    "code_revision",
                    return_value=REVISION,
                ),
            ):
                result = oos.run_remote(
                    [TASK],
                    "secret",
                    output,
                    summary,
                    generate_fn=fake_generate,
                )

            self.assertEqual(len(calls), 5)
            self.assertEqual(result["observation_count"], 5)
            self.assertAlmostEqual(result["total_cost"], 0.005)
            self.assertEqual(
                result["returned_models"],
                {oos.REMOTE_MODEL: 5},
            )

    def test_missing_remote_key_makes_no_request(self):
        calls = []

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(
                oos,
                "code_revision",
                return_value=REVISION,
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "OPENROUTER_API_KEY",
            ):
                oos.run_remote(
                    [TASK],
                    None,
                    Path(directory) / "remote.jsonl",
                    Path(directory) / "summary.json",
                    generate_fn=lambda *args: calls.append(args),
                )

        self.assertEqual(calls, [])

    def test_existing_cost_stop_makes_no_request(self):
        record = existing_record(
            provider="openrouter",
            model=oos.REMOTE_MODEL,
            cost=oos.MAX_COST_USD,
        )
        calls = []

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "remote.jsonl"
            summary = Path(directory) / "summary.json"
            write_jsonl(output, [record])

            with patch.object(
                oos,
                "code_revision",
                return_value=REVISION,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "cost stop",
                ):
                    oos.run_remote(
                        [TASK],
                        "secret",
                        output,
                        summary,
                        generate_fn=lambda *args: calls.append(
                            args
                        ),
                    )

        self.assertEqual(calls, [])

    def test_incomplete_run_cannot_have_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "local.jsonl"
            summary = Path(directory) / "summary.json"
            summary.write_text("{}\n", encoding="utf-8")

            with patch.object(
                oos,
                "code_revision",
                return_value=REVISION,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "summary exists",
                ):
                    oos.run_local(
                        [TASK],
                        {"model": oos.LOCAL_MODEL},
                        output,
                        summary,
                        generate_fn=lambda *args: result_local(),
                        residency_fn=lambda config: {},
                    )

    def test_existing_summary_must_match_evidence(self):
        records = [
            existing_record(rep=rep)
            for rep in range(1, 6)
        ]

        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.json"
            summary.write_text(
                '{"wrong":true}\n',
                encoding="utf-8",
            )

            with patch.object(
                oos,
                "OBSERVATION_COUNT",
                5,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "does not match evidence",
                ):
                    oos.finish_summary(
                        records,
                        summary,
                        "ollama",
                        oos.LOCAL_MODEL,
                    )

    def test_jsonl_writer_uses_lf_not_crlf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.jsonl"

            with path.open("a", encoding="utf-8") as handle:
                oos.append_record(
                    handle,
                    existing_record(),
                )

            self.assertNotIn(b"\r\n", path.read_bytes())


if __name__ == "__main__":
    unittest.main()
