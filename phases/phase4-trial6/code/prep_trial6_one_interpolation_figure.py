"""Draw one real six-hour interpolation example without other correction models."""

import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from calc_trial6_ridge import block_masks, load_rows
from calc_trial6_stress import HOUR_US, load_activity


ROOT = Path("phases/phase4-trial6")
SOURCE = ROOT / "data/analysis/trial6_stress_predictions.csv"
OUTPUT = ROOT / "figures/trial6_one_storm_interpolation.png"
STORM_ID = "S20230805T0546"


def main() -> None:
    """Input: one Trial6 t0 block and anchor residuals. Output: one PNG example."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    rows = load_rows()[STORM_ID]
    t0_us = load_activity()[STORM_ID]["t0_us"]
    block_start_us = t0_us - 3 * HOUR_US
    start_hour = (block_start_us - rows[0]["time_us"]) / HOUR_US
    masks = block_masks(rows, start_hour)
    if masks is None:
        raise ValueError("Selected block has no data on both sides.")
    elapsed = np.array([row["elapsed_hours"] for row in rows])
    residual = np.array([row["residual_log_density"] for row in rows])
    target_indices = np.flatnonzero(masks["test"])
    left = np.flatnonzero(masks["train"] & (elapsed < start_hour))[-1]
    right = np.flatnonzero(masks["train"] & (elapsed >= start_hour + 6))[0]
    with SOURCE.open(encoding="utf-8-sig", newline="") as source:
        saved = {int(row["time_us"]): row for row in csv.DictReader(source)
                 if row["storm_id"] == STORM_ID and row["selection"] == "t0_centered"}
    if set(saved) != {rows[index]["time_us"] for index in target_indices}:
        raise ValueError("Saved interpolation and hidden anchor keys differ.")
    for index in target_indices:
        predicted = np.interp(elapsed[index], elapsed[masks["train"]],
                              residual[masks["train"]])
        if not math.isclose(predicted, float(saved[rows[index]["time_us"]]["interpolation"]),
                            abs_tol=1e-12):
            raise ValueError("Plotted interpolation differs from saved Trial6 result.")
    time_h = (np.array([row["time_us"] for row in rows]) - t0_us) / HOUR_US
    correction_percent = 100 * (np.exp(residual) - 1)
    known = masks["train"] & (time_h >= -24) & (time_h <= 24)
    x = time_h[[left, right]]
    grid = np.linspace(x[0], x[1], 200)
    interpolated_log = np.interp(grid, x, residual[[left, right]])
    corrected_percent = 100 * (np.exp(interpolated_log) - 1)
    hidden_x = time_h[target_indices]
    hidden_percent = correction_percent[target_indices]
    predicted_percent = [100 * (math.exp(float(saved[rows[index]["time_us"]]["interpolation"]))
                                - 1) for index in target_indices]

    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, axis = plt.subplots(figsize=(15, 6))
    axis.axvspan(-3, 3, color="#e7eff7")
    axis.plot(time_h, np.where(known, correction_percent, np.nan), color="black",
              marker="o", ms=3.5, lw=1.5, label="缺口外可用的 L2 偏差")
    axis.axhline(0, color="#888888", lw=1.1, ls="--", label="0%：不修正 Trial4")
    axis.plot(grid, corrected_percent, color="#1261a0", lw=2.7,
              label="用兩端資料算出的內插")
    axis.scatter(hidden_x, predicted_percent, color="#1261a0", marker="s", s=55,
                 zorder=5)
    axis.scatter(x, correction_percent[[left, right]], color="black", s=70, zorder=5)
    axis.scatter(hidden_x, hidden_percent, facecolors="white", edgecolors="black",
                 linewidths=2, s=85, zorder=6, label="最後才揭曉的缺口 L2")
    axis.axvline(0, color="#555555", ls=":", lw=1.1)
    axis.text(0, 22, "中間六小時暫時不給看", ha="center", color="#33485e")
    axis.set_xlim(-24, 24)
    axis.set_ylim(-10, 24)
    axis.set_xlabel("距離磁暴 t0 的時間（小時）")
    axis.set_ylabel("L2 相對 Trial4 的差距（%）")
    axis.set_title("S20230805 磁暴：前後各 24 小時，只在中間六小時做內插")
    axis.grid(alpha=0.22)
    axis.legend(loc="upper left", fontsize=10, frameon=True, ncol=2)
    figure.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT, dpi=180)
    plt.close(figure)
    print(OUTPUT, flush=True)


if __name__ == "__main__":
    main()
