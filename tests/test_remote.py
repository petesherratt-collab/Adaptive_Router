import unittest

import requests

from remote import generate


CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openai/gpt-5.6-luna",
    "timeout_seconds": 90,
    "temperature": 0,
    "max_tokens": 256,
    "maximum_attempts": 2,
    "retry_backoff_seconds": 0.25,
}


class Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.headers = {"X-OpenRouter-Cache-Status": "MISS"}
        self.body = body if body is not None else self.success_body()

    @staticmethod
    def success_body():
        return {
            "id": "generation-test",
            "model": "openai/gpt-5.6-luna",
            "openrouter_metadata": {
                "provider_name": "test-provider",
            },
            "choices": [
                {
                    "message": {"content": "Positive"},
                    "finish_reason": "stop",
                    "native_finish_reason": "completed",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 3,
                "total_tokens": 15,
                "prompt_tokens_details": {
                    "cached_tokens": 4,
                    "cache_write_tokens": 0,
                },
                "completion_tokens_details": {
                    "reasoning_tokens": 1,
                },
                "cost": 0.000006,
            },
        }

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("request failed")

    def json(self):
        return self.body


class Session:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [Response()])
        self.url = None
        self.headers = None
        self.payload = None
        self.timeout = None
        self.calls = 0

    def post(self, url, headers, json, timeout):
        self.url = url
        self.headers = headers
        self.payload = json
        self.timeout = timeout
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RemoteGenerationTests(unittest.TestCase):
    def test_missing_key_makes_no_request(self):
        session = Session()
        result = generate("prompt", CONFIG, "", session)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "OPENROUTER_KEY_MISSING")
        self.assertEqual(result.model, CONFIG["model"])
        self.assertEqual(result.attempt_count, 0)
        self.assertEqual(session.calls, 0)

    def test_records_usage_identity_routing_cache_and_attempts(self):
        session = Session()
        result = generate(
            "Classify sentiment",
            CONFIG,
            "secret",
            session,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.text, "Positive")
        self.assertEqual(result.response_id, "generation-test")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.model, "openai/gpt-5.6-luna")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.native_finish_reason, "completed")
        self.assertEqual(result.prompt_tokens, 12)
        self.assertEqual(result.completion_tokens, 3)
        self.assertEqual(result.total_tokens, 15)
        self.assertEqual(result.reasoning_tokens, 1)
        self.assertEqual(result.cached_tokens, 4)
        self.assertEqual(result.cache_write_tokens, 0)
        self.assertEqual(result.cost, 0.000006)
        self.assertEqual(
            result.router_metadata,
            {"provider_name": "test-provider"},
        )
        self.assertEqual(result.cache_status, "MISS")
        self.assertEqual(result.attempt_count, 1)
        self.assertEqual(result.retry_count, 0)

        self.assertEqual(
            session.url,
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self.assertEqual(session.payload["temperature"], 0)
        self.assertEqual(session.payload["max_tokens"], 256)
        self.assertEqual(
            session.headers["X-OpenRouter-Metadata"],
            "enabled",
        )
        self.assertNotIn("secret", session.payload)

    def test_metadata_excludes_text_and_includes_attempts(self):
        result = generate(
            "Classify sentiment",
            CONFIG,
            "secret",
            Session(),
        )

        metadata = result.metadata()

        self.assertNotIn("text", metadata)
        self.assertEqual(metadata["response_id"], "generation-test")
        self.assertEqual(metadata["cached_tokens"], 4)
        self.assertEqual(metadata["attempt_count"], 1)
        self.assertEqual(metadata["retry_count"], 0)

    def test_rate_limit_retries_once_then_succeeds(self):
        session = Session([Response(429), Response()])
        delays = []
        result = generate(
            "prompt",
            CONFIG,
            "secret",
            session,
            sleep_fn=delays.append,
        )

        self.assertTrue(result.success)
        self.assertEqual(session.calls, 2)
        self.assertEqual(delays, [0.25])
        self.assertEqual(result.attempt_count, 2)
        self.assertEqual(result.retry_count, 1)

    def test_retryable_http_failure_stops_at_bound(self):
        session = Session([Response(503), Response(503)])
        delays = []
        result = generate(
            "prompt",
            CONFIG,
            "secret",
            session,
            sleep_fn=delays.append,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "OPENROUTER_HTTP_503")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.attempt_count, 2)
        self.assertEqual(result.retry_count, 1)
        self.assertEqual(session.calls, 2)
        self.assertEqual(delays, [0.25])

    def test_non_retryable_http_failure_is_not_retried(self):
        session = Session([Response(400), Response()])
        result = generate(
            "prompt",
            CONFIG,
            "secret",
            session,
            sleep_fn=lambda delay: self.fail("unexpected sleep"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "OPENROUTER_HTTP_400")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.attempt_count, 1)
        self.assertEqual(session.calls, 1)

    def test_timeout_retries_once_then_succeeds(self):
        session = Session([requests.Timeout("slow"), Response()])
        delays = []
        result = generate(
            "prompt",
            CONFIG,
            "secret",
            session,
            sleep_fn=delays.append,
        )

        self.assertTrue(result.success)
        self.assertEqual(session.calls, 2)
        self.assertEqual(delays, [0.25])
        self.assertEqual(result.retry_count, 1)

    def test_connection_error_has_stable_code(self):
        session = Session(
            [
                requests.ConnectionError("offline"),
                requests.ConnectionError("offline"),
            ]
        )
        result = generate(
            "prompt",
            CONFIG,
            "secret",
            session,
            sleep_fn=lambda delay: None,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "OPENROUTER_CONNECTION_ERROR")
        self.assertEqual(result.attempt_count, 2)

    def test_invalid_success_body_is_not_retried(self):
        session = Session([Response(body={"choices": []}), Response()])
        result = generate(
            "prompt",
            CONFIG,
            "secret",
            session,
            sleep_fn=lambda delay: self.fail("unexpected sleep"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "OPENROUTER_RESPONSE_INVALID")
        self.assertEqual(result.attempt_count, 1)
        self.assertEqual(session.calls, 1)

    def test_invalid_retry_configuration_makes_no_request(self):
        config = dict(CONFIG, maximum_attempts=0)
        session = Session()
        result = generate("prompt", config, "secret", session)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "OPENROUTER_CONFIG_ERROR")
        self.assertEqual(result.attempt_count, 0)
        self.assertEqual(session.calls, 0)


if __name__ == "__main__":
    unittest.main()
