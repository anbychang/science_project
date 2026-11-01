"""Refit event offsets and one gain for every shared response time."""

import sqlite3
import sys
from pathlib import Path

import numpy as np

PHASE4_CODE = Path(__file__).resolve().parents[2] / "phase4/code"
sys.path.insert(0, str(PHASE4_CODE))

from calc_trial4_joint_fit import FitState, model_score, tau_grid_hours, update_offsets_and_gain
from prep_trial4_joint_fit import load_density_rows, load_initial_gain, prepare_events


OUTPUT = Path("phases/phase4-v2/data/sqlite/shared_tau_grid_v1.sqlite")


def fit_shared_tau_grid() -> list[tuple[float, float, float]]:
    """Input: Phase 4 read-only snapshots. Output: [(tau h, G 1/nT, log RMSE), ...]."""
    events = prepare_events(load_density_rows())
    initial_gain = load_initial_gain()
    initial_offsets = np.log([event.r_rq for event in events])
    results = []
    for tau_index, tau_hours in enumerate(tau_grid_hours()):
        state = FitState(initial_offsets, np.full(len(events), tau_index), initial_gain)
        fitted = update_offsets_and_gain(events, state)
        score = model_score(events, fitted)
        results.append((float(tau_hours), fitted.gain_per_nt,
                        score["event_equal_rmse_log_density"]))
    return results


def main() -> None:
    """Input: Phase 4 read-only snapshots. Output: new SQLite shared-tau grid and best fit."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    results = fit_shared_tau_grid()
    best = min(results, key=lambda result: result[2])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE shared_tau_grid (
                tau_hours REAL PRIMARY KEY,
                gain_per_nt REAL NOT NULL,
                event_equal_rmse_log_density REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
        """)
        database.executemany("INSERT INTO shared_tau_grid VALUES (?,?,?,?)",
                             ((tau, gain, rmse, "shared_tau_grid_v1")
                              for tau, gain, rmse in results))
    print(f"best shared tau={best[0]:.1f} h, RMSE={best[2]:.6f}, G={best[1]:.9f}")


if __name__ == "__main__":
    main()
