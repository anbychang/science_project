"""Check fields read from the raw CelesTrak space-weather CSV."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_workspace.phases.phase0.code.data.space_weather.load_space_weather import load_space_weather


def raw_weather_row(day, last81_value):
    """Input: UTC day and F10.7 trailing-average value
    Output: one complete raw space-weather CSV row"""
    ap_values = "4,4,4,4,4,4,4,4"
    return f"{day.isoformat()},{ap_values},4,120,110,{last81_value},OBS\n"


class LoadSpaceWeatherTest(unittest.TestCase):
    """Input: a small complete raw space-weather file
    Output: selected F10.7 fields in one state"""

    def test_reads_trailing_f107_average(self):
        """Input: raw F10.7 centered and trailing averages
        Output: trailing average is retained separately"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            weather_file = Path(temporary_folder) / "weather.csv"
            header = (
                "DATE,AP1,AP2,AP3,AP4,AP5,AP6,AP7,AP8,AP_AVG,"
                "F10.7_OBS,F10.7_OBS_CENTER81,F10.7_OBS_LAST81,F10.7_DATA_TYPE\n"
            )
            first_day = datetime(2024, 5, 1).date()
            rows = header
            for day_offset in range(4):
                day = first_day + timedelta(days=day_offset)
                rows += raw_weather_row(day, 100 + day_offset)
            weather_file.write_text(rows, encoding="utf-8")

            state = load_space_weather(
                {"time": datetime(2024, 5, 4, 12, tzinfo=timezone.utc)},
                weather_file,
            )

        self.assertEqual(state["f107a_last81_sfu"], 103.0)

    def test_reloads_a_changed_weather_file_at_the_same_path(self):
        """Input: same weather path with changed CSV content
        Output: later load uses the new trailing average"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            weather_file = Path(temporary_folder) / "weather.csv"
            header = (
                "DATE,AP1,AP2,AP3,AP4,AP5,AP6,AP7,AP8,AP_AVG,"
                "F10.7_OBS,F10.7_OBS_CENTER81,F10.7_OBS_LAST81,F10.7_DATA_TYPE\n"
            )
            first_day = datetime(2024, 5, 1).date()
            rows = header
            for day_offset in range(4):
                rows += raw_weather_row(first_day + timedelta(days=day_offset), 100)
            weather_file.write_text(rows, encoding="utf-8")
            state_time = datetime(2024, 5, 4, 12, tzinfo=timezone.utc)
            load_space_weather({"time": state_time}, weather_file)

            rows = header
            for day_offset in range(4):
                rows += raw_weather_row(first_day + timedelta(days=day_offset), 200)
            weather_file.write_text(rows, encoding="utf-8")
            state = load_space_weather({"time": state_time}, weather_file)

        self.assertEqual(state["f107a_last81_sfu"], 200.0)


if __name__ == "__main__":
    unittest.main()
