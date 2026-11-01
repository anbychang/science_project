"""Measure six-day storm excess decay from strictly pre-window quiet days."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

from phases.phase1.code.calc_orbit_decay_diagnostics import ordinary_least_squares
from phases.phase6.code.calc_phase6_quiet_endpoint_sensitivity import endpoint_estimate
from phases.phase6.code.prep_phase6_quiet_audit import (
    daily_ap_maximums,
    day_start_us,
    sme_daily_maximum,
)


DEFAULT_PHASE1_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite",
)
DEFAULT_EVENT_DATABASE = Path(
    "phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite",
)
DEFAULT_SME_FOLDER = Path("phases/phase0/data/raw/sme")
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_storm_excess_decay_v2.sqlite",
)
PHASE_ORBIT_TABLE = "swarm_a_phase_orbit_mean_v2"
DAY_US = 86_400_000_000
LOOKBACK_DAYS = 90
WINDOW_START_DAYS = -2
WINDOW_STOP_DAYS = 4
MAXIMUM_AP = 7.0
MAXIMUM_SME_NT = 300.0
ENDPOINT_ORBIT_COUNTS = (4, 6, 8)
REFERENCE_ENDPOINT_ORBIT_COUNT = 6
ALGORITHM_VERSION = "phase6_quiet_background_excess_decay_v2"


@dataclass(frozen=True)
class CalculationPaths:
    """Input: orbit, event, SME, and new output paths.
    Output: immutable path record for the quiet-background calculation."""

    phase1_database: Path = DEFAULT_PHASE1_DATABASE
    event_database: Path = DEFAULT_EVENT_DATABASE
    sme_folder: Path = DEFAULT_SME_FOLDER
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class QuietDay:
    """Input: one complete UTC day of geomagnetic drivers.
    Output: accepted quiet-day start and observed maxima."""

    day_start_time_us: int
    ap_max: float
    sme_max_nt: float


@dataclass(frozen=True)
class StormEvent:
    """Input: one Phase 4 storm row.
    Output: event ID and t0 in UTC microseconds."""

    storm_id: str
    t0_time_us: int


@dataclass(frozen=True)
class OrbitMean:
    """Input: one complete Phase 1 orbit mean.
    Output: orbit timing, semi-major axis, and source chunk."""

    time_us: int
    orbit_start_time_us: int
    semi_major_axis_m: float
    chunk_id: int


@dataclass(frozen=True)
class QuietBaseline:
    """Input: one event's strictly pre-window quiet orbit means.
    Output: quiet-day coverage and optional OLS background slope."""

    event: StormEvent
    event_start_time_us: int
    search_start_time_us: int
    chunk_id: int | None
    quiet_day_count: int
    longest_quiet_run_days: int
    nearest_quiet_gap_days: float | None
    orbit_count: int
    coverage_days: float
    rate_m_day: float | None
    rate_1sigma_m_day: float | None
    residual_std_m: float | None
    status: str


@dataclass(frozen=True)
class StormExcessDecay:
    """Input: quiet background and complete [-2, +4) event orbit means.
    Output: observed, expected, and excess semi-major-axis changes."""

    baseline: QuietBaseline
    first_orbit_time_us: int | None
    last_orbit_time_us: int | None
    event_orbit_count: int
    duration_days: float | None
    observed_delta_a_4_m: float | None
    observed_delta_a_6_m: float | None
    observed_delta_a_8_m: float | None
    observed_ols_sigma_6_m: float | None
    endpoint_span_m: float | None
    background_delta_a_m: float | None
    excess_decay_4_m: float | None
    excess_decay_6_m: float | None
    excess_decay_8_m: float | None
    excess_decay_ols_sigma_6_m: float | None
    status: str


def load_events(connection: sqlite3.Connection) -> list[StormEvent]:
    """Input: Phase 4 event SQLite connection.
    Output: ordered [StormEvent, ...] for the fixed 25 storms."""
    return [
        StormEvent(str(storm_id), int(t0_time_us))
        for storm_id, t0_time_us in connection.execute(
            "SELECT storm_id, t0_time_us FROM trial4_25storm_overview ORDER BY t0_time_us",
        )
    ]


def load_quiet_days(
    connection: sqlite3.Connection,
    sme_folder: Path,
    events: list[StormEvent],
) -> list[QuietDay]:
    """Input: weather connection, SME folder, and event list.
    Output: complete UTC days passing fixed Ap and SME quiet thresholds."""
    first_start_us = min(event.t0_time_us for event in events) + WINDOW_START_DAYS * DAY_US
    last_start_us = max(event.t0_time_us for event in events) + WINDOW_START_DAYS * DAY_US
    ap_maximums = daily_ap_maximums(
        connection,
        first_start_us - LOOKBACK_DAYS * DAY_US,
        last_start_us,
    )
    quiet_days = []
    for day, ap_max in sorted(ap_maximums.items()):
        if ap_max > MAXIMUM_AP:
            continue
        sme_path = sme_folder / f"SME_{day:%Y%m%d}.csv"
        if not sme_path.exists():
            continue
        sme_max_nt = sme_daily_maximum(sme_path, day)
        if sme_max_nt is not None and sme_max_nt < MAXIMUM_SME_NT:
            quiet_days.append(QuietDay(day_start_us(day), ap_max, sme_max_nt))
    return quiet_days


def event_chunk_id(
    connection: sqlite3.Connection,
    event_start_time_us: int,
) -> int | None:
    """Input: Phase 1 connection and event-window start time.
    Output: latest source chunk strictly before the event window."""
    row = connection.execute(
        f"SELECT chunk_id FROM {PHASE_ORBIT_TABLE} WHERE time_us < ? "
        "ORDER BY time_us DESC LIMIT 1",
        (event_start_time_us,),
    ).fetchone()
    return None if row is None else int(row[0])


def load_orbit_rows(
    connection: sqlite3.Connection,
    chunk_id: int,
    time_bounds: tuple[int, int],
) -> list[OrbitMean]:
    """Input: Phase 1 connection, one chunk, and [start, stop) UTC bounds.
    Output: ordered complete orbit means inside the requested bounds."""
    start_time_us, stop_time_us = time_bounds
    rows = connection.execute(
        f"SELECT time_us, orbit_start_time_us, "
        f"phase_weighted_mean_semi_major_axis_m, chunk_id "
        f"FROM {PHASE_ORBIT_TABLE} WHERE chunk_id = ? "
        "AND time_us >= ? AND time_us < ? ORDER BY time_us",
        (chunk_id, start_time_us, stop_time_us),
    )
    return [
        OrbitMean(int(time_us), int(orbit_start_us), float(mean_a_m), int(row_chunk_id))
        for time_us, orbit_start_us, mean_a_m, row_chunk_id in rows
    ]


def select_quiet_rows(
    rows: list[OrbitMean],
    quiet_day_starts: set[int],
    event_start_time_us: int,
) -> list[OrbitMean]:
    """Input: candidate orbit means, accepted days, and event-window start.
    Output: rows on complete quiet UTC days ending before the event window."""
    return [
        row
        for row in rows
        if (
            row.time_us // DAY_US * DAY_US in quiet_day_starts
            and row.time_us // DAY_US * DAY_US + DAY_US <= event_start_time_us
        )
    ]


def longest_consecutive_days(day_starts: set[int]) -> int:
    """Input: accepted UTC day-start keys.
    Output: longest run of consecutive days, or zero for no days."""
    longest_run = 0
    current_run = 0
    previous_day_start = None
    for current_day_start in sorted(day_starts):
        current_run = (
            current_run + 1
            if previous_day_start is not None
            and current_day_start - previous_day_start == DAY_US
            else 1
        )
        longest_run = max(longest_run, current_run)
        previous_day_start = current_day_start
    return longest_run


def fit_quiet_baseline(
    event: StormEvent,
    chunk_id: int | None,
    quiet_rows: list[OrbitMean],
) -> QuietBaseline:
    """Input: event, pre-window source chunk, and selected quiet orbit means.
    Output: quiet-day coverage and OLS background slope when available."""
    event_start_time_us = event.t0_time_us + WINDOW_START_DAYS * DAY_US
    search_start_time_us = event_start_time_us - LOOKBACK_DAYS * DAY_US
    quiet_day_starts = {row.time_us // DAY_US * DAY_US for row in quiet_rows}
    if not quiet_rows:
        return QuietBaseline(
            event, event_start_time_us, search_start_time_us, chunk_id,
            0, 0, None, 0, 0.0, None, None, None, "no_quiet_orbits",
        )
    coverage_days = (
        quiet_rows[-1].time_us - quiet_rows[0].orbit_start_time_us
    ) / DAY_US
    nearest_day_end_us = max(quiet_day_starts) + DAY_US
    nearest_gap_days = (event_start_time_us - nearest_day_end_us) / DAY_US
    if len(quiet_rows) < 3:
        return QuietBaseline(
            event, event_start_time_us, search_start_time_us, chunk_id,
            len(quiet_day_starts), longest_consecutive_days(quiet_day_starts),
            nearest_gap_days, len(quiet_rows), coverage_days,
            None, None, None, "insufficient_quiet_orbits",
        )
    fit = ordinary_least_squares([
        (row.time_us, row.semi_major_axis_m)
        for row in quiet_rows
    ])
    return QuietBaseline(
        event, event_start_time_us, search_start_time_us, chunk_id,
        len(quiet_day_starts), longest_consecutive_days(quiet_day_starts),
        nearest_gap_days, len(quiet_rows), coverage_days,
        fit["rate_m_day"], fit["rate_1sigma_m_day"], fit["residual_std_m"],
        "evaluated",
    )


def measure_storm(
    baseline: QuietBaseline,
    event_rows: list[OrbitMean],
) -> StormExcessDecay:
    """Input: one quiet background and full [-2, +4) event orbit means.
    Output: six-day observed change, expected background, and excess loss."""
    if baseline.rate_m_day is None:
        return StormExcessDecay(
            baseline, None, None, len(event_rows), None,
            None, None, None, None, None, None,
            None, None, None, None, baseline.status,
        )
    if len(event_rows) < 2 * max(ENDPOINT_ORBIT_COUNTS):
        return StormExcessDecay(
            baseline, None, None, len(event_rows), None,
            None, None, None, None, None, None,
            None, None, None, None, "insufficient_event_orbits",
        )
    estimates = {
        orbit_count: endpoint_estimate(event_rows, orbit_count)
        for orbit_count in ENDPOINT_ORBIT_COUNTS
    }
    duration_days = (event_rows[-1].time_us - event_rows[0].time_us) / DAY_US
    background_delta_a_m = baseline.rate_m_day * duration_days
    excess_by_count = {
        orbit_count: background_delta_a_m - estimate.delta_a_m
        for orbit_count, estimate in estimates.items()
    }
    observed_deltas = [estimate.delta_a_m for estimate in estimates.values()]
    reference_sigma_m = estimates[REFERENCE_ENDPOINT_ORBIT_COUNT].ols_sigma_m
    baseline_sigma_m = baseline.rate_1sigma_m_day * duration_days
    return StormExcessDecay(
        baseline=baseline,
        first_orbit_time_us=event_rows[0].time_us,
        last_orbit_time_us=event_rows[-1].time_us,
        event_orbit_count=len(event_rows),
        duration_days=duration_days,
        observed_delta_a_4_m=estimates[4].delta_a_m,
        observed_delta_a_6_m=estimates[6].delta_a_m,
        observed_delta_a_8_m=estimates[8].delta_a_m,
        observed_ols_sigma_6_m=reference_sigma_m,
        endpoint_span_m=max(observed_deltas) - min(observed_deltas),
        background_delta_a_m=background_delta_a_m,
        excess_decay_4_m=excess_by_count[4],
        excess_decay_6_m=excess_by_count[6],
        excess_decay_8_m=excess_by_count[8],
        excess_decay_ols_sigma_6_m=sqrt(reference_sigma_m ** 2 + baseline_sigma_m ** 2),
        status="evaluated",
    )


def calculate_events(
    phase1: sqlite3.Connection,
    events: list[StormEvent],
    quiet_days: list[QuietDay],
) -> tuple[list[QuietBaseline], list[StormExcessDecay]]:
    """Input: Phase 1 connection, fixed events, and accepted quiet days.
    Output: per-event quiet baselines and six-day excess-decay results."""
    quiet_day_starts = {item.day_start_time_us for item in quiet_days}
    baselines = []
    measures = []
    for event in events:
        event_start_time_us = event.t0_time_us + WINDOW_START_DAYS * DAY_US
        chunk_id = event_chunk_id(phase1, event_start_time_us)
        if chunk_id is None:
            baseline = fit_quiet_baseline(event, None, [])
            event_rows = []
        else:
            candidate_rows = load_orbit_rows(
                phase1,
                chunk_id,
                (event_start_time_us - LOOKBACK_DAYS * DAY_US, event_start_time_us),
            )
            quiet_rows = select_quiet_rows(
                candidate_rows, quiet_day_starts, event_start_time_us,
            )
            baseline = fit_quiet_baseline(event, chunk_id, quiet_rows)
            event_rows = load_orbit_rows(
                phase1,
                chunk_id,
                (event_start_time_us, event.t0_time_us + WINDOW_STOP_DAYS * DAY_US),
            )
        baselines.append(baseline)
        measures.append(measure_storm(baseline, event_rows))
    return baselines, measures


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection.
    Output: versioned quiet-day, baseline, excess-decay, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_prestorm_quiet_day_v1 (
            day_start_time_us INTEGER PRIMARY KEY,
            ap_max REAL NOT NULL,
            sme_max_nt REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_prestorm_quiet_baseline_v1 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            event_start_time_us INTEGER NOT NULL,
            search_start_time_us INTEGER NOT NULL,
            chunk_id INTEGER,
            quiet_day_count INTEGER NOT NULL,
            longest_quiet_run_days INTEGER NOT NULL,
            nearest_quiet_gap_days REAL,
            quiet_orbit_count INTEGER NOT NULL,
            quiet_coverage_days REAL NOT NULL,
            quiet_rate_m_day REAL,
            quiet_rate_1sigma_m_day REAL,
            quiet_residual_std_m REAL,
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_storm_excess_decay_v2 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            event_start_time_us INTEGER NOT NULL,
            event_stop_time_us INTEGER NOT NULL,
            first_orbit_time_us INTEGER,
            last_orbit_time_us INTEGER,
            event_orbit_count INTEGER NOT NULL,
            chunk_id INTEGER,
            duration_days REAL,
            observed_delta_a_4_m REAL,
            observed_delta_a_6_m REAL,
            observed_delta_a_8_m REAL,
            observed_delta_a_ols_sigma_6_m REAL,
            endpoint_span_m REAL,
            quiet_background_delta_a_m REAL,
            excess_decay_4_m REAL,
            excess_decay_6_m REAL,
            excess_decay_8_m REAL,
            excess_decay_ols_sigma_6_m REAL,
            increased_decay INTEGER CHECK (increased_decay IN (0, 1)),
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_quiet_background_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_output(
    paths: CalculationPaths,
    quiet_days: list[QuietDay],
    results: tuple[list[QuietBaseline], list[StormExcessDecay]],
) -> None:
    """Input: paths, quiet-day audit, baselines, and event measures.
    Output: new Phase 6 SQLite without modifying upstream observations."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 6 output: {paths.output}")
    baselines, measures = results
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    temporary_path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_prestorm_quiet_day_v1 VALUES (?, ?, ?, ?)",
                [
                    (day.day_start_time_us, day.ap_max, day.sme_max_nt, ALGORITHM_VERSION)
                    for day in quiet_days
                ],
            )
            output.executemany(
                "INSERT INTO phase6_prestorm_quiet_baseline_v1 VALUES "
                f"({', '.join('?' for _ in range(15))})",
                [
                    (
                        item.event.storm_id, item.event.t0_time_us,
                        item.event_start_time_us, item.search_start_time_us,
                        item.chunk_id, item.quiet_day_count,
                        item.longest_quiet_run_days, item.nearest_quiet_gap_days,
                        item.orbit_count, item.coverage_days, item.rate_m_day,
                        item.rate_1sigma_m_day, item.residual_std_m,
                        item.status, ALGORITHM_VERSION,
                    )
                    for item in baselines
                ],
            )
            output.executemany(
                "INSERT INTO phase6_storm_excess_decay_v2 VALUES "
                f"({', '.join('?' for _ in range(22))})",
                [
                    (
                        item.baseline.event.storm_id,
                        item.baseline.event.t0_time_us,
                        item.baseline.event_start_time_us,
                        item.baseline.event.t0_time_us + WINDOW_STOP_DAYS * DAY_US,
                        item.first_orbit_time_us, item.last_orbit_time_us,
                        item.event_orbit_count, item.baseline.chunk_id,
                        item.duration_days, item.observed_delta_a_4_m,
                        item.observed_delta_a_6_m, item.observed_delta_a_8_m,
                        item.observed_ols_sigma_6_m, item.endpoint_span_m,
                        item.background_delta_a_m, item.excess_decay_4_m,
                        item.excess_decay_6_m, item.excess_decay_8_m,
                        item.excess_decay_ols_sigma_6_m,
                        None if item.excess_decay_6_m is None else int(item.excess_decay_6_m > 0),
                        item.status, ALGORITHM_VERSION,
                    )
                    for item in measures
                ],
            )
            output.executemany(
                "INSERT INTO phase6_quiet_background_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1_database)),
                    ("event_database", str(paths.event_database)),
                    ("quiet_search_days", str(LOOKBACK_DAYS)),
                    ("storm_window_days", "[-2, +4) from t0"),
                    ("quiet_rule", "complete UTC day; Ap<=7; SME<300 nT"),
                    ("density_required", "false"),
                    ("endpoint_orbit_counts", "4,6,8"),
                    ("sign", "positive excess_decay means faster loss than quiet background"),
                    ("limitation", "descriptive mean-element difference; not calibrated drag"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default Phase 1, Phase 4, SME, and Phase 6 paths.
    Output: new quiet-background excess-decay SQLite and result counts."""
    paths = CalculationPaths()
    with (
        closing(sqlite3.connect(paths.phase1_database)) as phase1,
        closing(sqlite3.connect(paths.event_database)) as event_database,
    ):
        events = load_events(event_database)
        quiet_days = load_quiet_days(phase1, paths.sme_folder, events)
        results = calculate_events(phase1, events, quiet_days)
    baselines, measures = results
    write_output(paths, quiet_days, results)
    return {
        "quiet_day_count": len(quiet_days),
        "storm_count": len(events),
        "evaluated_count": sum(item.status == "evaluated" for item in measures),
        "increased_decay_count": sum(
            item.excess_decay_6_m is not None and item.excess_decay_6_m > 0
            for item in measures
        ),
    }


def main() -> None:
    """Input: no command-line arguments.
    Output: one new Phase 6 v2 SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit(
            "Usage: python -m phases.phase6.code.calc_phase6_quiet_background_excess_decay",
        )
    print(run())


if __name__ == "__main__":
    main()
