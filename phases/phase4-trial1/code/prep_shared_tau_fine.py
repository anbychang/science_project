"""Refine the shared response time near the coarse-grid minimum."""

import sqlite3
import sys
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import numpy as np

PHASE4_CODE = Path(__file__).resolve().parents[2] / "phase4/code"
sys.path.insert(0, str(PHASE4_CODE))

from calc_h_tau import filtered_sme, phase_weighted_mean
from calc_trial4_joint_fit import FitState, model_score, update_offsets_and_gain
from prep_h_tau_phase import SOURCE, load_event, load_sme
from prep_trial4_joint_fit import SME_REFERENCE_NT, load_density_rows, load_initial_gain, prepare_events


OUTPUT = Path("phases/phase4-trial1/data/sqlite/shared_tau_fine_v1.sqlite")
FINE_TAU_HOURS = np.arange(460, 491) / 100


def fit_fine_grid() -> list[tuple[float, float, float]]:
    """Input: Phase 4 read-only snapshots. Output: [(tau h, G 1/nT, log RMSE), ...]."""
    density_by_storm = load_density_rows()
    events = prepare_events(density_by_storm)
    with closing(sqlite3.connect(f"file:{SOURCE.resolve().as_posix()}?mode=ro", uri=True)) as database:
        sme, first_time_us = load_sme(database)
        phase_events = [load_event(database, event.storm_id, first_time_us) for event in events]
    initial_offsets = np.log([event.r_rq for event in events])
    initial_gain = load_initial_gain()
    results = []
    for tau_hours in FINE_TAU_HOURS:
        response = filtered_sme(sme, float(tau_hours)) - SME_REFERENCE_NT
        fine_events = []
        for event, phase_event in zip(events, phase_events, strict=True):
            support = phase_event["support"]
            phase_response = phase_weighted_mean(
                response[phase_event["minute_index"]], phase_event["pair_count"], support
            )[support["valid"]]
            if len(phase_response) != len(event.log_density_anomaly):
                raise ValueError(f"Response length changed for {event.storm_id}")
            fine_events.append(replace(event, h_tau_grid_nt=phase_response[np.newaxis, :]))
        state = FitState(initial_offsets, np.zeros(len(events), dtype=np.int16), initial_gain)
        fitted = update_offsets_and_gain(fine_events, state)
        results.append((float(tau_hours), fitted.gain_per_nt,
                        model_score(fine_events, fitted)["event_equal_rmse_log_density"]))
    return results


def main() -> None:
    """Input: Phase 4 read-only snapshots. Output: new SQLite fine shared-tau grid."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    results = fit_fine_grid()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.execute("""CREATE TABLE shared_tau_fine (
            tau_hours REAL PRIMARY KEY,
            gain_per_nt REAL NOT NULL,
            event_equal_rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        )""")
        database.executemany("INSERT INTO shared_tau_fine VALUES (?,?,?,?)",
                             ((tau, gain, rmse, "shared_tau_fine_v1")
                              for tau, gain, rmse in results))
    best = min(results, key=lambda result: result[2])
    print(f"best shared tau={best[0]:.2f} h, RMSE={best[2]:.9f}, G={best[1]:.9f}")


if __name__ == "__main__":
    main()
