"""Check SQLite schema upgrades used by the raw-data writer."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import connect_database, create_tables


class SQLiteTableTest(unittest.TestCase):
    """Input: a database with an older space_weather table
    Output: required current table columns"""

    def test_adds_trailing_f107a_column_to_existing_table(self):
        """Input: old space_weather schema
        Output: f107a_last81_sfu column"""
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE space_weather (time_us INTEGER PRIMARY KEY)")

        create_tables(connection)

        column_names = []
        for column in connection.execute("PRAGMA table_info(space_weather)"):
            column_names.append(column[1])
        connection.close()

        self.assertIn("f107a_last81_sfu", column_names)

    def test_creates_derived_pod_source_provenance_table(self):
        """Input: empty SQLite database
        Output: derived provenance table keyed by source_id"""
        connection = sqlite3.connect(":memory:")
        create_tables(connection)

        column_names = [
            column[1]
            for column in connection.execute(
                "PRAGMA table_info(swarm_a_pod_source_provenance)"
            )
        ]
        connection.close()

        self.assertEqual(
            column_names,
            [
                "source_id",
                "sp3_frame_label",
                "coverage_start_time_us",
                "coverage_end_time_us",
                "epoch_count",
                "cadence_s",
                "time_system",
            ],
        )

    def test_writer_connection_enforces_foreign_keys(self):
        """Input: writer connection and an orphan provenance record
        Output: SQLite rejects the invalid foreign-key write"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "phase1.sqlite"
            connection = connect_database(database_path)
            try:
                create_tables(connection)
                foreign_keys_enabled = connection.execute(
                    "PRAGMA foreign_keys"
                ).fetchone()[0]
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO swarm_a_pod_source_provenance VALUES
                        (1, 'ITRF', 1, 2, 1, 10.0, 'GPS')
                        """
                    )
            finally:
                connection.close()

        self.assertEqual(foreign_keys_enabled, 1)


if __name__ == "__main__":
    unittest.main()
