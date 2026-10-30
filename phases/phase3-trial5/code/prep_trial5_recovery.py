"""Write Trial5 recovery-fit analysis, SQLite, and residual overview figure."""

import csv
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from calc_trial5_recovery import RecoveryEvent, RecoveryFit, fit_recovery_grid, recovery_shape


SOURCE = Path("phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
OUTPUT = Path("phases/phase3-trial5/data/sqlite/swarm_a_trial5_recovery_v1.sqlite")
MODEL_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_models.csv")
GRID_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_grid_01h.csv")
EVENT_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_events.csv")
FIGURE = Path("phases/phase3-trial5/figures/trial5_recovery_25storm_residuals.png")
ALGORITHM_VERSION = "trial5_recovery_v1"
EXPECTED_STORM_COUNT = 25
EXPECTED_MINUTE_COUNT = 214_907
MICROSECONDS_PER_HOUR = 3_600_000_000
MICROSECONDS_PER_DAY = 86_400_000_000
PLOT_STEP_MINUTES = 30


@dataclass(frozen=True)
class Trial4Event:
    """Input: Trial4 minute rows for one storm. Output: fixed-baseline recovery input."""

    recovery_event: RecoveryEvent
    time_us: np.ndarray
    rho_l2_phase_kg_m3: np.ndarray
    rho_msis_quiet_phase_kg_m3: np.ndarray
    rho_msis_full_phase_kg_m3: np.ndarray
    rho_trial4_joint_phase_kg_m3: np.ndarray
    r_fit: float
    tau_hours: float
    t0_time_us: int
    symh_min_nt: int


@dataclass(frozen=True)
class RecoveryOutputEvent:
    """Input: fixed Trial4 event and Trial5 fit. Output: Trial5 event output arrays."""

    trial4_event: Trial4Event
    recovery_amplitude: float
    recovery_term_log_density: np.ndarray
    trial5_residual_log_density: np.ndarray
    rho_trial5_recovery_phase_kg_m3: np.ndarray


def read_trial4_events() -> list[Trial4Event]:
    """Input: read-only Trial4 SQLite. Output: [aligned events with fixed residuals]."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    grouped: dict[str, list[tuple]] = {}
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT minute.storm_id,minute.time_us,overview.t0_time_us,
                   overview.symh_min_nt,minute.residual_log_density,
                   minute.rho_l2_phase_kg_m3,
                   minute.rho_msis_quiet_phase_kg_m3,
                   minute.rho_msis_full_phase_kg_m3,
                   minute.rho_trial4_joint_phase_kg_m3,
                   minute.r_fit,minute.tau_hours
            FROM trial4_joint_fit_minute AS minute
            JOIN trial4_25storm_overview AS overview
              ON overview.storm_id=minute.storm_id
            ORDER BY overview.t0_time_us,minute.time_us
        """).fetchall()
    for row in rows:
        grouped.setdefault(row[0], []).append(row[1:])
    if len(grouped) != EXPECTED_STORM_COUNT or len(rows) != EXPECTED_MINUTE_COUNT:
        raise ValueError("Trial4 input does not contain its full 25-storm minute set.")
    events = []
    for storm_id, storm_rows in grouped.items():
        time_us = np.array([row[0] for row in storm_rows], dtype=np.int64)
        t0_time_us = int(storm_rows[0][1])
        residual = np.array([row[3] for row in storm_rows], dtype=float)
        arrays = [
            np.array([row[index] for row in storm_rows], dtype=float)
            for index in range(4, 8)
        ]
        r_fit = float(storm_rows[0][8])
        tau_hours = float(storm_rows[0][9])
        if (not np.isfinite(residual).all() or any(not np.isfinite(values).all()
                or np.any(values <= 0) for values in arrays)
                or r_fit <= 0 or r_fit >= 2 or tau_hours < 0 or tau_hours > 15):
            raise ValueError(f"Invalid Trial4 recovery input: {storm_id}")
        events.append(Trial4Event(
            recovery_event=RecoveryEvent(
                storm_id=storm_id,
                hours_from_t0=(time_us - t0_time_us) / MICROSECONDS_PER_HOUR,
                trial4_residual_log_density=residual,
            ),
            time_us=time_us,
            rho_l2_phase_kg_m3=arrays[0],
            rho_msis_quiet_phase_kg_m3=arrays[1],
            rho_msis_full_phase_kg_m3=arrays[2],
            rho_trial4_joint_phase_kg_m3=arrays[3],
            r_fit=r_fit,
            tau_hours=tau_hours,
            t0_time_us=t0_time_us,
            symh_min_nt=int(storm_rows[0][2]),
        ))
    return events


def baseline_event_equal_mse(events: list[Trial4Event]) -> float:
    """Input: [fixed Trial4 events]. Output: equal-weight Trial4 residual MSE."""
    return float(np.mean([
        np.mean(event.recovery_event.trial4_residual_log_density ** 2)
        for event in events
    ]))


