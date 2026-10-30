"""Show three Trial6 storms with their two targeted six-hour gaps."""

import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path("phases/phase4-trial6")
FEATURES = ROOT / "data/sqlite/swarm_a_trial6_day_fraction.sqlite"
ACTIVITY = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
PREDICTIONS = ROOT / "data/analysis/trial6_stress_predictions.csv"
METRICS = ROOT / "data/analysis/trial6_stress_metrics.csv"
FIGURES = ROOT / "figures"
STORMS = ("S20230805T0546", "S20240511T0214", "S20260120T1152")
HOUR_US = 3_600_000_000
DENSITY_SCALE = 1e-12
METHODS = (
    ("interpolation", "Interpolation", "#1261a0", "s"),
    ("ridge_time", "Ridge: time", "#bc6c25", "^"),
    ("ridge_time_day", "Ridge: time + day", "#7b3294", "x"),
)


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def load_case(storm_id: str, predictions: list[dict], metrics: list[dict]) -> dict:
    """Input: storm ID, [predictions], [metrics]. Output: case arrays and blocks."""
    selected = [row for row in predictions if row["storm_id"] == storm_id]
    scored = {row["selection"]: row for row in metrics if row["storm_id"] == storm_id}
    if len(scored) != 2:
        raise ValueError(f"Expected two stress blocks: {storm_id}")
    with closing(read_only(FEATURES)) as database:
        anchors = database.execute("""
            SELECT time_us,rho_l2_phase_kg_m3,rho_trial4_phase_kg_m3
            FROM trial6_anchor_feature WHERE storm_id=? ORDER BY time_us
        """, (storm_id,)).fetchall()
    with closing(read_only(ACTIVITY)) as database:
        activity = database.execute("""
            SELECT source_time_us,symh_nt FROM storm_minute_feature_v5
            WHERE storm_id=? ORDER BY source_time_us
        """, (storm_id,)).fetchall()
    if not anchors or not activity:
        raise ValueError(f"Missing case source: {storm_id}")
    t0_us = int(selected[0]["t0_time_us"])
    anchor_time = np.array([row[0] for row in anchors], dtype=np.int64)
    return {
        "storm_id": storm_id,
        "t0_us": t0_us,
        "time_us": anchor_time,
        "time_h": (anchor_time - t0_us) / HOUR_US,
        "rho_l2": np.array([row[1] for row in anchors]) / DENSITY_SCALE,
        "rho_trial4": np.array([row[2] for row in anchors]) / DENSITY_SCALE,
        "symh_time_h": (np.array([row[0] for row in activity], dtype=np.int64)
                        - t0_us) / HOUR_US,
        "symh_nt": np.array([row[1] for row in activity], dtype=float),
        "blocks": {selection: [row for row in selected if row["selection"] == selection]
                   for selection in scored},
        "metrics": scored,
    }


def draw_overview(axis: plt.Axes, case: dict) -> None:
    """Input: overview axes, case arrays. Output: full-storm lines on axes."""
    axis.plot(case["time_h"], case["rho_l2"], color="black", lw=1.4, label="Swarm-A L2")
    axis.plot(case["time_h"], case["rho_trial4"], color="#777777", lw=1.4,
              label="Trial4")
    for selection, color, label in (
        ("t0_centered", "#b9d7ea", "t0 +/- 3 h"),
        ("symh_variation_outside_t0", "#e9c9d9", "High SYM-H variation"),
    ):
        block_start = int(case["metrics"][selection]["block_start_us"])
        start_h = (block_start - case["t0_us"]) / HOUR_US
        axis.axvspan(start_h, start_h + 6, color=color, alpha=0.55, label=label)
    axis.axvline(0, color="#16634a", lw=1.0, ls="--")
    activity_axis = axis.twinx()
    activity_axis.plot(case["symh_time_h"][::15], case["symh_nt"][::15],
                       color="#16634a", lw=0.8, alpha=0.65)
    activity_axis.set_ylabel("SYM-H (nT)", color="#16634a")
    activity_axis.tick_params(axis="y", labelcolor="#16634a")
    axis.set_ylabel("Density (10^-12 kg/m^3)")
    axis.set_xlabel("Hours from t0")
    axis.set_title(f"{case['storm_id']}: full event")
    axis.grid(alpha=0.18)
    axis.legend(loc="upper left", ncol=2, fontsize=9)


