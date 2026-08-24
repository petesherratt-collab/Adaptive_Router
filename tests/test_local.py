import unittest

from local import model_residency


CONFIG = {"base_url": "http://localhost:11434", "model": "gemma3:1b", "timeout_seconds": 45}


class Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class Session:
    def __init__(self, body):
        self.body = body
        self.url = None
        self.timeout = None

    def get(self, url, timeout):
        self.url, self.timeout = url, timeout
        return Response(self.body)


class ModelResidencyTests(unittest.TestCase):
    def test_reports_matching_loaded_model_and_size(self):
        session = Session({"models": [{"name": "gemma3:1b", "size": 880000000}]})
        self.assertEqual(
            model_residency(CONFIG, session),
            {"resident": True, "size_bytes": 880000000},
        )
        self.assertEqual(session.url, "http://localhost:11434/api/ps")
        self.assertEqual(session.timeout, 2)

    def test_non_matching_model_is_not_resident(self):
        session = Session({"models": [{"name": "other:latest", "size": 123}]})
        self.assertEqual(
            model_residency(CONFIG, session),
            {"resident": False, "size_bytes": None},
        )


if __name__ == "__main__":
    unittest.main()
