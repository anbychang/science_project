"""Compare 90-day all-data and quiet-day semi-major-axis slopes before storms."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase1.code.calc_orbit_decay_diagnostics import ordinary_least_squares


DEFAULT_PHASE1_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite",
)
DEFAULT_EVENT_DATABASE = Path(
    "phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite",
)
DEFAULT_QUIET_DATABASE = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_quiet_audit_v1.sqlite",
)
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_prestorm_baseline_v1.sqlite",
)
PHASE_ORBIT_TABLE = "swarm_a_phase_orbit_mean_v2"
DAY_US = 86_400_000_000
LOOKBACK_DAYS = 90
ALGORITHM_VERSION = "phase6_prestorm_90day_baseline_v1"


@dataclass(frozen=True)
class BaselinePaths:
    """Input: read-only Phase 1, event, quiet-day, and new output paths.
    Output: immutable Phase 6 baseline path record."""

    phase1_database: Path = DEFAULT_PHASE1_DATABASE
    event_database: Path = DEFAULT_EVENT_DATABASE
    quiet_database: Path = DEFAULT_QUIET_DATABASE
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class OrbitMean:
    """Input: one Phase 1 complete-orbit mean row.
    Output: UTC time, semi-major axis, orbit start, and chunk identity."""

    time_us: int
    semi_major_axis_m: float
    orbit_start_time_us: int
    chunk_id: int


@dataclass(frozen=True)
class FitSummary:
    """Input: one collection of orbit means.
    Output: count, coverage, slope, OLS sigma, and residual spread."""

    orbit_count: int
    coverage_days: float
    rate_m_day: float | None
    rate_1sigma_m_day: float | None
    residual_std_m: float | None


@dataclass(frozen=True)
class StormBaseline:
    """Input: one storm's 90-day orbit means and quiet-day subset.
    Output: comparable all-data and quiet-only baseline fits."""

    storm_id: str
    t0_time_us: int
    lookback_start_time_us: int
    chunk_id: int | None
    all_fit: FitSummary
    quiet_day_count: int
    quiet_fit: FitSummary
    status: str


def storm_events(connection: sqlite3.Connection) -> list[tuple[str, int]]:
    """Input: Phase 4 event SQLite connection.
    Output: ordered [(storm_id, t0_time_us), ...] for the fixed 25 storms."""
    return [
        (str(storm_id), int(t0_time_us))
        for storm_id, t0_time_us in connection.execute(
            "SELECT storm_id, t0_time_us FROM trial4_25storm_overview ORDER BY t0_time_us",
        )
    ]


def quiet_day_starts(connection: sqlite3.Connection) -> set[int]:
    """Input: Phase 6 quiet-audit SQLite connection.
    Output: UTC day-start keys that passed the fixed quiet-day rules."""
    return {
        int(row[0])
        for row in connection.execute(
            "SELECT day_start_time_us FROM phase6_quiet_day_v1",
        )
    }


def event_orbit_rows(
    connection: sqlite3.Connection,
    t0_time_us: int,
) -> tuple[int | None, list[OrbitMean]]:
    """Input: Phase 1 connection and one storm t0.
    Output: latest pre-t0 chunk and its orbit means within the prior 90 days."""
    chunk_row = connection.execute(
        f"SELECT chunk_id FROM {PHASE_ORBIT_TABLE} WHERE time_us < ? "
        "ORDER BY time_us DESC LIMIT 1",
        (t0_time_us,),
    ).fetchone()
    if chunk_row is None:
        return None, []
    chunk_id = int(chunk_row[0])
    start_time_us = t0_time_us - LOOKBACK_DAYS * DAY_US
    rows = connection.execute(
        f"SELECT time_us, phase_weighted_mean_semi_major_axis_m, "
        f"orbit_start_time_us, chunk_id FROM {PHASE_ORBIT_TABLE} "
        "WHERE chunk_id = ? AND time_us >= ? AND time_us < ? ORDER BY time_us",
        (chunk_id, start_time_us, t0_time_us),
    )
    return chunk_id, [
        OrbitMean(int(time_us), float(mean_a_m), int(orbit_start_us), int(row_chunk_id))
        for time_us, mean_a_m, orbit_start_us, row_chunk_id in rows
    ]


def quiet_rows(rows: list[OrbitMean], day_starts: set[int]) -> list[OrbitMean]:
    """Input: ordered orbit means and accepted quiet UTC day-start keys.
    Output: orbit means whose end time lies on an accepted quiet day."""
    return [row for row in rows if row.time_us // DAY_US * DAY_US in day_starts]


def fit_summary(rows: list[OrbitMean]) -> FitSummary:
    """Input: ordered same-chunk orbit means.
    Output: OLS baseline slope summary, or missing fit values below three points."""
    if not rows:
        return FitSummary(0, 0.0, None, None, None)
    coverage_days = (rows[-1].time_us - rows[0].orbit_start_time_us) / DAY_US
    if len(rows) < 3:
        return FitSummary(len(rows), coverage_days, None, None, None)
    fit = ordinary_least_squares([
        (row.time_us, row.semi_major_axis_m)
        for row in rows
    ])
    return FitSummary(
        len(rows), coverage_days, fit["rate_m_day"],
        fit["rate_1sigma_m_day"], fit["residual_std_m"],
    )


def measure_storm_baseline(
    event: tuple[str, int],
    rows: list[OrbitMean],
    day_starts: set[int],
) -> StormBaseline:
    """Input: one storm, its pre-t0 orbit means, and accepted quiet days.
    Output: all-data and quiet-day 90-day slope comparison."""
    storm_id, t0_time_us = event
    all_fit = fit_summary(rows)
    selected_quiet_rows = quiet_rows(rows, day_starts)
    quiet_fit = fit_summary(selected_quiet_rows)
    quiet_day_count = len({row.time_us // DAY_US * DAY_US for row in selected_quiet_rows})
    status = "evaluated" if all_fit.rate_m_day is not None else "insufficient_phase_orbits"
    if quiet_fit.rate_m_day is None:
        status += ";no_quiet_fit"
    return StormBaseline(
        storm_id=storm_id,
        t0_time_us=t0_time_us,
        lookback_start_time_us=t0_time_us - LOOKBACK_DAYS * DAY_US,
        chunk_id=rows[-1].chunk_id if rows else None,
        all_fit=all_fit,
        quiet_day_count=quiet_day_count,
        quiet_fit=quiet_fit,
        status=status,
    )


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 baseline SQLite connection.
    Output: versioned pre-storm baseline and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_prestorm_baseline_v1 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            lookback_start_time_us INTEGER NOT NULL,
            chunk_id INTEGER,
            all_orbit_count INTEGER NOT NULL,
            all_coverage_days REAL NOT NULL,
            all_rate_m_day REAL,
            all_rate_1sigma_m_day REAL,
            all_residual_std_m REAL,
            quiet_day_count INTEGER NOT NULL,
            quiet_orbit_count INTEGER NOT NULL,
            quiet_coverage_days REAL NOT NULL,
            quiet_rate_m_day REAL,
            quiet_rate_1sigma_m_day REAL,
            quiet_residual_std_m REAL,
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_prestorm_baseline_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_baselines(paths: BaselinePaths, baselines: list[StormBaseline]) -> None:
    """Input: Phase 6 paths and measured storm baselines.
    Output: a new SQLite comparison without modifying Phase 1 or Phase 4."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_prestorm_baseline_v1 VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        baseline.storm_id, baseline.t0_time_us,
                        baseline.lookback_start_time_us, baseline.chunk_id,
                        baseline.all_fit.orbit_count, baseline.all_fit.coverage_days,
                        baseline.all_fit.rate_m_day, baseline.all_fit.rate_1sigma_m_day,
                        baseline.all_fit.residual_std_m, baseline.quiet_day_count,
                        baseline.quiet_fit.orbit_count, baseline.quiet_fit.coverage_days,
                        baseline.quiet_fit.rate_m_day, baseline.quiet_fit.rate_1sigma_m_day,
                        baseline.quiet_fit.residual_std_m, baseline.status, ALGORITHM_VERSION,
                    )
                    for baseline in baselines
                ],
            )
            output.executemany(
                "INSERT INTO phase6_prestorm_baseline_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1_database)),
                    ("event_database", str(paths.event_database)),
                    ("quiet_database", str(paths.quiet_database)),
                    ("lookback_days", str(LOOKBACK_DAYS)),
                    ("scope", "same pre-t0 chunk; all orbit means versus accepted quiet UTC days"),
                    ("limitation", "long-window descriptive trend, not physical drag or storm-free counterfactual"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default Phase 1, Phase 4 event, and Phase 6 quiet-audit SQLite files.
    Output: a new pre-storm baseline SQLite and event-fit counts."""
    paths = BaselinePaths()
    with (
        closing(sqlite3.connect(paths.phase1_database)) as phase1,
        closing(sqlite3.connect(paths.event_database)) as events,
        closing(sqlite3.connect(paths.quiet_database)) as quiet,
    ):
        day_starts = quiet_day_starts(quiet)
        baselines = []
        for event in storm_events(events):
            _, rows = event_orbit_rows(phase1, event[1])
            baselines.append(measure_storm_baseline(event, rows, day_starts))
    write_baselines(paths, baselines)
    return {
        "storm_count": len(baselines),
        "all_fit_count": sum(baseline.all_fit.rate_m_day is not None for baseline in baselines),
        "quiet_fit_count": sum(baseline.quiet_fit.rate_m_day is not None for baseline in baselines),
    }


def main() -> None:
    """Input: no command-line arguments.
    Output: one new Phase 6 pre-storm baseline SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_prestorm_baseline")
    print(run())


if __name__ == "__main__":
    main()
