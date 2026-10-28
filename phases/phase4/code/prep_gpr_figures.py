"""Plot held-out M1 and GPR density against one-cycle L2 anchors."""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from phases.phase4.code.load_phase4_inputs import PHASE3_RESULTS


FIGURE_DIR = Path("phases/phase4/figures/gpr_loso")
OVERVIEW = Path("phases/phase4/figures/gpr_loso_25storm_overview.png")
PREDICTIONS = Path("phases/phase4/data/sqlite/swarm_a_phase4_gpr_loso_v1.sqlite")
DENSITY_SCALE = 1e12


def load_storms() -> list[dict]:
    """Input: Phase 3 t0 and Phase 4 held-out SQLite. Output: [storm plot arrays]."""
    source_uri = f"file:{PHASE3_RESULTS.resolve().as_posix()}?mode=ro"
    result_uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        t0_by_storm = dict(source.execute(
            "SELECT storm_id,t0_time_us FROM phase3_25storm_overview"))
    with closing(sqlite3.connect(result_uri, uri=True)) as result:
        rows = result.execute("""
            SELECT storm_id,time_us,rho_l2_phase_kg_m3,rho_phys_phase_kg_m3,
                   rho_gpr_median_kg_m3,rho_95_lower_kg_m3,rho_95_upper_kg_m3
            FROM phase4_gpr_prediction ORDER BY storm_id,time_us
        """).fetchall()
    storms = []
    for storm_id in sorted(t0_by_storm):
        selected = [row for row in rows if row[0] == storm_id]
        if not selected:
            raise ValueError(f"Missing held-out predictions for {storm_id}.")
        values = np.array([row[1:] for row in selected], dtype=float)
        storms.append({"storm_id": storm_id,
                       "hours": (values[:, 0] - t0_by_storm[storm_id]) / 3_600_000_000,
                       "l2": values[:, 1] * DENSITY_SCALE,
                       "m1": values[:, 2] * DENSITY_SCALE,
                       "gpr": values[:, 3] * DENSITY_SCALE,
                       "lower": values[:, 4] * DENSITY_SCALE,
                       "upper": values[:, 5] * DENSITY_SCALE})
    return storms


def draw_curves(axis: plt.Axes, storm: dict) -> None:
    """Input: plot axis and storm arrays. Output: L2/M1/GPR curves and interval."""
    axis.fill_between(storm["hours"], storm["lower"], storm["upper"],
                      color="#2563eb", alpha=0.15, label="GPR 95% interval")
    axis.plot(storm["hours"], storm["l2"], color="#374151", linewidth=1.3,
              marker=".", markersize=3, label="L2")
    axis.plot(storm["hours"], storm["m1"], color="#d97706", linewidth=1.2,
              label="M1")
    axis.plot(storm["hours"], storm["gpr"], color="#2563eb", linewidth=1.3,
              label="M1 + GPR")
    axis.axvline(0, color="#111827", linestyle="--", linewidth=0.9)
    axis.grid(alpha=0.2)


def draw_event(storm: dict) -> None:
    """Input: one held-out storm. Output: full and peak-window PNG."""
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    for axis in axes:
        draw_curves(axis, storm)
    axes[0].set(title=f"{storm['storm_id']} | held-out one-cycle anchors",
                ylabel="Density (10^-12 kg/m^3)", xlim=(-49, 98))
    axes[1].set(title="Peak neighborhood", xlabel="Hours from t0",
                ylabel="Density (10^-12 kg/m^3)", xlim=(-12, 24))
    axes[0].legend(loc="best", frameon=False)
    figure.savefig(FIGURE_DIR / f"{storm['storm_id']}_m1_gpr_l2.png", dpi=170)
    plt.close(figure)


def draw_overview(storms: list[dict]) -> None:
    """Input: 25 held-out storms. Output: 5 x 5 overview PNG."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 15), sharex=True,
                                     constrained_layout=True)
    for axis, storm in zip(axes.flat, storms):
        draw_curves(axis, storm)
        axis.set_xlim(-49, 98)
        axis.set_title(storm["storm_id"], fontsize=9)
        axis.tick_params(labelsize=7)
    figure.supxlabel("Hours from t0")
    figure.supylabel("Density (10^-12 kg/m^3)")
    figure.suptitle("Held-out one-cycle anchors: L2 (gray), M1 (orange), "
                    "M1 + GPR (blue)", fontsize=13)
    OVERVIEW.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def main() -> None:
    """Input: Phase 3/4 read-only SQLite. Output: 26 GPR comparison PNGs."""
    if not PREDICTIONS.exists():
        raise FileNotFoundError("Run Phase 4 LOSO before plotting GPR curves.")
    storms = load_storms()
    if len(storms) != 25:
        raise ValueError("Expected 25 held-out storms.")
    paths = [OVERVIEW] + [
        FIGURE_DIR / f"{storm['storm_id']}_m1_gpr_l2.png" for storm in storms
    ]
    if any(path.exists() for path in paths):
        raise FileExistsError("Phase 4 GPR figures already exist.")
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for storm in storms:
        draw_event(storm)
    draw_overview(storms)
    print(f"Saved {len(storms)} held-out storm figures and one overview")


if __name__ == "__main__":
    main()
