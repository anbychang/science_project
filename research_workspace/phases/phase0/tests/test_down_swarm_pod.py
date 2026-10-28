"""Check that incomplete POD downloads are discarded."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_workspace.phases.phase0.code.data.pod.down_swarm_pod import download_file, select_latest_files


class PodDownloadTest(unittest.TestCase):
    """Input: POD download response
    Output: complete local ZIP or clear failure"""

    def test_excludes_files_after_the_requested_end(self):
        """Input: POD files on both sides of the inclusive end date.
        Output: only the in-range POD file."""
        files = [
            {"name": "SW_OPER_SP3ACOM_2__20240629T235942_20240630T235942_0201.ZIP"},
            {"name": "SW_OPER_SP3ACOM_2__20240630T235942_20240701T235942_0201.ZIP"},
        ]

        selected_files = select_latest_files(files, "2024-01-01", "2024-06-30")

        self.assertEqual(len(selected_files), 1)
        self.assertIn("20240630T235942", selected_files[0]["name"])

    def test_discards_a_download_with_the_wrong_size(self):
        """Input: response shorter than ESA metadata size
        Output: ValueError and no retained ZIP"""
        source_file = {"name": "POD.ZIP", "path": "remote/POD.ZIP", "size": 10}

        with tempfile.TemporaryDirectory() as temporary_folder:
            data_folder = Path(temporary_folder)

            def write_short_file(_url, output_path):
                Path(output_path).write_bytes(b"short")

            with patch("research_workspace.phases.phase0.code.data.pod.down_swarm_pod.sleep"):
                with patch(
                    "research_workspace.phases.phase0.code.data.pod.down_swarm_pod.urlretrieve",
                    side_effect=write_short_file,
                ):
                    with self.assertRaisesRegex(ValueError, "Incomplete POD download"):
                        download_file(source_file, data_folder)

            self.assertFalse((data_folder / "POD.ZIP").exists())

    def test_retries_a_short_download_until_it_is_complete(self):
        """Input: short first response then complete retry.
        Output: complete ZIP returned without retaining the short response."""
        source_file = {"name": "POD.ZIP", "path": "remote/POD.ZIP", "size": 10}

        with tempfile.TemporaryDirectory() as temporary_folder:
            data_folder = Path(temporary_folder)

            def write_file(_url, output_path):
                content = b"short" if write_file.calls == 0 else b"complete!!"
                write_file.calls += 1
                Path(output_path).write_bytes(content)

            write_file.calls = 0
            with patch("research_workspace.phases.phase0.code.data.pod.down_swarm_pod.sleep") as sleep_mock:
                with patch(
                    "research_workspace.phases.phase0.code.data.pod.down_swarm_pod.urlretrieve",
                    side_effect=write_file,
                ):
                    output_path = download_file(source_file, data_folder)

            self.assertEqual(output_path.stat().st_size, 10)
            self.assertEqual(write_file.calls, 2)
            sleep_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
