import unittest

import fast_path_ceiling_v5 as ceiling
import fast_path_planned_bench_v5 as bench


class BenchV5Tests(unittest.TestCase):
    def test_self_verify_with_placeholder_prose(self):
        bench.self_verify(prose=bench.placeholder_prose())
        self.assertEqual(len(bench.SHAPES), 8)

    def test_every_reading_has_a_ceiling_step(self):
        for shape in bench.SHAPES:
            field, label, values = shape["reading"]
            step = ceiling.READING[shape["name"]]
            self.assertEqual((step["field"], step["label"]), (field, label))
            for value in values:
                self.assertIn(f"'{value}'", step["spec"])
