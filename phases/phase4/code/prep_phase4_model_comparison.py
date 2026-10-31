"""Draw the stored L2, M0, Phase 3 M1, and Phase 4 D-model comparison."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PHASE3 = Path(
    "phases/phase4/data/sqlite/"
    "swarm_a_phase3_prediction_tau465_exploratory.sqlite"
)
PHASE4 = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
FIGURE = Path("phases/phase4/figures/phase4_model_comparison_25storm.png")
EXPECTED_STORM_COUNT = 25
EXPECTED_MINUTE_COUNT = 214_907
MICROSECONDS_PER_DAY = 86_400_000_000
PLOT_STEP_MINUTES = 30


@dataclass(frozen=True)
class ComparisonSeries:
    """Input: one storm's aligned density arrays. Output: one four-curve plot series."""

    storm_id: str
    t0_time_us: int
    time_us: np.ndarray
    rho_l2_kg_m3: np.ndarray
    rho_m0_kg_m3: np.ndarray
    rho_phase3_m1_kg_m3: np.ndarray
    rho_phase4_d_kg_m3: np.ndarray


def read_phase3_rows() -> dict[str, list[tuple]]:
    """Input: read-only Phase 3 snapshot SQLite. Output: {storm_id: source rows}."""
    uri = f"file:{PHASE3.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT prediction.storm_id,overview.t0_time_us,prediction.time_us,
                   prediction.rho_l2_phase_kg_m3,
                   prediction.rho_msis_full_phase_kg_m3,
                   prediction.rho_m1_pooled_phase_kg_m3
            FROM phase3_prediction_minute AS prediction
            JOIN phase3_25storm_overview AS overview
              ON overview.storm_id=prediction.storm_id
            ORDER BY overview.t0_time_us,prediction.time_us
        """).fetchall()
    grouped: dict[str, list[tuple]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(row[1:])
    if len(grouped) != EXPECTED_STORM_COUNT or len(rows) != EXPECTED_MINUTE_COUNT:
        raise ValueError("Phase 3 comparison input has unexpected storm or minute count.")
    return grouped


def read_phase4_rows() -> dict[str, list[tuple]]:
    """Input: read-only Phase 4 D-model SQLite. Output: {storm_id: D-model rows}."""
    uri = f"file:{PHASE4.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,rho_trial4_joint_phase_kg_m3
            FROM trial4_joint_fit_minute ORDER BY storm_id,time_us
        """).fetchall()
    grouped: dict[str, list[tuple]] = {}
    for storm_id, time_us, density in rows:
        grouped.setdefault(storm_id, []).append((time_us, density))
    if len(grouped) != EXPECTED_STORM_COUNT or len(rows) != EXPECTED_MINUTE_COUNT:
        raise ValueError("Phase 4 comparison input has unexpected storm or minute count.")
    return grouped


def build_comparison_series() -> list[ComparisonSeries]:
    """Input: saved Phase 3 and Phase 4 SQLite tables. Output: [aligned plot series]."""
    phase3_by_storm = read_phase3_rows()
    phase4_by_storm = read_phase4_rows()
    if set(phase3_by_storm) != set(phase4_by_storm):
        raise ValueError("Phase 3 and Phase 4 storm IDs differ.")
    series = []
    for storm_id, phase3_rows in phase3_by_storm.items():
        phase4_rows = phase4_by_storm[storm_id]
        phase3_times = np.array([row[1] for row in phase3_rows], dtype=np.int64)
        phase4_times = np.array([row[0] for row in phase4_rows], dtype=np.int64)
        if not np.array_equal(phase3_times, phase4_times):
            raise ValueError(f"Phase 3 and Phase 4 time keys differ: {storm_id}")
        densities = np.array([row[2:] for row in phase3_rows], dtype=float)
        phase4_density = np.array([row[1] for row in phase4_rows], dtype=float)
        if (not np.isfinite(densities).all() or not np.isfinite(phase4_density).all()
                or np.any(densities <= 0) or np.any(phase4_density <= 0)):
            raise ValueError(f"Invalid density values for comparison: {storm_id}")
        series.append(ComparisonSeries(
            storm_id=storm_id,
            t0_time_us=int(phase3_rows[0][0]),
            time_us=phase3_times,
            rho_l2_kg_m3=densities[:, 0],
            rho_m0_kg_m3=densities[:, 1],
            rho_phase3_m1_kg_m3=densities[:, 2],
            rho_phase4_d_kg_m3=phase4_density,
        ))
    return series


def draw_comparison(series: list[ComparisonSeries]) -> None:
    """Input: [four-curve plot series]. Output: saved 25-storm PNG comparison."""
    if FIGURE.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure: {FIGURE}")
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                                constrained_layout=True)
    curves = (
        ("Swarm-A L2 observation", "#111827", "rho_l2_kg_m3"),
        ("M0 full MSIS", "#64748b", "rho_m0_kg_m3"),
        ("Phase 3 M1", "#d97706", "rho_phase3_m1_kg_m3"),
        ("Phase 4 D-model", "#2563eb", "rho_phase4_d_kg_m3"),
    )
    for axis, storm in zip(axes.flat, series, strict=True):
        selected = slice(None, None, PLOT_STEP_MINUTES)
        days_from_t0 = (storm.time_us - storm.t0_time_us) / MICROSECONDS_PER_DAY
        for label, color, attribute in curves:
            axis.plot(days_from_t0[selected], getattr(storm, attribute)[selected] * 1e12,
                      color=color, label=label, linewidth=0.8)
        axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
        axis.set_title(storm.storm_id[1:9], fontsize=8)
        axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("Density (1e-12 kg/m3)")
    axes[0, 0].legend(fontsize=7)
    figure.suptitle("L2 observation, M0, Phase 3 M1, and Phase 4 D-model")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: saved Phase 3 and Phase 4 SQLite. Output: four-curve comparison PNG."""
    series = build_comparison_series()
    draw_comparison(series)
    print(f"Saved four-curve comparison for {len(series)} storms")


if __name__ == "__main__":
    main()
