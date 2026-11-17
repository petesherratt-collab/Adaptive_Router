import json
from pathlib import Path
import tempfile
import unittest

import fast_path_real_bench as real


def write(folder, name, data):
    Path(folder, name).write_text(json.dumps(data), encoding="utf-8")


GOOD = {
    "name": "doubles",
    "description": "Double the number n and return it as a number.",
    "jobs": [{"inputs": {"n": i}, "answer": i * 2} for i in range(6)],
}


class RealBenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_loads_tasks_and_skips_examples(self):
        write(self.tmp.name, "doubles.json", GOOD)
        write(self.tmp.name, "example_x.json", {**GOOD, "name": "example_x"})
        shapes = real.load_all(self.tmp.name, include_examples=False)
        self.assertEqual([s["name"] for s in shapes], ["doubles"])
        self.assertEqual(len(real.load_all(self.tmp.name, include_examples=True)), 2)
        shape = shapes[0]
        instances = real.stream(shape)
        self.assertEqual(instances[2], ({"n": 2}, {}))
        self.assertEqual(real.gold(shape, instances)[3], {"result": 6})

    def test_format_errors_are_explained(self):
        cases = [
            ({**GOOD, "extra": 1}, "exactly the keys name"),
            ({**GOOD, "name": "bad name"}, "letters, digits"),
            ({**GOOD, "jobs": GOOD["jobs"][:3]}, "at least 5 jobs"),
            ({**GOOD, "jobs": GOOD["jobs"] + [{"inputs": {"m": 1}, "answer": 2}]}, "different input keys"),
            ({**GOOD, "description": "Double the value and return it, please."}, "never names the input 'n'"),
            ({**GOOD, "jobs": [{"inputs": {"n": 1}}] * 5}, "exactly the keys inputs, answer"),
        ]
        for data, message in cases:
            with self.subTest(message=message):
                write(self.tmp.name, "t.json", data)
                with self.assertRaises(real.RealTaskError) as caught:
                    real.load_task(Path(self.tmp.name, "t.json"))
                self.assertIn(message, str(caught.exception))

    def test_shipped_example_is_valid(self):
        shape = real.load_task(Path(real.__file__).resolve().parent / "real_tasks" / "example_invoice_check.json")
        self.assertEqual(len(shape["jobs"]), 5)


if __name__ == "__main__":
    unittest.main()
