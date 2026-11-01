"""Build 2022 phase-orbit means and chunk-local 90-day baseline slopes."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase1.code.calc_orbit_decay_diagnostics import ordinary_least_squares
from phases.phase1.code.prep_10_phase_orbit_mean import (
    phase_orbit_rows,
    trailing_mean_element_rows,
)


DEFAULT_SOURCE = Path(
    "phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite",
)
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_2022_baseline_v1.sqlite",
)
START_2022_US = 1_640_995_200_000_000
STOP_2022_US = 1_672_531_200_000_000
DAY_US = 86_400_000_000
LOOKBACK_DAYS = 90
ALGORITHM_VERSION = "phase6_2022_chunk_90day_baseline_v1"


@dataclass(frozen=True)
class OrbitMean:
    """Input: one accepted complete phase orbit.
    Output: orbit timing, mean semi-major axis, and source chunk."""

    time_us: int
    orbit_start_time_us: int
    semi_major_axis_m: float
    chunk_id: int


@dataclass(frozen=True)
class ChunkBaseline:
    """Input: one 2022 source chunk and its trailing 90-day orbit means.
    Output: coverage and optional OLS baseline fit."""

    chunk_id: int
    chunk_start_time_us: int
    chunk_stop_time_us: int
    chunk_orbit_count: int
    chunk_coverage_days: float
    fit_start_time_us: int
    fit_orbit_count: int
    fit_coverage_days: float
    rate_m_day: float | None
    rate_1sigma_m_day: float | None
    residual_std_m: float | None
    status: str


def source_connection(path: Path) -> sqlite3.Connection:
    """Input: existing Phase 1R SQLite path.
    Output: read-only SQLite connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def load_2022_orbit_means(connection: sqlite3.Connection) -> list[OrbitMean]:
    """Input: read-only Phase 1R mean-element tables.
    Output: [OrbitMean, ...] for accepted complete 2022 phase orbits."""
    rows = phase_orbit_rows(
        trailing_mean_element_rows(connection, START_2022_US, STOP_2022_US),
    )
    return [
        OrbitMean(
            time_us=int(row[0]),
            orbit_start_time_us=int(row[1]),
            semi_major_axis_m=float(row[2]),
            chunk_id=int(row[12]),
        )
        for row in rows
        if START_2022_US <= row[0] < STOP_2022_US
    ]


def calculate_chunk_baseline(rows: list[OrbitMean]) -> ChunkBaseline:
    """Input: time-ordered complete orbit means from one source chunk.
    Output: chunk coverage and its trailing 90-day OLS fit when available."""
    if not rows:
        raise ValueError("Cannot fit an empty source chunk.")
    chunk_ids = {row.chunk_id for row in rows}
    if len(chunk_ids) != 1:
        raise ValueError("A 90-day baseline cannot cross source chunks.")

    fit_stop_time_us = rows[-1].time_us
    fit_start_time_us = fit_stop_time_us - LOOKBACK_DAYS * DAY_US
    fit_rows = [row for row in rows if row.time_us >= fit_start_time_us]
    chunk_coverage_days = (
        rows[-1].time_us - rows[0].orbit_start_time_us
    ) / DAY_US
    fit_coverage_days = (
        fit_rows[-1].time_us - fit_rows[0].orbit_start_time_us
    ) / DAY_US

    if chunk_coverage_days < LOOKBACK_DAYS:
        return ChunkBaseline(
            rows[0].chunk_id, rows[0].orbit_start_time_us, rows[-1].time_us,
            len(rows), chunk_coverage_days, fit_start_time_us, len(fit_rows),
            fit_coverage_days, None, None, None, "insufficient_90day_coverage",
        )

    fit = ordinary_least_squares([
        (row.time_us, row.semi_major_axis_m)
        for row in fit_rows
    ])
    return ChunkBaseline(
        rows[0].chunk_id, rows[0].orbit_start_time_us, rows[-1].time_us,
        len(rows), chunk_coverage_days, fit_start_time_us, len(fit_rows),
        fit_coverage_days, fit["rate_m_day"], fit["rate_1sigma_m_day"],
        fit["residual_std_m"], "evaluated",
    )


