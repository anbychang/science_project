"""Check fixed provenance parsing from a SP3 header."""

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.load_sp3_inventory import load_sp3_inventory
from satellite_orbit.data.pod.prep_02_source_provenance import write_source_provenance


HEADER = "\n".join(
    [
        "#dV2022  1  1  0  0  0.00000000    8640 U+u   IGb14 FIT TUD",
        "## 2190 518400.00000000    10.00000000 59580 0.0000000000000",
        "+",
        "+",
        "+",
        "+",
        "+",
        "++",
        "++",
        "++",
        "++",
        "++",
        "%c M  cc GPS ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc",
    ]
)


class Sp3InventoryTest(unittest.TestCase):
    """Input: one minimal Swarm-style SP3 header
    Output: fixed source provenance values"""

    def test_reads_frame_coverage_epoch_count_and_cadence(self):
        """Input: GPS SP3 header with IGb14 frame
        Output: UTC coverage and immutable provenance"""
        with tempfile.TemporaryDirectory() as temp_folder:
            zip_path = Path(temp_folder) / "POD.ZIP"
            with ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr("orbit.sp3", HEADER)
            inventory = load_sp3_inventory(zip_path)

        self.assertEqual(inventory["sp3_frame_label"], "IGb14")
        self.assertEqual(inventory["epoch_count"], 8640)
        self.assertEqual(inventory["cadence_s"], 10.0)
        self.assertEqual(inventory["time_system"], "GPS")
        self.assertEqual(inventory["coverage_start"].isoformat(), "2021-12-31T23:59:42+00:00")
        self.assertEqual(inventory["coverage_end"].isoformat(), "2022-01-01T23:59:32+00:00")

    def test_writes_each_source_once(self):
        """Input: one immutable source file
        Output: stored provenance and idempotent rerun"""
        with tempfile.TemporaryDirectory() as temp_folder:
            folder = Path(temp_folder)
            zip_path = folder / "POD.ZIP"
            with ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr("orbit.sp3", HEADER)

            import sqlite3

            connection = sqlite3.connect(folder / "test.sqlite")
            try:
                create_tables(connection)
                connection.execute(
                    "INSERT INTO source_files (file_name, signature) VALUES (?, ?)",
                    (zip_path.name, "fixed-signature"),
                )
                self.assertEqual(write_source_provenance(connection, folder), 1)
                row = connection.execute(
                    "SELECT sp3_frame_label, epoch_count, cadence_s, time_system "
                    "FROM swarm_a_pod_source_provenance"
                ).fetchone()
                self.assertEqual(row, ("IGb14", 8640, 10.0, "GPS"))
                raw_columns = [
                    column[1]
                    for column in connection.execute("PRAGMA table_info(source_files)")
                ]
                self.assertEqual(raw_columns, ["source_id", "file_name", "signature"])
                self.assertEqual(write_source_provenance(connection, folder), 0)
            finally:
                connection.close()

    def test_keeps_legacy_raw_provenance_columns_unchanged(self):
        """Input: an old source_files table with legacy SP3 values
        Output: derived provenance is added without updating raw records"""
        with tempfile.TemporaryDirectory() as temp_folder:
            folder = Path(temp_folder)
            zip_path = folder / "POD.ZIP"
            with ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr("orbit.sp3", HEADER)

            import sqlite3

            connection = sqlite3.connect(folder / "test.sqlite")
            try:
                connection.execute(
                    """
                    CREATE TABLE source_files (
                        source_id INTEGER PRIMARY KEY,
                        file_name TEXT NOT NULL UNIQUE,
                        signature TEXT NOT NULL,
                        sp3_frame_label TEXT
                    )
                    """
                )
                create_tables(connection)
                connection.execute(
                    """
                    INSERT INTO source_files (
                        file_name, signature, sp3_frame_label
                    ) VALUES ('POD.ZIP', 'fixed-signature', 'legacy-frame')
                    """
                )

                self.assertEqual(write_source_provenance(connection, folder), 1)
                raw_frame = connection.execute(
                    "SELECT sp3_frame_label FROM source_files"
                ).fetchone()[0]
                derived_frame = connection.execute(
                    "SELECT sp3_frame_label FROM swarm_a_pod_source_provenance"
                ).fetchone()[0]
                self.assertEqual(raw_frame, "legacy-frame")
                self.assertEqual(derived_frame, "IGb14")
            finally:
                connection.close()
