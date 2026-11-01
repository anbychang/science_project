"""Measure post-t0 semi-major-axis loss beyond each pre-storm baseline."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

from phases.phase1.code.calc_orbit_decay_diagnostics import ordinary_least_squares
from phases.phase6.code.calc_phase6_quiet_endpoint_sensitivity import fitted_value_and_sigma


DEFAULT_PHASE1_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite",
)
DEFAULT_BASELINE_DATABASE = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_prestorm_baseline_v1.sqlite",
)
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_storm_excess_decay_v1.sqlite",
)
PHASE_ORBIT_TABLE = "swarm_a_phase_orbit_mean_v2"
DAY_US = 86_400_000_000
WINDOW_START_DAYS = -2
WINDOW_STOP_DAYS = 4
ENDPOINT_ORBIT_COUNTS = (4, 6, 8)
REFERENCE_ENDPOINT_ORBIT_COUNT = 6
ALGORITHM_VERSION = "phase6_storm_post_t0_excess_decay_v1"


@dataclass(frozen=True)
class ExcessDecayPaths:
    """Input: Phase 1 orbit, Phase 6 baseline, and new output paths.
    Output: immutable path record for the storm-window calculation."""

    phase1_database: Path = DEFAULT_PHASE1_DATABASE
    baseline_database: Path = DEFAULT_BASELINE_DATABASE
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class StormBaseline:
    """Input: one pre-storm baseline database row.
    Output: event timing, source chunk, and fitted background rate."""

    storm_id: str
    t0_time_us: int
    chunk_id: int
    coverage_days: float
    rate_m_day: float
    rate_1sigma_m_day: float


@dataclass(frozen=True)
class OrbitMean:
    """Input: one complete Phase 1 orbit mean.
    Output: orbit timing, semi-major axis, and source chunk."""

    time_us: int
    orbit_start_time_us: int
    semi_major_axis_m: float
    chunk_id: int


@dataclass(frozen=True)
class BoundaryFit:
    """Input: one local endpoint fit.
    Output: fitted semi-major axis and OLS sigma at one boundary."""

    time_us: int
    semi_major_axis_m: float
    ols_sigma_m: float


@dataclass(frozen=True)
class ExcessDecayMeasure:
    """Input: one storm's [-2, +4) orbit means and background slope.
    Output: pre-t0 control and post-t0 excess-decay measurements."""

    baseline: StormBaseline
    nominal_start_time_us: int
    nominal_stop_time_us: int
    first_orbit_time_us: int
    t0_anchor_time_us: int
    last_orbit_time_us: int
    orbit_count: int
    pre_t0_orbit_count: int
    post_t0_orbit_count: int
    pre_duration_days: float
    post_duration_days: float
    pre_observed_delta_a_6_m: float
    pre_background_delta_a_m: float
    pre_excess_decay_6_m: float
    post_observed_delta_a_6_m: float
    post_background_delta_a_m: float
    post_excess_decay_4_m: float
    post_excess_decay_6_m: float
    post_excess_decay_8_m: float
    post_excess_decay_ols_sigma_6_m: float
    post_endpoint_span_m: float
    local_pre_rate_m_day: float
    local_pre_rate_1sigma_m_day: float
    local_post_background_delta_a_m: float
    local_post_excess_decay_4_m: float
    local_post_excess_decay_6_m: float
    local_post_excess_decay_8_m: float
    local_post_excess_decay_ols_sigma_6_m: float


def load_baselines(connection: sqlite3.Connection) -> list[StormBaseline]:
    """Input: Phase 6 pre-storm baseline SQLite connection.
    Output: ordered storm baselines with available all-data slopes."""
    rows = connection.execute("""
        SELECT storm_id, t0_time_us, chunk_id, all_coverage_days,
               all_rate_m_day, all_rate_1sigma_m_day
        FROM phase6_prestorm_baseline_v1
        WHERE chunk_id IS NOT NULL AND all_rate_m_day IS NOT NULL
        ORDER BY t0_time_us
    """)
    return [
        StormBaseline(
            str(storm_id), int(t0_time_us), int(chunk_id), float(coverage_days),
            float(rate_m_day), float(rate_sigma_m_day),
        )
        for storm_id, t0_time_us, chunk_id, coverage_days, rate_m_day, rate_sigma_m_day in rows
    ]


def load_window_rows(
    connection: sqlite3.Connection,
    baseline: StormBaseline,
) -> list[OrbitMean]:
    """Input: Phase 1 connection and one storm baseline.
    Output: ordered orbit means in the nominal [-2, +4 day) window."""
    start_time_us = baseline.t0_time_us + WINDOW_START_DAYS * DAY_US
    stop_time_us = baseline.t0_time_us + WINDOW_STOP_DAYS * DAY_US
    rows = connection.execute(
        f"SELECT time_us, orbit_start_time_us, phase_weighted_mean_semi_major_axis_m, "
        f"chunk_id FROM {PHASE_ORBIT_TABLE} WHERE time_us >= ? AND time_us < ? "
        "ORDER BY time_us",
        (start_time_us, stop_time_us),
    )
    return [
        OrbitMean(int(time_us), int(orbit_start_us), float(mean_a_m), int(chunk_id))
        for time_us, orbit_start_us, mean_a_m, chunk_id in rows
    ]


def boundary_fit(rows: list[OrbitMean], target_time_us: int) -> BoundaryFit:
    """Input: local orbit means and their boundary UTC time.
    Output: fitted semi-major axis and OLS sigma at that time."""
    value_m, sigma_m = fitted_value_and_sigma(rows, target_time_us)
    return BoundaryFit(target_time_us, value_m, sigma_m)


def measure_storm(
    baseline: StormBaseline,
    rows: list[OrbitMean],
) -> ExcessDecayMeasure:
    """Input: one baseline and its ordered [-2, +4) orbit means.
    Output: pre-t0 control and post-t0 excess loss, positive when decay increases."""
    minimum_orbit_count = 2 * max(ENDPOINT_ORBIT_COUNTS)
    if len(rows) < minimum_orbit_count:
        raise ValueError(f"{baseline.storm_id} has too few orbit means: {len(rows)}")
    chunk_ids = {row.chunk_id for row in rows}
    if chunk_ids != {baseline.chunk_id}:
        raise ValueError(
            f"{baseline.storm_id} window chunks {sorted(chunk_ids)} do not match "
            f"baseline chunk {baseline.chunk_id}.",
        )
    pre_t0_rows = [row for row in rows if row.time_us < baseline.t0_time_us]
    post_t0_rows = [row for row in rows if row.time_us >= baseline.t0_time_us]
    if len(pre_t0_rows) < max(ENDPOINT_ORBIT_COUNTS):
        raise ValueError(f"{baseline.storm_id} has too few pre-t0 orbit means.")
    if len(post_t0_rows) < max(ENDPOINT_ORBIT_COUNTS):
        raise ValueError(f"{baseline.storm_id} has too few post-t0 orbit means.")

    boundaries = {
        orbit_count: (
            boundary_fit(rows[:orbit_count], rows[0].time_us),
            boundary_fit(pre_t0_rows[-orbit_count:], baseline.t0_time_us),
            boundary_fit(rows[-orbit_count:], rows[-1].time_us),
        )
        for orbit_count in ENDPOINT_ORBIT_COUNTS
    }
    reference_start, reference_anchor, reference_stop = boundaries[
        REFERENCE_ENDPOINT_ORBIT_COUNT
    ]
    pre_duration_days = (reference_anchor.time_us - reference_start.time_us) / DAY_US
    post_duration_days = (reference_stop.time_us - reference_anchor.time_us) / DAY_US
    pre_observed_delta_a_m = (
        reference_anchor.semi_major_axis_m - reference_start.semi_major_axis_m
    )
    post_observed_delta_a_m = (
        reference_stop.semi_major_axis_m - reference_anchor.semi_major_axis_m
    )
    pre_background_delta_a_m = baseline.rate_m_day * pre_duration_days
    post_background_delta_a_m = baseline.rate_m_day * post_duration_days
    post_excess_by_count = {
        orbit_count: post_background_delta_a_m - (
            stop.semi_major_axis_m - anchor.semi_major_axis_m
        )
        for orbit_count, (_, anchor, stop) in boundaries.items()
    }
    post_endpoint_span_m = max(post_excess_by_count.values()) - min(
        post_excess_by_count.values()
    )
    post_baseline_sigma_m = baseline.rate_1sigma_m_day * post_duration_days
    post_endpoint_sigma_m = sqrt(
        reference_anchor.ols_sigma_m ** 2 + reference_stop.ols_sigma_m ** 2
    )
    local_pre_fit = ordinary_least_squares([
        (row.time_us, row.semi_major_axis_m)
        for row in pre_t0_rows
    ])
    local_post_background_delta_a_m = (
        local_pre_fit["rate_m_day"] * post_duration_days
    )
    local_post_excess_by_count = {
        orbit_count: local_post_background_delta_a_m - (
            stop.semi_major_axis_m - anchor.semi_major_axis_m
        )
        for orbit_count, (_, anchor, stop) in boundaries.items()
    }
    local_baseline_sigma_m = (
        local_pre_fit["rate_1sigma_m_day"] * post_duration_days
    )

    return ExcessDecayMeasure(
        baseline=baseline,
        nominal_start_time_us=baseline.t0_time_us + WINDOW_START_DAYS * DAY_US,
        nominal_stop_time_us=baseline.t0_time_us + WINDOW_STOP_DAYS * DAY_US,
        first_orbit_time_us=reference_start.time_us,
        t0_anchor_time_us=reference_anchor.time_us,
        last_orbit_time_us=reference_stop.time_us,
        orbit_count=len(rows),
        pre_t0_orbit_count=len(pre_t0_rows),
        post_t0_orbit_count=len(post_t0_rows),
        pre_duration_days=pre_duration_days,
        post_duration_days=post_duration_days,
        pre_observed_delta_a_6_m=pre_observed_delta_a_m,
        pre_background_delta_a_m=pre_background_delta_a_m,
        pre_excess_decay_6_m=pre_background_delta_a_m - pre_observed_delta_a_m,
        post_observed_delta_a_6_m=post_observed_delta_a_m,
        post_background_delta_a_m=post_background_delta_a_m,
        post_excess_decay_4_m=post_excess_by_count[4],
        post_excess_decay_6_m=post_excess_by_count[6],
        post_excess_decay_8_m=post_excess_by_count[8],
        post_excess_decay_ols_sigma_6_m=sqrt(
            post_endpoint_sigma_m ** 2 + post_baseline_sigma_m ** 2
        ),
        post_endpoint_span_m=post_endpoint_span_m,
        local_pre_rate_m_day=local_pre_fit["rate_m_day"],
        local_pre_rate_1sigma_m_day=local_pre_fit["rate_1sigma_m_day"],
        local_post_background_delta_a_m=local_post_background_delta_a_m,
        local_post_excess_decay_4_m=local_post_excess_by_count[4],
        local_post_excess_decay_6_m=local_post_excess_by_count[6],
        local_post_excess_decay_8_m=local_post_excess_by_count[8],
        local_post_excess_decay_ols_sigma_6_m=sqrt(
            post_endpoint_sigma_m ** 2 + local_baseline_sigma_m ** 2
        ),
    )


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection.
    Output: versioned storm excess-decay and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_storm_excess_decay_v1 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            nominal_start_time_us INTEGER NOT NULL,
            nominal_stop_time_us INTEGER NOT NULL,
            first_orbit_time_us INTEGER NOT NULL,
            t0_anchor_time_us INTEGER NOT NULL,
            last_orbit_time_us INTEGER NOT NULL,
            orbit_count INTEGER NOT NULL,
            pre_t0_orbit_count INTEGER NOT NULL,
            post_t0_orbit_count INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            baseline_coverage_days REAL NOT NULL,
            baseline_rate_m_day REAL NOT NULL,
            baseline_rate_1sigma_m_day REAL NOT NULL,
            pre_duration_days REAL NOT NULL,
            post_duration_days REAL NOT NULL,
            pre_observed_delta_a_6_m REAL NOT NULL,
            pre_background_delta_a_m REAL NOT NULL,
            pre_excess_decay_6_m REAL NOT NULL,
            post_observed_delta_a_6_m REAL NOT NULL,
            post_background_delta_a_m REAL NOT NULL,
            post_excess_decay_4_m REAL NOT NULL,
            post_excess_decay_6_m REAL NOT NULL,
            post_excess_decay_8_m REAL NOT NULL,
            post_excess_decay_ols_sigma_6_m REAL NOT NULL,
            post_endpoint_span_m REAL NOT NULL,
            long_baseline_increased_decay INTEGER NOT NULL
                CHECK (long_baseline_increased_decay IN (0, 1)),
            local_pre_rate_m_day REAL NOT NULL,
            local_pre_rate_1sigma_m_day REAL NOT NULL,
            local_post_background_delta_a_m REAL NOT NULL,
            local_post_excess_decay_4_m REAL NOT NULL,
            local_post_excess_decay_6_m REAL NOT NULL,
            local_post_excess_decay_8_m REAL NOT NULL,
            local_post_excess_decay_ols_sigma_6_m REAL NOT NULL,
            local_increased_decay INTEGER NOT NULL
                CHECK (local_increased_decay IN (0, 1)),
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_storm_excess_decay_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_output(paths: ExcessDecayPaths, measures: list[ExcessDecayMeasure]) -> None:
    """Input: Phase 6 paths and measured storm-window differences.
    Output: new SQLite result without modifying upstream observations."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    temporary_path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_storm_excess_decay_v1 VALUES "
                f"({', '.join('?' for _ in range(36))})",
                [
                    (
                        item.baseline.storm_id, item.baseline.t0_time_us,
                        item.nominal_start_time_us, item.nominal_stop_time_us,
                        item.first_orbit_time_us, item.t0_anchor_time_us,
                        item.last_orbit_time_us, item.orbit_count,
                        item.pre_t0_orbit_count, item.post_t0_orbit_count,
                        item.baseline.chunk_id, item.baseline.coverage_days,
                        item.baseline.rate_m_day, item.baseline.rate_1sigma_m_day,
                        item.pre_duration_days, item.post_duration_days,
                        item.pre_observed_delta_a_6_m,
                        item.pre_background_delta_a_m,
                        item.pre_excess_decay_6_m,
                        item.post_observed_delta_a_6_m,
                        item.post_background_delta_a_m,
                        item.post_excess_decay_4_m,
                        item.post_excess_decay_6_m,
                        item.post_excess_decay_8_m,
                        item.post_excess_decay_ols_sigma_6_m,
                        item.post_endpoint_span_m,
                        int(item.post_excess_decay_6_m > 0.0),
                        item.local_pre_rate_m_day,
                        item.local_pre_rate_1sigma_m_day,
                        item.local_post_background_delta_a_m,
                        item.local_post_excess_decay_4_m,
                        item.local_post_excess_decay_6_m,
                        item.local_post_excess_decay_8_m,
                        item.local_post_excess_decay_ols_sigma_6_m,
                        int(item.local_post_excess_decay_6_m > 0.0),
                        ALGORITHM_VERSION,
                    )
                    for item in measures
                ],
            )
            output.executemany(
                "INSERT INTO phase6_storm_excess_decay_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1_database)),
                    ("baseline_database", str(paths.baseline_database)),
                    ("nominal_window_days", "[-2, +4) from t0"),
                    ("pre_t0_role", "[-2, 0) background-control diagnostic"),
                    ("post_t0_role", "[0, +4) storm excess-decay measurement"),
                    ("endpoint_orbit_counts", "4,6,8"),
                    ("reference_endpoint_orbit_count", str(REFERENCE_ENDPOINT_ORBIT_COUNT)),
                    ("primary_baseline", "local OLS over [-2, 0) orbit means"),
                    ("sensitivity_baseline", "long pre-storm baseline database rate"),
                    ("sign", "positive excess decay means faster loss than background"),
                    ("limitation", "descriptive mean-element difference; not calibrated drag"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default orbit and baseline SQLite files.
    Output: new Phase 6 post-t0 excess-decay SQLite and sign counts."""
    paths = ExcessDecayPaths()
    with (
        closing(sqlite3.connect(paths.phase1_database)) as phase1,
        closing(sqlite3.connect(paths.baseline_database)) as baseline_database,
    ):
        baselines = load_baselines(baseline_database)
        measures = [
            measure_storm(baseline, load_window_rows(phase1, baseline))
            for baseline in baselines
        ]
    write_output(paths, measures)
    return {
        "storm_count": len(measures),
        "local_increased_decay_count": sum(
            item.local_post_excess_decay_6_m > 0.0 for item in measures
        ),
        "local_nonincrease_count": sum(
            item.local_post_excess_decay_6_m <= 0.0 for item in measures
        ),
    }


def main() -> None:
    """Input: no command-line arguments.
    Output: one new Phase 6 excess-decay SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_storm_excess_decay")
    print(run())


if __name__ == "__main__":
    main()
