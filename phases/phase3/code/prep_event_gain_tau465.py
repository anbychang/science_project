"""Measure event-specific gain with the shared Phase 3 time constant fixed."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from phases.phase3.code.prep_prediction_tau465 import (
    OUTPUT as PREDICTIONS,
    TAU_HOURS,
    load_global_gain,
)


OUTPUT = Path("phases/phase3/data/sqlite/swarm_a_phase3_event_gain_tau465_diagnostic_v1.sqlite")
FIGURE = Path("phases/phase3/figures/event_gain_tau465_diagnostic.png")
ALGORITHM_VERSION = "phase3_event_gain_tau465_diagnostic_v1"


def fit_event_gain(
    response_nt: np.ndarray, log_anomaly: np.ndarray, pooled_gain_per_nt: float
) -> dict:
    """Input: [H nT], [log density anomaly], pooled G 1/nT. Output: gain and RMSE."""
    if (len(response_nt) == 0 or len(response_nt) != len(log_anomaly)
            or not np.isfinite(response_nt).all()
            or not np.isfinite(log_anomaly).all()
            or not math.isfinite(pooled_gain_per_nt)
            or pooled_gain_per_nt <= 0):
        raise ValueError("Gain fit needs aligned finite data and positive pooled G.")
    response_square_sum = float(response_nt @ response_nt)
    if response_square_sum <= 0:
        raise ValueError("Gain is unidentified when every response is zero.")
    event_gain = float(response_nt @ log_anomaly) / response_square_sum
    pooled_error = log_anomaly - pooled_gain_per_nt * response_nt
    event_error = log_anomaly - event_gain * response_nt
    pooled_rmse = float(np.sqrt(np.mean(pooled_error ** 2)))
    event_rmse = float(np.sqrt(np.mean(event_error ** 2)))
    return {
        "gain_event_fit_per_nt": event_gain,
        "gain_ratio_to_pooled": event_gain / pooled_gain_per_nt,
        "rmse_pooled_log_density": pooled_rmse,
        "rmse_event_fit_log_density": event_rmse,
        "rmse_reduction_pct": (
            100 * (pooled_rmse - event_rmse) / pooled_rmse
            if pooled_rmse > 0 else 0.0
        ),
    }


def fit_events() -> list[dict]:
    """Input: read-only Phase 3 predictions and provisional R. Output: 25 gain rows."""
    pooled_gain = load_global_gain()
    uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        overview = database.execute("""
            SELECT storm_id,t0_time_us,symh_min_nt,valid_phase_minutes,
                   tau_hours,r_candidate
            FROM phase3_25storm_overview ORDER BY t0_time_us
        """).fetchall()
        if len(overview) != 25:
            raise ValueError("Expected 25 Phase 3 storm summaries.")
        results = []
        for storm_id, t0_time_us, symh_min_nt, expected, tau_hours, quiet_ratio in overview:
            if not math.isclose(tau_hours, TAU_HOURS):
                raise ValueError(f"Unexpected tau for {storm_id}.")
            samples = database.execute("""
                SELECT h_phase_nt,rho_l2_phase_kg_m3,
                       rho_msis_quiet_phase_kg_m3,rho_m1_pooled_phase_kg_m3
                FROM phase3_prediction_minute WHERE storm_id=? ORDER BY time_us
            """, (storm_id,)).fetchall()
            if len(samples) != expected:
                raise ValueError(f"Prediction count differs for {storm_id}.")
            values = np.asarray(samples, dtype=float)
            response_nt, l2_density, quiet_density, pooled_prediction = values.T
            if (quiet_ratio <= 0 or not np.isfinite(values).all()
                    or np.any(l2_density <= 0) or np.any(quiet_density <= 0)):
                raise ValueError(f"Invalid paired density for {storm_id}.")
            reconstructed = quiet_density * quiet_ratio * np.exp(
                pooled_gain * response_nt
            )
            if not np.allclose(reconstructed, pooled_prediction, rtol=1e-10, atol=0):
                raise ValueError(f"Pooled prediction changed for {storm_id}.")
            log_anomaly = np.log(l2_density / quiet_density) - math.log(quiet_ratio)
            fit = fit_event_gain(response_nt, log_anomaly, pooled_gain)
            results.append({
                "storm_id": storm_id,
                "t0_time_us": t0_time_us,
                "symh_min_nt": symh_min_nt,
                "valid_phase_minutes": expected,
                "tau_hours": tau_hours,
                "r_candidate": quiet_ratio,
                "gain_pooled_per_nt": pooled_gain,
                **fit,
                "algorithm_version": ALGORITHM_VERSION,
            })
    return results


def save_results(rows: list[dict]) -> None:
    """Input: 25 event gain rows. Output: new derived SQLite with provenance."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="phase3_event_gain_tau465.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase3_event_gain_tau465_diagnostic (
                    storm_id TEXT PRIMARY KEY,
                    t0_time_us INTEGER NOT NULL UNIQUE,
                    symh_min_nt INTEGER NOT NULL,
                    valid_phase_minutes INTEGER NOT NULL,
                    tau_hours REAL NOT NULL,
                    r_candidate REAL NOT NULL,
                    gain_pooled_per_nt REAL NOT NULL,
                    gain_event_fit_per_nt REAL NOT NULL,
                    gain_ratio_to_pooled REAL NOT NULL,
                    rmse_pooled_log_density REAL NOT NULL,
                    rmse_event_fit_log_density REAL NOT NULL,
                    rmse_reduction_pct REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE phase3_event_gain_metadata (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            database.executemany(
                "INSERT INTO phase3_event_gain_metadata VALUES (?,?)",
                (
                    ("source", PREDICTIONS.as_posix()),
                    ("tau_hours", str(TAU_HOURS)),
                    ("fit_scope", "in-sample storm-time L2; diagnostic only"),
                    ("algorithm_version", ALGORITHM_VERSION),
                ),
            )
            database.executemany("""
                INSERT INTO phase3_event_gain_tau465_diagnostic
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                (
                    row["storm_id"],
                    row["t0_time_us"],
                    row["symh_min_nt"],
                    row["valid_phase_minutes"],
                    row["tau_hours"],
                    row["r_candidate"],
                    row["gain_pooled_per_nt"],
                    row["gain_event_fit_per_nt"],
                    row["gain_ratio_to_pooled"],
                    row["rmse_pooled_log_density"],
                    row["rmse_event_fit_log_density"],
                    row["rmse_reduction_pct"],
                    row["algorithm_version"],
                )
                for row in rows
            ))
            count = database.execute(
                "SELECT count(*) FROM phase3_event_gain_tau465_diagnostic"
            ).fetchone()[0]
            if (count != len(rows)
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Event gain SQLite failed count or integrity checks.")
            database.commit()
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def draw_results(rows: list[dict]) -> None:
    """Input: 25 gain rows. Output: in-sample gain and RMSE comparison PNG."""
    positions = np.arange(len(rows))
    labels = [row["storm_id"][1:9] for row in rows]
    figure, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                               constrained_layout=True)
    axes[0].axhline(1, color="#64748b", linewidth=1, label="shared G")
    axes[0].scatter(positions, [row["gain_ratio_to_pooled"] for row in rows],
                    color="#2563eb", label="event-fitted G / shared G")
    axes[0].set_ylabel("Gain ratio")
    axes[0].legend()
    axes[1].plot(positions, [row["rmse_pooled_log_density"] for row in rows],
                 "o-", color="#64748b", label="shared G")
    axes[1].plot(positions, [row["rmse_event_fit_log_density"] for row in rows],
                 "o-", color="#2563eb", label="event-fitted G")
    axes[1].set(ylabel="Log-density RMSE", title="Fixed tau=4.65 h; in-sample diagnostic")
    axes[1].legend()
    axes[1].set_xticks(positions, labels, rotation=60, ha="right")
    for axis in axes:
        axis.grid(alpha=0.2)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: existing Phase 3 prediction SQLite. Output: gain SQLite and PNG."""
    if OUTPUT.exists() or FIGURE.exists():
        raise FileExistsError("Event gain diagnostic already exists.")
    rows = fit_events()
    save_results(rows)
    draw_results(rows)
    print(f"Saved fixed-tau event gain diagnostic for {len(rows)} storms.")


if __name__ == "__main__":
    main()
