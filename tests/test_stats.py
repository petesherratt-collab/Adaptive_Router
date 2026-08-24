import unittest
from datetime import datetime, timezone
from stats import task_statistics, wilson_interval, rolling_median

class StatsTests(unittest.TestCase):
    def test_wilson_known(self):
        lo, hi = wilson_interval(5, 10); self.assertAlmostEqual(lo, .2366, places=3); self.assertAlmostEqual(hi, .7634, places=3)
    def test_counts_and_insufficient(self):
        rows = [{"task_class":"rewrite","local":{"attempted":True},"decision":{"reason":"LOCAL_ACCEPTED"}}, {"task_class":"rewrite","local":{"attempted":True},"decision":{"reason":"VALIDATOR_FAILED"}}]
        result = task_statistics(rows)["rewrite"]; self.assertEqual((result["N"], result["successes"]), (2,1)); self.assertEqual(result["evidence"], "INSUFFICIENT_EVIDENCE")
    def test_baseline(self):
        rows = [{"timestamp":datetime.now(timezone.utc).isoformat(), "probe_ms":i, "local":{"attempted":True,"success":True,"ttft_ms":i}, "decision":{}} for i in range(30)]
        self.assertEqual(rolling_median(rows, "probe_ms")["median"], 14.5)
