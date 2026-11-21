import unittest

import fast_path_ceiling_v3 as ceiling
import fast_path_code_only_v1 as code_only
import fast_path_planned_bench_v3 as bench


class BenchV3Tests(unittest.TestCase):
    def test_self_verify_with_placeholder_prose(self):
        bench.self_verify(prose=bench.placeholder_prose())
        self.assertEqual(len(bench.SHAPES), 8)

    def test_every_reading_has_rules_and_a_ceiling_step(self):
        for shape in bench.SHAPES:
            field, label, values = shape["reading"]
            self.assertEqual((ceiling.READING[shape["name"]]["field"],
                              ceiling.READING[shape["name"]]["label"]), (field, label))
            for value in values:
                self.assertIn(f"'{value}'", ceiling.READING[shape["name"]]["spec"])
            for text in ("", "hello there", "!!! urgent north Dublin brakes vegan renew formal"):
                self.assertIn(code_only.RULES[shape["name"]](text), values)

    def test_hand_check_exclusions_are_removed(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prose.json"
            path.write_text(json.dumps({
                "texts": {"s": {"a": ["keep", "drop"], "b": ["x"]}},
                "excluded": [{"shape": "s", "label": "a", "text": "drop"}],
            }))
            self.assertEqual(bench.load_prose(path), {"s": {"a": ["keep"], "b": ["x"]}})
