"""Tests for Phase 2R chunk-safe event preparation."""

import math
import sqlite3

from phases.phase2r.code.prep_2r3_t0_phase_window import (
    contiguous_segments,
    segment_at_time,
)


def row(time_us: int, chunk_id: int) -> sqlite3.Row:
    """Input: UTC us and chunk id. Output: SQLite-like row mapping."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE sample (time_us INTEGER, chunk_id INTEGER, "
        "mean_argument_of_perigee_rad REAL, mean_anomaly_rad REAL)"
    )
    connection.execute(
        "INSERT INTO sample VALUES (?,?,?,?)",
        (time_us, chunk_id, 0.0, math.fmod(time_us / 10_000_000, math.tau)),
    )
    result = connection.execute("SELECT * FROM sample").fetchone()
    connection.close()
    return result


def test_segments_split_at_chunk_change():
    """Input: adjacent rows from two chunks. Output: two contiguous segments."""
    rows = [row(0, 1), row(10_000_000, 1), row(20_000_000, 2)]
    assert [len(segment) for segment in contiguous_segments(rows)] == [2, 1]


def test_segment_at_time_selects_only_bracketing_chunk():
    """Input: two separated chunks. Output: segment containing requested t0."""
    rows = [row(0, 1), row(10_000_000, 1), row(30_000_000, 2), row(40_000_000, 2)]
    selected = segment_at_time(rows, 35_000_000)
    assert [item["chunk_id"] for item in selected] == [2, 2]
