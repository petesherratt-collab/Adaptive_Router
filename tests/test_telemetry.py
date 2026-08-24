from types import SimpleNamespace
import unittest
from unittest.mock import patch

from telemetry import collect_system_metrics


class TelemetryTests(unittest.TestCase):
    @patch("telemetry.os.getloadavg", return_value=(0.1, 0.2, 0.3))
    @patch("telemetry.os.sysconf", return_value=4096)
    @patch("telemetry.psutil.virtual_memory")
    @patch("telemetry.psutil.cpu_percent", return_value=12.5)
    @patch("telemetry.psutil.swap_memory")
    def test_swap_occupancy_and_activity_are_distinct(self, swap_memory, cpu_percent,
                                                       virtual_memory, sysconf, getloadavg):
        swap_memory.side_effect = [
            SimpleNamespace(used=495 * 1048576, percent=96.9, sin=4096, sout=8192),
            SimpleNamespace(used=495 * 1048576, percent=96.9, sin=12288, sout=12288),
        ]
        virtual_memory.return_value = SimpleNamespace(available=2177 * 1048576, percent=42.7)

        metrics = collect_system_metrics()

        self.assertEqual(metrics["swap_used_mb"], 495)
        self.assertEqual(metrics["swap_percent"], 96.9)
        self.assertEqual(metrics["swap_in_bytes"], 8192)
        self.assertEqual(metrics["swap_in_pages"], 2)
        self.assertEqual(metrics["swap_out_bytes"], 4096)
        self.assertEqual(metrics["swap_out_pages"], 1)
        cpu_percent.assert_called_once_with(interval=0.1)


if __name__ == "__main__":
    unittest.main()
