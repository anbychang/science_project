"""Show the one-cycle Phase 3 curve and the Phase 4 training anchors."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from phases.phase4.code.load_phase4_inputs import load_inputs


FIGURE_DIR = Path("phases/phase4/figures/one_cycle_anchors")
OVERVIEW = Path("phases/phase4/figures/one_cycle_25storm_overview.png")
QC = Path("phases/phase4/data/analysis/phase4_one_cycle_anchor_qc.csv")
DENSITY_SCALE = 1e12


def draw_curve(axis: plt.Axes, event: dict) -> None:
    """Input: plot axis and event. Output: one-cycle curve and selected anchors."""
    one_time = (event["time_us"] - event["t0_time_us"]) / 3_600_000_000
    selected_time = one_time[event["anchors"]]
    axis.plot(one_time, event["rho_l2_one_cycle"] * DENSITY_SCALE,
              color="#9ca3af", linewidth=0.9, label="All one-cycle centers")
    axis.plot(selected_time, event["rho_l2"] * DENSITY_SCALE,
              color="#1769aa", linewidth=1.3, marker="o", markersize=2.5,
              label="Selected every 2pi")
    axis.axvline(0, color="#b45309", linestyle="--", linewidth=1, label="t0")
    axis.grid(alpha=0.2)


def draw_event(event: dict) -> None:
    """Input: event with one-cycle densities. Output: one detailed PNG."""
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    for axis in axes:
        draw_curve(axis, event)
    axes[0].set(title=f"{event['storm_id']} | full t0-centered event",
                ylabel="L2 density (10^-12 kg/m^3)", xlim=(-49, 98))
    axes[1].set(title="Peak neighborhood", xlabel="Hours from t0",
                ylabel="L2 density (10^-12 kg/m^3)", xlim=(-12, 24))
    axes[0].legend(loc="best", frameon=False)
    figure.savefig(FIGURE_DIR / f"{event['storm_id']}_one_cycle_anchors.png", dpi=170)
    plt.close(figure)


def draw_overview(events: list[dict]) -> None:
    """Input: 25 events. Output: 5 x 5 one-cycle anchor overview PNG."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 15), sharex=True,
                                     constrained_layout=True)
    for axis, event in zip(axes.flat, events):
        draw_curve(axis, event)
        axis.set_xlim(-49, 98)
        axis.set_title(event["storm_id"], fontsize=9)
        axis.tick_params(labelsize=7)
    figure.supxlabel("Hours from t0")
    figure.supylabel("L2 density (10^-12 kg/m^3)")
    figure.suptitle("One-cycle L2: all minute centers (gray) vs 2pi anchors (blue); "
                    "dashed = t0", fontsize=13)
    OVERVIEW.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def save_qc(events: list[dict]) -> None:
    """Input: 25 events. Output: selected one-cycle anchor counts by storm."""
    QC.parent.mkdir(parents=True, exist_ok=True)
    with QC.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=(
            "storm_id", "phase3_valid_minute_anchors", "phase4_one_cycle_anchors",
            "first_anchor_hours_from_t0", "last_anchor_hours_from_t0",
        ))
        writer.writeheader()
        for event in events:
            hours = (event["time_us"][event["anchors"]] - event["t0_time_us"])
            hours = hours / 3_600_000_000
            writer.writerow({
                "storm_id": event["storm_id"],
                "phase3_valid_minute_anchors": int(np.count_nonzero(
                    np.isfinite(event["rho_l2_one_cycle"]))),
                "phase4_one_cycle_anchors": len(event["anchors"]),
                "first_anchor_hours_from_t0": float(hours[0]),
                "last_anchor_hours_from_t0": float(hours[-1]),
            })


def main() -> None:
    """Input: frozen Phase 2/3 data. Output: 26 PNGs and anchor QC CSV."""
    events, _ = load_inputs()
    paths = [OVERVIEW, QC] + [
        FIGURE_DIR / f"{event['storm_id']}_one_cycle_anchors.png" for event in events
    ]
    if any(path.exists() for path in paths):
        raise FileExistsError("Phase 4 one-cycle figure output already exists.")
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for event in events:
        draw_event(event)
    draw_overview(events)
    save_qc(events)
    print(f"Saved {len(events)} storm figures and one overview; "
          f"{sum(len(event['anchors']) for event in events)} one-cycle anchors")


if __name__ == "__main__":
    main()
