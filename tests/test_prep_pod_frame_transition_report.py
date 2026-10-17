"""Check SP3 frame-transition detection."""

import sqlite3
import unittest

from satellite_orbit.data.pod.prep_pod_frame_transition_report import find_frame_transitions


class FrameTransitionReportTest(unittest.TestCase):
    """Input: ordered SP3 source labels
    Output: frame-label boundaries"""

    def test_finds_only_changed_frame_labels(self):
        """Input: repeated labels with one transition
        Output: previous and next source metadata"""
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                "CREATE TABLE swarm_a_pod_source_provenance "
                "(source_id INTEGER, sp3_frame_label TEXT)"
            )
            connection.executemany(
                "INSERT INTO swarm_a_pod_source_provenance VALUES (?, ?)",
                [(1, "IGb14"), (2, "IGb14"), (3, "IGS20")],
            )
            self.assertEqual(
                find_frame_transitions(connection),
                [
                    {
                        "old_source_id": 2,
                        "new_source_id": 3,
                        "old_frame": "IGb14",
                        "new_frame": "IGS20",
                    }
                ],
            )
        finally:
            connection.close()
