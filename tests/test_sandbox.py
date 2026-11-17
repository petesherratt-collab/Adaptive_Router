import unittest

import sandbox


class CheckSourceTests(unittest.TestCase):
    def test_accepts_plain_function_with_allowed_import(self):
        source = "import re\ndef solve(s):\n    return re.sub('a', 'b', s)\n"
        self.assertEqual(sandbox.check_source(source), (True, "OK"))

    def test_rejections(self):
        cases = {
            "": "EMPTY_SOURCE",
            "def solve(:\n": "SYNTAX_ERROR",
            "def other():\n    return 1\n": "ENTRY_POINT_MISSING",
            "print(1)\ndef solve():\n    return 1\n": "TOP_LEVEL_STATEMENT",
            "import os\ndef solve():\n    return 1\n": "MODULE_NOT_ALLOWED",
            "def solve():\n    import socket\n": "MODULE_NOT_ALLOWED",
            "from re import _compile\ndef solve():\n    return 1\n": "PRIVATE_NAME",
            "def solve():\n    return ().__class__\n": "PRIVATE_NAME",
            "def solve():\n    return __builtins__\n": "PRIVATE_NAME",
            "class A:\n    pass\ndef solve():\n    return 1\n": "TOP_LEVEL_STATEMENT",
            "def solve():\n    class A:\n        pass\n": "BANNED_CONSTRUCT",
            "def solve():\n    with x:\n        pass\n": "BANNED_CONSTRUCT",
            "x" * (sandbox.MAX_SOURCE_CHARS + 1): "SOURCE_TOO_LONG",
        }
        for source, reason in cases.items():
            with self.subTest(reason=reason, source=source[:30]):
                self.assertEqual(sandbox.check_source(source), (False, reason))


class RunFunctionTests(unittest.TestCase):
    def run_one(self, source, args=()):
        return sandbox.run_function(source, [list(args)], timeout_seconds=1.0, cpu_seconds=1)

    def test_returns_json_values_per_call(self):
        result = sandbox.run_function(
            "def solve(a, b):\n    return (a + b, [a])\n", [[1, 2], [3, 4]]
        )
        self.assertTrue(result.ok)
        self.assertEqual(
            [r["value"] for r in result.results], [[3, [1]], [7, [3]]]
        )

    def test_exception_is_a_failed_call_not_a_crash(self):
        result = sandbox.run_function(
            "def solve(a):\n    return 1 // a\n", [[0], [1]]
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.results[0], {"ok": False, "error": "ZeroDivisionError"})
        self.assertEqual(result.results[1], {"ok": True, "value": 1})

    def test_non_json_and_non_finite_values_fail(self):
        self.assertFalse(self.run_one("def solve():\n    return {1, 2}\n").results[0]["ok"])
        self.assertFalse(
            self.run_one("import math\ndef solve():\n    return math.inf\n").results[0]["ok"]
        )

    def test_dangerous_builtins_are_absent(self):
        for call in ("open('/etc/passwd')", "eval('1')", "getattr(1, 'real')", "print(1)"):
            with self.subTest(call=call):
                result = self.run_one(f"def solve():\n    return {call}\n")
                self.assertEqual(result.results[0], {"ok": False, "error": "NameError"})

    def test_module_proxy_hides_submodules(self):
        result = self.run_one("import re\ndef solve():\n    return re.enum\n")
        self.assertEqual(result.results[0], {"ok": False, "error": "AttributeError"})

    def test_infinite_loop_times_out(self):
        result = self.run_one("def solve():\n    while True:\n        pass\n")
        self.assertFalse(result.ok)
        self.assertIn(result.error, {"SANDBOX_TIMEOUT", "SANDBOX_CRASHED"})

    def test_memory_bomb_does_not_succeed(self):
        result = self.run_one("def solve():\n    return 'x' * 10 ** 10\n")
        self.assertFalse(result.ok and result.results[0]["ok"])

    def test_static_rejection_short_circuits(self):
        result = self.run_one("import os\ndef solve():\n    return 1\n")
        self.assertEqual((result.ok, result.error), (False, "MODULE_NOT_ALLOWED"))

    def test_canonical_is_type_strict(self):
        self.assertNotEqual(sandbox.canonical(True), sandbox.canonical(1))
        self.assertNotEqual(sandbox.canonical(1), sandbox.canonical(1.0))
        self.assertEqual(sandbox.canonical({"b": 1, "a": 2}), sandbox.canonical({"a": 2, "b": 1}))


if __name__ == "__main__":
    unittest.main()
