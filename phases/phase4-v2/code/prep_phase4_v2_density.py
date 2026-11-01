"""Build the shared-tau Phase 4 v2 density without changing v1."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from calc_phase4_v2_fit import fit_shared_tau, response_at_tau
from load_phase4_v2_inputs import load_density_rows, load_phase_events


OUTPUT = Path("phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite")
FINE_GRID = Path("phases/phase4-v2/data/sqlite/shared_tau_fine_v1.sqlite")
ALGORITHM_VERSION = "phase4_v2_shared_tau_475_v1"
EXPECTED_STORMS = 25
EXPECTED_MINUTES = 214_907


def selected_tau_hours() -> tuple[float, float]:
    """Input: completed fine-grid SQLite. Output: (best tau h, fitted log RMSE)."""
    with closing(sqlite3.connect(f"file:{FINE_GRID.resolve().as_posix()}?mode=ro", uri=True)) as database:
        count = database.execute("SELECT count(*) FROM shared_tau_fine").fetchone()[0]
        tau_hours, rmse = database.execute("""
            SELECT tau_hours,event_equal_rmse_log_density
            FROM shared_tau_fine ORDER BY event_equal_rmse_log_density LIMIT 1
        """).fetchone()
    if count != 31 or not math.isclose(tau_hours, 4.75, abs_tol=1e-12):
        raise ValueError("Fine-grid selection changed; review the v2 model decision.")
    return float(tau_hours), float(rmse)


def fitted_density() -> tuple[list[dict], list[dict], float, float]:
    """Input: frozen Phase 2/3 SQLite and selected tau. Output: minute/event rows, tau, G."""
    tau_hours, selected_rmse = selected_tau_hours()
    density_by_storm = load_density_rows()
    sme, phase_events = load_phase_events(list(density_by_storm))
    responses = response_at_tau(sme, phase_events, density_by_storm, tau_hours)
    r_values, gain, rmse = fit_shared_tau(density_by_storm, responses)
    if not math.isclose(rmse, selected_rmse, abs_tol=1e-12):
        raise ValueError("V2 minute fit does not reproduce the selected fine-grid score.")
    minute_rows = []
    event_rows = []
    for (storm_id, density), response, fitted_r in zip(
        density_by_storm.items(), responses, r_values, strict=True
    ):
        r_fit = float(fitted_r)
        predicted = density["rho_quiet"] * r_fit * np.exp(
            gain * response
        )
        residual = np.log(density["rho_l2"] / predicted)
        if not np.isfinite(predicted).all() or r_fit <= 0 or r_fit >= 2:
            raise ValueError(f"Invalid v2 fit for {storm_id}")
        event_rows.append({"storm_id": storm_id, "r_fit": r_fit,
                           "minute_count": len(predicted),
                           "rmse": float(np.sqrt(np.mean(residual * residual)))})
        minute_rows.extend({"storm_id": storm_id, "time_us": int(time_us),
                            "h_phase_nt": float(h_phase), "rho_l2": float(rho_l2),
                            "rho_quiet": float(rho_quiet), "rho_v2": float(rho_v2),
                            "residual": float(error), "r_fit": r_fit}
                           for time_us, h_phase, rho_l2, rho_quiet, rho_v2, error in zip(
                               density["time_us"], response,
                               density["rho_l2"],
                               density["rho_quiet"], predicted, residual,
                               strict=True))
    if len(event_rows) != EXPECTED_STORMS or len(minute_rows) != EXPECTED_MINUTES:
        raise ValueError("V2 event or minute count changed.")
    return minute_rows, event_rows, tau_hours, gain


def main() -> None:
    """Input: frozen Phase 2/3 SQLite and fine grid. Output: atomic Phase 4 v2 SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    minute_rows, event_rows, tau_hours, gain = fitted_density()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase4_v2_minute (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL,
                    h_phase_nt REAL NOT NULL, rho_l2_phase_kg_m3 REAL NOT NULL,
                    rho_msis_quiet_phase_kg_m3 REAL NOT NULL,
                    rho_phase4_v2_phase_kg_m3 REAL NOT NULL,
                    residual_log_density REAL NOT NULL, r_fit REAL NOT NULL,
                    tau_hours REAL NOT NULL, gain_per_nt REAL NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase4_v2_events (
                    storm_id TEXT PRIMARY KEY, r_fit REAL NOT NULL,
                    valid_phase_minutes INTEGER NOT NULL,
                    rmse_log_density REAL NOT NULL, tau_hours REAL NOT NULL,
                    gain_per_nt REAL NOT NULL, algorithm_version TEXT NOT NULL
                );
                CREATE TABLE phase4_v2_metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            database.executemany("INSERT INTO phase4_v2_minute VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 ((row["storm_id"], row["time_us"], row["h_phase_nt"],
                                   row["rho_l2"], row["rho_quiet"], row["rho_v2"],
                                   row["residual"], row["r_fit"], tau_hours, gain,
                                   ALGORITHM_VERSION) for row in minute_rows))
            database.executemany("INSERT INTO phase4_v2_events VALUES (?,?,?,?,?,?,?)",
                                 ((row["storm_id"], row["r_fit"], row["minute_count"],
                                   row["rmse"], tau_hours, gain, ALGORITHM_VERSION)
                                  for row in event_rows))
            database.executemany("INSERT INTO phase4_v2_metadata VALUES (?,?)", (
                ("selection", "shared tau 4.6..4.9 h step 0.01 h; event-equal log MSE"),
                ("source", "frozen Phase 2/3 SQLite; independent of Phase 4 v1"),
                ("status", "retrospective in-sample; not a forecast"),
            ))
            database.commit()
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Phase 4 v2 SQLite integrity check failed.")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Phase 4 v2: {len(minute_rows)} minutes, {len(event_rows)} storms, tau={tau_hours:.2f} h")


if __name__ == "__main__":
    main()
