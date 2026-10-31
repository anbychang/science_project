"""Draw held-out Trial4-plus-GPR predictions for five 20/5 storm folds."""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SOURCE = Path("phases/phase5-trial2/data/sqlite/swarm_a_phase4_trial4_altitude_groupcv20_5_v2.sqlite")
FIGURE = Path("phases/phase5-trial2/figures/phase4_trial4_groupcv20_5_25storm.png")
MICROSECONDS_PER_HOUR = 3_600_000_000


def load_rows() -> dict[str, list[tuple]]:
    """Input: group-CV SQLite. Output: {storm_id: held-out prediction rows}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,fold_index,rho_l2_phase_kg_m3,
                   rho_trial4_phase_kg_m3,rho_gpr_median_kg_m3,
                   rho_95_lower_kg_m3,rho_95_upper_kg_m3,altitude_phase_m
            FROM phase4_groupcv20_5_prediction ORDER BY storm_id,time_us
        """).fetchall()
    grouped: dict[str, list[tuple]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(row[1:])
    if len(grouped) != 25:
        raise ValueError("Phase 5 group-CV figure needs 25 storms.")
    return grouped


def main() -> None:
    """Input: saved held-out predictions. Output: 5x5 20/5 group-CV PNG."""
    if FIGURE.exists():
        raise FileExistsError(FIGURE)
    grouped = load_rows()
    figure, axes = plt.subplots(5, 5, figsize=(20, 16), sharex=False,
                                constrained_layout=True)
    for axis, (storm_id, rows) in zip(axes.flat, grouped.items(), strict=True):
        values = np.array(rows, dtype=float)
        hours = (values[:, 0] - values[0, 0]) / MICROSECONDS_PER_HOUR
        fold_index = int(values[0, 1])
        axis.plot(hours, values[:, 2] * 1e12, color="#111827", linewidth=0.8,
                  label="L2")
        axis.plot(hours, values[:, 3] * 1e12, color="#2563eb", linewidth=0.8,
                  label="Trial4")
        axis.plot(hours, values[:, 4] * 1e12, color="#dc2626", linewidth=0.8,
                  label="held-out GPR")
        axis.fill_between(hours, values[:, 5] * 1e12, values[:, 6] * 1e12,
                          color="#dc2626", alpha=0.12)
        altitude_axis = axis.twinx()
        altitude_axis.plot(hours, values[:, 7] / 1000, color="#059669",
                           alpha=0.45, linewidth=0.6)
        altitude_axis.set_yticks([])
        axis.set_title(f"{storm_id}  fold {fold_index}", fontsize=7)
        axis.grid(alpha=0.15)
    axes[0, 0].legend(fontsize=6, loc="upper right")
    figure.suptitle(
        "Phase 5 20/5 storm-group CV: L2, Trial4 baseline, held-out GPR; green=altitude",
        fontsize=13,
    )
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


if __name__ == "__main__":
    main()
