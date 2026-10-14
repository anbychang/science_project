"""Check that incomplete POD downloads are discarded."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from satellite_orbit.data.down_swarm_pod import download_file


class PodDownloadTest(unittest.TestCase):
    """Input: POD download response
    Output: complete local ZIP or clear failure"""

    def test_discards_a_download_with_the_wrong_size(self):
        """Input: response shorter than ESA metadata size
        Output: ValueError and no retained ZIP"""
        source_file = {"name": "POD.ZIP", "path": "remote/POD.ZIP", "size": 10}

        with tempfile.TemporaryDirectory() as temporary_folder:
            data_folder = Path(temporary_folder)

            def write_short_file(_url, output_path):
                Path(output_path).write_bytes(b"short")

            with patch(
                "satellite_orbit.data.down_swarm_pod.urlretrieve",
                side_effect=write_short_file,
            ):
                with self.assertRaisesRegex(ValueError, "Incomplete POD download"):
                    download_file(source_file, data_folder)

            self.assertFalse((data_folder / "POD.ZIP").exists())


if __name__ == "__main__":
    unittest.main()
