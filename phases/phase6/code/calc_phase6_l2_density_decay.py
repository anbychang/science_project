"""Convert centered Swarm L2 orbit-mean density into candidate semi-major-axis decay."""

import math
import os
import sqlite3
import sys
from bisect import bisect_left
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path


EARTH_GRAVITATIONAL_PARAMETER_M3_S2 = 3.986004418e14
MICROSECONDS_PER_SECOND = 1_000_000
SECONDS_PER_DAY = 86_400
TWO_PI = 2.0 * math.pi
MAXIMUM_POD_GAP_S = 10.0
MINIMUM_ORBIT_SAMPLES = 500
PHASE5_ANCHOR_TOLERANCE_RAD = 0.02 * math.pi
SOURCE_PADDING_US = 2 * 60 * 60 * MICROSECONDS_PER_SECOND
CALIBRATION_WINDOW_IDS = ("Q20240202", "Q20240316", "Q20240424")
ALGORITHM_VERSION = "phase6_l2_centered_orbit_beta_eff_v1"


@dataclass(frozen=True)
class CalculationPaths:
    """Input: Phase 1, Phase 5, calibration, and output paths.
    Output: immutable Phase 6 calculation paths."""

    phase1: Path = Path(
        "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
    )
    phase5: Path = Path(
        "phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite",
    )
    calibration: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_quiet_closure_v4.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_l2_density_decay_v1.sqlite",
    )


@dataclass(frozen=True)
class CalibrationWindow:
    """Input: one quiet-window density kernel and positive loss.
    Output: one zero-intercept beta-fit observation."""

    window_id: str
    density_kernel_kg_m: float
    observed_loss_m: float


@dataclass(frozen=True)
class BetaFit:
    """Input: fixed 2024 quiet windows. Output: beta_eff fit and conditional SE."""

    beta_eff_m2_kg: float
    standard_error_m2_kg: float
    calibration_window_count: int


@dataclass(frozen=True)
class DensityAnchor:
    """Input: one Phase 5 L2 centered-orbit density row.
    Output: source-keyed density anchor."""

    storm_id: str
    time_us: int
    u_rel_rad: float
    density_kg_m3: float


@dataclass(frozen=True)
class MeanSample:
    """Input: one usable Phase 1 mean-element sample.
    Output: {time_us, chunk_id, semi_major_axis_m, phase_rad}."""

    time_us: int
    chunk_id: int
    semi_major_axis_m: float
    phase_rad: float


@dataclass(frozen=True)
class CenteredOrbit:
    """Input: Phase 1 samples over one centered 2-pi phase window.
    Output: same-window mean and boundary semi-major axes."""

    window_start_time_us: int
    window_stop_time_us: int
    window_start_a_m: float
    window_stop_a_m: float
    mean_semi_major_axis_m: float
    orbit_period_s: float
    source_sample_count: int
    phase_coverage_rad: float
    maximum_pod_gap_s: float
    chunk_id: int


@dataclass(frozen=True)
class DecayOrbit:
    """Input: one L2 density anchor, same-window orbit, and beta_eff.
    Output: candidate L2-derived semi-major-axis decay row."""

    anchor: DensityAnchor
    orbit: CenteredOrbit
    phase_grid: int
    predicted_decay_rate_m_s: float
    predicted_orbit_delta_a_m: float
    block_index: int = 0
    block_cumulative_delta_a_m: float = 0.0
    predicted_window_end_a_m: float = 0.0


@dataclass(frozen=True)
class RejectedAnchor:
    """Input: one unusable Phase 5 anchor. Output: source key and reject reason."""

    storm_id: str
    time_us: int
    reject_reason: str


@dataclass(frozen=True)
class EventSummary:
    """Input: accepted and rejected rows for one storm.
    Output: covered L2-derived and observed semi-major-axis changes."""

    storm_id: str
    first_time_us: int
    last_time_us: int
    accepted_orbit_count: int
    rejected_anchor_count: int
    block_count: int
    covered_duration_s: float
    predicted_delta_a_m: float
    observed_delta_a_m: float
    prediction_error_m: float


@dataclass(frozen=True)
class CalculationResult:
    """Input: complete Phase 6 L2 calculation. Output: rows ready for SQLite."""

    beta_fit: BetaFit
    orbits: list[DecayOrbit]
    rejected: list[RejectedAnchor]
    events: list[EventSummary]


