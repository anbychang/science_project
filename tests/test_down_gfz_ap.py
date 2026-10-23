"""Check GFZ ap coverage and source-value safeguards without network access."""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from satellite_orbit.data.geomagnetic.down_gfz_ap import validate_ap, write_new


def one_day_payload() -> dict:
    """Input: none. Output: one UTC day of synthetic GFZ ap slots."""
    first_slot = datetime(2023, 7, 1, tzinfo=timezone.utc)
    return {
        "datetime": [(first_slot + timedelta(hours=3 * index)).isoformat().replace("+00:00", "Z") for index in range(8)],
        "ap": [7.0] * 8,
        "status": ["def"] * 8,
    }


class GfzApDownloadTest(unittest.TestCase):
    """Input: synthetic GFZ JSON. Output: validated or rejected UTC slots."""

    def test_accepts_complete_definitive_day(self):
        """Input: eight valid three-hour slots. Output: eight accepted slots."""
        payload = json.dumps(one_day_payload()).encode()
        self.assertEqual(validate_ap(payload, date(2023, 7, 1), date(2023, 7, 1)), 8)

    def test_rejects_missing_slot(self):
        """Input: seven slots. Output: explicit coverage error."""
        data = one_day_payload()
        for values in data.values():
            values.pop()
        with self.assertRaisesRegex(ValueError, "cover"):
            validate_ap(json.dumps(data).encode(), date(2023, 7, 1), date(2023, 7, 1))

    def test_rejects_shifted_slot(self):
        """Input: one shifted time. Output: UTC grid error."""
        data = one_day_payload()
        data["datetime"][3] = "2023-07-01T09:01:00Z"
        with self.assertRaisesRegex(ValueError, "UTC start"):
            validate_ap(json.dumps(data).encode(), date(2023, 7, 1), date(2023, 7, 1))

    def test_rejects_non_definitive_slot(self):
        """Input: provisional source value. Output: status error."""
        data = one_day_payload()
        data["status"][2] = "nowcast"
        with self.assertRaisesRegex(ValueError, "definitive"):
            validate_ap(json.dumps(data).encode(), date(2023, 7, 1), date(2023, 7, 1))

    def test_preserves_existing_partial_file(self):
        """Input: occupied partial path. Output: no overwrite or deletion."""
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "ap.json"
            partial = Path(folder) / "ap.json.part"
            partial.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                write_new(target, b"new")
            self.assertEqual(partial.read_bytes(), b"existing")
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
