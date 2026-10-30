"""Draw the 25-storm Phase 4 Trial4-plus-GPR retrospective overview."""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SOURCE = Path("phases/phase4/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite")
FIGURE = Path("phases/phase4/figures/phase4_trial4_altitude_gpr_25storm.png")
MICROSECONDS_PER_HOUR = 3_600_000_000


def load_rows() -> dict[str, list[tuple]]:
    """Input: Phase 4 SQLite. Output: {storm_id: ordered prediction rows}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,rho_l2_phase_kg_m3,rho_trial4_phase_kg_m3,
                   rho_gpr_median_kg_m3,rho_95_lower_kg_m3,rho_95_upper_kg_m3,
                   altitude_phase_m
            FROM phase4_trial4_gpr_prediction ORDER BY storm_id,time_us
        """).fetchall()
    grouped: dict[str, list[tuple]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(row[1:])
    if len(grouped) != 25:
        raise ValueError("Phase 4 figure needs 25 storms.")
    return grouped


def main() -> None:
    """Input: saved Phase 4 prediction SQLite. Output: 5x5 density and altitude PNG."""
    if FIGURE.exists():
        raise FileExistsError(FIGURE)
    grouped = load_rows()
    figure, axes = plt.subplots(5, 5, figsize=(20, 16), sharex=False,
                                constrained_layout=True)
    for axis, (storm_id, rows) in zip(axes.flat, grouped.items(), strict=True):
        values = np.array(rows, dtype=float)
        hours = (values[:, 0] - values[0, 0]) / MICROSECONDS_PER_HOUR
        axis.plot(hours, values[:, 1] * 1e12, color="#111827", linewidth=0.8,
                  label="L2")
        axis.plot(hours, values[:, 2] * 1e12, color="#2563eb", linewidth=0.8,
                  label="Trial4")
        axis.plot(hours, values[:, 3] * 1e12, color="#dc2626", linewidth=0.8,
                  label="Trial4+GPR")
        axis.fill_between(hours, values[:, 4] * 1e12, values[:, 5] * 1e12,
                          color="#dc2626", alpha=0.12)
        altitude_axis = axis.twinx()
        altitude_axis.plot(hours, values[:, 6] / 1000, color="#059669",
                           alpha=0.45, linewidth=0.6)
        altitude_axis.set_yticks([])
        axis.set_title(storm_id, fontsize=7)
        axis.grid(alpha=0.15)
    axes[0, 0].legend(fontsize=6, loc="upper right")
    figure.suptitle(
        "Phase 4 descriptive fit: L2, Trial4 baseline, Trial4+GPR; green=altitude",
        fontsize=13,
    )
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


if __name__ == "__main__":
    main()
