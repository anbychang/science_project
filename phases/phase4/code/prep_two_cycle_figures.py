"""Compare Phase 3 one-cycle density with Phase 4 two-cycle density."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from phases.phase4.code.load_phase4_inputs import load_inputs


FIGURE_DIR = Path("phases/phase4/figures/two_cycle_window")
OVERVIEW = Path("phases/phase4/figures/two_cycle_25storm_overview.png")
QC = Path("phases/phase4/data/analysis/phase4_two_cycle_anchor_qc.csv")
DENSITY_SCALE = 1e12


def relative_hours(times_us: np.ndarray, t0_time_us: int) -> np.ndarray:
    """Input: [UTC time_us], t0 time_us. Output: [hours from t0]."""
    return (times_us - t0_time_us) / 3_600_000_000


def draw_density(axis: plt.Axes, event: dict) -> None:
    """Input: plot axis, event. Output: one/two-cycle curves on axis."""
    one_time = relative_hours(event["time_us"], event["t0_time_us"])
    two_time = relative_hours(event["time_us"][event["anchors"]],
                              event["t0_time_us"])
    axis.plot(one_time, event["rho_l2_one_cycle"] * DENSITY_SCALE,
              color="#9ca3af", linewidth=0.9, label="Phase 3: one-cycle L2")
    axis.plot(two_time, event["rho_l2"] * DENSITY_SCALE,
              color="#1769aa", linewidth=1.4, marker="o", markersize=2.5,
              label="Phase 4: two-cycle L2")
    axis.axvline(0, color="#b45309", linestyle="--", linewidth=1, label="t0")
    axis.grid(alpha=0.2)


def draw_event(event: dict) -> None:
    """Input: event with one/two-cycle L2. Output: one PNG in Phase 4 figures."""
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    draw_density(axes[0], event)
    draw_density(axes[1], event)
    axes[0].set_xlim(-49, 98)
    axes[1].set_xlim(-12, 24)
    axes[0].set(title=f"{event['storm_id']} | full t0-centered event",
                ylabel="L2 density (10^-12 kg/m^3)")
    axes[1].set(title="Peak neighborhood", xlabel="Hours from t0",
                ylabel="L2 density (10^-12 kg/m^3)")
    axes[0].legend(loc="best", frameon=False)
    figure.savefig(FIGURE_DIR / f"{event['storm_id']}_one_vs_two_cycle.png", dpi=170)
    plt.close(figure)


def draw_overview(events: list[dict]) -> None:
    """Input: 25 events. Output: 5 x 5 storm overview PNG."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 15), sharex=True,
                                     constrained_layout=True)
    for axis, event in zip(axes.flat, events):
        draw_density(axis, event)
        axis.set_xlim(-49, 98)
        axis.set_title(event["storm_id"], fontsize=9)
        axis.tick_params(labelsize=7)
    figure.supxlabel("Hours from t0")
    figure.supylabel("L2 density (10^-12 kg/m^3)")
    figure.suptitle("Phase 3 one-cycle L2 (gray) vs Phase 4 two-cycle L2 (blue); "
                    "dashed = t0", fontsize=13)
    OVERVIEW.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def save_qc(events: list[dict]) -> None:
    """Input: 25 events. Output: one Phase 4 anchor-count CSV."""
    QC.parent.mkdir(parents=True, exist_ok=True)
    with QC.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=(
            "storm_id", "phase3_valid_minute_anchors", "phase4_two_cycle_anchors",
            "first_anchor_hours_from_t0", "last_anchor_hours_from_t0",
        ))
        writer.writeheader()
        for event in events:
            hours = relative_hours(event["time_us"][event["anchors"]],
                                   event["t0_time_us"])
            writer.writerow({
                "storm_id": event["storm_id"],
                "phase3_valid_minute_anchors": int(np.count_nonzero(
                    np.isfinite(event["rho_l2_one_cycle"]))),
                "phase4_two_cycle_anchors": len(event["anchors"]),
                "first_anchor_hours_from_t0": float(hours[0]),
                "last_anchor_hours_from_t0": float(hours[-1]),
            })


def main() -> None:
    """Input: frozen Phase 2/3 data. Output: 26 PNGs and anchor QC CSV."""
    events, _ = load_inputs(2)
    paths = [OVERVIEW, QC] + [
        FIGURE_DIR / f"{event['storm_id']}_one_vs_two_cycle.png" for event in events
    ]
    if any(path.exists() for path in paths):
        raise FileExistsError("Phase 4 two-cycle figure output already exists.")
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for event in events:
        draw_event(event)
    draw_overview(events)
    save_qc(events)
    print(f"Saved {len(events)} storm figures and one overview; "
          f"{sum(len(event['anchors']) for event in events)} two-cycle anchors")


if __name__ == "__main__":
    main()
