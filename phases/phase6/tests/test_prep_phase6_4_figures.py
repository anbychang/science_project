import sqlite3
from pathlib import Path

from phases.phase6.code.prep_phase6_4_figures import (
    density_gap_pairs,
    event_orbit_mean_points,
    load_event_series,
)


def test_orbit_means_use_one_pre_event_reference() -> None:
    """Input: complete event orbits. Output: one event-relative POD trend."""
    points = event_orbit_mean_points(
        reference_mean_a_m=6_800_010.0,
        orbit_means=[
            (100, 90, 6_800_000.0, 3),
            (200, 110, 6_799_995.0, 3),
            (300, 210, 6_799_990.0, 3),
        ],
    )

    assert [point.time_us for point in points] == [100, 200, 300]
    assert [point.segment_index for point in points] == [1, 1, 1]
    assert [point.delta_a_m for point in points] == [-10.0, -15.0, -20.0]


def test_pod_gap_starts_a_new_plot_segment() -> None:
    """Input: non-adjacent complete orbits. Output: POD line does not cross its gap."""
    points = event_orbit_mean_points(
        reference_mean_a_m=100.0,
        orbit_means=[
            (100_000_000, 10_000_000, 99.0, 2),
            (200_000_000, 110_000_000, 98.0, 2),
            (400_000_000, 300_000_000, 97.0, 2),
        ],
    )

    assert [point.segment_index for point in points] == [1, 1, 2]


def test_density_series_exactly_joins_l2_reference(tmp_path: Path) -> None:
    """Input: matching P6.4/L2 minutes. Output: density rows include L2."""
    comparison = sqlite3.connect(":memory:", uri=True)
    comparison.row_factory = sqlite3.Row
    comparison.execute("""
        CREATE TABLE phase6_4_decay_comparison_minute_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            predicted_m0_covered_delta_a_m REAL NOT NULL,
            predicted_ridge_covered_delta_a_m REAL NOT NULL,
            rho_m0_kg_m3 REAL NOT NULL,
            rho_ridge_kg_m3 REAL NOT NULL
        )
    """)
    comparison.executemany(
        "INSERT INTO phase6_4_decay_comparison_minute_v1 "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (f"S{event_index:08d}", event_index, 1, 1, 0.0, 0.0, 0.0, 1e-12, 2e-12)
            for event_index in range(25)
        ],
    )
    l2_path = tmp_path / "l2.sqlite"
    with sqlite3.connect(l2_path) as l2:
        l2.execute("""
            CREATE TABLE density_comparison (
                storm_id TEXT NOT NULL,
                time_us INTEGER NOT NULL,
                rho_l2_phase_kg_m3 REAL NOT NULL,
                PRIMARY KEY (storm_id, time_us)
            )
        """)
        l2.executemany(
            "INSERT INTO density_comparison VALUES (?,?,?)",
            [
                (f"S{event_index:08d}", event_index, 3e-12)
                for event_index in range(25)
            ],
        )

    events = load_event_series(comparison, l2_path)

    assert len(events) == 25
    assert all(rows[0]["rho_l2_kg_m3"] == 3e-12 for rows in events.values())


def test_density_gap_pairs_report_interpolation_endpoints() -> None:
    """Input: minute rows with one gap. Output: interpolation endpoint pair."""
    rows = [
        {"time_us": 0},
        {"time_us": 60_000_000},
        {"time_us": 180_000_000},
    ]

    pairs = density_gap_pairs(rows)

    assert [
        (previous["time_us"], current["time_us"])
        for previous, current in pairs
    ] == [(60_000_000, 180_000_000)]
