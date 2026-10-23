"""Checks for complete-orbit geomagnetic summaries."""

import sqlite3

import pytest

from satellite_orbit.phase2.prep_25_geomag_orbit import (
    MINUTE_US,
    expected_minute_count,
    orbit_rows,
)


def make_source(second_orbit_sme_count: int = 60) -> sqlite3.Connection:
    """Input: second-orbit SME count. Output: two-orbit in-memory source SQLite."""
    source = sqlite3.connect(":memory:")
    source.executescript("""
        CREATE TABLE storm_event_orbit_v3 (
            storm_id TEXT,orbit_id INTEGER,orbit_start_time_us INTEGER,
            orbit_end_time_us INTEGER
        );
        CREATE TABLE storm_minute_feature_v3 (
            storm_id TEXT,orbit_id INTEGER,source_time_us INTEGER,
            sme_nt REAL,symh_nt REAL,sme_station_count INTEGER
        );
    """)
    source.executemany("INSERT INTO storm_event_orbit_v3 VALUES (?,?,?,?)", (
        ("S1", 1, 0, 60 * MINUTE_US),
        ("S1", 2, 60 * MINUTE_US, 120 * MINUTE_US),
    ))
    minute_rows = []
    for orbit_id in (1, 2):
        for index in range(60):
            sme_valid = orbit_id == 1 or index < second_orbit_sme_count
            minute_rows.append((
                "S1", orbit_id, ((orbit_id - 1) * 60 + index) * MINUTE_US,
                float(orbit_id * 100) if sme_valid else None,
                float(-orbit_id * 10), 80 if orbit_id == 1 else 100,
            ))
    source.executemany("INSERT INTO storm_minute_feature_v3 VALUES (?,?,?,?,?,?)", minute_rows)
    return source


@pytest.mark.parametrize("start_us,end_us,expected", (
    (0, MINUTE_US, 1),
    (1, MINUTE_US, 0),
    (1, MINUTE_US + 1, 1),
))
def test_expected_minute_count_uses_orbit_bounds(start_us, end_us, expected):
    """Input: orbit time bounds. Output: exact count of center-labeled minutes."""
    assert expected_minute_count(start_us, end_us) == expected


def test_derivative_uses_previous_orbit_only():
    """Input: two complete orbits. Output: second derivative is -10 nT/h."""
    with make_source() as source:
        summaries = orbit_rows(source)
    assert summaries[1][11] == pytest.approx(-10)


def test_first_orbit_has_no_previous_derivative():
    """Input: first event orbit. Output: unavailable previous derivative is null."""
    with make_source() as source:
        summaries = orbit_rows(source)
    assert summaries[0][11] is None


def test_eighty_percent_sme_is_valid():
    """Input: 48 of 60 valid SME minutes. Output: orbit passes coverage."""
    with make_source(48) as source:
        summaries = orbit_rows(source)
    assert summaries[1][-2] == 1


def test_below_eighty_percent_sme_is_invalid():
    """Input: 47 of 60 valid SME minutes. Output: orbit fails coverage."""
    with make_source(47) as source:
        summaries = orbit_rows(source)
    assert summaries[1][-2] == 0
