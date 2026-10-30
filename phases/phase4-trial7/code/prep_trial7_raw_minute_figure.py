"""Compare raw one-minute L2 with a pointwise Trial4 formula and residual mean."""

import csv
import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path("phases/phase3-trial4/code").resolve()))
from calc_h_tau import filtered_sme, phase_weighted_mean  # noqa: E402
from prep_h_tau_phase import load_event, load_sme  # noqa: E402
from prep_trial7_moving_average_figure import centered_mean  # noqa: E402


TRIAL4 = Path("phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
QUIET = Path("phases/phase3-trial4/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite")
ACTIVITY = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
OUTPUT = Path("phases/phase4-trial7/data/analysis/trial7_s20240511t0214_raw_minute.csv")
FIGURE = Path("phases/phase4-trial7/figures/trial7_s20240511t0214_raw_minute.png")
STORM_ID = "S20240511T0214"
HALF_WINDOW_MINUTES = 30
MINUTE_US = 60_000_000
HOUR_US = 3_600_000_000
REFERENCE_SME_NT = 65.0
DENSITY_SCALE = 1e-12
ALGORITHM_VERSION = "phase4_trial7_pointwise_trial4_centered_mean_61min_v1"


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def load_pointwise_event(storm_id: str, sme: dict) -> dict:
    """Input: storm ID, {SME values, first time_us}. Output: {t0_us, minute arrays}."""
    with closing(read_only(TRIAL4)) as database:
        fitted = database.execute("""
            SELECT t0_time_us,r_fit,tau_hours,gain_per_nt
            FROM trial4_25storm_overview WHERE storm_id=?
        """, (storm_id,)).fetchone()
        phase_rows = database.execute("""
            SELECT time_us,h_phase_nt,rho_msis_quiet_phase_kg_m3,
                   rho_trial4_joint_phase_kg_m3
            FROM trial4_joint_fit_minute WHERE storm_id=? ORDER BY time_us
        """, (storm_id,)).fetchall()
    with closing(read_only(QUIET)) as database:
        rows = database.execute("""
            SELECT time_us,paired_sample_count,rho_l2_kg_m3,
                   rho_msis_quiet_kg_m3
            FROM phase3_quiet_density_minute
            WHERE storm_id=? ORDER BY time_us
        """, (storm_id,)).fetchall()
    if fitted is None or not phase_rows or not rows:
        raise ValueError(f"Missing one-minute Trial4 inputs: {storm_id}")
    time_us = np.array([row[0] for row in rows], dtype=np.int64)
    paired = np.array([row[1] for row in rows], dtype=np.int16)
    l2_density = np.array([row[2] for row in rows], dtype=float)
    quiet_density = np.array([row[3] for row in rows], dtype=float)
    valid = paired > 0
    if (not np.all(np.diff(time_us) == MINUTE_US)
            or not np.array_equal(valid, np.isfinite(l2_density))
            or not np.array_equal(valid, np.isfinite(quiet_density))
            or np.any(l2_density[valid] <= 0)
            or np.any(quiet_density[valid] <= 0)):
        raise ValueError(f"Invalid paired one-minute densities: {storm_id}")
    t0_us, r_fit, tau_hours, gain_per_nt = fitted
    with closing(read_only(ACTIVITY)) as database:
        phase_event = load_event(database, storm_id, sme["first_time_us"])
    if (not np.array_equal(time_us, phase_event["time_us"])
            or not np.array_equal(paired, phase_event["pair_count"])):
        raise ValueError("Phase 2 and Phase 3 minute inputs differ.")
    response_nt = (filtered_sme(sme["values"], tau_hours)
                   [phase_event["minute_index"]] - REFERENCE_SME_NT)
    phase_valid = phase_event["support"]["valid"]
    official_time = np.array([row[0] for row in phase_rows], dtype=np.int64)
    phase_response = np.array([row[1] for row in phase_rows], dtype=float)
    phase_quiet = np.array([row[2] for row in phase_rows], dtype=float)
    official_prediction = np.array([row[3] for row in phase_rows], dtype=float)
    reconstructed_response = phase_weighted_mean(
        response_nt, paired, phase_event["support"])[phase_valid]
    reconstructed_quiet = phase_weighted_mean(
        quiet_density, paired, phase_event["support"])[phase_valid]
    if (not np.array_equal(time_us[phase_valid], official_time)
            or not np.allclose(reconstructed_response, phase_response,
                               rtol=1e-10, atol=1e-8)
            or not np.allclose(reconstructed_quiet, phase_quiet,
                               rtol=1e-9, atol=0)
            or not np.allclose(
                reconstructed_quiet * r_fit * np.exp(gain_per_nt * phase_response),
                official_prediction, rtol=1e-9, atol=0)):
        raise ValueError("One-minute inputs do not reconstruct official Trial4.")
    pointwise_trial4 = quiet_density * r_fit * np.exp(gain_per_nt * response_nt)
    return {"storm_id": storm_id, "t0_us": int(t0_us), "time_us": time_us,
            "l2_density": l2_density, "trial4_density": pointwise_trial4,
            "residual": np.log(l2_density / pointwise_trial4)}


def write_rows(event: dict, correction: np.ndarray) -> None:
    """Input: {raw minute arrays}, [smoothed log residual]. Output: derived CSV."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("storm_id", "time_us", "rho_l2_minute_kg_m3",
                         "rho_trial4_pointwise_kg_m3", "residual_log_density",
                         "moving_mean_log_residual", "rho_trial7_minute_kg_m3",
                         "algorithm_version"))
        for time_us, l2, trial4, residual, mean in zip(
            event["time_us"], event["l2_density"], event["trial4_density"],
            event["residual"], correction, strict=True
        ):
            writer.writerow((STORM_ID, int(time_us), float(l2), float(trial4),
                             float(residual), float(mean),
                             float(trial4 * math.exp(mean)), ALGORITHM_VERSION))


def draw_figure(event: dict, correction: np.ndarray) -> None:
    """Input: {raw minute arrays}, [smoothed log residual]. Output: PNG."""
    time_hours = (event["time_us"] - event["t0_us"]) / HOUR_US
    corrected = event["trial4_density"] * np.exp(correction)
    curves = (
        (event["l2_density"], "Swarm-A L2, one minute", "#1f2937", 0.85),
        (event["trial4_density"], "Trial 4 formula, one minute", "#d97706", 0.95),
        (corrected, "Moving-average correction", "#0f766e", 1.0),
    )
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    for axis in axes:
        for density, label, color, width in curves:
            axis.plot(time_hours, density / DENSITY_SCALE, color=color,
                      linewidth=width, label=label, alpha=0.85)
        axis.axvline(0, color="#6b7280", linestyle="--", linewidth=0.9)
        axis.set_ylabel(r"Density ($10^{-12}$ kg/m$^3$)")
        axis.grid(alpha=0.22)
    axes[0].set_title(f"{STORM_ID}: complete event, raw one-minute densities")
    axes[0].legend(loc="upper right", ncol=3, frameon=False)
    axes[1].set_xlim(-24, 24)
    axes[1].set_title("48 hours around the SYM-H minimum")
    axes[1].set_xlabel(r"Hours from $t_0$")
    figure.suptitle("Retrospective: Trial 4 formula + L2 residual mean (61 min)",
                    fontsize=14)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen Phase 2/3/Trial4 outputs. Output: raw-minute CSV and PNG."""
    with closing(read_only(ACTIVITY)) as database:
        sme_values, first_time_us = load_sme(database)
    event = load_pointwise_event(
        STORM_ID, {"values": sme_values, "first_time_us": first_time_us})
    correction = centered_mean(event["residual"], HALF_WINDOW_MINUTES)
    write_rows(event, correction)
    draw_figure(event, correction)
    baseline_rmse = float(np.sqrt(np.mean(event["residual"] ** 2)))
    smoothed_rmse = float(np.sqrt(np.mean((event["residual"] - correction) ** 2)))
    print(f"Saved {len(event['time_us'])} raw one-minute rows; "
          f"same-data log RMSE {baseline_rmse:.5f} -> {smoothed_rmse:.5f}")


if __name__ == "__main__":
    main()
