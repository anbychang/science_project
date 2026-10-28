"""Check Swarm-A POD SP3 field parsing."""

import unittest
from datetime import datetime

from phases.phase0.code.data.pod.load_swarm_pod import _read_time


class PodTimeParseTest(unittest.TestCase):
    """Input: SP3 epoch line
    Output: normalized GPS datetime"""

    def test_carries_fractional_second_rounding_into_next_minute(self):
        """Input: 59.9999996 seconds
        Output: next minute at zero microseconds"""
        result = _read_time("*  2026  8 11 23 59 59.9999996\n")

        self.assertEqual(result, datetime(2026, 8, 12, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
