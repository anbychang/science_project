"""Summarize all 25 retrospective Phase 3 storm predictions."""

import csv
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from satellite_orbit.phase3.prep_h_tau_phase import SOURCE
from satellite_orbit.phase3.prep_prediction_tau465 import OUTPUT as PREDICTIONS


PREDICTION_REPORT = Path("output/report/phase3_prediction_tau465_exploratory.csv")
QUIET_REPORT = Path("output/report/phase3_rquiet_near_zero_25.csv")
FIGURE = Path("output/image/Phase3/prediction_tau465_25storm_overview.png")


def read_csv_by_storm(path: Path) -> dict[str, dict]:
    """Input: storm-keyed CSV path. Output: {storm_id: row}."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    result = {row["storm_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate storm ID in {path}")
    return result


def prepare_rows() -> list[dict]:
    """Input: event metadata and Phase 3 CSVs. Output: 25 joined storm records."""
    predictions = read_csv_by_storm(PREDICTION_REPORT)
    quiet = read_csv_by_storm(QUIET_REPORT)
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        events = database.execute("""
            SELECT storm_id,t0_time_us,symh_min_nt
            FROM storm_event_t0_phase_v5 ORDER BY t0_time_us
        """).fetchall()
    if len(events) != 25 or set(predictions) != {row[0] for row in events} or (
        set(quiet) != set(predictions)
    ):
        raise ValueError("The 25 source, prediction and R event IDs differ.")
    rows = []
    for storm_id, t0_us, symh_min_nt in events:
        forecast = predictions[storm_id]
        calibration = quiet[storm_id]
        rows.append({
            "storm_id": storm_id,
            "t0_time_us": t0_us,
            "symh_min_nt": symh_min_nt,
            "valid_phase_minutes": int(forecast["valid_minutes"]),
            "tau_hours": float(forecast["tau_hours"]),
            "r_candidate": float(forecast["r_candidate"]),
            "r_pre_distance_days": float(
                calibration["distance_before_first_minimum_days"]),
            "r_candidate_status": calibration["status"],
            "gain_excluding_this_storm_per_nt": float(
                forecast["gain_held_out_per_nt"]),
            "m1_excluding_this_storm_g_rmse_log_density": float(
                forecast["m1_held_out_rmse_log_density"]),
            "m0_uncalibrated_rmse_log_density": float(
                forecast["full_rmse_log_density"]),
            "algorithm_version": "phase3_25storm_overview_v1",
        })
    return rows


def save_overview(rows: list[dict]) -> None:
    """Input: 25 storm records. Output: versioned table in Phase 3 SQLite."""
    with closing(sqlite3.connect(PREDICTIONS)) as database:
        exists = database.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='phase3_25storm_overview'
        """).fetchone()
        if exists:
            raise FileExistsError("phase3_25storm_overview already exists.")
        with database:
            database.execute("""
                CREATE TABLE phase3_25storm_overview (
                    storm_id TEXT PRIMARY KEY,
                    t0_time_us INTEGER NOT NULL UNIQUE,
                    symh_min_nt INTEGER NOT NULL,
                    valid_phase_minutes INTEGER NOT NULL,
                    tau_hours REAL NOT NULL,
                    r_candidate REAL NOT NULL,
                    r_pre_distance_days REAL NOT NULL,
                    r_candidate_status TEXT NOT NULL,
                    gain_excluding_this_storm_per_nt REAL NOT NULL,
                    m1_excluding_this_storm_g_rmse_log_density REAL NOT NULL,
                    m0_uncalibrated_rmse_log_density REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                )
            """)
            database.executemany(
                "INSERT INTO phase3_25storm_overview VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (tuple(row.values()) for row in rows),
            )
            count, total_minutes = database.execute("""
                SELECT count(*),sum(valid_phase_minutes)
                FROM phase3_25storm_overview
            """).fetchone()
            predicted_minutes = database.execute(
                "SELECT count(*) FROM phase3_prediction_minute").fetchone()[0]
            mismatched = database.execute("""
                SELECT count(*) FROM phase3_25storm_overview AS storm
                WHERE storm.valid_phase_minutes <> (
                    SELECT count(*) FROM phase3_prediction_minute AS minute
                    WHERE minute.storm_id=storm.storm_id
                )
            """).fetchone()[0]
            if (count != 25 or total_minutes != predicted_minutes or mismatched
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Phase 3 storm overview failed its key audit.")


def draw_overview(rows: list[dict]) -> None:
    """Input: 25 storm records and prediction table. Output: 5x5 PNG."""
    uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                                     constrained_layout=True)
    with closing(sqlite3.connect(uri, uri=True)) as database:
        for axis, storm in zip(axes.flat, rows, strict=True):
            minute_rows = database.execute("""
                SELECT time_us,rho_l2_phase_kg_m3,
                       rho_msis_full_phase_kg_m3,rho_m1_held_out_phase_kg_m3
                FROM phase3_prediction_minute
                WHERE storm_id=? ORDER BY time_us
            """, (storm["storm_id"],)).fetchall()
            if len(minute_rows) != storm["valid_phase_minutes"]:
                raise ValueError(f"Prediction row count differs: {storm['storm_id']}")
            t0_us = storm["t0_time_us"]
            selected = minute_rows[::30]
            relative_days = [(row[0] - t0_us) / 86_400_000_000
                             for row in selected]
            for index, label, color in (
                (1, "Swarm L2", "#111827"),
                (2, "M0 raw", "#64748b"),
                (3, "M1 fixed tau", "#2563eb"),
            ):
                axis.plot(relative_days, [row[index] * 1e12 for row in selected],
                          linewidth=0.9, color=color, label=label)
            axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
            axis.set_title(f"{storm['storm_id'][1:9]}  "
                           f"SYM-H {storm['symh_min_nt']} nT", fontsize=9)
            axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("Density (1e-12 kg/m3)")
    figure.suptitle("25 storms: L2 (black), M0 raw (gray), M1 (blue)",
                    fontsize=13)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: 25 event predictions. Output: SQLite summary and curve PNG."""
    rows = prepare_rows()
    save_overview(rows)
    draw_overview(rows)
    print(f"Saved {len(rows)} SQLite storm rows and one 25-panel overview")


if __name__ == "__main__":
    main()
