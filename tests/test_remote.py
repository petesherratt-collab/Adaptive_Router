import unittest

import requests

from remote import generate


CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openai/gpt-5.6-luna",
    "timeout_seconds": 90,
    "temperature": 0,
    "max_tokens": 256,
}


class Response:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "id": "generation-test",
            "model": "openai/gpt-5.6-luna",
            "choices": [
                {
                    "message": {"content": "Positive"},
                    "finish_reason": "stop",
                    "native_finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 3,
                "total_tokens": 15,
                "completion_tokens_details": {
                    "reasoning_tokens": 1,
                },
                "cost": 0.000006,
            },
        }


class Session:
    def __init__(self):
        self.url = None
        self.headers = None
        self.payload = None
        self.timeout = None

    def post(self, url, headers, json, timeout):
        self.url = url
        self.headers = headers
        self.payload = json
        self.timeout = timeout
        return Response()


class ErrorResponse:
    status_code = 429

    def raise_for_status(self):
        raise requests.HTTPError("rate limited")


class ErrorSession(Session):
    def post(self, url, headers, json, timeout):
        self.url = url
        self.headers = headers
        self.payload = json
        self.timeout = timeout
        return ErrorResponse()


class RemoteGenerationTests(unittest.TestCase):
    def test_missing_key_makes_no_request(self):
        result = generate("prompt", CONFIG, "")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "OPENROUTER_KEY_MISSING")
        self.assertEqual(result.model, CONFIG["model"])

    def test_records_usage_and_identity(self):
        session = Session()
        result = generate("Classify sentiment", CONFIG, "secret", session)

        self.assertTrue(result.success)
        self.assertEqual(result.text, "Positive")
        self.assertEqual(result.response_id, "generation-test")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.model, "openai/gpt-5.6-luna")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.native_finish_reason, "stop")
        self.assertEqual(result.prompt_tokens, 12)
        self.assertEqual(result.completion_tokens, 3)
        self.assertEqual(result.total_tokens, 15)
        self.assertEqual(result.reasoning_tokens, 1)
        self.assertEqual(result.cost, 0.000006)

        self.assertEqual(
            session.url,
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self.assertEqual(session.payload["temperature"], 0)
        self.assertEqual(session.payload["max_tokens"], 256)
        self.assertNotIn("secret", session.payload)

    def test_http_failure_records_status_without_body(self):
        result = generate("prompt", CONFIG, "secret", ErrorSession())

        self.assertFalse(result.success)
        self.assertEqual(result.error, "HTTPError")
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result.model, CONFIG["model"])


if __name__ == "__main__":
    unittest.main()
