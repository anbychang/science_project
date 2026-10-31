"""Score a past-only GPR correction at one anchor per Swarm-A orbit."""

import csv
import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from calc_trial8_next_orbit_gpr import predict_event


ROOT = Path("phases/phase5-trial8")
ANCHORS = Path("phases/phase5-trial1/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite")
TRIAL4 = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
POINTS = ROOT / "data/analysis/trial8_next_orbit_predictions.csv"
METRICS = ROOT / "data/analysis/trial8_next_orbit_metrics.csv"
FIGURES = ROOT / "figures/next_orbit_25storm"
OVERVIEW = ROOT / "figures/trial8_next_orbit_rmse.png"
VERSION = "phase4_trial8_lag_residual_gpr_v1"
HOUR_US = 3_600_000_000


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def load_events() -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Input: fixed orbit anchors and Trial4 event times. Output: {storm: [orbit]}, {storm: t0}."""
    with closing(read_only(ANCHORS)) as database:
        source = database.execute("""
            SELECT storm_id,time_us,u_rel_rad,rho_l2_phase_kg_m3,
                   rho_trial4_phase_kg_m3,residual_log_density
            FROM phase4_trial4_gpr_prediction ORDER BY storm_id,time_us
        """).fetchall()
    with closing(read_only(TRIAL4)) as database:
        event_times = dict(database.execute(
            "SELECT storm_id,t0_time_us FROM trial4_25storm_overview"))
    events = defaultdict(list)
    for storm_id, time_us, phase, l2, baseline, residual in source:
        if (l2 <= 0 or baseline <= 0 or not math.isfinite(residual)
                or not math.isclose(residual, math.log(l2 / baseline),
                                    rel_tol=1e-12, abs_tol=1e-12)):
            raise ValueError(f"Invalid fixed residual: {storm_id}:{time_us}")
        events[storm_id].append({"storm_id": storm_id, "time_us": time_us,
                                 "u_rel_rad": phase, "rho_l2_phase_kg_m3": l2,
                                 "rho_trial4_phase_kg_m3": baseline,
                                 "residual_log_density": residual})
    if len(source) != 2295 or len(events) != 25 or set(events) != set(event_times):
        raise ValueError("Expected 2,295 anchors from the same 25 Trial4 storms.")
    return dict(events), event_times


def score(rows: list[dict], storm_id: str) -> dict:
    """Input: [eligible orbit predictions], storm ID. Output: one comparable metric row."""
    actual = np.array([row["residual_log_density"] for row in rows])
    previous = np.array([row["previous_log_residual"] for row in rows])
    gp = np.array([row["gp_log_residual_mean"] for row in rows])
    return {"storm_id": storm_id, "scored_orbits": len(rows),
            "trial4_log_rmse": float(np.sqrt(np.mean(actual ** 2))),
            "previous_orbit_log_rmse": float(np.sqrt(np.mean((actual - previous) ** 2))),
            "gpr_log_rmse": float(np.sqrt(np.mean((actual - gp) ** 2))),
            "trial4_log_mae": float(np.mean(np.abs(actual))),
            "previous_orbit_log_mae": float(np.mean(np.abs(actual - previous))),
            "gpr_log_mae": float(np.mean(np.abs(actual - gp))),
            "algorithm_version": VERSION}


def draw_event(rows: list[dict], storm_id: str, t0_us: int) -> None:
    """Input: [eligible orbit predictions], storm ID, t0. Output: one comparison PNG."""
    hours = [(row["time_us"] - t0_us) / HOUR_US for row in rows]
    curves = (
        ("rho_l2_phase_kg_m3", "Swarm-A L2", "#111827"),
        ("rho_trial4_phase_kg_m3", "Trial4 D-model", "#d97706"),
        ("rho_previous_kg_m3", "Previous orbit", "#2563eb"),
        ("rho_gpr_kg_m3", "Lag-residual GPR", "#dc2626"),
    )
    figure, axis = plt.subplots(figsize=(12, 4.5), layout="constrained")
    for field, label, color in curves:
        axis.plot(hours, [row[field] / 1e-12 for row in rows], label=label,
                  color=color, linewidth=1.1)
    axis.axvline(0, color="#6b7280", linestyle="--", linewidth=0.9)
    axis.set_title(f"{storm_id}: next-orbit correction from completed orbits")
    axis.set_xlabel(r"Hours from event time $t_0$")
    axis.set_ylabel(r"One-orbit phase density ($10^{-12}$ kg/m$^3$)")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, ncol=4)
    figure.savefig(FIGURES / f"{storm_id.lower()}_next_orbit.png", dpi=160)
    plt.close(figure)


def draw_overview(metrics: list[dict]) -> None:
    """Input: [25 storm metrics]. Output: one per-storm RMSE PNG."""
    positions = np.arange(len(metrics))
    figure, axis = plt.subplots(figsize=(10, 11), layout="constrained")
    for offset, field, label, color in (
        (-0.25, "trial4_log_rmse", "Trial4 D-model", "#d97706"),
        (0, "previous_orbit_log_rmse", "Previous orbit", "#2563eb"),
        (0.25, "gpr_log_rmse", "Lag-residual GPR", "#dc2626"),
    ):
        axis.barh(positions + offset, [row[field] for row in metrics],
                  height=0.24, label=label, color=color)
    axis.set_yticks(positions, [row["storm_id"] for row in metrics])
    axis.invert_yaxis()
    axis.set_xlabel("Log-density RMSE on the same eligible orbit anchors")
    axis.set_title("25 storms: correction using completed orbits only")
    axis.legend(frameon=False)
    axis.grid(axis="x", alpha=0.2)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: output path, [{field: value}]. Output: new UTF-8 CSV."""
    with path.open("x", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Input: read-only Trial1/Trial4 SQLite. Output: Trial8 CSVs and PNGs."""
    if POINTS.exists() or METRICS.exists() or OVERVIEW.exists():
        raise FileExistsError("Trial8 result already exists; keep the first run immutable.")
    events, event_times = load_events()
    predictions = []
    metrics = []
    for storm_id, event in events.items():
        scored = predict_event(event)
        if not scored:
            raise ValueError(f"No eligible orbit anchors: {storm_id}")
        for row in scored:
            baseline = row["rho_trial4_phase_kg_m3"]
            row["rho_previous_kg_m3"] = baseline * math.exp(row["previous_log_residual"])
            row["rho_gpr_kg_m3"] = baseline * math.exp(row["gp_log_residual_mean"])
            row["algorithm_version"] = VERSION
        predictions.extend(scored)
        metrics.append(score(scored, storm_id))
        print(f"Predicted {storm_id}: {len(scored)} orbits", flush=True)
    overall = score(predictions, "all_eligible_orbits")
    POINTS.parent.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    write_csv(POINTS, predictions)
    write_csv(METRICS, [*metrics, overall])
    for storm_id, event in events.items():
        draw_event([row for row in predictions if row["storm_id"] == storm_id],
                   storm_id, event_times[storm_id])
    draw_overview(metrics)
    print(overall)


if __name__ == "__main__":
    main()
