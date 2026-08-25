import json
from pathlib import Path
import tempfile
import unittest

from remote import RemoteResult
from run_remote_benchmark import (
    MODEL,
    load_existing,
    run_remote,
    write_remote_summary,
)


TASKS = [
    {
        "task_id": "sentiment",
        "task_class": "classification",
        "normalization": "text",
        "prompt": "Classify this sentiment: excellent",
        "expected": "positive",
    },
    {
        "task_id": "reverse",
        "task_class": "transform",
        "normalization": "text",
        "prompt": "Reverse abc",
        "expected": "cba",
    },
]


def successful_result(text, response_id, cost=0.00001):
    return RemoteResult(
        True,
        text=text,
        total_ms=125.0,
        model=MODEL,
        response_id=response_id,
        status_code=200,
        finish_reason="stop",
        native_finish_reason="completed",
        prompt_tokens=10,
        completion_tokens=2,
        total_tokens=12,
        reasoning_tokens=0,
        cost=cost,
    )


class Generator:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = 0

    def __call__(self, prompt, config, api_key):
        self.calls += 1
        self.last_prompt = prompt
        self.last_config = config
        self.last_api_key = api_key
        return next(self.outputs)


class RemoteBenchmarkTests(unittest.TestCase):
    def test_writes_complete_auditable_record(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            generator = Generator([
                successful_result("Positive", "gen-1"),
            ])

            records = run_remote(
                TASKS[:1],
                "secret",
                output_path=output,
                reps=1,
                generate_fn=generator,
            )

            self.assertEqual(len(records), 1)
            record = records[0]

            self.assertEqual(record["task_id"], "sentiment")
            self.assertEqual(record["rep"], 1)
            self.assertEqual(record["requested_model"], MODEL)
            self.assertEqual(record["returned_model"], MODEL)
            self.assertEqual(record["raw_output"], "Positive")
            self.assertEqual(record["normalized_output"], "positive")
            self.assertTrue(record["oracle_correct"])
            self.assertEqual(record["validator_status"], "PASS")
            self.assertEqual(record["response_id"], "gen-1")
            self.assertEqual(record["prompt_tokens"], 10)
            self.assertEqual(record["completion_tokens"], 2)
            self.assertEqual(record["total_tokens"], 12)
            self.assertEqual(record["cost"], 0.00001)
            self.assertIn("benchmark_sha256", record)
            self.assertIn("code_revision", record)
            self.assertNotIn("secret", json.dumps(record))
            self.assertEqual(generator.calls, 1)

            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), record)

    def test_resume_skips_completed_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"

            first_generator = Generator([
                successful_result("Positive", "gen-1"),
            ])
            run_remote(
                TASKS[:1],
                "secret",
                output_path=output,
                reps=1,
                generate_fn=first_generator,
            )

            second_generator = Generator([
                successful_result("Positive", "gen-2"),
            ])
            records = run_remote(
                TASKS[:1],
                "secret",
                output_path=output,
                reps=2,
                generate_fn=second_generator,
            )

            self.assertEqual(len(records), 2)
            self.assertEqual(second_generator.calls, 1)
            self.assertEqual(
                {(record["task_id"], record["rep"]) for record in records},
                {("sentiment", 1), ("sentiment", 2)},
            )

    def test_duplicate_existing_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            record = {
                "task_id": "sentiment",
                "rep": 1,
                "requested_model": MODEL,
            }
            line = json.dumps(record) + "\n"
            output.write_text(line + line, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_existing(output, TASKS[:1], reps=1)

    def test_other_requested_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            output.write_text(
                json.dumps({
                    "task_id": "sentiment",
                    "rep": 1,
                    "requested_model": "another/model",
                }) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "another requested model"):
                load_existing(output, TASKS[:1], reps=1)

    def test_existing_cost_stop_prevents_request(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            output.write_text(
                json.dumps({
                    "task_id": "sentiment",
                    "rep": 1,
                    "requested_model": MODEL,
                    "cost": 0.10,
                }) + "\n",
                encoding="utf-8",
            )
            generator = Generator([
                successful_result("Positive", "must-not-run"),
            ])

            with self.assertRaisesRegex(RuntimeError, "cost stop"):
                run_remote(
                    TASKS[:1],
                    "secret",
                    output_path=output,
                    reps=2,
                    max_cost_usd=0.10,
                    generate_fn=generator,
                )

            self.assertEqual(generator.calls, 0)

    def test_missing_key_prevents_request(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            generator = Generator([
                successful_result("Positive", "must-not-run"),
            ])

            with self.assertRaisesRegex(
                ValueError,
                "OPENROUTER_API_KEY",
            ):
                run_remote(
                    TASKS[:1],
                    "",
                    output_path=output,
                    reps=1,
                    generate_fn=generator,
                )

            self.assertEqual(generator.calls, 0)
            self.assertFalse(output.exists())

    def test_summary_aggregates_reported_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            summary_path = Path(directory) / "summary.json"
            generator = Generator([
                successful_result("Positive", "gen-1", cost=0.00001),
                successful_result("abc", "gen-2", cost=0.00002),
            ])

            records = run_remote(
                TASKS,
                "secret",
                output_path=output,
                reps=1,
                generate_fn=generator,
            )
            summary = write_remote_summary(records, summary_path)

            self.assertEqual(summary["observation_count"], 2)
            self.assertEqual(summary["overall_pass_count"], 1)
            self.assertEqual(summary["successful_response_count"], 2)
            self.assertEqual(summary["total_prompt_tokens"], 20)
            self.assertEqual(summary["total_completion_tokens"], 4)
            self.assertEqual(summary["total_tokens"], 24)
            self.assertAlmostEqual(summary["total_cost"], 0.00003)
            self.assertEqual(summary["returned_models"], {MODEL: 2})
            self.assertEqual(summary["finish_reasons"], {"stop": 2})

            written = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(written, summary)


if __name__ == "__main__":
    unittest.main()