class OrbitWindowError(ValueError):
    """Input: invalid centered orbit support. Output: actionable anchor rejection."""


def read_only(path: Path) -> sqlite3.Connection:
    """Input: existing SQLite path. Output: read-only SQLite connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def fit_beta_eff(windows: list[CalibrationWindow]) -> BetaFit:
    """Input: [2024 quiet-window {K, loss}, ...]. Output: zero-intercept beta_eff fit."""
    if len(windows) < 2:
        raise ValueError("beta_eff fitting needs at least two calibration windows.")
    denominator = sum(window.density_kernel_kg_m ** 2 for window in windows)
    if denominator <= 0.0:
        raise ValueError("beta_eff fitting needs positive density kernels.")
    beta_eff = sum(
        window.density_kernel_kg_m * window.observed_loss_m
        for window in windows
    ) / denominator
    residual_sum_squares = sum(
        (window.observed_loss_m - beta_eff * window.density_kernel_kg_m) ** 2
        for window in windows
    )
    residual_variance = residual_sum_squares / (len(windows) - 1)
    return BetaFit(
        beta_eff_m2_kg=beta_eff,
        standard_error_m2_kg=math.sqrt(residual_variance / denominator),
        calibration_window_count=len(windows),
    )


def load_beta_fit(connection: sqlite3.Connection) -> BetaFit:
    """Input: Phase 6 quiet-closure SQLite. Output: fixed 2024 beta_eff fit."""
    placeholders = ",".join("?" for _ in CALIBRATION_WINDOW_IDS)
    rows = connection.execute(f"""
        SELECT window_id,density_kernel_kg_m,-observed_delta_a_m
        FROM phase6_quiet_closure_window_v4
        WHERE window_id IN ({placeholders})
        ORDER BY window_id
    """, CALIBRATION_WINDOW_IDS).fetchall()
    if [row[0] for row in rows] != list(CALIBRATION_WINDOW_IDS):
        raise ValueError("Quiet closure does not contain the fixed 2024 calibration windows.")
    windows = [CalibrationWindow(str(row[0]), float(row[1]), float(row[2])) for row in rows]
    if any(window.observed_loss_m <= 0.0 for window in windows):
        raise ValueError("Fixed beta_eff calibration windows must show positive loss.")
    return fit_beta_eff(windows)


def load_density_anchors(connection: sqlite3.Connection) -> dict[str, list[DensityAnchor]]:
    """Input: adopted Phase 5 SQLite. Output: {storm_id: [L2 density anchor, ...]}."""
    rows = connection.execute("""
        SELECT storm_id,time_us,u_rel_rad,rho_l2_phase_kg_m3
        FROM phase5_orbit_anchor
        ORDER BY storm_id,time_us
    """).fetchall()
    anchors: dict[str, list[DensityAnchor]] = defaultdict(list)
    for storm_id, time_us, u_rel_rad, density_kg_m3 in rows:
        if density_kg_m3 <= 0.0 or not math.isfinite(density_kg_m3):
            raise ValueError(f"Invalid L2 density: {storm_id}:{time_us}")
        anchors[str(storm_id)].append(DensityAnchor(
            str(storm_id), int(time_us), float(u_rel_rad), float(density_kg_m3),
        ))
    if len(anchors) != 25 or sum(map(len, anchors.values())) != 2295:
        raise ValueError("Expected 2,295 L2 anchors from 25 Phase 5 storms.")
    return dict(anchors)


def raw_mean_rows(
    connection: sqlite3.Connection,
    start_time_us: int,
    stop_time_us: int,
) -> list[tuple[int, int, float, float]]:
    """Input: Phase 1 connection and UTC range. Output: usable {time, chunk, a, raw phase}."""
    return connection.execute("""
        SELECT mean.time_us,quality.chunk_id,mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad + mean.mean_anomaly_rad
        FROM swarm_a_mean_orbit_elements_v1 AS mean
        JOIN swarm_a_pod_quality AS quality ON quality.time_us=mean.time_us
        WHERE mean.time_us BETWEEN ? AND ?
          AND quality.is_usable=1 AND quality.chunk_id IS NOT NULL
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
        ORDER BY mean.time_us
    """, (start_time_us, stop_time_us)).fetchall()


def mean_segments(rows: list[tuple[int, int, float, float]]) -> list[list[MeanSample]]:
    """Input: ordered usable Phase 1 rows. Output: monotonic chunk-local phase segments."""
    segments: list[list[MeanSample]] = []
    current: list[MeanSample] = []
    previous_raw_phase: float | None = None
    previous_phase: float | None = None
    for time_us, chunk_id, semi_major_axis_m, raw_phase in rows:
        raw_phase = float(raw_phase) % TWO_PI
        gap_s = None if not current else (int(time_us) - current[-1].time_us) / MICROSECONDS_PER_SECOND
        new_segment = bool(current) and (
            int(chunk_id) != current[-1].chunk_id or gap_s > MAXIMUM_POD_GAP_S
        )
        if new_segment:
            segments.append(current)
            current = []
            previous_raw_phase = None
            previous_phase = None
        phase = raw_phase
        if previous_raw_phase is not None and previous_phase is not None:
            increment = (raw_phase - previous_raw_phase + math.pi) % TWO_PI - math.pi
            if increment <= 0.0:
                segments.append(current)
                current = []
                previous_phase = None
                phase = raw_phase
            else:
                phase = previous_phase + increment
        current.append(MeanSample(
            int(time_us), int(chunk_id), float(semi_major_axis_m), phase,
        ))
        previous_raw_phase = raw_phase
        previous_phase = phase
    if current:
        segments.append(current)
    return [segment for segment in segments if len(segment) >= 2]


def interpolate_by_time(left: MeanSample, right: MeanSample, target_time_us: int) -> MeanSample:
    """Input: two adjacent samples and UTC target. Output: linearly interpolated mean sample."""
    gap_us = right.time_us - left.time_us
    if left.chunk_id != right.chunk_id or not 0 < gap_us <= MAXIMUM_POD_GAP_S * MICROSECONDS_PER_SECOND:
        raise OrbitWindowError("center_time_gap_or_chunk")
    fraction = (target_time_us - left.time_us) / gap_us
    if not 0.0 <= fraction <= 1.0:
        raise OrbitWindowError("center_time_not_bracketed")
    return MeanSample(
        target_time_us,
        left.chunk_id,
        left.semi_major_axis_m + fraction * (right.semi_major_axis_m - left.semi_major_axis_m),
        left.phase_rad + fraction * (right.phase_rad - left.phase_rad),
    )


def interpolate_by_phase(left: MeanSample, right: MeanSample, target_phase: float) -> MeanSample:
    """Input: two adjacent samples and phase target. Output: linearly interpolated boundary."""
    phase_gap = right.phase_rad - left.phase_rad
    time_gap_us = right.time_us - left.time_us
    if (left.chunk_id != right.chunk_id or phase_gap <= 0.0
            or not 0 < time_gap_us <= MAXIMUM_POD_GAP_S * MICROSECONDS_PER_SECOND):
        raise OrbitWindowError("boundary_gap_or_chunk")
    fraction = (target_phase - left.phase_rad) / phase_gap
    if not 0.0 <= fraction <= 1.0:
        raise OrbitWindowError("boundary_phase_not_bracketed")
    return MeanSample(
        round(left.time_us + fraction * time_gap_us),
        left.chunk_id,
        left.semi_major_axis_m + fraction * (right.semi_major_axis_m - left.semi_major_axis_m),
        target_phase,
    )


def phase_boundary(samples: list[MeanSample], target_phase: float) -> MeanSample:
    """Input: one monotonic phase segment and target phase. Output: interpolated boundary sample."""
    phases = [sample.phase_rad for sample in samples]
    index = bisect_left(phases, target_phase)
    if index == 0 or index == len(samples):
        raise OrbitWindowError("phase_boundary_outside_segment")
    return interpolate_by_phase(samples[index - 1], samples[index], target_phase)


def centered_orbit(segments: list[list[MeanSample]], anchor: DensityAnchor) -> CenteredOrbit:
    """Input: chunk-local Phase 1 segments and one L2 anchor. Output: same centered orbit mean."""
    segment = next(
        (candidate for candidate in segments
         if candidate[0].time_us <= anchor.time_us <= candidate[-1].time_us),
        None,
    )
    if segment is None:
        raise OrbitWindowError("anchor_time_outside_phase1_segment")
    times = [sample.time_us for sample in segment]
    center_index = bisect_left(times, anchor.time_us)
    if center_index == 0 or center_index == len(segment):
        raise OrbitWindowError("anchor_time_not_bracketed")
    center = interpolate_by_time(segment[center_index - 1], segment[center_index], anchor.time_us)
    start_phase = center.phase_rad - math.pi
    stop_phase = center.phase_rad + math.pi
    start = phase_boundary(segment, start_phase)
    stop = phase_boundary(segment, stop_phase)
    interior = [sample for sample in segment if start_phase < sample.phase_rad < stop_phase]
    if len(interior) < MINIMUM_ORBIT_SAMPLES:
        raise OrbitWindowError("fewer_than_500_source_samples")
    window_samples = [start, *interior, stop]
    maximum_gap_s = max(
        (right.time_us - left.time_us) / MICROSECONDS_PER_SECOND
        for left, right in zip(window_samples, window_samples[1:])
    )
    if maximum_gap_s > MAXIMUM_POD_GAP_S:
        raise OrbitWindowError("pod_gap_above_10_seconds")
    phase_integral = sum(
        0.5 * (left.semi_major_axis_m + right.semi_major_axis_m)
        * (right.phase_rad - left.phase_rad)
        for left, right in zip(window_samples, window_samples[1:])
    )
    orbit_period_s = (stop.time_us - start.time_us) / MICROSECONDS_PER_SECOND
    return CenteredOrbit(
        start.time_us,
        stop.time_us,
        start.semi_major_axis_m,
        stop.semi_major_axis_m,
        phase_integral / TWO_PI,
        orbit_period_s,
        len(interior),
        stop.phase_rad - start.phase_rad,
        maximum_gap_s,
        center.chunk_id,
    )


def predict_decay(anchor: DensityAnchor, orbit: CenteredOrbit, beta_eff: float) -> DecayOrbit:
    """Input: L2 density, same-window orbit, and beta_eff. Output: one candidate decay row."""
    phase_grid = round(anchor.u_rel_rad / TWO_PI)
    if abs(anchor.u_rel_rad - TWO_PI * phase_grid) > PHASE5_ANCHOR_TOLERANCE_RAD:
        raise OrbitWindowError("phase5_anchor_outside_grid_tolerance")
    rate_m_s = -beta_eff * anchor.density_kg_m3 * math.sqrt(
        EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * orbit.mean_semi_major_axis_m,
    )
    return DecayOrbit(
        anchor=anchor,
        orbit=orbit,
        phase_grid=phase_grid,
        predicted_decay_rate_m_s=rate_m_s,
        predicted_orbit_delta_a_m=rate_m_s * orbit.orbit_period_s,
    )


def assign_blocks(orbits: list[DecayOrbit]) -> list[DecayOrbit]:
    """Input: accepted rows ordered by storm/time. Output: block-local cumulative decay paths."""
    assigned: list[DecayOrbit] = []
    previous: DecayOrbit | None = None
    block_index = 0
    cumulative_delta_a_m = 0.0
    initial_a_m = 0.0
    for orbit in orbits:
        new_block = previous is None or (
            orbit.anchor.storm_id != previous.anchor.storm_id
            or orbit.phase_grid != previous.phase_grid + 1
            or orbit.orbit.chunk_id != previous.orbit.chunk_id
        )
        if new_block:
            block_index = 1 if previous is None or orbit.anchor.storm_id != previous.anchor.storm_id else block_index + 1
            cumulative_delta_a_m = 0.0
            initial_a_m = orbit.orbit.window_start_a_m
        cumulative_delta_a_m += orbit.predicted_orbit_delta_a_m
        assigned_orbit = replace(
            orbit,
            block_index=block_index,
            block_cumulative_delta_a_m=cumulative_delta_a_m,
            predicted_window_end_a_m=initial_a_m + cumulative_delta_a_m,
        )
        assigned.append(assigned_orbit)
        previous = assigned_orbit
    return assigned


def summarize_events(
    orbits: list[DecayOrbit],
    rejected: list[RejectedAnchor],
) -> list[EventSummary]:
    """Input: accepted and rejected anchor rows. Output: one covered-change summary per storm."""
    accepted_by_storm: dict[str, list[DecayOrbit]] = defaultdict(list)
    rejected_count: dict[str, int] = defaultdict(int)
    for orbit in orbits:
        accepted_by_storm[orbit.anchor.storm_id].append(orbit)
    for row in rejected:
        rejected_count[row.storm_id] += 1
    summaries = []
    for storm_id, storm_orbits in sorted(accepted_by_storm.items()):
        blocks: dict[int, list[DecayOrbit]] = defaultdict(list)
        for orbit in storm_orbits:
            blocks[orbit.block_index].append(orbit)
        observed_delta_a_m = sum(
            block[-1].orbit.window_stop_a_m - block[0].orbit.window_start_a_m
            for block in blocks.values()
        )
        predicted_delta_a_m = sum(orbit.predicted_orbit_delta_a_m for orbit in storm_orbits)
        summaries.append(EventSummary(
            storm_id=storm_id,
            first_time_us=storm_orbits[0].anchor.time_us,
            last_time_us=storm_orbits[-1].anchor.time_us,
            accepted_orbit_count=len(storm_orbits),
            rejected_anchor_count=rejected_count[storm_id],
            block_count=len(blocks),
            covered_duration_s=sum(orbit.orbit.orbit_period_s for orbit in storm_orbits),
            predicted_delta_a_m=predicted_delta_a_m,
            observed_delta_a_m=observed_delta_a_m,
            prediction_error_m=predicted_delta_a_m - observed_delta_a_m,
        ))
    return summaries


def calculate(paths: CalculationPaths) -> CalculationResult:
    """Input: Phase 1, Phase 5, and calibration SQLite files. Output: complete L2 decay result."""
    with closing(read_only(paths.calibration)) as calibration:
        beta_fit = load_beta_fit(calibration)
    with closing(read_only(paths.phase5)) as phase5:
        anchors_by_storm = load_density_anchors(phase5)
    accepted: list[DecayOrbit] = []
    rejected: list[RejectedAnchor] = []
    with closing(read_only(paths.phase1)) as phase1:
        for storm_id, anchors in anchors_by_storm.items():
            rows = raw_mean_rows(
                phase1,
                anchors[0].time_us - SOURCE_PADDING_US,
                anchors[-1].time_us + SOURCE_PADDING_US,
            )
            segments = mean_segments(rows)
            for anchor in anchors:
                try:
                    orbit = centered_orbit(segments, anchor)
                    accepted.append(predict_decay(anchor, orbit, beta_fit.beta_eff_m2_kg))
                except OrbitWindowError as error:
                    rejected.append(RejectedAnchor(storm_id, anchor.time_us, str(error)))
    assigned = assign_blocks(accepted)
    events = summarize_events(assigned, rejected)
    return CalculationResult(beta_fit, assigned, rejected, events)


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection. Output: versioned L2 decay tables."""
    connection.executescript("""
        CREATE TABLE phase6_l2_decay_orbit_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            phase_grid INTEGER NOT NULL,
            u_rel_rad REAL NOT NULL,
            window_start_time_us INTEGER NOT NULL,
            window_stop_time_us INTEGER NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL CHECK (rho_l2_phase_kg_m3 > 0),
            mean_semi_major_axis_m REAL NOT NULL CHECK (mean_semi_major_axis_m > 0),
            observed_window_start_a_m REAL NOT NULL,
            observed_window_stop_a_m REAL NOT NULL,
            orbit_period_s REAL NOT NULL CHECK (orbit_period_s > 0),
            beta_eff_m2_kg REAL NOT NULL CHECK (beta_eff_m2_kg > 0),
            predicted_decay_rate_m_s REAL NOT NULL CHECK (predicted_decay_rate_m_s < 0),
            predicted_decay_rate_m_day REAL NOT NULL CHECK (predicted_decay_rate_m_day < 0),
            predicted_orbit_delta_a_m REAL NOT NULL CHECK (predicted_orbit_delta_a_m < 0),
            block_index INTEGER NOT NULL CHECK (block_index > 0),
            block_cumulative_delta_a_m REAL NOT NULL,
            predicted_window_end_a_m REAL NOT NULL,
            source_sample_count INTEGER NOT NULL,
            phase_coverage_rad REAL NOT NULL,
            maximum_pod_gap_s REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE phase6_l2_decay_reject_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            reject_reason TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE phase6_l2_decay_event_v1 (
            storm_id TEXT PRIMARY KEY,
            first_time_us INTEGER NOT NULL,
            last_time_us INTEGER NOT NULL,
            accepted_orbit_count INTEGER NOT NULL,
            rejected_anchor_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            covered_duration_s REAL NOT NULL,
            predicted_delta_a_m REAL NOT NULL,
            observed_delta_a_m REAL NOT NULL,
            prediction_error_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_l2_decay_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_result(paths: CalculationPaths, result: CalculationResult) -> None:
    """Input: output path and calculated rows. Output: one new immutable Phase 6 SQLite."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    if temporary.exists():
        temporary.unlink()
    try:
        with closing(sqlite3.connect(temporary)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_l2_decay_orbit_v1 VALUES (" + ",".join("?" for _ in range(23)) + ")",
                [(
                    row.anchor.storm_id,
                    row.anchor.time_us,
                    row.phase_grid,
                    row.anchor.u_rel_rad,
                    row.orbit.window_start_time_us,
                    row.orbit.window_stop_time_us,
                    row.anchor.density_kg_m3,
                    row.orbit.mean_semi_major_axis_m,
                    row.orbit.window_start_a_m,
                    row.orbit.window_stop_a_m,
                    row.orbit.orbit_period_s,
                    result.beta_fit.beta_eff_m2_kg,
                    row.predicted_decay_rate_m_s,
                    row.predicted_decay_rate_m_s * SECONDS_PER_DAY,
                    row.predicted_orbit_delta_a_m,
                    row.block_index,
                    row.block_cumulative_delta_a_m,
                    row.predicted_window_end_a_m,
                    row.orbit.source_sample_count,
                    row.orbit.phase_coverage_rad,
                    row.orbit.maximum_pod_gap_s,
                    row.orbit.chunk_id,
                    ALGORITHM_VERSION,
                ) for row in result.orbits],
            )
            output.executemany(
                "INSERT INTO phase6_l2_decay_reject_v1 VALUES (?,?,?,?)",
                [(row.storm_id, row.time_us, row.reject_reason, ALGORITHM_VERSION)
                 for row in result.rejected],
            )
            output.executemany(
                "INSERT INTO phase6_l2_decay_event_v1 VALUES (" + ",".join("?" for _ in range(11)) + ")",
                [(
                    row.storm_id,
                    row.first_time_us,
                    row.last_time_us,
                    row.accepted_orbit_count,
                    row.rejected_anchor_count,
                    row.block_count,
                    row.covered_duration_s,
                    row.predicted_delta_a_m,
                    row.observed_delta_a_m,
                    row.prediction_error_m,
                    ALGORITHM_VERSION,
                ) for row in result.events],
            )
            output.executemany(
                "INSERT INTO phase6_l2_decay_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1)),
                    ("phase5_database", str(paths.phase5)),
                    ("calibration_database", str(paths.calibration)),
                    ("calibration_windows", ",".join(CALIBRATION_WINDOW_IDS)),
                    ("beta_eff_m2_kg", repr(result.beta_fit.beta_eff_m2_kg)),
                    ("beta_eff_standard_error_m2_kg", repr(result.beta_fit.standard_error_m2_kg)),
                    ("density_field", "phase5_orbit_anchor.rho_l2_phase_kg_m3"),
                    ("orbit_window", "Phase 5 anchor centered u-pi to u+pi"),
                    ("limitation", "retrospective candidate; beta_eff is not physical CdA/m"),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)


def run(paths: CalculationPaths = CalculationPaths()) -> dict[str, float | int]:
    """Input: calculation paths. Output: new SQLite and compact row-count summary."""
    result = calculate(paths)
    write_result(paths, result)
    return {
        "beta_eff_m2_kg": result.beta_fit.beta_eff_m2_kg,
        "accepted_orbit_count": len(result.orbits),
        "rejected_anchor_count": len(result.rejected),
        "event_count": len(result.events),
    }


def main() -> None:
    """Input: no command-line arguments. Output: Phase 6 L2 decay SQLite summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_l2_density_decay")
    print(run())


if __name__ == "__main__":
    main()
