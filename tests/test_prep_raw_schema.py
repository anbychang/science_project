"""Check SQLite schema upgrades used by the raw-data writer."""

import sqlite3
import unittest

from satellite_orbit.data.prep_raw_schema import create_tables


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


if __name__ == "__main__":
    unittest.main()
