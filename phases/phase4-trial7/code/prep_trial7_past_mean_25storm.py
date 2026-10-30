"""Score a past-only one-minute residual average across all 25 storms."""

import csv
import gzip
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from calc_trial7_past_mean import past_mean
from prep_trial7_raw_minute_figure import (
    ACTIVITY, DENSITY_SCALE, HOUR_US, TRIAL4, load_pointwise_event, load_sme,
    read_only,
)


ROOT = Path("phases/phase4-trial7")
SUMMARY = ROOT / "data/analysis/trial7_25storm_past_mean_summary.csv"
POINTS = ROOT / "data/analysis/trial7_25storm_past_mean_minute.csv.gz"
FIGURES = ROOT / "figures/past_mean_25storm"
OVERVIEW = ROOT / "figures/trial7_25storm_past_mean_rmse.png"
HISTORY_MINUTES = 60
ALGORITHM_VERSION = "phase4_trial7_past_60min_residual_mean_v1"


def load_storm_ids() -> list[str]:
    """Input: frozen Trial4 overview. Output: [25 storm IDs in UTC order]."""
    with closing(read_only(TRIAL4)) as database:
        storm_ids = [row[0] for row in database.execute(
            "SELECT storm_id FROM trial4_25storm_overview ORDER BY t0_time_us")]
    if len(storm_ids) != 25 or len(set(storm_ids)) != 25:
        raise ValueError("Expected 25 distinct Trial4 storms.")
    return storm_ids


def score_event(event: dict, estimate: np.ndarray) -> dict:
    """Input: {minute event}, [past estimates]. Output: one storm metric record."""
    scored = np.isfinite(estimate) & np.isfinite(event["residual"])
    if not np.any(scored):
        raise ValueError(f"No scored minutes: {event['storm_id']}")
    residual = event["residual"][scored]
    error = residual - estimate[scored]
    time_hours = (event["time_us"] - event["t0_us"]) / HOUR_US
    t0_scored = scored & (np.abs(time_hours) <= 24)
    if not np.any(t0_scored):
        raise ValueError(f"No scored t0 minutes: {event['storm_id']}")
    t0_residual = event["residual"][t0_scored]
    t0_error = t0_residual - estimate[t0_scored]
    return {
        "storm_id": event["storm_id"],
        "minute_count": len(event["time_us"]),
        "valid_l2_count": int(np.count_nonzero(np.isfinite(event["residual"]))),
        "scored_count": int(np.count_nonzero(scored)),
        "trial4_log_rmse": float(np.sqrt(np.mean(residual ** 2))),
        "past_mean_log_rmse": float(np.sqrt(np.mean(error ** 2))),
        "trial4_log_mae": float(np.mean(np.abs(residual))),
        "past_mean_log_mae": float(np.mean(np.abs(error))),
        "t0_48h_scored_count": int(np.count_nonzero(t0_scored)),
        "t0_48h_trial4_log_rmse": float(np.sqrt(np.mean(t0_residual ** 2))),
        "t0_48h_past_mean_log_rmse": float(np.sqrt(np.mean(t0_error ** 2))),
        "algorithm_version": ALGORITHM_VERSION,
    }


def write_points(writer: csv.writer, event: dict, estimate: np.ndarray) -> None:
    """Input: CSV writer, {minute event}, [past estimates]. Output: appended rows."""
    for time_us, l2, trial4, residual, mean in zip(
        event["time_us"], event["l2_density"], event["trial4_density"],
        event["residual"], estimate, strict=True
    ):
        corrected = trial4 * math.exp(mean) if np.isfinite(mean) else None
        writer.writerow((event["storm_id"], int(time_us),
                         float(l2) if np.isfinite(l2) else None,
                         float(trial4) if np.isfinite(trial4) else None,
                         float(residual) if np.isfinite(residual) else None,
                         float(mean) if np.isfinite(mean) else None,
                         float(corrected) if corrected is not None else None,
                         ALGORITHM_VERSION))


