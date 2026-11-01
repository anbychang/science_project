"""Score M0 and Ridge decay against every complete POD orbit."""

import math
import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from phases.phase6.code.calc_phase6_1_beff import read_only
from phases.phase6.code.prep_phase6_1_l2_minute_pairs import MINUTE_US, minute_label


ALGORITHM_VERSION = "phase6_4_storm_primary_score_v2"
MAXIMUM_ORBIT_LINK_GAP_US = 10_000_000
EXPECTED_EVENT_COUNT = 25


@dataclass(frozen=True)
class OrbitScorePaths:
    """Input: Phase 1/P6.4 SQLite paths. Output: orbit-score output path."""

    phase1: Path = Path(
        "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
    )
    comparison: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_4_decay_comparison_v1.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_4_orbit_scores_v1.sqlite",
    )


@dataclass(frozen=True)
class EventWindow:
    """Input: one P6.4 event row. Output: event score bounds in UTC us."""

    storm_id: str
    start_time_us: int
    stop_time_us: int


@dataclass(frozen=True)
class OrbitMean:
    """Input: one Phase 1 complete orbit. Output: time, chunk, and mean a in SI."""

    time_us: int
    orbit_start_time_us: int
    chunk_id: int
    mean_semi_major_axis_m: float


@dataclass(frozen=True)
class MinutePrediction:
    """Input: one P6.4 minute. Output: block-local M0/Ridge prediction values."""

    block_index: int
    chunk_id: int
    predicted_m0_delta_a_m: float
    predicted_ridge_delta_a_m: float
    b_eff_m2_kg: float


@dataclass(frozen=True)
class OrbitScore:
    """Input: two adjacent orbit means and model endpoints. Output: local orbit errors."""

    storm_id: str
    orbit_end_time_us: int
    previous_orbit_end_time_us: int
    model_start_time_us: int
    model_stop_time_us: int
    chunk_id: int
    block_index: int
    orbit_duration_s: float
    model_minute_count: int
    previous_pod_mean_a_m: float
    current_pod_mean_a_m: float
    observed_orbit_delta_a_m: float
    predicted_m0_orbit_delta_a_m: float
    m0_error_m: float
    predicted_ridge_orbit_delta_a_m: float
    ridge_error_m: float
    closer_model: str
    b_eff_m2_kg: float


@dataclass(frozen=True)
class ErrorMetrics:
    """Input: one model's local orbit errors. Output: aggregate meter metrics."""

    count: int
    mean_error_m: float
    mean_absolute_error_m: float
    median_absolute_error_m: float
    root_mean_square_error_m: float


