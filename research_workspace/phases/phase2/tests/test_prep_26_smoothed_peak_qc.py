"""Check the final P2.6 checkpoint builds directly from P2.5."""

import math
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from research_workspace.phases.phase2.code.calc_centered_mean import centered_mean
from research_workspace.phases.phase2.code.prep_26_smoothed_peak_qc import (
    SmoothedPeakPaths,
    write_smoothed_peak_qc,
)


def test_final_peak_qc_needs_no_raw_peak_checkpoint() -> None:
    """Input: P2.5 minute rows only. Output: final smoothed rows and one peak QC."""
    with TemporaryDirectory(dir=Path.cwd()) as directory:
        source = Path(directory) / "analysis.sqlite"
        output = Path(directory) / "final.sqlite"
        with closing(sqlite3.connect(source)) as database, database:
            database.executescript("""
                CREATE TABLE phase2_metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO phase2_metadata VALUES
                    ('p2_5_algorithm_version', 'storm_minute_analysis_v2');
                CREATE TABLE storm_event_t0_phase_v5 (storm_id TEXT PRIMARY KEY);
                INSERT INTO storm_event_t0_phase_v5 VALUES ('S');
                CREATE TABLE storm_minute_analysis_v2 (
                    storm_id TEXT,
                    source_time_us INTEGER,
                    t0_time_us INTEGER,
                    t_rel_h REAL,
                    u_rel_rad REAL,
                    sme_nt REAL,
                    log_ratio_obs REAL,
                    storm_status TEXT
                );
            """)
            database.executemany(
                "INSERT INTO storm_minute_analysis_v2 VALUES (?,?,?,?,?,?,?,?)",
                (
                    ("S", minute * 60_000_000, 0, minute / 60, minute / 10,
                     1000.0 if minute == -10 else 100.0,
                     1.0 if minute == 10 else 0.1, "used")
                    for minute in range(-120, 121)
                ),
            )

        result = write_smoothed_peak_qc(SmoothedPeakPaths(source, output))
        with closing(sqlite3.connect(output)) as database:
            peak = database.execute("""
                SELECT candidate_start_t_rel_h, candidate_end_t_rel_h,
                       sme_peak_time_us, density_peak_time_us, algorithm_version
                FROM storm_minute_peak_qc_v4
            """).fetchone()
            smooth_count = database.execute(
                "SELECT count(*) FROM storm_minute_smooth_v4"
            ).fetchone()[0]

    assert (result["storms"], result["candidate_minutes"], smooth_count,
            peak[:2], peak[2] is not None, peak[3] is not None, peak[4]) == (
                1, 241, 241, (-12.0, 24.0), True, True, "storm_minute_peak_qc_v4"
            )


def test_centered_mean_requires_complete_window_and_80_percent_valid() -> None:
    """Input: five equally spaced samples with one gap. Output: only valid center mean."""
    values = centered_mean([0, 1, 2, 3, 4], [1.0, 2.0, None, 4.0, 5.0], 2)
    assert values[2] == 3.0


def test_centered_mean_omits_incomplete_edge_window() -> None:
    """Input: edge sample without full support. Output: NaN instead of partial mean."""
    values = centered_mean([0, 1, 2, 3, 4], [1.0, 2.0, 3.0, 4.0, 5.0], 2)
    assert math.isnan(values[0])
