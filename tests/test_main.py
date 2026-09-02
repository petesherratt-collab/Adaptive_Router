import io
import unittest
from contextlib import redirect_stdout

from main import build_parser, show
from remote import RemoteResult


class MainOutputTests(unittest.TestCase):
    def test_remote_failure_preserves_initial_decision(self):
        result = {
            "text": "",
            "route": "remote",
            "reason": "REMOTE_ERROR",
            "trigger": "REMOTE_DEFAULT_TASK",
            "local": None,
            "remote": RemoteResult(False, error="OPENROUTER_KEY_MISSING"),
        }
        output = io.StringIO()
        with redirect_stdout(output):
            show(result)
        self.assertIn(
            "[initial decision: REMOTE_DEFAULT_TASK]", output.getvalue()
        )
        self.assertIn(
            "[remote failure: OPENROUTER_KEY_MISSING]", output.getvalue()
        )

    def test_deterministic_result_is_displayed(self):
        result = {
            "text": "northstar5",
            "route": "deterministic",
            "reason": "DETERMINISTIC_EXECUTED",
            "local": None,
            "remote": None,
        }
        output = io.StringIO()
        with redirect_stdout(output):
            show(result)
        self.assertIn("[route: DETERMINISTIC]", output.getvalue())
        self.assertIn("[reason: DETERMINISTIC_EXECUTED]", output.getvalue())
        self.assertTrue(output.getvalue().rstrip().endswith("northstar5"))

    def test_prompt_and_request_file_are_mutually_exclusive(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["--prompt", "rewrite this", "--request-json", "request.json"]
            )


if __name__ == "__main__":
    unittest.main()
