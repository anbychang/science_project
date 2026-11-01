"""Apply a continuous time-linear decay baseline anchored to paper values."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from phases.phase6.code.calc_phase6_quiet_background_excess_decay import (
    DAY_US,
    ENDPOINT_ORBIT_COUNTS,
    REFERENCE_ENDPOINT_ORBIT_COUNT,
    WINDOW_START_DAYS,
    WINDOW_STOP_DAYS,
    OrbitMean,
    StormEvent,
    event_chunk_id,
    load_events,
    load_orbit_rows,
)
from phases.phase6.code.calc_phase6_quiet_endpoint_sensitivity import endpoint_estimate


DEFAULT_PHASE1_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite",
)
DEFAULT_EVENT_DATABASE = Path(
    "phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite",
)
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_paper_time_linear_baseline_v3.sqlite",
)
FIRST_MODEL_YEAR = 2023
LAST_MODEL_YEAR = 2026
ANCHOR_2024_TIME_US = int(
    datetime(2024, 5, 4, 12, tzinfo=timezone.utc).timestamp() * 1_000_000,
)
ANCHOR_2026_TIME_US = int(
    datetime(2026, 1, 31, 12, tzinfo=timezone.utc).timestamp() * 1_000_000,
)
ANCHOR_2024_RATE_M_DAY = -19.91
ANCHOR_2026_RATE_M_DAY = -79.43
RATE_CHANGE_PER_DAY = (
    (ANCHOR_2026_RATE_M_DAY - ANCHOR_2024_RATE_M_DAY)
    / ((ANCHOR_2026_TIME_US - ANCHOR_2024_TIME_US) / DAY_US)
)
ALGORITHM_VERSION = "phase6_paper_time_linear_baseline_v3"


@dataclass(frozen=True)
class PaperBaselinePaths:
    """Input: Phase 1 orbit, Phase 4 event, and output paths.
    Output: immutable paths for the time-linear calculation."""

    phase1_database: Path = DEFAULT_PHASE1_DATABASE
    event_database: Path = DEFAULT_EVENT_DATABASE
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class TimeBaseline:
    """Input: one supported event time.
    Output: continuous paper-linear rate and interpolation role."""

    rate_m_day: float
    offset_from_2024_anchor_days: float
    source_role: str


@dataclass(frozen=True)
class EventMeasure:
    """Input: one event window and its time-linear background.
    Output: observed, expected, and excess semi-major-axis changes."""

    event: StormEvent
    baseline: TimeBaseline | None
    chunk_id: int | None
    first_orbit_time_us: int | None
    last_orbit_time_us: int | None
    orbit_count: int
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
    status: str


def utc_year(time_us: int) -> int:
    """Input: UTC microseconds.
    Output: UTC calendar year."""
    return datetime.fromtimestamp(time_us / 1_000_000, timezone.utc).year


def paper_time_baseline(time_us: int) -> TimeBaseline | None:
    """Input: event UTC microseconds.
    Output: continuous rate for 2023--2026, or None outside scope."""
    if not FIRST_MODEL_YEAR <= utc_year(time_us) <= LAST_MODEL_YEAR:
        return None
    offset_days = (time_us - ANCHOR_2024_TIME_US) / DAY_US
    if time_us < ANCHOR_2024_TIME_US:
        source_role = "backward_extrapolation"
    elif time_us > ANCHOR_2026_TIME_US:
        source_role = "forward_extrapolation"
    else:
        source_role = "linear_interpolation"
    return TimeBaseline(
        rate_m_day=ANCHOR_2024_RATE_M_DAY + RATE_CHANGE_PER_DAY * offset_days,
        offset_from_2024_anchor_days=offset_days,
        source_role=source_role,
    )


def measure_event(
    event: StormEvent,
    baseline: TimeBaseline | None,
    rows: list[OrbitMean],
) -> EventMeasure:
    """Input: event, optional time baseline, and six-day orbit means.
    Output: time-linear expected change and observed excess loss."""
    chunk_id = rows[0].chunk_id if rows else None
    if baseline is None:
        return EventMeasure(
            event, None, chunk_id, None, None, len(rows), None,
            None, None, None, None, None, None, None, None, None,
            "outside_2023_2026",
        )
    if len(rows) < 2 * max(ENDPOINT_ORBIT_COUNTS):
        return EventMeasure(
            event, baseline, chunk_id, None, None, len(rows), None,
            None, None, None, None, None, None, None, None, None,
            "insufficient_event_orbits",
        )
    estimates = {
        orbit_count: endpoint_estimate(rows, orbit_count)
        for orbit_count in ENDPOINT_ORBIT_COUNTS
    }
    duration_days = (rows[-1].time_us - rows[0].time_us) / DAY_US
    background_delta_a_m = baseline.rate_m_day * duration_days
    excess_by_count = {
        orbit_count: background_delta_a_m - estimate.delta_a_m
        for orbit_count, estimate in estimates.items()
    }
    observed_values = [estimate.delta_a_m for estimate in estimates.values()]
    return EventMeasure(
        event=event,
        baseline=baseline,
        chunk_id=chunk_id,
        first_orbit_time_us=rows[0].time_us,
        last_orbit_time_us=rows[-1].time_us,
        orbit_count=len(rows),
        duration_days=duration_days,
        observed_delta_a_4_m=estimates[4].delta_a_m,
        observed_delta_a_6_m=estimates[6].delta_a_m,
        observed_delta_a_8_m=estimates[8].delta_a_m,
        observed_ols_sigma_6_m=estimates[REFERENCE_ENDPOINT_ORBIT_COUNT].ols_sigma_m,
        endpoint_span_m=max(observed_values) - min(observed_values),
        background_delta_a_m=background_delta_a_m,
        excess_decay_4_m=excess_by_count[4],
        excess_decay_6_m=excess_by_count[6],
        excess_decay_8_m=excess_by_count[8],
        status="evaluated",
    )


def calculate_measures(
    phase1: sqlite3.Connection,
    events: list[StormEvent],
) -> list[EventMeasure]:
    """Input: Phase 1 connection and fixed storm events.
    Output: time-linear six-day measures for all events."""
    measures = []
    for event in events:
        start_time_us = event.t0_time_us + WINDOW_START_DAYS * DAY_US
        stop_time_us = event.t0_time_us + WINDOW_STOP_DAYS * DAY_US
        chunk_id = event_chunk_id(phase1, start_time_us)
        rows = [] if chunk_id is None else load_orbit_rows(
            phase1, chunk_id, (start_time_us, stop_time_us),
        )
        measures.append(measure_event(
            event,
            paper_time_baseline(event.t0_time_us),
            rows,
        ))
    return measures


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection.
    Output: anchor, event-result, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_paper_time_anchor_v3 (
            anchor_time_us INTEGER PRIMARY KEY,
            rate_m_day REAL NOT NULL,
            source_date TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_paper_time_linear_excess_decay_v3 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            year INTEGER NOT NULL,
            event_rate_m_day REAL,
            offset_from_2024_anchor_days REAL,
            source_role TEXT,
            first_orbit_time_us INTEGER,
            last_orbit_time_us INTEGER,
            orbit_count INTEGER NOT NULL,
            chunk_id INTEGER,
            duration_days REAL,
            observed_delta_a_4_m REAL,
            observed_delta_a_6_m REAL,
            observed_delta_a_8_m REAL,
            observed_delta_a_ols_sigma_6_m REAL,
            endpoint_span_m REAL,
            paper_background_delta_a_m REAL,
            excess_decay_4_m REAL,
            excess_decay_6_m REAL,
            excess_decay_8_m REAL,
            increased_decay INTEGER CHECK (increased_decay IN (0, 1)),
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_paper_time_linear_metadata_v3 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_output(paths: PaperBaselinePaths, measures: list[EventMeasure]) -> None:
    """Input: Phase 6 paths and time-linear event measures.
    Output: new versioned SQLite without changing source records."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    temporary_path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_paper_time_anchor_v3 VALUES (?, ?, ?, ?)",
                [
                    (ANCHOR_2024_TIME_US, ANCHOR_2024_RATE_M_DAY, "2024-05-04", ALGORITHM_VERSION),
                    (ANCHOR_2026_TIME_US, ANCHOR_2026_RATE_M_DAY, "2026-01-31", ALGORITHM_VERSION),
                ],
            )
            output.executemany(
                "INSERT INTO phase6_paper_time_linear_excess_decay_v3 VALUES "
                f"({', '.join('?' for _ in range(23))})",
                [
                    (
                        item.event.storm_id, item.event.t0_time_us,
                        utc_year(item.event.t0_time_us),
                        None if item.baseline is None else item.baseline.rate_m_day,
                        None if item.baseline is None else item.baseline.offset_from_2024_anchor_days,
                        None if item.baseline is None else item.baseline.source_role,
                        item.first_orbit_time_us, item.last_orbit_time_us,
                        item.orbit_count, item.chunk_id, item.duration_days,
                        item.observed_delta_a_4_m, item.observed_delta_a_6_m,
                        item.observed_delta_a_8_m, item.observed_ols_sigma_6_m,
                        item.endpoint_span_m, item.background_delta_a_m,
                        item.excess_decay_4_m, item.excess_decay_6_m,
                        item.excess_decay_8_m,
                        None if item.excess_decay_6_m is None else int(item.excess_decay_6_m > 0),
                        item.status, ALGORITHM_VERSION,
                    )
                    for item in measures
                ],
            )
            output.executemany(
                "INSERT INTO phase6_paper_time_linear_metadata_v3 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("rate_change_per_day", str(RATE_CHANGE_PER_DAY)),
                    ("paper_doi", "10.1029/2026GL125768"),
                    ("storm_window_days", "[-2, +4) from t0"),
                    ("scope", "event t0 in UTC years 2023 through 2026"),
                    ("limitation", "time-only empirical proxy; ignores altitude, local time, season, and solar state"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default Phase 1, Phase 4, and output paths.
    Output: new time-linear SQLite and event counts."""
    paths = PaperBaselinePaths()
    with (
        closing(sqlite3.connect(paths.phase1_database)) as phase1,
        closing(sqlite3.connect(paths.event_database)) as event_database,
    ):
        measures = calculate_measures(phase1, load_events(event_database))
    write_output(paths, measures)
    return {
        "event_count": len(measures),
        "evaluated_count": sum(item.status == "evaluated" for item in measures),
        "increased_decay_count": sum(
            item.excess_decay_6_m is not None and item.excess_decay_6_m > 0
            for item in measures
        ),
    }


def main() -> None:
    """Input: no command-line arguments.
    Output: one new time-linear SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit(
            "Usage: python -m phases.phase6.code.calc_phase6_paper_time_linear_baseline",
        )
    print(run())


if __name__ == "__main__":
    main()
