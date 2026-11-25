import unittest

import analyze_phase_c
import fast_path_planned_bench_v7 as bench


class BenchV7Tests(unittest.TestCase):
    def test_self_verify_with_placeholder_prose(self):
        bench.self_verify(bench.placeholder_prose())

    def test_families_and_reading_shapes(self):
        one = [s for s in bench.SHAPES if s["family"] == "one"]
        many = [s for s in bench.SHAPES if s["family"] == "many"]
        self.assertEqual((len(one), len(many)), (4, 4))
        self.assertTrue(all("item_field" in s for s in many) and not any("item_field" in s for s in one))

    def test_by_family_splits_jobs(self):
        rows = []
        for shape in bench.SHAPES:
            for i in range(4):
                for arm, ms, ok in (("R", 100.0, True), ("P", 50.0 if shape["family"] == "one" else 150.0, True)):
                    rows.append({"shape": shape["name"], "index": i, "arm": arm, "answer_ms": ms, "correct": ok,
                                 "answered": True, "route": "race"})
        out = analyze_phase_c.by_family(rows, replicates=50)
        self.assertLess(out["one"]["p_vs_r"]["time_ratio"], 1.0)
        self.assertGreater(out["many"]["p_vs_r"]["time_ratio"], 1.0)
        self.assertEqual(sorted(out["one"]["shapes"]), sorted(s["name"] for s in bench.SHAPES if s["family"] == "one"))


if __name__ == "__main__":
    unittest.main()
