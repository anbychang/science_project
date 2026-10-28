"""Unit checks for P2.5 minute-key matching."""

import sqlite3

from research_workspace.phases.phase2.code.prep_25_minute_analysis import minute_key_mismatches


def test_minute_key_mismatches_checks_both_directions() -> None:
    """Input: partially overlapping minute keys. Output: one missing key in each direction."""
    database = sqlite3.connect(":memory:")
    database.executescript("""
        CREATE TABLE storm_minute_feature_v5 (storm_id TEXT, source_time_us INTEGER);
        CREATE TABLE storm_density_1min_v5 (storm_id TEXT, source_time_us INTEGER);
        INSERT INTO storm_minute_feature_v5 VALUES ('A', 1), ('A', 2);
        INSERT INTO storm_density_1min_v5 VALUES ('A', 1), ('A', 3);
    """)

    assert minute_key_mismatches(database) == (1, 1)
    database.close()
