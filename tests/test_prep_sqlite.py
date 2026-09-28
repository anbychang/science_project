"""Check that small geomagnetic CSV files reach SQLite correctly."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.prep_sqlite_geomagnetic import write_ae, write_sym_h
from satellite_orbit.data.prep_sqlite_tables import create_tables


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


if __name__ == "__main__":
    unittest.main()