def calculate_baselines(rows: list[OrbitMean]) -> list[ChunkBaseline]:
    """Input: all accepted 2022 orbit means.
    Output: one trailing 90-day baseline record per source chunk."""
    rows_by_chunk: dict[int, list[OrbitMean]] = {}
    for row in rows:
        rows_by_chunk.setdefault(row.chunk_id, []).append(row)
    return [
        calculate_chunk_baseline(chunk_rows)
        for chunk_rows in rows_by_chunk.values()
    ]


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection.
    Output: versioned 2022 orbit-mean, baseline, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_2022_orbit_mean_v1 (
            time_us INTEGER PRIMARY KEY,
            orbit_start_time_us INTEGER NOT NULL,
            phase_weighted_mean_semi_major_axis_m REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_2022_chunk_baseline_v1 (
            chunk_id INTEGER PRIMARY KEY,
            chunk_start_time_us INTEGER NOT NULL,
            chunk_stop_time_us INTEGER NOT NULL,
            chunk_orbit_count INTEGER NOT NULL,
            chunk_coverage_days REAL NOT NULL,
            fit_start_time_us INTEGER NOT NULL,
            fit_orbit_count INTEGER NOT NULL,
            fit_coverage_days REAL NOT NULL,
            rate_m_day REAL,
            rate_1sigma_m_day REAL,
            residual_std_m REAL,
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_2022_baseline_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_output(
    output_path: Path,
    orbit_rows: list[OrbitMean],
    baselines: list[ChunkBaseline],
) -> None:
    """Input: output path, 2022 orbit means, and chunk fits.
    Output: new Phase 6 SQLite file; source records remain unchanged."""
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 6 output: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".part")
    temporary_path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_2022_orbit_mean_v1 VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        row.time_us, row.orbit_start_time_us,
                        row.semi_major_axis_m, row.chunk_id, ALGORITHM_VERSION,
                    )
                    for row in orbit_rows
                ],
            )
            output.executemany(
                "INSERT INTO phase6_2022_chunk_baseline_v1 VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        fit.chunk_id, fit.chunk_start_time_us, fit.chunk_stop_time_us,
                        fit.chunk_orbit_count, fit.chunk_coverage_days,
                        fit.fit_start_time_us, fit.fit_orbit_count,
                        fit.fit_coverage_days, fit.rate_m_day,
                        fit.rate_1sigma_m_day, fit.residual_std_m,
                        fit.status, ALGORITHM_VERSION,
                    )
                    for fit in baselines
                ],
            )
            output.executemany(
                "INSERT INTO phase6_2022_baseline_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("source_database", str(DEFAULT_SOURCE)),
                    ("source_scope", "2022-01-01T00:00:00Z/2023-01-01T00:00:00Z"),
                    ("lookback_days", str(LOOKBACK_DAYS)),
                    ("limitation", "descriptive same-chunk trend; not physical drag"),
                ],
            )
            output.commit()
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default Phase 1R source and Phase 6 output paths.
    Output: counts for stored 2022 orbit means and evaluated 90-day fits."""
    with closing(source_connection(DEFAULT_SOURCE)) as source:
        orbit_rows = load_2022_orbit_means(source)
    baselines = calculate_baselines(orbit_rows)
    write_output(DEFAULT_OUTPUT, orbit_rows, baselines)
    return {
        "orbit_count": len(orbit_rows),
        "chunk_count": len(baselines),
        "evaluated_fit_count": sum(fit.status == "evaluated" for fit in baselines),
    }


def main() -> None:
    """Input: no command-line arguments.
    Output: new Phase 6 2022 SQLite file or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_2022_baseline")
    print(run())


if __name__ == "__main__":
    main()
