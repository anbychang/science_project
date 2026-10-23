"""Check observed SYM-H CSV import without time-grid expansion."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from satellite_orbit.phase2.prep_20_symh_1min import write_symh_1min


def utc_us(time_text: str) -> int:
    """Input: ISO UTC time text. Output: Unix microseconds."""
    return round(
        datetime.fromisoformat(time_text).replace(tzinfo=timezone.utc).timestamp() * 1_000_000
    )


class SymhOneMinuteTest(unittest.TestCase):
    """Input: small raw CSV. Output: checked native-minute SQLite rows."""

    def test_preserves_observations_and_missing_minute(self):
        """Input: signed values with a gap. Output: observed one-minute rows only."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_dir:
            root = Path(temporary_dir)
            source_dir = root / "geomagnetic"
            source_dir.mkdir()
            header = {
                "cadence": "PT1M",
                "timeStampLocation": "center",
                "modificationDate": "2024-05-10T00:00:00Z",
                "parameters": [
                    {"name": "Time"},
                    {"name": "symHValue"},
                    {"name": "versionCode"},
                ],
            }
            (source_dir / "sym_h_2024-05-10_2024-05-10.csv").write_text(
                "#" + json.dumps(header) + "\n"
                + "2024-05-10T11:59:00Z,5,10\n"
                + "2024-05-10T12:00:00Z,-40,10\n"
                + "2024-05-10T12:02:00Z,-50,20\n",
                encoding="utf-8",
            )
            output_db = root / "phase2.sqlite"
            result = write_symh_1min(
                source_dir, (date(2024, 5, 10), date(2024, 5, 10)), output_db
            )
            with closing(sqlite3.connect(output_db)) as connection:
                rows = connection.execute(
                    "SELECT source_time_us, symh_nt, symh_version "
                    "FROM symh_1min_v1 ORDER BY source_time_us"
                ).fetchall()
                tables = {
                    row[0] for row in connection.execute("SELECT name FROM sqlite_master")
                }
            self.assertEqual(
                rows,
                [
                    (utc_us("2024-05-10T11:59:00"), 5, 10),
                    (utc_us("2024-05-10T12:00:00"), -40, 10),
                    (utc_us("2024-05-10T12:02:00"), -50, 20),
                ],
            )
            self.assertNotIn("symh_10s_v1", tables)
            self.assertEqual(result, {"source_files": 1, "minute_rows": 3})


if __name__ == "__main__":
    unittest.main()
