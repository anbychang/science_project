"""Refit event offsets and one gain for every shared response time."""

import sqlite3
from pathlib import Path

import numpy as np

from calc_phase4_v2_fit import fit_shared_tau, response_at_tau
from load_phase4_v2_inputs import load_density_rows, load_phase_events


OUTPUT = Path("phases/phase4-v2/data/sqlite/shared_tau_grid_v1.sqlite")


def fit_shared_tau_grid() -> list[tuple[float, float, float]]:
    """Input: frozen Phase 2/3 SQLite. Output: [(tau h, G 1/nT, log RMSE), ...]."""
    density = load_density_rows()
    sme, phase_events = load_phase_events(list(density))
    results = []
    for tau_hours in np.arange(151) / 10:
        responses = response_at_tau(sme, phase_events, density, float(tau_hours))
        _, gain, rmse = fit_shared_tau(density, responses)
        results.append((float(tau_hours), gain, rmse))
    return results


def main() -> None:
    """Input: frozen Phase 2/3 SQLite. Output: new SQLite grid and best fit."""
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
