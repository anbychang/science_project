"""Checks for descriptive Phase 2 peak-order auditing."""

import math
import sqlite3

import pytest

from satellite_orbit.data.density.down_swarm_density_pod import sha256_file
from satellite_orbit.phase2.prep_26_peak_order import (
    HOUR_US,
    check_peak_order,
    observed_orbit_ratios,
    write_peak_order,
)


def make_sources(density_peak_hour: int) -> tuple[sqlite3.Connection, sqlite3.Connection]:
    """Input: density peak hour relative to t0. Output: synthetic P2.4/P2.5 sources."""
    density = sqlite3.connect(":memory:")
    geomag = sqlite3.connect(":memory:")
    density.executescript("""
        CREATE TABLE storm_catalog_v3 (storm_id TEXT,t0_time_us INTEGER,status TEXT);
        CREATE TABLE storm_density_1min_v3 (
            storm_id TEXT,orbit_id INTEGER,rho_l2_kg_m3 REAL,
            rho_msis_kg_m3 REAL,paired_sample_count INTEGER
        );
    """)
    geomag.execute("""
        CREATE TABLE storm_geomag_orbit_v1 (
            storm_id TEXT,orbit_id INTEGER,t_mid_time_us INTEGER,
            q_sme_nt REAL,is_valid INTEGER
        )
    """)
    t0_us = 100 * HOUR_US
    density.execute("INSERT INTO storm_catalog_v3 VALUES (?,?,?)", ("S1", t0_us, "used"))
    for orbit_id, relative_hour, q_nt in ((1, -30, 100), (2, -2, 10),
                                          (3, -1, 5), (4, 1, 3)):
        ratio = 3 if relative_hour == density_peak_hour else 1
        density.execute("INSERT INTO storm_density_1min_v3 VALUES (?,?,?,?,?)",
                        ("S1", orbit_id, ratio, 1, 1))
        geomag.execute("INSERT INTO storm_geomag_orbit_v1 VALUES (?,?,?,?,?)",
                       ("S1", orbit_id, t0_us + relative_hour * HOUR_US, q_nt, 1))
    return density, geomag


def test_peak_order_ignores_activity_outside_main_pulse():
    """Input: stronger SME outside 24 h. Output: nearby SME peak at -2 h."""
    density, geomag = make_sources(-1)
    try:
        result = check_peak_order(density, geomag)
    finally:
        density.close()
        geomag.close()
    assert result[0][4] == -2


def test_sme_density_symh_order_matches_when_density_leads_t0():
    """Input: peaks at -2 h, -1 h, and t0. Output: expected order passes."""
    density, geomag = make_sources(-1)
    try:
        result = check_peak_order(density, geomag)
    finally:
        density.close()
        geomag.close()
    assert result[0][7] == 1


def test_density_after_t0_does_not_match_expected_order():
    """Input: density peak at +1 h. Output: expected order fails."""
    density, geomag = make_sources(1)
    try:
        result = check_peak_order(density, geomag)
    finally:
        density.close()
        geomag.close()
    assert result[0][7] == 0


def test_density_ratio_uses_paired_sample_weights():
    """Input: one orbit with unequal minute sample counts. Output: weighted log ratio."""
    density = sqlite3.connect(":memory:")
    density.execute("""
        CREATE TABLE storm_density_1min_v3 (
            storm_id TEXT,orbit_id INTEGER,rho_l2_kg_m3 REAL,
            rho_msis_kg_m3 REAL,paired_sample_count INTEGER
        )
    """)
    density.executemany("INSERT INTO storm_density_1min_v3 VALUES (?,?,?,?,?)", (
        ("S1", 1, 1, 1, 1), ("S1", 1, 3, 1, 3)
    ))
    try:
        ratio = observed_orbit_ratios(density)[("S1", 1)]
    finally:
        density.close()
    assert ratio == pytest.approx(math.log(2.5))


def test_peak_order_writes_source_locked_sqlite(tmp_path):
    """Input: two small checked sources. Output: one traceable P2.6 SQLite row."""
    density, geomag = make_sources(-1)
    density_path = tmp_path / "density.sqlite"
    geomag_path = tmp_path / "geomag.sqlite"
    output_path = tmp_path / "peak.sqlite"
    density.commit()
    with sqlite3.connect(density_path) as target:
        density.backup(target)
    density.close()
    geomag.execute("CREATE TABLE phase2_metadata (name TEXT, value TEXT)")
    geomag.execute("INSERT INTO phase2_metadata VALUES (?,?)", (
        "p2_5_source_sha256", sha256_file(density_path)
    ))
    geomag.commit()
    with sqlite3.connect(geomag_path) as target:
        geomag.backup(target)
    geomag.close()

    result = write_peak_order(density_path, geomag_path, output_path)

    with sqlite3.connect(output_path) as database:
        row = database.execute(
            "SELECT storm_id,expected_order FROM storm_peak_order_v1"
        ).fetchone()
        source_hash = database.execute(
            "SELECT value FROM phase2_metadata WHERE name='p2_6_density_source_sha256'"
        ).fetchone()[0]
        integrity = database.execute("PRAGMA integrity_check").fetchone()[0]
    assert result == {"storms": 1, "expected_order": 1}
    assert row == ("S1", 1)
    assert source_hash == sha256_file(density_path)
    assert integrity == "ok"