def draw_event(event: dict, estimate: np.ndarray) -> None:
    """Input: {minute event}, [past estimates]. Output: one storm PNG."""
    time_hours = (event["time_us"] - event["t0_us"]) / HOUR_US
    corrected = event["trial4_density"] * np.exp(estimate)
    curves = (
        (event["l2_density"], "Swarm-A L2, one minute", "#1f2937", 0.8),
        (event["trial4_density"], "Trial 4 formula, one minute", "#d97706", 0.9),
        (corrected, "Past-only moving mean", "#0f766e", 0.95),
    )
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    for axis in axes:
        for density, label, color, width in curves:
            axis.plot(time_hours, density / DENSITY_SCALE, color=color,
                      linewidth=width, label=label, alpha=0.85)
        axis.axvline(0, color="#6b7280", linestyle="--", linewidth=0.9)
        axis.set_ylabel(r"Density ($10^{-12}$ kg/m$^3$)")
        axis.grid(alpha=0.22)
    axes[0].set_title(f"{event['storm_id']}: complete event")
    axes[0].legend(loc="upper right", ncol=3, frameon=False)
    axes[1].set_xlim(-24, 24)
    axes[1].set_title("48 hours around the SYM-H minimum")
    axes[1].set_xlabel(r"Hours from $t_0$")
    figure.suptitle("Previous 60 observed minutes only; current L2 excluded",
                    fontsize=14)
    figure.savefig(FIGURES / f"{event['storm_id'].lower()}_past_mean.png", dpi=150)
    plt.close(figure)


def draw_overview(rows: list[dict]) -> None:
    """Input: [25 storm metrics]. Output: per-storm RMSE comparison PNG."""
    positions = np.arange(len(rows))
    figure, axis = plt.subplots(figsize=(10, 11), layout="constrained")
    axis.barh(positions - 0.18, [row["trial4_log_rmse"] for row in rows],
              height=0.36, color="#d97706", label="Trial 4 formula")
    axis.barh(positions + 0.18, [row["past_mean_log_rmse"] for row in rows],
              height=0.36, color="#0f766e", label="Past-only moving mean")
    axis.set_yticks(positions, [row["storm_id"] for row in rows])
    axis.invert_yaxis()
    axis.set_xlabel("Log-density RMSE on the same scored one-minute rows")
    axis.set_title("25 storms: previous 60 observed minutes, current L2 excluded")
    axis.legend(frameon=False)
    axis.grid(axis="x", alpha=0.22)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def main() -> None:
    """Input: frozen Phase 2/3/Trial4 data. Output: 25 charts and score CSVs."""
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    with closing(read_only(ACTIVITY)) as database:
        sme_values, first_time_us = load_sme(database)
    sme = {"values": sme_values, "first_time_us": first_time_us}
    scores = []
    with gzip.open(POINTS, "wt", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("storm_id", "time_us", "rho_l2_minute_kg_m3",
                         "rho_trial4_pointwise_kg_m3", "residual_log_density",
                         "past_mean_log_residual", "rho_past_mean_kg_m3",
                         "algorithm_version"))
        for storm_id in load_storm_ids():
            event = load_pointwise_event(storm_id, sme)
            estimate = past_mean(event["residual"], HISTORY_MINUTES)
            scores.append(score_event(event, estimate))
            write_points(writer, event, estimate)
            draw_event(event, estimate)
            print(f"Scored {storm_id}: {scores[-1]['scored_count']} minutes")
    with SUMMARY.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(scores[0]))
        writer.writeheader()
        writer.writerows(scores)
    draw_overview(scores)
    improved = sum(row["past_mean_log_rmse"] < row["trial4_log_rmse"]
                   for row in scores)
    print(f"Saved 25 storm charts; improved {improved}/25 storms")


if __name__ == "__main__":
    main()
