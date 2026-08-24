import io
import unittest
from contextlib import redirect_stdout

from main import show
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
        self.assertIn("[initial decision: REMOTE_DEFAULT_TASK]", output.getvalue())
        self.assertIn("[remote failure: OPENROUTER_KEY_MISSING]", output.getvalue())


if __name__ == "__main__":
    unittest.main()
