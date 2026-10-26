"""Fit each storm separately on the existing exploratory 0.25-hour grid."""

import csv
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from satellite_orbit.phase3.prep_exploratory_fit import (
    load_fit_arrays, load_r_candidates, fit_grid,
)
from satellite_orbit.phase3.prep_h_tau_phase import SOURCE


REPORT = Path("output/report/phase3_event_tau_exploratory.csv")
FIGURE = Path("output/image/Phase3/tau_vs_symh_exploratory.png")
MAX_TAU_HOURS = 10.0
UNCERTAIN_WIDTH_HOURS = 4.0


def summarize_grid(grid: list[dict]) -> dict:
    """Input: one event's 41 fit rows. Output: best fit and uncertainty flags."""
    best = min(grid, key=lambda row: row["train_rmse_log_density"])
    supported = [row["tau_hours"] for row in grid
                 if row["train_rmse_log_density"]
                 <= 1.05 * best["train_rmse_log_density"]]
    lower = min(supported)
    upper = max(supported)
    at_boundary = best["tau_hours"] in (0.0, MAX_TAU_HOURS)
    broad = upper - lower > UNCERTAIN_WIDTH_HOURS
    positive_gain = best["gain_per_nt"] > 0
    return {
        "tau_hours": best["tau_hours"],
        "gain_per_nt": best["gain_per_nt"],
        "rmse_log_density": best["train_rmse_log_density"],
        "tau_5pct_lower_hours": lower,
        "tau_5pct_upper_hours": upper,
        "tau_5pct_width_hours": upper - lower,
        "at_grid_boundary": at_boundary,
        "broad_5pct_range": broad,
        "positive_gain": positive_gain,
        "trend_eligible": not at_boundary and not broad and positive_gain,
    }


def load_storm_strength() -> dict[str, int]:
    """Input: frozen Phase 2 event table. Output: {storm: SYM-H minimum in nT}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        return dict(database.execute(
            "SELECT storm_id,symh_min_nt FROM storm_event_t0_phase_v5"))


def fit_events() -> list[dict]:
    """Input: aligned Phase 3 data and provisional R. Output: 25 event fit rows."""
    z, h, event_index, identifiers = load_fit_arrays(load_r_candidates())
    symh_by_storm = load_storm_strength()
    rows = []
    for index, storm_id in enumerate(identifiers):
        selected = event_index == index
        fit = summarize_grid(fit_grid(z[selected], h[selected]))
        rows.append({"storm_id": storm_id,
                     "symh_min_nt": symh_by_storm[storm_id],
                     "fit_minutes": int(np.count_nonzero(selected)),
                     **fit, "status": "provisional_R_exploratory"})
    return rows


def draw_comparison(rows: list[dict]) -> None:
    """Input: 25 event fit rows. Output: exploratory SYM-H comparison PNG."""
    figure, axis = plt.subplots(figsize=(9, 5), constrained_layout=True)
    groups = (
        ("trend_eligible", "Within grid and narrow", "#2563eb", "o"),
        ("at_grid_boundary", "Best at 10 h boundary", "#64748b", "x"),
        ("broad_5pct_range", "Wide 5% range", "#d97706", "s"),
    )
    for field, label, color, marker in groups:
        selected = [row for row in rows if row[field]
                    and (field != "broad_5pct_range"
                         or not row["at_grid_boundary"])]
        if not selected:
            continue
        strength = [-row["symh_min_nt"] for row in selected]
        tau = [row["tau_hours"] for row in selected]
        lower = [row["tau_hours"] - row["tau_5pct_lower_hours"]
                 for row in selected]
        upper = [row["tau_5pct_upper_hours"] - row["tau_hours"]
                 for row in selected]
        axis.errorbar(strength, tau, yerr=[lower, upper], fmt=marker,
                      color=color, capsize=2, label=f"{label} (n={len(selected)})")
    axis.set(xlabel="Storm strength: -minimum SYM-H (nT)",
             ylabel="Event-specific tau (hours)", ylim=(-0.5, 10.5),
             title="Exploratory event fits: provisional R")
    axis.grid(alpha=0.25)
    axis.legend()
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: Phase 3 paired tables and Phase 2 event minima. Output: CSV and PNG."""
    if REPORT.exists() or FIGURE.exists():
        raise FileExistsError("Event-specific exploratory output already exists.")
    rows = fit_events()
    with REPORT.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    draw_comparison(rows)
    eligible = [row for row in rows if row["trend_eligible"]]
    correlation = spearmanr([-row["symh_min_nt"] for row in eligible],
                            [row["tau_hours"] for row in eligible])
    print(f"Events: {len(rows)}; 10-hour boundary: "
          f"{sum(row['at_grid_boundary'] for row in rows)}; "
          f"wide 5% range: {sum(row['broad_5pct_range'] for row in rows)}; "
          f"trend eligible: {len(eligible)}; "
          f"eligible Spearman rho: {correlation.statistic:.3f}")


if __name__ == "__main__":
    main()