@dataclass(frozen=True)
class StormMetrics:
    """Input: per-storm M0/Ridge orbit MAEs. Output: equal-weight storm metrics."""

    storm_count: int
    m0_win_count: int
    ridge_win_count: int
    tied_storm_count: int
    m0_macro_mean_orbit_mae_m: float
    ridge_macro_mean_orbit_mae_m: float


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty SQLite. Output: orbit, event, summary, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_4_orbit_score_v1 (
            storm_id TEXT NOT NULL,
            orbit_end_time_us INTEGER NOT NULL,
            previous_orbit_end_time_us INTEGER NOT NULL,
            model_start_time_us INTEGER NOT NULL,
            model_stop_time_us INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            orbit_duration_s REAL NOT NULL,
            model_minute_count INTEGER NOT NULL,
            previous_pod_mean_a_m REAL NOT NULL,
            current_pod_mean_a_m REAL NOT NULL,
            observed_orbit_delta_a_m REAL NOT NULL,
            predicted_m0_orbit_delta_a_m REAL NOT NULL,
            m0_error_m REAL NOT NULL,
            predicted_ridge_orbit_delta_a_m REAL NOT NULL,
            ridge_error_m REAL NOT NULL,
            closer_model TEXT NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, orbit_end_time_us)
        );
        CREATE TABLE phase6_4_orbit_event_summary_v1 (
            storm_id TEXT PRIMARY KEY,
            scored_orbit_count INTEGER NOT NULL,
            m0_mean_error_m REAL NOT NULL,
            m0_mean_absolute_error_m REAL NOT NULL,
            m0_median_absolute_error_m REAL NOT NULL,
            m0_root_mean_square_error_m REAL NOT NULL,
            ridge_mean_error_m REAL NOT NULL,
            ridge_mean_absolute_error_m REAL NOT NULL,
            ridge_median_absolute_error_m REAL NOT NULL,
            ridge_root_mean_square_error_m REAL NOT NULL,
            m0_closer_orbit_count INTEGER NOT NULL,
            ridge_closer_orbit_count INTEGER NOT NULL,
            tied_orbit_count INTEGER NOT NULL,
            winner_model TEXT NOT NULL,
            mae_margin_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_4_storm_summary_v1 (
            summary_id TEXT PRIMARY KEY,
            storm_count INTEGER NOT NULL,
            m0_win_count INTEGER NOT NULL,
            ridge_win_count INTEGER NOT NULL,
            tied_storm_count INTEGER NOT NULL,
            m0_macro_mean_orbit_mae_m REAL NOT NULL,
            ridge_macro_mean_orbit_mae_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_4_orbit_summary_v1 (
            model_id TEXT PRIMARY KEY,
            event_count INTEGER NOT NULL,
            scored_orbit_count INTEGER NOT NULL,
            mean_error_m REAL NOT NULL,
            mean_absolute_error_m REAL NOT NULL,
            median_absolute_error_m REAL NOT NULL,
            root_mean_square_error_m REAL NOT NULL,
            closer_orbit_count INTEGER NOT NULL,
            tied_orbit_count INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_4_orbit_score_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def load_event_windows(connection: sqlite3.Connection) -> list[EventWindow]:
    """Input: P6.4 comparison SQLite. Output: [25 event score windows]."""
    rows = connection.execute("""
        SELECT storm_id,start_time_us,stop_time_us
        FROM phase6_4_decay_comparison_event_v1
        ORDER BY storm_id
    """).fetchall()
    windows = [EventWindow(str(row[0]), int(row[1]), int(row[2])) for row in rows]
    if len(windows) != EXPECTED_EVENT_COUNT:
        raise ValueError(f"P6.4 orbit scoring requires 25 events, found {len(windows)}.")
    return windows


def load_orbit_means(
    connection: sqlite3.Connection,
    window: EventWindow,
) -> list[OrbitMean]:
    """Input: Phase 1 SQLite and one event. Output: ordered complete orbit means."""
    rows = connection.execute("""
        SELECT time_us,orbit_start_time_us,chunk_id,
               phase_weighted_mean_semi_major_axis_m
        FROM swarm_a_phase_orbit_mean_v2
        WHERE time_us >= ? AND time_us <= ?
        ORDER BY time_us
    """, (window.start_time_us, window.stop_time_us))
    return [
        OrbitMean(int(row[0]), int(row[1]), int(row[2]), float(row[3]))
        for row in rows
    ]


def load_minute_predictions(
    connection: sqlite3.Connection,
    storm_id: str,
) -> dict[int, MinutePrediction]:
    """Input: P6.4 SQLite and storm ID. Output: {time_us: minute prediction}."""
    rows = connection.execute("""
        SELECT time_us,block_index,chunk_id,predicted_m0_block_delta_a_m,
               predicted_ridge_block_delta_a_m,b_eff_m2_kg
        FROM phase6_4_decay_comparison_minute_v1
        WHERE storm_id = ?
        ORDER BY time_us
    """, (storm_id,))
    return {
        int(row[0]): MinutePrediction(
            int(row[1]), int(row[2]), float(row[3]), float(row[4]), float(row[5]),
        )
        for row in rows
    }


def closer_model(m0_error_m: float, ridge_error_m: float) -> str:
    """Input: M0/Ridge local errors in m. Output: closer model ID or TIE."""
    m0_absolute_error = abs(m0_error_m)
    ridge_absolute_error = abs(ridge_error_m)
    if m0_absolute_error < ridge_absolute_error:
        return "M0"
    if ridge_absolute_error < m0_absolute_error:
        return "P5V2_RIDGE"
    return "TIE"


def score_event(
    window: EventWindow,
    orbit_means: list[OrbitMean],
    predictions: dict[int, MinutePrediction],
) -> list[OrbitScore]:
    """Input: one event's orbit means and minute models. Output: valid local orbit scores."""
    scores = []
    for previous, current in zip(orbit_means, orbit_means[1:]):
        orbit_link_gap_us = current.orbit_start_time_us - previous.time_us
        pod_is_continuous = (
            current.chunk_id == previous.chunk_id
            and 0 <= orbit_link_gap_us <= MAXIMUM_ORBIT_LINK_GAP_US
        )
        if not pod_is_continuous:
            continue
        model_start_time_us = minute_label(previous.time_us)
        model_stop_time_us = minute_label(current.time_us)
        model_start = predictions.get(model_start_time_us)
        model_stop = predictions.get(model_stop_time_us)
        if model_start is None or model_stop is None:
            continue
        model_is_continuous = (
            model_start.block_index == model_stop.block_index
            and model_start.chunk_id == model_stop.chunk_id == current.chunk_id
        )
        if not model_is_continuous:
            continue
        if model_start.b_eff_m2_kg != model_stop.b_eff_m2_kg:
            raise ValueError(f"P6.4 B_eff changed within orbit {current.time_us}.")
        observed_delta = (
            current.mean_semi_major_axis_m - previous.mean_semi_major_axis_m
        )
        predicted_m0_delta = (
            model_stop.predicted_m0_delta_a_m - model_start.predicted_m0_delta_a_m
        )
        predicted_ridge_delta = (
            model_stop.predicted_ridge_delta_a_m
            - model_start.predicted_ridge_delta_a_m
        )
        m0_error = predicted_m0_delta - observed_delta
        ridge_error = predicted_ridge_delta - observed_delta
        scores.append(OrbitScore(
            window.storm_id,
            current.time_us,
            previous.time_us,
            model_start_time_us,
            model_stop_time_us,
            current.chunk_id,
            model_start.block_index,
            (current.time_us - previous.time_us) / 1_000_000.0,
            (model_stop_time_us - model_start_time_us) // MINUTE_US + 1,
            previous.mean_semi_major_axis_m,
            current.mean_semi_major_axis_m,
            observed_delta,
            predicted_m0_delta,
            m0_error,
            predicted_ridge_delta,
            ridge_error,
            closer_model(m0_error, ridge_error),
            model_start.b_eff_m2_kg,
        ))
    return scores


def error_metrics(errors: list[float]) -> ErrorMetrics:
    """Input: local orbit errors in m. Output: count, bias, MAE, median AE, RMSE."""
    if not errors:
        raise ValueError("P6.4 orbit scoring requires at least one error.")
    absolute_errors = [abs(error) for error in errors]
    return ErrorMetrics(
        len(errors),
        sum(errors) / len(errors),
        sum(absolute_errors) / len(absolute_errors),
        float(median(absolute_errors)),
        math.sqrt(sum(error * error for error in errors) / len(errors)),
    )


def score_all_events(
    phase1: sqlite3.Connection,
    comparison: sqlite3.Connection,
    windows: list[EventWindow],
) -> dict[str, list[OrbitScore]]:
    """Input: Phase 1/P6.4 sources and windows. Output: {storm_id: [orbit score]}."""
    scores_by_event = {}
    for window in windows:
        scores = score_event(
            window,
            load_orbit_means(phase1, window),
            load_minute_predictions(comparison, window.storm_id),
        )
        if not scores:
            raise ValueError(f"P6.4 has no valid orbit score for {window.storm_id}.")
        scores_by_event[window.storm_id] = scores
    return scores_by_event


def store_orbit_scores(
    connection: sqlite3.Connection,
    scores_by_event: dict[str, list[OrbitScore]],
) -> None:
    """Input: event orbit scores. Output: populated orbit-score table."""
    rows = []
    for scores in scores_by_event.values():
        for score in scores:
            rows.append((*score.__dict__.values(), ALGORITHM_VERSION))
    connection.executemany(
        "INSERT INTO phase6_4_orbit_score_v1 VALUES ("
        + ",".join("?" for _ in range(19)) + ")",
        rows,
    )


def closer_counts(scores: list[OrbitScore]) -> tuple[int, int, int]:
    """Input: local orbit scores. Output: M0, Ridge, and tied win counts."""
    return (
        sum(score.closer_model == "M0" for score in scores),
        sum(score.closer_model == "P5V2_RIDGE" for score in scores),
        sum(score.closer_model == "TIE" for score in scores),
    )


def storm_metrics(event_maes: list[tuple[float, float]]) -> StormMetrics:
    """Input: [(M0 orbit MAE, Ridge orbit MAE), ...]. Output: storm-level score."""
    if not event_maes:
        raise ValueError("P6.4 storm scoring requires at least one event.")
    winners = [closer_model(m0_mae, ridge_mae) for m0_mae, ridge_mae in event_maes]
    return StormMetrics(
        len(event_maes),
        winners.count("M0"),
        winners.count("P5V2_RIDGE"),
        winners.count("TIE"),
        sum(m0_mae for m0_mae, _ in event_maes) / len(event_maes),
        sum(ridge_mae for _, ridge_mae in event_maes) / len(event_maes),
    )


def store_summaries(
    connection: sqlite3.Connection,
    scores_by_event: dict[str, list[OrbitScore]],
) -> None:
    """Input: event orbit scores. Output: event and global metric tables."""
    all_scores = []
    event_rows = []
    event_maes = []
    for storm_id, scores in scores_by_event.items():
        all_scores.extend(scores)
        m0_metrics = error_metrics([score.m0_error_m for score in scores])
        ridge_metrics = error_metrics([score.ridge_error_m for score in scores])
        m0_closer, ridge_closer, ties = closer_counts(scores)
        event_maes.append((
            m0_metrics.mean_absolute_error_m,
            ridge_metrics.mean_absolute_error_m,
        ))
        event_rows.append((
            storm_id,
            len(scores),
            m0_metrics.mean_error_m,
            m0_metrics.mean_absolute_error_m,
            m0_metrics.median_absolute_error_m,
            m0_metrics.root_mean_square_error_m,
            ridge_metrics.mean_error_m,
            ridge_metrics.mean_absolute_error_m,
            ridge_metrics.median_absolute_error_m,
            ridge_metrics.root_mean_square_error_m,
            m0_closer,
            ridge_closer,
            ties,
            closer_model(
                m0_metrics.mean_absolute_error_m,
                ridge_metrics.mean_absolute_error_m,
            ),
            abs(
                m0_metrics.mean_absolute_error_m
                - ridge_metrics.mean_absolute_error_m
            ),
            ALGORITHM_VERSION,
        ))
    connection.executemany(
        "INSERT INTO phase6_4_orbit_event_summary_v1 VALUES ("
        + ",".join("?" for _ in range(16)) + ")",
        event_rows,
    )
    primary_metrics = storm_metrics(event_maes)
    connection.execute(
        "INSERT INTO phase6_4_storm_summary_v1 VALUES (?,?,?,?,?,?,?,?)",
        (
            "PRIMARY",
            *primary_metrics.__dict__.values(),
            ALGORITHM_VERSION,
        ),
    )
    m0_metrics = error_metrics([score.m0_error_m for score in all_scores])
    ridge_metrics = error_metrics([score.ridge_error_m for score in all_scores])
    m0_closer, ridge_closer, ties = closer_counts(all_scores)
    connection.executemany(
        "INSERT INTO phase6_4_orbit_summary_v1 VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (
                "M0", len(scores_by_event), m0_metrics.count,
                m0_metrics.mean_error_m, m0_metrics.mean_absolute_error_m,
                m0_metrics.median_absolute_error_m,
                m0_metrics.root_mean_square_error_m, m0_closer, ties,
                ALGORITHM_VERSION,
            ),
            (
                "P5V2_RIDGE", len(scores_by_event), ridge_metrics.count,
                ridge_metrics.mean_error_m, ridge_metrics.mean_absolute_error_m,
                ridge_metrics.median_absolute_error_m,
                ridge_metrics.root_mean_square_error_m, ridge_closer, ties,
                ALGORITHM_VERSION,
            ),
        ],
    )


def validate_output(connection: sqlite3.Connection) -> tuple[int, int]:
    """Input: populated score SQLite. Output: verified event and orbit counts."""
    event_count, orbit_count = connection.execute("""
        SELECT COUNT(DISTINCT storm_id),COUNT(*)
        FROM phase6_4_orbit_score_v1
    """).fetchone()
    summary_count = connection.execute(
        "SELECT COUNT(*) FROM phase6_4_orbit_event_summary_v1",
    ).fetchone()[0]
    if event_count != EXPECTED_EVENT_COUNT or summary_count != EXPECTED_EVENT_COUNT:
        raise ValueError(
            f"P6.4 orbit score expected 25 events, found {event_count}/{summary_count}.",
        )
    if orbit_count <= EXPECTED_EVENT_COUNT:
        raise ValueError(f"P6.4 orbit score count is too small: {orbit_count}.")
    storm_count, decision_count = connection.execute("""
        SELECT storm_count,m0_win_count + ridge_win_count + tied_storm_count
        FROM phase6_4_storm_summary_v1
        WHERE summary_id = 'PRIMARY'
    """).fetchone()
    if storm_count != EXPECTED_EVENT_COUNT or decision_count != EXPECTED_EVENT_COUNT:
        raise ValueError(
            f"P6.4 storm score expected 25 decisions, found {storm_count}/{decision_count}.",
        )
    return int(event_count), int(orbit_count)


def write_result(paths: OrbitScorePaths) -> dict[str, int]:
    """Input: Phase 1/P6.4 SQLite. Output: new local-orbit score SQLite."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    temporary.unlink(missing_ok=True)
    try:
        with closing(read_only(paths.phase1)) as phase1, closing(
            read_only(paths.comparison),
        ) as comparison, closing(sqlite3.connect(temporary)) as output:
            create_tables(output)
            windows = load_event_windows(comparison)
            scores_by_event = score_all_events(phase1, comparison, windows)
            store_orbit_scores(output, scores_by_event)
            store_summaries(output, scores_by_event)
            event_count, orbit_count = validate_output(output)
            output.executemany(
                "INSERT INTO phase6_4_orbit_score_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1)),
                    ("comparison_database", str(paths.comparison)),
                    ("primary_score_unit", "one storm, decided by within-storm orbit MAE"),
                    ("orbit_evidence_unit", "one local change between adjacent complete POD orbits"),
                    ("model_time_match", "nearest UTC minute at both orbit endpoints"),
                    ("gap_policy", "skip orbit if POD or model interval is not continuous"),
                    ("percentage_metric", "omitted because local observed change can approach zero"),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"event_count": event_count, "scored_orbit_count": orbit_count}


def run(paths: OrbitScorePaths = OrbitScorePaths()) -> dict[str, int]:
    """Input: default Phase 1/P6.4 paths. Output: orbit-score counts."""
    return write_result(paths)


def main() -> None:
    """Input: no command-line arguments. Output: P6.4 orbit-score counts."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_4_orbit_scores")
    print(run())


if __name__ == "__main__":
    main()
