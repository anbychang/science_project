"""Check the frozen source-audit SQLite checkpoint."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from research_workspace.phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file
from research_workspace.phases.phase2.code.prep_20_source_checkpoint import write_source_checkpoint
from research_workspace.phases.phase2.code.prep_21_geomag_1min import source_audit


class SourceCheckpointTest(unittest.TestCase):
    """Input: source-audit JSON. Output: an immutable SQLite source checkpoint."""

    def test_checkpoint_preserves_audit_and_rejects_overwrite(self):
        """Input: pilot audit. Output: matching SHA-256 in a new SQLite file."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            audit_path = Path(folder) / "audit.json"
            database_path = Path(folder) / "p20.sqlite"
            audit_path.write_text(
                json.dumps({"date_range_utc": ["2023-07-01", "2026-06-30"]}),
                encoding="utf-8",
            )
            audit_hash = sha256_file(audit_path)
            self.assertEqual(write_source_checkpoint(audit_path, database_path), audit_hash)
            with closing(sqlite3.connect(database_path)) as connection:
                row = connection.execute("SELECT audit_sha256, algorithm_version FROM source_audit_v2").fetchone()
                embedded_audit = source_audit(connection)
            self.assertEqual(row, (audit_hash, "source_audit_v2"))
            self.assertEqual(embedded_audit["date_range_utc"], ["2023-07-01", "2026-06-30"])
            with self.assertRaises(FileExistsError):
                write_source_checkpoint(audit_path, database_path)
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute("UPDATE source_audit_v2 SET audit_json = '{}' ")
                connection.commit()
                with self.assertRaisesRegex(ValueError, "hash is invalid"):
                    source_audit(connection)


if __name__ == "__main__":
    unittest.main()
