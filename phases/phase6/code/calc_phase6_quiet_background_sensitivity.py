"""Test storm excess decay by leaving out each pre-window quiet day."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase1.code.calc_orbit_decay_diagnostics import ordinary_least_squares
from phases.phase6.code.calc_phase6_quiet_background_excess_decay import (
    DAY_US,
    OrbitMean,
    load_orbit_rows,
    select_quiet_rows,
)


DEFAULT_PHASE1_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite",
)
DEFAULT_EXCESS_DATABASE = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_storm_excess_decay_v2.sqlite",
)
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_quiet_background_sensitivity_v1.sqlite",
)
ALGORITHM_VERSION = "phase6_quiet_background_leave_one_day_out_v1"


@dataclass(frozen=True)
class SensitivityPaths:
    """Input: Phase 1, v2 excess-decay, and new output paths.
    Output: immutable path record for quiet-day sensitivity."""

    phase1_database: Path = DEFAULT_PHASE1_DATABASE
    excess_database: Path = DEFAULT_EXCESS_DATABASE
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class EventContext:
    """Input: one evaluated v2 event and its quiet-background metadata.
    Output: source bounds and reference six-day difference."""

    storm_id: str
    event_start_time_us: int
    search_start_time_us: int
    chunk_id: int
    quiet_day_count: int
    event_duration_days: float
    observed_delta_a_6_m: float
    reference_rate_m_day: float
    reference_excess_decay_6_m: float


@dataclass(frozen=True)
class OmissionResult:
    """Input: one omitted quiet UTC day and remaining orbit means.
    Output: refitted background rate and six-day excess loss."""

    storm_id: str
    omitted_day_start_time_us: int
    remaining_quiet_day_count: int
    remaining_orbit_count: int
    rate_m_day: float
    rate_1sigma_m_day: float
    excess_decay_6_m: float


@dataclass(frozen=True)
class SensitivitySummary:
    """Input: one event's reference and leave-one-day-out results.
    Output: rate and excess ranges with sign-stability status."""

    context: EventContext
    omission_count: int
    rate_min_m_day: float | None
    rate_max_m_day: float | None
    excess_min_m: float | None
    excess_max_m: float | None
    maximum_absolute_excess_change_m: float | None
    sign_stable: int | None
    positive_under_all_omissions: int | None
    status: str


def quiet_day_starts(connection: sqlite3.Connection) -> set[int]:
    """Input: v2 quiet-background SQLite connection.
    Output: accepted pre-window quiet UTC day-start keys."""
    return {
        int(row[0])
        for row in connection.execute(
            "SELECT day_start_time_us FROM phase6_prestorm_quiet_day_v1",
        )
    }


def load_contexts(connection: sqlite3.Connection) -> list[EventContext]:
    """Input: v2 quiet-background SQLite connection.
    Output: ordered evaluated event contexts for leave-one-day-out tests."""
    rows = connection.execute("""
        SELECT baseline.storm_id, baseline.event_start_time_us,
               baseline.search_start_time_us, baseline.chunk_id,
               baseline.quiet_day_count, event.duration_days,
               event.observed_delta_a_6_m, baseline.quiet_rate_m_day,
               event.excess_decay_6_m
        FROM phase6_prestorm_quiet_baseline_v1 AS baseline
        JOIN phase6_storm_excess_decay_v2 AS event USING (storm_id)
        WHERE event.status = 'evaluated'
        ORDER BY baseline.t0_time_us
    """)
    return [
        EventContext(
            str(storm_id), int(event_start_time_us), int(search_start_time_us),
            int(chunk_id), int(day_count), float(duration_days),
            float(observed_delta_a_m), float(rate_m_day), float(excess_decay_m),
        )
        for (
            storm_id, event_start_time_us, search_start_time_us, chunk_id,
            day_count, duration_days, observed_delta_a_m, rate_m_day, excess_decay_m,
        ) in rows
    ]


def leave_one_day_out(
    context: EventContext,
    quiet_rows: list[OrbitMean],
) -> list[OmissionResult]:
    """Input: one event context and its selected pre-window quiet orbit means.
    Output: one background refit for each omitted quiet UTC day."""
    day_starts = sorted({row.time_us // DAY_US * DAY_US for row in quiet_rows})
    if len(day_starts) < 2:
        return []
    results = []
    for omitted_day_start in day_starts:
        remaining_rows = [
            row
            for row in quiet_rows
            if row.time_us // DAY_US * DAY_US != omitted_day_start
        ]
        if len(remaining_rows) < 3:
            continue
        fit = ordinary_least_squares([
            (row.time_us, row.semi_major_axis_m)
            for row in remaining_rows
        ])
        excess_decay_m = (
            fit["rate_m_day"] * context.event_duration_days
            - context.observed_delta_a_6_m
        )
        results.append(OmissionResult(
            storm_id=context.storm_id,
            omitted_day_start_time_us=omitted_day_start,
            remaining_quiet_day_count=len(day_starts) - 1,
            remaining_orbit_count=len(remaining_rows),
            rate_m_day=fit["rate_m_day"],
            rate_1sigma_m_day=fit["rate_1sigma_m_day"],
            excess_decay_6_m=excess_decay_m,
        ))
    return results


def summarize_sensitivity(
    context: EventContext,
    omissions: list[OmissionResult],
) -> SensitivitySummary:
    """Input: one reference event and its omission refits.
    Output: leave-one-day-out ranges and sign stability."""
    if not omissions:
        return SensitivitySummary(
            context, 0, None, None, None, None, None,
            None, None, "insufficient_quiet_days",
        )
    rates = [item.rate_m_day for item in omissions]
    excess_values = [item.excess_decay_6_m for item in omissions]
    reference_is_positive = context.reference_excess_decay_6_m > 0.0
    omission_signs = [value > 0.0 for value in excess_values]
    return SensitivitySummary(
        context=context,
        omission_count=len(omissions),
        rate_min_m_day=min(rates),
        rate_max_m_day=max(rates),
        excess_min_m=min(excess_values),
        excess_max_m=max(excess_values),
        maximum_absolute_excess_change_m=max(
            abs(value - context.reference_excess_decay_6_m)
            for value in excess_values
        ),
        sign_stable=int(all(sign == reference_is_positive for sign in omission_signs)),
        positive_under_all_omissions=int(
            reference_is_positive and all(omission_signs)
        ),
        status="evaluated",
    )


def calculate_sensitivity(
    phase1: sqlite3.Connection,
    source: sqlite3.Connection,
) -> tuple[list[OmissionResult], list[SensitivitySummary]]:
    """Input: Phase 1 orbit and v2 quiet-background connections.
    Output: all omission refits and one summary per evaluated event."""
    accepted_days = quiet_day_starts(source)
    omission_rows = []
    summaries = []
    for context in load_contexts(source):
        candidate_rows = load_orbit_rows(
            phase1,
            context.chunk_id,
            (context.search_start_time_us, context.event_start_time_us),
        )
        selected_rows = select_quiet_rows(
            candidate_rows, accepted_days, context.event_start_time_us,
        )
        omissions = leave_one_day_out(context, selected_rows)
        omission_rows.extend(omissions)
        summaries.append(summarize_sensitivity(context, omissions))
    return omission_rows, summaries


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection.
    Output: versioned omission, summary, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_quiet_background_omission_v1 (
            storm_id TEXT NOT NULL,
            omitted_day_start_time_us INTEGER NOT NULL,
            remaining_quiet_day_count INTEGER NOT NULL,
            remaining_orbit_count INTEGER NOT NULL,
            rate_m_day REAL NOT NULL,
            rate_1sigma_m_day REAL NOT NULL,
            excess_decay_6_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, omitted_day_start_time_us)
        );
        CREATE TABLE phase6_quiet_background_sensitivity_v1 (
            storm_id TEXT PRIMARY KEY,
            quiet_day_count INTEGER NOT NULL,
            reference_rate_m_day REAL NOT NULL,
            reference_excess_decay_6_m REAL NOT NULL,
            omission_count INTEGER NOT NULL,
            rate_min_m_day REAL,
            rate_max_m_day REAL,
            excess_min_m REAL,
            excess_max_m REAL,
            maximum_absolute_excess_change_m REAL,
            sign_stable INTEGER CHECK (sign_stable IN (0, 1)),
            positive_under_all_omissions INTEGER
                CHECK (positive_under_all_omissions IN (0, 1)),
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_quiet_background_sensitivity_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_output(
    paths: SensitivityPaths,
    results: tuple[list[OmissionResult], list[SensitivitySummary]],
) -> None:
    """Input: Phase 6 paths and quiet-day omission results.
    Output: new sensitivity SQLite without modifying v2 source results."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 6 output: {paths.output}")
    omission_rows, summaries = results
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    temporary_path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_quiet_background_omission_v1 VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.storm_id, item.omitted_day_start_time_us,
                        item.remaining_quiet_day_count, item.remaining_orbit_count,
                        item.rate_m_day, item.rate_1sigma_m_day,
                        item.excess_decay_6_m, ALGORITHM_VERSION,
                    )
                    for item in omission_rows
                ],
            )
            output.executemany(
                "INSERT INTO phase6_quiet_background_sensitivity_v1 VALUES "
                f"({', '.join('?' for _ in range(14))})",
                [
                    (
                        item.context.storm_id, item.context.quiet_day_count,
                        item.context.reference_rate_m_day,
                        item.context.reference_excess_decay_6_m,
                        item.omission_count, item.rate_min_m_day,
                        item.rate_max_m_day, item.excess_min_m,
                        item.excess_max_m, item.maximum_absolute_excess_change_m,
                        item.sign_stable, item.positive_under_all_omissions,
                        item.status, ALGORITHM_VERSION,
                    )
                    for item in summaries
                ],
            )
            output.executemany(
                "INSERT INTO phase6_quiet_background_sensitivity_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1_database)),
                    ("excess_database", str(paths.excess_database)),
                    ("method", "omit one accepted quiet UTC day and refit all remaining orbits"),
                    ("limitation", "one-day remaining fits are mathematical sensitivity only"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default Phase 1, v2 excess-decay, and new output paths.
    Output: new leave-one-day-out SQLite and stability counts."""
    paths = SensitivityPaths()
    with (
        closing(sqlite3.connect(paths.phase1_database)) as phase1,
        closing(sqlite3.connect(paths.excess_database)) as source,
    ):
        results = calculate_sensitivity(phase1, source)
    write_output(paths, results)
    _, summaries = results
    return {
        "event_count": len(summaries),
        "evaluated_sensitivity_count": sum(item.status == "evaluated" for item in summaries),
        "sign_stable_count": sum(item.sign_stable == 1 for item in summaries),
        "positive_under_all_omissions_count": sum(
            item.positive_under_all_omissions == 1 for item in summaries
        ),
    }


def main() -> None:
    """Input: no command-line arguments.
    Output: one new sensitivity SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit(
            "Usage: python -m phases.phase6.code.calc_phase6_quiet_background_sensitivity",
        )
    print(run())


if __name__ == "__main__":
    main()
