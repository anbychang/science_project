"""Inspect aligned full-MSIS residuals before defining an independent M2 correction."""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


M0 = Path("phases/phase3/data/sqlite/swarm_a_phase3_m0_ap_alignment_v1.sqlite")
RESPONSE = Path("phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
OUTPUT = Path("phases/phase3/data/sqlite/swarm_a_phase3_m2_residual_diagnostic_v1.sqlite")
FIGURE = Path("phases/phase3/figures/m2_full_msis_residual_7_boundary.png")
VERSION = "phase3_m2_residual_diagnostic_v1"
BOUNDARY_STORMS = (
    "S20231201T1330", "S20240303T1800", "S20240324T1621",
    "S20240628T1206", "S20240804T1704", "S20240812T1652",
    "S20260402T0841",
)


def load_events() -> list[dict]:
    """Input: read-only aligned M0 and SME response SQLite. Output: [event arrays]."""
    uri = f"file:{M0.resolve().as_posix()}?mode=ro"
    response_uri = f"file:{RESPONSE.resolve().as_posix()}?mode=ro"
    events = []
    with closing(sqlite3.connect(uri, uri=True)) as database:
        database.execute("ATTACH DATABASE ? AS response", (response_uri,))
        for storm_id, t0_time_us in database.execute(
            "SELECT storm_id,t0_time_us FROM response.phase3_25storm_overview "
            "ORDER BY t0_time_us"
        ):
            rows = database.execute("""
                SELECT m.time_us,m.rho_l2_phase_kg_m3,
                       m.rho_m0_aligned_phase_kg_m3,p.h_phase_nt,
                       p.rho_l2_phase_kg_m3
                FROM phase3_m0_ap_alignment_minute AS m
                JOIN response.phase3_prediction_minute AS p
                  ON m.storm_id=p.storm_id AND m.time_us=p.time_us
                WHERE m.storm_id=? AND m.phase_is_valid_80pct=1
                ORDER BY m.time_us
            """, (storm_id,)).fetchall()
            times = np.array([row[0] for row in rows], dtype=np.int64)
            l2 = np.array([row[1] for row in rows])
            m0 = np.array([row[2] for row in rows])
            response = np.array([row[3] for row in rows])
            original_l2 = np.array([row[4] for row in rows])
            if not len(rows) or not np.allclose(l2, original_l2,
                                                rtol=1e-10, atol=0):
                raise ValueError(f"L2 phase pairing differs: {storm_id}")
            if np.any(l2 <= 0) or np.any(m0 <= 0) or not np.isfinite(response).all():
                raise ValueError(f"Invalid M2 diagnostic inputs: {storm_id}")
            events.append({"storm_id": storm_id, "t0_time_us": t0_time_us,
                           "times": times, "l2": l2, "m0": m0,
                           "h": response, "residual": np.log(l2 / m0)})
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, found {len(events)}")
    return events


def summarize(event: dict) -> tuple:
    """Input: {storm, [residual], [SME response]}. Output: one event summary row."""
    residual = event["residual"]
    response = event["h"]
    centered_residual = residual - np.mean(residual)
    centered_response = response - np.mean(response)
    slope = float((centered_response @ centered_residual)
                  / (centered_response @ centered_response))
    return (event["storm_id"], int(event["t0_time_us"]), len(residual),
            float(np.median(residual)), float(np.quantile(residual, 0.25)),
            float(np.quantile(residual, 0.75)), float(np.mean(residual > 0)),
            float(np.sqrt(np.mean(residual ** 2))),
            float(np.corrcoef(response, residual)[0, 1]), slope, VERSION)


def save_sqlite(events: list[dict]) -> None:
    """Input: [25 event arrays]. Output: independent residual and summary SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="m2_residual_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            with database:
                database.execute("""
                    CREATE TABLE phase3_m2_residual_minute (
                        storm_id TEXT NOT NULL,
                        time_us INTEGER NOT NULL,
                        rho_l2_phase_kg_m3 REAL NOT NULL,
                        rho_m0_aligned_phase_kg_m3 REAL NOT NULL,
                        h_tau465_phase_nt REAL NOT NULL,
                        residual_log_density REAL NOT NULL,
                        algorithm_version TEXT NOT NULL,
                        PRIMARY KEY (storm_id,time_us)
                    )
                """)
                database.execute("""
                    CREATE TABLE phase3_m2_residual_storm (
                        storm_id TEXT PRIMARY KEY,
                        t0_time_us INTEGER NOT NULL,
                        valid_minutes INTEGER NOT NULL,
                        median_residual_log_density REAL NOT NULL,
                        q1_residual_log_density REAL NOT NULL,
                        q3_residual_log_density REAL NOT NULL,
                        positive_residual_fraction REAL NOT NULL,
                        m0_rmse_log_density REAL NOT NULL,
                        correlation_with_h REAL NOT NULL,
                        centered_slope_per_nt REAL NOT NULL,
                        algorithm_version TEXT NOT NULL
                    )
                """)
                for event in events:
                    database.executemany(
                        "INSERT INTO phase3_m2_residual_minute VALUES (?,?,?,?,?,?,?)",
                        ((event["storm_id"], int(time), float(l2), float(m0),
                          float(h), float(residual), VERSION)
                         for time, l2, m0, h, residual in zip(
                             event["times"], event["l2"], event["m0"],
                             event["h"], event["residual"], strict=True)),
                    )
                    database.execute("INSERT INTO phase3_m2_residual_storm "
                                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)", summarize(event))
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("M2 diagnostic SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def draw_boundary_events(events: list[dict]) -> None:
    """Input: [25 event arrays]. Output: residual and SME-response diagnostic PNG."""
    selected = {event["storm_id"]: event for event in events}
    figure, axes = plt.subplots(len(BOUNDARY_STORMS), 2, figsize=(13, 15),
                                sharex=True, constrained_layout=True)
    for row, storm_id in enumerate(BOUNDARY_STORMS):
        event = selected[storm_id]
        days = (event["times"] - event["t0_time_us"]) / 86_400_000_000
        for column, values, color in (
            (0, event["residual"], "#2563eb"),
            (1, event["h"], "#b45309"),
        ):
            axis = axes[row, column]
            axis.plot(days[::5], values[::5], color=color, linewidth=0.8)
            axis.axhline(0, color="#475569", linewidth=0.8)
            axis.axvline(0, color="#64748b", linestyle="--", linewidth=0.8)
            axis.grid(alpha=0.2)
            axis.set_ylabel(storm_id[1:9])
    axes[0, 0].set_title("ln(L2 / full MSIS with aligned Ap)")
    axes[0, 1].set_title("SME response H at tau = 4.65 h (nT)")
    for axis in axes[-1]:
        axis.set_xlabel("Days relative to SYM-H minimum")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=170)
    plt.close(figure)


def main() -> None:
    """Input: frozen Phase 3 derived data. Output: M2 diagnostic SQLite and PNG."""
    if OUTPUT.exists() or FIGURE.exists():
        raise FileExistsError("M2 diagnostic output already exists")
    events = load_events()
    save_sqlite(events)
    draw_boundary_events(events)
    print(f"Saved M2 residuals for {len(events)} events")


if __name__ == "__main__":
    main()