def draw_gap(axis: plt.Axes, case: dict, selection: str) -> None:
    """Input: zoom axes, case arrays, selection. Output: gap comparison lines."""
    block = case["blocks"][selection]
    if not block:
        raise ValueError(f"Missing block predictions: {case['storm_id']}:{selection}")
    start_us = int(block[0]["block_start_us"])
    start_h = (start_us - case["t0_us"]) / HOUR_US
    time_h = case["time_h"]
    visible = (time_h >= start_h - 6) & (time_h <= start_h + 12)
    held = (time_h >= start_h) & (time_h < start_h + 6)
    l2_visible = np.where(visible & ~held, case["rho_l2"], np.nan)
    l2_hidden = np.where(visible & held, case["rho_l2"], np.nan)
    axis.axvspan(start_h, start_h + 6, color="#e5eaf0", alpha=0.8)
    axis.plot(time_h[visible], case["rho_trial4"][visible], color="#777777",
              lw=1.5, marker=".", label="Trial4")
    axis.plot(time_h, l2_visible, color="black", lw=1.6, marker="o", ms=3,
              label="L2 used outside gap")
    axis.plot(time_h, l2_hidden, color="black", lw=1.5, ls="--", marker="o",
              mfc="white", ms=5, label="L2 revealed for scoring")
    anchor_by_time = {int(time_us): index for index, time_us in enumerate(case["time_us"])}
    for field, label, color, marker in METHODS:
        points = sorted(block, key=lambda row: int(row["time_us"]))
        x = [(int(row["time_us"]) - case["t0_us"]) / HOUR_US for row in points]
        y = [case["rho_trial4"][anchor_by_time[int(row["time_us"])]]
             * math.exp(float(row[field])) for row in points]
        axis.plot(x, y, color=color, lw=1.7, marker=marker, ms=5, label=label)
    label = "t0 +/- 3 h" if selection == "t0_centered" else "High SYM-H variation"
    metric = case["metrics"][selection]
    axis.set_title(f"{label}  |  RMSE: interp {float(metric['interpolation_rmse']):.3f}, "
                   f"Ridge {float(metric['ridge_time_rmse']):.3f}")
    axis.set_xlim(start_h - 6, start_h + 12)
    axis.set_xlabel("Hours from t0")
    axis.grid(alpha=0.2)


def draw_case(case: dict) -> Path:
    """Input: one case with two blocks. Output: saved PNG path."""
    figure = plt.figure(figsize=(15, 10))
    grid = figure.add_gridspec(2, 2, height_ratios=(1, 1.15), hspace=0.34, wspace=0.24)
    overview = figure.add_subplot(grid[0, :])
    left = figure.add_subplot(grid[1, 0])
    right = figure.add_subplot(grid[1, 1])
    draw_overview(overview, case)
    draw_gap(left, case, "t0_centered")
    draw_gap(right, case, "symh_variation_outside_t0")
    left.set_ylabel("Density (10^-12 kg/m^3)")
    right.set_ylabel("Density (10^-12 kg/m^3)")
    handles, labels = left.get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3, frameon=False,
                  bbox_to_anchor=(0.5, 0.055), fontsize=10)
    figure.text(0.5, 0.014,
                "Dashed L2 inside each shaded gap was hidden from the correction methods.",
                ha="center", fontsize=10)
    output = FIGURES / f"trial6_case_{case['storm_id'].lower()}.png"
    if output.exists():
        raise FileExistsError(output)
    figure.subplots_adjust(bottom=0.17)
    figure.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return output


def main() -> None:
    """Input: Trial6 feature/stress sources. Output: three storm case PNGs."""
    with PREDICTIONS.open(encoding="utf-8-sig", newline="") as source:
        predictions = list(csv.DictReader(source))
    with METRICS.open(encoding="utf-8-sig", newline="") as source:
        metrics = list(csv.DictReader(source))
    FIGURES.mkdir(parents=True, exist_ok=True)
    for storm_id in STORMS:
        output = draw_case(load_case(storm_id, predictions, metrics))
        print(output, flush=True)


if __name__ == "__main__":
    main()
