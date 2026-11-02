"""Plot storm-level errors against each storm's minimum SYM-H."""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from phases.phase6.code.prep_phase6_4_figures import read_only


FIGURES = Path("phases/phase6/figures")
SCORES = Path("phases/phase6/data/sqlite/swarm_a_phase6_4_orbit_scores_v1.sqlite")
STORMS = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_3_t0_phase_v5.sqlite")


def plot_orbit_errors(scores: sqlite3.Connection, storms: sqlite3.Connection) -> None:
    """Input: scored orbits and Phase 2 events. Output: storm MAE PNG."""
    symh_by_storm = dict(storms.execute(
        "SELECT storm_id, symh_min_nt FROM storm_event_t0_phase_v5"
    ).fetchall())
    rows = scores.execute(
        "SELECT storm_id, AVG(ABS(m0_error_m)) AS m0_mae, "
        "AVG(ABS(ridge_error_m)) AS ridge_mae "
        "FROM phase6_4_orbit_score_v1 GROUP BY storm_id ORDER BY storm_id"
    ).fetchall()
    missing = {row["storm_id"] for row in rows} - symh_by_storm.keys()
    if missing:
        raise ValueError(f"Storms missing Phase 2 SYM-H: {sorted(missing)}")

    x = [symh_by_storm[row["storm_id"]] for row in rows]
    figure, ax = plt.subplots(figsize=(8, 6))
    for field, label, color in (
        ("m0_mae", "M0", "#64748b"),
        ("ridge_mae", "Ridge", "#ea580c"),
    ):
        ax.scatter(x, [row[field] for row in rows], s=36, label=label, color=color)
    ax.set_title("Within-storm orbit MAE")
    ax.set_xlabel("Minimum SYM-H (nT; more negative = stronger)")
    ax.set_ylabel("Orbit MAE (m/orbit)")
    ax.grid(alpha=0.2)
    ax.legend()
    figure.tight_layout()
    figure.savefig(FIGURES / "phase6_4_symh_absolute_error.png", dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: current orbit scores and frozen Phase 2 events. Output: MAE PNG."""
    with closing(read_only(SCORES)) as scores, closing(read_only(STORMS)) as storms:
        plot_orbit_errors(scores, storms)


if __name__ == "__main__":
    main()
