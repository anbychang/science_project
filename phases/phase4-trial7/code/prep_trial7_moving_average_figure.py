"""Show a one-minute retrospective moving average of Trial4 residuals."""

import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


SOURCE = Path("phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
OUTPUT = Path("phases/phase4-trial7/data/analysis/trial7_s20240511t0214_minute.csv")
FIGURE = Path("phases/phase4-trial7/figures/trial7_s20240511t0214_moving_average.png")
STORM_ID = "S20240511T0214"
HALF_WINDOW_MINUTES = 30
MINUTE_US = 60_000_000
HOUR_US = 3_600_000_000
DENSITY_SCALE = 1e-12
ALGORITHM_VERSION = "phase4_trial7_centered_residual_mean_61min_v1"


def load_event() -> dict:
    """Input: frozen Trial4 SQLite and storm ID. Output: {t0_us, minute arrays}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        metadata = database.execute(
            "SELECT t0_time_us FROM trial4_25storm_overview WHERE storm_id=?",
            (STORM_ID,),
        ).fetchone()
        rows = database.execute("""
            SELECT time_us,rho_l2_phase_kg_m3,
                   rho_trial4_joint_phase_kg_m3,residual_log_density
            FROM trial4_joint_fit_minute
            WHERE storm_id=? ORDER BY time_us
        """, (STORM_ID,)).fetchall()
    if metadata is None or not rows:
        raise ValueError(f"Missing Trial4 minute series: {STORM_ID}")
    time_us = np.array([row[0] for row in rows], dtype=np.int64)
    l2_density = np.array([row[1] for row in rows], dtype=float)
    trial4_density = np.array([row[2] for row in rows], dtype=float)
    residual = np.array([row[3] for row in rows], dtype=float)
    if not np.all(np.diff(time_us) == MINUTE_US):
        raise ValueError("Selected event is not a continuous one-minute series.")
    if (np.any(l2_density <= 0) or np.any(trial4_density <= 0)
            or not np.all(np.isfinite(residual))
            or not np.allclose(np.log(l2_density / trial4_density), residual,
                               rtol=0, atol=1e-10)):
        raise ValueError("Trial4 minute residual contract failed.")
    return {"t0_us": int(metadata[0]), "time_us": time_us,
            "l2_density": l2_density, "trial4_density": trial4_density,
            "residual": residual}


def centered_mean(values: np.ndarray, half_window: int) -> np.ndarray:
    """Input: [one-minute values], radius in minutes. Output: [local means]."""
    if half_window < 0 or len(values) < 2 * half_window + 1:
        raise ValueError("Moving-average window exceeds the minute series.")
    window = np.ones(2 * half_window + 1)
    summed = np.convolve(values, window, mode="same")
    counts = np.convolve(np.ones(len(values)), window, mode="same")
    return summed / counts


def write_rows(event: dict, correction: np.ndarray) -> None:
    """Input: {minute arrays}, [smoothed log residual]. Output: derived CSV."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("storm_id", "time_us", "rho_l2_phase_kg_m3",
                         "rho_trial4_phase_kg_m3", "residual_log_density",
                         "moving_mean_log_residual", "rho_trial7_phase_kg_m3",
                         "algorithm_version"))
        for time_us, l2, trial4, residual, mean in zip(
            event["time_us"], event["l2_density"], event["trial4_density"],
            event["residual"], correction, strict=True
        ):
            writer.writerow((STORM_ID, int(time_us), float(l2), float(trial4),
                             float(residual), float(mean),
                             float(trial4 * math.exp(mean)), ALGORITHM_VERSION))


def draw_figure(event: dict, correction: np.ndarray) -> None:
    """Input: {minute arrays}, [smoothed log residual]. Output: comparison PNG."""
    time_hours = (event["time_us"] - event["t0_us"]) / HOUR_US
    trial7_density = event["trial4_density"] * np.exp(correction)
    curves = (
        (event["l2_density"], "Swarm-A L2", "#1f2937", 1.0),
        (event["trial4_density"], "Phase 3 Trial 4", "#d97706", 1.1),
        (trial7_density, "Moving-average correction", "#0f766e", 1.4),
    )
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    for axis in axes:
        for density, label, color, width in curves:
            axis.plot(time_hours, density / DENSITY_SCALE, color=color,
                      linewidth=width, label=label)
        axis.axvline(0, color="#6b7280", linestyle="--", linewidth=0.9)
        axis.set_ylabel(r"Density ($10^{-12}$ kg/m$^3$)")
        axis.grid(alpha=0.22)
    axes[0].set_title(f"{STORM_ID}: complete event, one-minute samples")
    axes[0].legend(loc="upper right", ncol=3, frameon=False)
    axes[1].set_xlim(-24, 24)
    axes[1].set_title("48 hours around the SYM-H minimum")
    axes[1].set_xlabel(r"Hours from $t_0$")
    figure.suptitle("Trial 4 residual: centered 61-minute moving average",
                    fontsize=14)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen Trial4 minute SQLite. Output: derived CSV and figure."""
    synthetic = centered_mean(np.array([0.0, 0.0, 3.0, 0.0, 0.0]), 1)
    if not np.allclose(synthetic, [0.0, 1.0, 1.0, 1.0, 0.0]):
        raise AssertionError("Centered moving-average check failed.")
    event = load_event()
    correction = centered_mean(event["residual"], HALF_WINDOW_MINUTES)
    write_rows(event, correction)
    draw_figure(event, correction)
    baseline_rmse = float(np.sqrt(np.mean(event["residual"] ** 2)))
    smoothed_rmse = float(np.sqrt(np.mean((event["residual"] - correction) ** 2)))
    print(f"Saved {len(event['time_us'])} one-minute rows; "
          f"in-sample log RMSE {baseline_rmse:.5f} -> {smoothed_rmse:.5f}")


if __name__ == "__main__":
    main()
