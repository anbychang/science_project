"""Refine the shared response time near the coarse-grid minimum."""

import sqlite3
from pathlib import Path

import numpy as np

from calc_phase4_v2_fit import fit_shared_tau, response_at_tau
from load_phase4_v2_inputs import load_density_rows, load_phase_events


OUTPUT = Path("phases/phase4-v2/data/sqlite/shared_tau_fine_v1.sqlite")
FINE_TAU_HOURS = np.arange(460, 491) / 100


def fit_fine_grid() -> list[tuple[float, float, float]]:
    """Input: frozen Phase 2/3 SQLite. Output: [(tau h, G 1/nT, log RMSE), ...]."""
    density_by_storm = load_density_rows()
    sme, phase_events = load_phase_events(list(density_by_storm))
    results = []
    for tau_hours in FINE_TAU_HOURS:
        responses = response_at_tau(sme, phase_events, density_by_storm, float(tau_hours))
        _, gain, rmse = fit_shared_tau(density_by_storm, responses)
        results.append((float(tau_hours), gain, rmse))
    return results


def main() -> None:
    """Input: frozen Phase 2/3 SQLite. Output: new SQLite fine shared-tau grid."""
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
