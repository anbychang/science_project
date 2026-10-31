"""Score and draw trailing one-orbit means of saved Trial 7 minute densities."""

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


ROOT = Path("phases/phase5-trial7")
POINTS = ROOT / "data/analysis/trial7_25storm_past_mean_minute.csv.gz"
FIGURES = ROOT / "figures/orbit_mean_25storm"
SUMMARY = ROOT / "data/analysis/trial7_25storm_orbit_mean_summary.csv"
OVERVIEW = ROOT / "figures/trial7_25storm_orbit_mean_rmse.png"
ACTIVITY = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
TRIAL4 = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
DENSITY_SCALE = 1e-12
HOUR_US = 3_600_000_000
SOURCE_VERSION = "phase4_trial7_past_60min_residual_mean_v1"
ALGORITHM_VERSION = "phase4_trial7_trailing_orbit_mean_score_v1"


def load_saved_events() -> dict[str, dict]:
    """Input: saved Trial 7 minute CSV.gz. Output: {storm_id: {column: [value]}}."""
    columns = ("time_us", "rho_l2_minute_kg_m3", "rho_trial4_pointwise_kg_m3",
               "rho_past_mean_kg_m3")
    events: dict[str, dict[str, list]] = {}
    with gzip.open(POINTS, "rt", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["algorithm_version"] != SOURCE_VERSION:
                raise ValueError("Saved Trial 7 correction version differs.")
            event = events.setdefault(row["storm_id"], {name: [] for name in columns})
            event["time_us"].append(int(row["time_us"]))
            for name in columns[1:]:
                event[name].append(float(row[name]) if row[name] else math.nan)
    if len(events) != 25:
        raise ValueError("Expected 25 saved Trial 7 storms.")
    return {storm_id: {name: np.asarray(values, dtype=np.int64 if name == "time_us" else float)
                       for name, values in event.items()}
            for storm_id, event in events.items()}


def load_orbit_phase(database: sqlite3.Connection, storm_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Input: Phase 2 database and storm ID. Output: [time_us], [phase_rad], [pair_count]."""
    rows = database.execute("""
        SELECT feature.source_time_us,feature.u_rel_rad,density.paired_sample_count
        FROM storm_minute_feature_v5 AS feature
        JOIN storm_density_1min_v5 AS density
          ON density.storm_id=feature.storm_id
         AND density.source_time_us=feature.source_time_us
        WHERE feature.storm_id=? ORDER BY feature.source_time_us
    """, (storm_id,)).fetchall()
    return (np.asarray([row[0] for row in rows], dtype=np.int64),
            np.asarray([row[1] for row in rows], dtype=float),
            np.asarray([row[2] for row in rows], dtype=int))


def trailing_orbit_mean(values: np.ndarray, phase_rad: np.ndarray,
                        pair_count: np.ndarray) -> np.ndarray:
    """Input: [density], [increasing phase rad], [native pair count]. Output: [past-orbit means]."""
    if (len(values) != len(phase_rad) or len(values) != len(pair_count)
            or not np.all(np.diff(phase_rad) > 0)):
        raise ValueError("Minute densities and increasing orbit phase must align.")
    right = np.arange(1, len(values) + 1)
    left = np.searchsorted(phase_rad, phase_rad - 2 * math.pi, side="left")
    valid = np.isfinite(values) & (pair_count > 0)
    weights = np.where(valid, pair_count, 0)
    weighted = np.where(valid, values, 0.0) * weights
    weight_sum = np.r_[0, np.cumsum(weights)]
    value_sum = np.r_[0.0, np.cumsum(weighted)]
    invalid_sum = np.r_[0, np.cumsum(~valid)]
    window_weights = weight_sum[right] - weight_sum[left]
    full_orbit = phase_rad - 2 * math.pi >= phase_rad[0]
    complete = full_orbit & (invalid_sum[right] == invalid_sum[left])
    result = np.full(len(values), np.nan)
    result[complete] = ((value_sum[right] - value_sum[left])[complete]
                        / window_weights[complete])
    return result


def score_event(event: dict) -> dict:
    """Input: {three orbit-mean densities, minute times, t0}. Output: one storm score."""
    l2 = event["orbit_l2"]
    trial4 = event["orbit_trial4"]
    corrected = event["orbit_corrected"]
    scored = np.isfinite(l2) & np.isfinite(trial4) & np.isfinite(corrected)
    if not np.any(scored) or np.any(l2[scored] <= 0) or np.any(trial4[scored] <= 0) or np.any(corrected[scored] <= 0):
        raise ValueError(f"No positive shared orbit means: {event['storm_id']}")
    baseline_error = np.log(l2[scored] / trial4[scored])
    corrected_error = np.log(l2[scored] / corrected[scored])
    near_t0 = scored & (np.abs(event["time_us"] - event["t0_us"]) <= 24 * HOUR_US)
    if not np.any(near_t0):
        raise ValueError(f"No scored orbit means near t0: {event['storm_id']}")
    return {
        "storm_id": event["storm_id"],
        "scored_count": int(np.count_nonzero(scored)),
        "trial4_log_rmse": float(np.sqrt(np.mean(baseline_error ** 2))),
        "corrected_log_rmse": float(np.sqrt(np.mean(corrected_error ** 2))),
        "t0_48h_scored_count": int(np.count_nonzero(near_t0)),
        "t0_48h_trial4_log_rmse": float(np.sqrt(np.mean(np.log(l2[near_t0] / trial4[near_t0]) ** 2))),
        "t0_48h_corrected_log_rmse": float(np.sqrt(np.mean(np.log(l2[near_t0] / corrected[near_t0]) ** 2))),
        "algorithm_version": ALGORITHM_VERSION,
    }


def draw_event(event: dict) -> None:
    """Input: {storm_id, t0_us, minute densities, phase, pair counts}. Output: one PNG."""
    time_hours = (event["time_us"] - event["t0_us"]) / HOUR_US
    curves = (
        ("orbit_l2", "Swarm-A L2", "#1f2937"),
        ("orbit_trial4", "Trial 4 formula", "#d97706"),
        ("orbit_corrected", "Past-only correction", "#0f766e"),
    )
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    for column, label, color in curves:
        for axis in axes:
            axis.plot(time_hours, event[column] / DENSITY_SCALE, color=color,
                      linewidth=1.3, label=label)
    for axis in axes:
        axis.axvline(0, color="#6b7280", linestyle="--", linewidth=0.9)
        axis.set_ylabel(r"Density ($10^{-12}$ kg/m$^3$)")
        axis.grid(alpha=0.22)
    axes[0].set_title(f"{event['storm_id']}: complete event")
    axes[0].legend(loc="upper right", ncol=3, frameon=False)
    axes[1].set_xlim(-24, 24)
    axes[1].set_title("48 hours around the SYM-H minimum")
    axes[1].set_xlabel(r"Hours from $t_0$")
    figure.suptitle("Trailing one-orbit mean (2pi phase); score uses these same mean curves",
                    fontsize=13)
    figure.savefig(FIGURES / f"{event['storm_id'].lower()}_orbit_mean.png", dpi=150)
    plt.close(figure)


def draw_overview(rows: list[dict]) -> None:
    """Input: [25 orbit-mean score records]. Output: per-storm RMSE PNG."""
    positions = np.arange(len(rows))
    figure, axis = plt.subplots(figsize=(10, 11), layout="constrained")
    axis.barh(positions - 0.18, [row["trial4_log_rmse"] for row in rows],
              height=0.36, color="#d97706", label="Trial 4 formula")
    axis.barh(positions + 0.18, [row["corrected_log_rmse"] for row in rows],
              height=0.36, color="#0f766e", label="Past-only correction")
    axis.set_yticks(positions, [row["storm_id"] for row in rows])
    axis.invert_yaxis()
    axis.set_xlabel("Log-density RMSE of trailing one-orbit means")
    axis.set_title("25 storms: same orbit-mean rows, original minute correction")
    axis.legend(frameon=False)
    axis.grid(axis="x", alpha=0.22)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def main() -> None:
    """Input: saved Trial 7 points and read-only orbit phase. Output: scores and PNGs."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    events = load_saved_events()
    scores = []
    with closing(sqlite3.connect(f"file:{ACTIVITY.resolve().as_posix()}?mode=ro", uri=True)) as activity:
        with closing(sqlite3.connect(f"file:{TRIAL4.resolve().as_posix()}?mode=ro", uri=True)) as trial4:
            for storm_id, event in events.items():
                times, phase_rad, pair_count = load_orbit_phase(activity, storm_id)
                if not np.array_equal(event["time_us"], times):
                    raise ValueError(f"Saved Trial 7 minutes and orbit phase differ: {storm_id}")
                t0_row = trial4.execute(
                    "SELECT t0_time_us FROM trial4_25storm_overview WHERE storm_id=?",
                    (storm_id,)).fetchone()
                if t0_row is None:
                    raise ValueError(f"Missing Trial 4 event time: {storm_id}")
                event.update(storm_id=storm_id, t0_us=t0_row[0],
                             phase_rad=phase_rad, pair_count=pair_count)
                for source, target in (("rho_l2_minute_kg_m3", "orbit_l2"),
                                       ("rho_trial4_pointwise_kg_m3", "orbit_trial4"),
                                       ("rho_past_mean_kg_m3", "orbit_corrected")):
                    event[target] = trailing_orbit_mean(event[source], phase_rad, pair_count)
                scores.append(score_event(event))
                draw_event(event)
    with SUMMARY.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(scores[0]))
        writer.writeheader()
        writer.writerows(scores)
    draw_overview(scores)
    improved = sum(row["corrected_log_rmse"] < row["trial4_log_rmse"] for row in scores)
    count = sum(row["scored_count"] for row in scores)
    baseline_rmse = math.sqrt(sum(row["scored_count"] * row["trial4_log_rmse"] ** 2
                                  for row in scores) / count)
    corrected_rmse = math.sqrt(sum(row["scored_count"] * row["corrected_log_rmse"] ** 2
                                   for row in scores) / count)
    print(f"Saved {len(scores)} orbit-mean scores and figures; {count} scored windows; "
          f"RMSE {baseline_rmse:.5f} -> {corrected_rmse:.5f}; improved {improved}/25")


if __name__ == "__main__":
    main()
