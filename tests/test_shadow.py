import unittest
from shadow import should_shadow

class ShadowTests(unittest.TestCase):
    def test_deterministic_and_salt(self):
        self.assertEqual(should_shadow("id", .5, "salt"), should_shadow("id", .5, "salt"))
        assignments = [should_shadow(str(i), .5, "a") != should_shadow(str(i), .5, "b") for i in range(100)]
        self.assertTrue(any(assignments))
    def test_edges(self):
        self.assertFalse(any(should_shadow(str(i), 0, "s") for i in range(100)))
        self.assertTrue(all(should_shadow(str(i), 1, "s") for i in range(100)))
    def test_rate(self):
        selected = sum(should_shadow(str(i), .05, "s") for i in range(10000))
        self.assertTrue(400 <= selected <= 600, selected)