def build_output_events(events: list[Trial4Event], fit: RecoveryFit) -> list[RecoveryOutputEvent]:
    """Input: [Trial4 events], final recovery fit. Output: [Trial5 prediction arrays]."""
    output_events = []
    for event in events:
        recovery_event = event.recovery_event
        amplitude = fit.amplitude_by_storm[recovery_event.storm_id]
        recovery_term = amplitude * recovery_shape(
            recovery_event.hours_from_t0, fit.recovery_time_hours
        )
        residual = recovery_event.trial4_residual_log_density - recovery_term
        prediction = event.rho_trial4_joint_phase_kg_m3 * np.exp(recovery_term)
        if not np.isfinite(prediction).all() or np.any(prediction <= 0):
            raise ValueError(f"Invalid Trial5 prediction: {recovery_event.storm_id}")
        output_events.append(RecoveryOutputEvent(
            trial4_event=event,
            recovery_amplitude=amplitude,
            recovery_term_log_density=recovery_term,
            trial5_residual_log_density=residual,
            rho_trial5_recovery_phase_kg_m3=prediction,
        ))
    return output_events


def event_row(event: RecoveryOutputEvent, fit: RecoveryFit) -> dict:
    """Input: one Trial5 event output and fit. Output: one analysis CSV row."""
    trial4_residual = event.trial4_event.recovery_event.trial4_residual_log_density
    return {
        "storm_id": event.trial4_event.recovery_event.storm_id,
        "t0_time_us": event.trial4_event.t0_time_us,
        "symh_min_nt": event.trial4_event.symh_min_nt,
        "valid_phase_minutes": len(event.trial4_event.time_us),
        "r_fit": event.trial4_event.r_fit,
        "tau_hours": event.trial4_event.tau_hours,
        "recovery_amplitude_log_density": event.recovery_amplitude,
        "recovery_time_hours": fit.recovery_time_hours,
        "trial4_rmse_log_density": float(np.sqrt(np.mean(trial4_residual ** 2))),
        "trial5_rmse_log_density": float(np.sqrt(np.mean(
            event.trial5_residual_log_density ** 2
        ))),
        "algorithm_version": ALGORITHM_VERSION,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    """Input: [{field: value}], new CSV path. Output: saved Trial5 analysis CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def create_output_schema(database: sqlite3.Connection) -> None:
    """Input: empty SQLite connection. Output: Trial5 recovery output tables."""
    database.executescript("""
        CREATE TABLE trial5_recovery_minute (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            hours_from_t0 REAL NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL,
            rho_msis_quiet_phase_kg_m3 REAL NOT NULL,
            rho_msis_full_phase_kg_m3 REAL NOT NULL,
            rho_trial4_joint_phase_kg_m3 REAL NOT NULL,
            recovery_term_log_density REAL NOT NULL,
            rho_trial5_recovery_phase_kg_m3 REAL NOT NULL,
            trial4_residual_log_density REAL NOT NULL,
            trial5_residual_log_density REAL NOT NULL,
            recovery_amplitude_log_density REAL NOT NULL,
            recovery_time_hours REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE trial5_25storm_recovery_overview (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL UNIQUE,
            symh_min_nt INTEGER NOT NULL,
            valid_phase_minutes INTEGER NOT NULL,
            r_fit REAL NOT NULL,
            tau_hours REAL NOT NULL,
            recovery_amplitude_log_density REAL NOT NULL,
            recovery_time_hours REAL NOT NULL,
            trial4_rmse_log_density REAL NOT NULL,
            trial5_rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE trial5_recovery_metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_sqlite(events: list[RecoveryOutputEvent], fit: RecoveryFit) -> None:
    """Input: [Trial5 events], final fit. Output: atomic Trial5 recovery SQLite."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="trial5_recovery.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            create_output_schema(database)
            database.executemany(
                "INSERT INTO trial5_recovery_metadata VALUES (?,?)",
                (
                    ("source", "Trial4 joint-fit SQLite; read-only"),
                    ("recovery_model", "A_k*exp[-(t-t0)/T] for t>=t0; A_k>=0"),
                    ("recovery_time_hours", str(fit.recovery_time_hours)),
                    ("evaluation", "retrospective; event-equal loss; fixed Trial4 R,tau,G"),
                ),
            )
            for event in events:
                trial4 = event.trial4_event
                values = zip(
                    trial4.time_us, trial4.recovery_event.hours_from_t0,
                    trial4.rho_l2_phase_kg_m3, trial4.rho_msis_quiet_phase_kg_m3,
                    trial4.rho_msis_full_phase_kg_m3,
                    trial4.rho_trial4_joint_phase_kg_m3,
                    event.recovery_term_log_density,
                    event.rho_trial5_recovery_phase_kg_m3,
                    trial4.recovery_event.trial4_residual_log_density,
                    event.trial5_residual_log_density, strict=True
                )
                database.executemany(
                    "INSERT INTO trial5_recovery_minute VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ((trial4.recovery_event.storm_id, int(time_us), *(float(value) for value in row),
                      event.recovery_amplitude, fit.recovery_time_hours,
                      ALGORITHM_VERSION)
                     for time_us, *row in values),
                )
            overview_rows = [event_row(event, fit) for event in events]
            database.executemany(
                "INSERT INTO trial5_25storm_recovery_overview VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ((row["storm_id"], row["t0_time_us"], row["symh_min_nt"],
                  row["valid_phase_minutes"], row["r_fit"], row["tau_hours"],
                  row["recovery_amplitude_log_density"], row["recovery_time_hours"],
                  row["trial4_rmse_log_density"], row["trial5_rmse_log_density"],
                  ALGORITHM_VERSION)
                 for row in overview_rows),
            )
            database.commit()
            validate_saved_sqlite(database)
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def validate_saved_sqlite(database: sqlite3.Connection) -> None:
    """Input: open Trial5 SQLite. Output: raises unless counts and bounds are valid."""
    minute_count = database.execute(
        "SELECT count(*) FROM trial5_recovery_minute"
    ).fetchone()[0]
    storm_count, overview_minutes = database.execute("""
        SELECT count(*),sum(valid_phase_minutes) FROM trial5_25storm_recovery_overview
    """).fetchone()
    invalid_count = database.execute("""
        SELECT count(*) FROM trial5_recovery_minute
        WHERE recovery_amplitude_log_density < 0 OR recovery_time_hours <= 0
    """).fetchone()[0]
    if (minute_count != EXPECTED_MINUTE_COUNT or storm_count != EXPECTED_STORM_COUNT
            or overview_minutes != minute_count or invalid_count
            or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
        raise ValueError("Trial5 recovery SQLite failed its output audit.")


def draw_residual_overview(events: list[RecoveryOutputEvent], fit: RecoveryFit) -> None:
    """Input: [Trial5 events], final fit. Output: 25-panel residual PNG."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                                constrained_layout=True)
    for axis, event in zip(axes.flat, events, strict=True):
        trial4 = event.trial4_event
        selected = slice(None, None, PLOT_STEP_MINUTES)
        days_from_t0 = (trial4.time_us - trial4.t0_time_us) / MICROSECONDS_PER_DAY
        axis.plot(days_from_t0[selected],
                  trial4.recovery_event.trial4_residual_log_density[selected],
                  color="#111827", linewidth=0.8, label="Trial4 residual")
        axis.plot(days_from_t0[selected], event.trial5_residual_log_density[selected],
                  color="#2563eb", linewidth=0.8, label="Trial5 residual")
        axis.axhline(0, color="#9ca3af", linewidth=0.6)
        axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
        axis.set_title(
            f"{trial4.recovery_event.storm_id[1:9]}  A={event.recovery_amplitude:.2f}",
            fontsize=8,
        )
        axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("log residual")
    figure.suptitle(
        f"Trial5 recovery: Trial4 (black), A exp(-t/{fit.recovery_time_hours:.1f} h) corrected (blue)",
        fontsize=13,
    )
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def ensure_outputs_are_new() -> None:
    """Input: planned Trial5 paths. Output: raises before any output overwrite."""
    outputs = (OUTPUT, MODEL_REPORT, GRID_REPORT, EVENT_REPORT, FIGURE)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite Trial5 outputs: {existing}")


def main() -> None:
    """Input: Trial4 SQLite. Output: Trial5 recovery analysis, SQLite, and figure."""
    ensure_outputs_are_new()
    events = read_trial4_events()
    recovery_events = [event.recovery_event for event in events]
    fits = fit_recovery_grid(recovery_events)
    best_fit = min(fits, key=lambda fit: fit.event_equal_mse_log_density)
    output_events = build_output_events(events, best_fit)
    baseline_mse = baseline_event_equal_mse(events)
    model_rows = [
        {
            "model": "D_trial4_baseline",
            "recovery_time_hours": "",
            "event_equal_mse_log_density": baseline_mse,
            "event_equal_rmse_log_density": math.sqrt(baseline_mse),
        },
        {
            "model": "E_trial5_recovery",
            "recovery_time_hours": best_fit.recovery_time_hours,
            "event_equal_mse_log_density": best_fit.event_equal_mse_log_density,
            "event_equal_rmse_log_density": math.sqrt(best_fit.event_equal_mse_log_density),
        },
    ]
    grid_rows = [
        {
            "recovery_time_hours": fit.recovery_time_hours,
            "event_equal_mse_log_density": fit.event_equal_mse_log_density,
            "event_equal_rmse_log_density": math.sqrt(fit.event_equal_mse_log_density),
        }
        for fit in fits
    ]
    write_csv(model_rows, MODEL_REPORT)
    write_csv(grid_rows, GRID_REPORT)
    write_csv([event_row(event, best_fit) for event in output_events], EVENT_REPORT)
    write_sqlite(output_events, best_fit)
    draw_residual_overview(output_events, best_fit)
    print(f"Saved Trial5 recovery fit: T={best_fit.recovery_time_hours:.1f} h, "
          f"RMSE={math.sqrt(best_fit.event_equal_mse_log_density):.6f}")


if __name__ == "__main__":
    main()
