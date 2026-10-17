"""Check that small geomagnetic CSV files reach SQLite correctly."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.geomagnetic.prep_raw_geomagnetic import write_ae, write_sym_h


class GeomagneticSQLiteTest(unittest.TestCase):
    """Input: one small SYM-H CSV and one small AE CSV
    Output: one SQLite row with both values"""

    def test_writes_sym_h_and_ae_to_one_time(self):
        """Input: matching SYM-H and AE times
        Output: both values are kept in the same table row"""
        with tempfile.TemporaryDirectory() as temp_folder:
            folder = Path(temp_folder)
            (folder / "sym_h_test.csv").write_text(
                "2024-05-10T12:00:00Z,-45,1\n",
                encoding="utf-8",
            )
            (folder / "ae_test.csv").write_text(
                "2024-05-10T12:00:00Z,300,1\n",
                encoding="utf-8",
            )

            connection = sqlite3.connect(":memory:")
            create_tables(connection)
            self.assertEqual(write_sym_h(connection, folder), 1)
            self.assertEqual(write_ae(connection, folder), 1)

            row = connection.execute(
                "SELECT sym_h_nt, ae_nt FROM geomagnetic"
            ).fetchone()
            self.assertEqual(row, (-45.0, 300.0))
            connection.close()

    def test_does_not_replace_an_existing_sym_h_observation(self):
        """Input: same time with a different SYM-H value
        Output: original raw SYM-H observation remains stored"""
        with tempfile.TemporaryDirectory() as temp_folder:
            folder = Path(temp_folder)
            file_path = folder / "sym_h_test.csv"
            file_path.write_text("2024-05-10T12:00:00Z,-45,1\n", encoding="utf-8")
            connection = sqlite3.connect(":memory:")
            create_tables(connection)
            write_sym_h(connection, folder)
            file_path.write_text("2024-05-10T12:00:00Z,-99,2\n", encoding="utf-8")

            write_sym_h(connection, folder)

            self.assertEqual(
                connection.execute(
                    "SELECT sym_h_nt, sym_h_version FROM geomagnetic"
                ).fetchone(),
                (-45.0, 1),
            )
            connection.close()


if __name__ == "__main__":
    unittest.main()
