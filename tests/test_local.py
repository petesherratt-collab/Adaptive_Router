import json
import unittest

from local import generate, model_residency


CONFIG = {
    "base_url": "http://localhost:11434",
    "model": "gemma3:1b",
    "timeout_seconds": 45,
}


class Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class Session:
    def __init__(self, body, stream_body=None):
        self.body = body
        self.stream_body = stream_body if stream_body is not None else []
        self.url = None
        self.timeout = None
        self.payload = None

    def get(self, url, timeout):
        self.url, self.timeout = url, timeout
        return Response(self.body)

    def post(self, url, json, timeout, stream):
        self.url, self.timeout, self.payload = url, timeout, json
        return ResponseStream(self.stream_body)


class ResponseStream:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def iter_lines(self):
        return [json.dumps(item).encode("utf-8") for item in self.body]


class ModelResidencyTests(unittest.TestCase):
    def test_reports_matching_loaded_model_and_size(self):
        session = Session(
            {"models": [{"name": "gemma3:1b", "size": 880000000}]}
        )
        self.assertEqual(
            model_residency(CONFIG, session),
            {"resident": True, "size_bytes": 880000000},
        )
        self.assertEqual(session.url, "http://localhost:11434/api/ps")
        self.assertEqual(session.timeout, 2)

    def test_non_matching_model_is_not_resident(self):
        session = Session(
            {"models": [{"name": "other:latest", "size": 123}]}
        )
        self.assertEqual(
            model_residency(CONFIG, session),
            {"resident": False, "size_bytes": None},
        )


class GenerateMetricsTests(unittest.TestCase):
    def test_empty_output_has_unavailable_tokens_per_second(self):
        session = Session(
            {},
            [
                {
                    "response": "",
                    "done": True,
                    "eval_count": 1,
                    "eval_duration": 1,
                }
            ],
        )
        result = generate("prompt", CONFIG, session)
        self.assertIsNone(result.tokens_per_second)

    def test_no_token_output_has_unavailable_tokens_per_second(self):
        session = Session(
            {},
            [
                {
                    "response": "ignored",
                    "done": True,
                    "eval_count": 0,
                    "eval_duration": 1,
                }
            ],
        )
        result = generate("prompt", CONFIG, session)
        self.assertIsNone(result.tokens_per_second)

    def test_live_options_match_frozen_generation_settings(self):
        config = {
            **CONFIG,
            "temperature": 0,
            "max_tokens": 256,
            "keep_alive": -1,
        }
        session = Session(
            {},
            [
                {
                    "response": "ok",
                    "done": True,
                    "eval_count": 1,
                    "eval_duration": 1,
                }
            ],
        )

        result = generate("prompt", config, session)

        self.assertTrue(result.success)
        self.assertEqual(
            session.payload,
            {
                "model": "gemma3:1b",
                "prompt": "prompt",
                "stream": True,
                "options": {"temperature": 0, "num_predict": 256},
                "keep_alive": -1,
            },
        )

    def test_optional_generation_settings_are_not_invented(self):
        session = Session(
            {},
            [
                {
                    "response": "ok",
                    "done": True,
                    "eval_count": 1,
                    "eval_duration": 1,
                }
            ],
        )

        result = generate("prompt", CONFIG, session)

        self.assertTrue(result.success)
        self.assertNotIn("options", session.payload)
        self.assertNotIn("keep_alive", session.payload)


if __name__ == "__main__":
    unittest.main()
