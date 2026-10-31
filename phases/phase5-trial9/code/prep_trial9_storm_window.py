"""Score saved held-out orbit predictions near each storm event time."""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from prep_trial9_pooled_orbit_gpr import HOUR_US, POINTS, ROOT, load_events, score, write_csv


METRICS = ROOT / "data/analysis/trial9_t0_48h_event_metrics.csv"
FIGURE = ROOT / "figures/trial9_t0_48h_rmse.png"
WINDOW_HOURS = 24


def within_window(rows: list[dict], t0_us: int) -> list[dict]:
    """Input: [predictions], event time. Output: [matched rows within t0 +/-24 h]."""
    return [row for row in rows
            if row["same_storm_gpr_log_residual"] is not None
            and abs(row["time_us"] - t0_us) <= WINDOW_HOURS * HOUR_US]


def load_predictions() -> dict[str, list[dict]]:
    """Input: saved Trial9 CSV. Output: {storm ID: [prediction rows]}."""
    grouped = defaultdict(list)
    with POINTS.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            for field in ("time_us", "previous_time_us"):
                row[field] = int(row[field])
            for field in ("residual_log_density", "previous_log_residual",
                          "pooled_gpr_log_residual"):
                row[field] = float(row[field])
            if row["same_storm_gpr_log_residual"]:
                row["same_storm_gpr_log_residual"] = float(
                    row["same_storm_gpr_log_residual"])
            else:
                row["same_storm_gpr_log_residual"] = None
            grouped[row["storm_id"]].append(row)
    return dict(grouped)


def draw_overview(rows: list[dict]) -> None:
    """Input: [25 storm-window metrics]. Output: t0 +/-24 h comparison PNG."""
    positions = np.arange(len(rows))
    figure, axis = plt.subplots(figsize=(10, 11), layout="constrained")
    for offset, field, label, color in (
        (-0.27, "trial4_log_rmse", "Trial4 D-model", "#d97706"),
        (-0.09, "previous_orbit_log_rmse", "Previous orbit", "#2563eb"),
        (0.09, "same_storm_gpr_log_rmse", "Same-storm GPR", "#6b7280"),
        (0.27, "pooled_gpr_log_rmse", "Other-storm GPR", "#dc2626"),
    ):
        axis.barh(positions + offset, [row[field] for row in rows],
                  height=0.17, label=label, color=color)
    axis.set_yticks(positions, [row["storm_id"] for row in rows])
    axis.invert_yaxis()
    axis.set_xlabel("Log-density RMSE on matched orbit anchors")
    axis.set_title(r"25 storms: $t_0 \pm 24$ hours, held-out GPR")
    axis.legend(frameon=False)
    axis.grid(axis="x", alpha=0.2)
    figure.savefig(FIGURE, dpi=160)
    plt.close(figure)


def main() -> None:
    """Input: saved Trial9 predictions and Trial4 t0. Output: window CSV and PNG."""
    if METRICS.exists() or FIGURE.exists():
        raise FileExistsError("Trial9 storm-window result already exists.")
    events, event_times = load_events()
    predictions = load_predictions()
    if set(predictions) != set(events):
        raise ValueError("Trial9 predictions and Trial4 events differ.")
    selected = {storm_id: within_window(predictions[storm_id], event_times[storm_id])
                for storm_id in events}
    if any(not rows for rows in selected.values()):
        raise ValueError("At least one storm has no matched orbit in the event window.")
    metrics = [score(rows, storm_id) for storm_id, rows in selected.items()]
    all_rows = [row for rows in selected.values() for row in rows]
    overall = score(all_rows, "all_t0_48h_matched_orbits")
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    write_csv(METRICS, [*metrics, overall])
    draw_overview(metrics)
    print(overall)


if __name__ == "__main__":
    main()
