import unittest

import fast_path_ceiling_v6 as ceiling
import fast_path_planned_bench_v6 as bench
import run_fast_path_planned_v1 as runner


class BenchV6Tests(unittest.TestCase):
    def test_self_verify_with_placeholder_prose(self):
        bench.self_verify(prose=bench.placeholder_prose())
        self.assertEqual(len(bench.SHAPES), 8)

    def test_every_reading_has_a_per_item_ceiling_step(self):
        for shape in bench.SHAPES:
            step = ceiling.READING[shape["name"]]
            self.assertEqual(step["field"], shape["reading"][0])
            self.assertEqual(step["item_field"], shape["item_field"])
            for value in shape["reading"][2]:
                self.assertIn(f"'{value}'", step["spec"])

    def test_ceiling_reads_every_item(self):
        shape = next(s for s in bench.SHAPES if s["name"] == "menu_check")
        inputs = {"dishes": [{"name": "Tart", "price": "8.00", "description": "almond"},
                             {"name": "Bake", "price": "8.00", "description": "plain"}], "allergy": "nuts"}

        class Router:
            def handle(self, request, learn=True):
                text = request["args"][0]
                return {"route": "model", "value": "nuts" if "almond" in text else "none"}

        answered, value, label = runner.ceiling_answer(shape, ceiling.READING["menu_check"], inputs, Router())
        self.assertTrue(answered)
        self.assertEqual(label, ["nuts", "none"])
        self.assertEqual(value, "1 of 2 safe | cheapest safe Bake | avoid Tart")
