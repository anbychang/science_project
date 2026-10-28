"""Check that raw space-weather rows are not replaced."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research_workspace.phases.phase0.code.data.database.prep_raw_schema import create_tables
from research_workspace.phases.phase0.code.data.space_weather.prep_raw_weather import write_space_weather


def weather_state(state, _file_path):
    """Input: state with UTC time
    Output: state with one complete weather record"""
    return {
        "time": state["time"],
        "f107_sfu": 100.0,
        "f107a_sfu": 110.0,
        "f107a_last81_sfu": 105.0,
        "ap_values": [1.0] * 7,
        "f107_data_type": "OBS",
    }


class SpaceWeatherSQLiteTest(unittest.TestCase):
    """Input: revised raw weather CSV
    Output: existing raw rows stay unchanged"""

    def test_rejects_a_revised_weather_source(self):
        """Input: changed CSV after initial raw write
        Output: ValueError and original raw row"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            weather_file = Path(temporary_folder) / "weather.csv"
            weather_file.write_text(
                "DATE,AP1,AP2,AP3,AP4,AP5,AP6,AP7,AP8\n"
                "2024-05-01,1,1,1,1,1,1,1,1\n",
                encoding="utf-8",
            )
            connection = sqlite3.connect(":memory:")
            create_tables(connection)
            with patch(
                "research_workspace.phases.phase0.code.data.space_weather.prep_raw_weather.load_space_weather",
                side_effect=weather_state,
            ):
                write_space_weather(connection, weather_file)

            weather_file.write_text(
                "DATE,AP1,AP2,AP3,AP4,AP5,AP6,AP7,AP8\n"
                "2024-05-01,2,1,1,1,1,1,1,1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "fresh database"):
                write_space_weather(connection, weather_file)

            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM space_weather").fetchone()[0],
                8,
            )
            connection.close()

    def test_rejects_missing_interior_ap_data_without_writing_metadata(self):
        """Input: CSV with one missing Ap slot between complete days
        Output: ValueError and no raw weather provenance"""
        header = (
            "DATE,AP1,AP2,AP3,AP4,AP5,AP6,AP7,AP8,AP_AVG,"
            "F10.7_OBS,F10.7_OBS_CENTER81,F10.7_OBS_LAST81,F10.7_DATA_TYPE\n"
        )
        with tempfile.TemporaryDirectory() as temporary_folder:
            weather_file = Path(temporary_folder) / "weather.csv"
            weather_file.write_text(
                header
                + "2024-05-01,1,1,1,1,1,1,1,1,1,100,110,105,OBS\n"
                + "2024-05-02,1,1,1,,1,1,1,1,1,100,110,105,OBS\n"
                + "2024-05-03,1,1,1,1,1,1,1,1,1,100,110,105,OBS\n",
                encoding="utf-8",
            )
            connection = sqlite3.connect(":memory:")
            create_tables(connection)

            with self.assertRaisesRegex(ValueError, "missing or invalid"):
                write_space_weather(connection, weather_file)

            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM space_weather").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM metadata").fetchone()[0],
                0,
            )
            connection.close()

    def test_rejects_blank_interior_ap1_without_writing_metadata(self):
        """Input: CSV with a blank AP1 between complete days
        Output: ValueError and no raw weather provenance"""
        header = (
            "DATE,AP1,AP2,AP3,AP4,AP5,AP6,AP7,AP8,AP_AVG,"
            "F10.7_OBS,F10.7_OBS_CENTER81,F10.7_OBS_LAST81,F10.7_DATA_TYPE\n"
        )
        with tempfile.TemporaryDirectory() as temporary_folder:
            weather_file = Path(temporary_folder) / "weather.csv"
            weather_file.write_text(
                header
                + "2024-05-01,1,1,1,1,1,1,1,1,1,100,110,105,OBS\n"
                + "2024-05-02,,1,1,1,1,1,1,1,1,100,110,105,OBS\n"
                + "2024-05-03,1,1,1,1,1,1,1,1,1,100,110,105,OBS\n",
                encoding="utf-8",
            )
            connection = sqlite3.connect(":memory:")
            create_tables(connection)

            with self.assertRaisesRegex(ValueError, "missing or invalid"):
                write_space_weather(connection, weather_file)

            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM space_weather").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM metadata").fetchone()[0],
                0,
            )
            connection.close()

    def test_allows_blank_trailing_ap1_rows(self):
        """Input: CSV with blanks after its final complete day
        Output: writes only the complete source day"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            weather_file = Path(temporary_folder) / "weather.csv"
            weather_file.write_text(
                "DATE,AP1,AP2,AP3,AP4,AP5,AP6,AP7,AP8\n"
                "2024-05-01,1,1,1,1,1,1,1,1\n"
                "2024-05-02,,,,,,,,\n",
                encoding="utf-8",
            )
            connection = sqlite3.connect(":memory:")
            create_tables(connection)

            with patch(
                "research_workspace.phases.phase0.code.data.space_weather.prep_raw_weather.load_space_weather",
                side_effect=weather_state,
            ):
                self.assertEqual(write_space_weather(connection, weather_file), 8)

            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM space_weather").fetchone()[0],
                8,
            )
            connection.close()


if __name__ == "__main__":
    unittest.main()
