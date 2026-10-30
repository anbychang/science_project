"""Create per-storm residual panels from the frozen Phase 3 prediction output."""

import csv
import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SOURCE = Path(
    "phases/phase3-trial4/data/sqlite/"
    "swarm_a_phase3_prediction_tau465_exploratory.sqlite"
)
REPORT = Path("phases/phase3-trial4/data/analysis/trial4_25storm_residual_screen.csv")
FIGURE = Path("phases/phase3-trial4/figures/trial4_25storm_residual_panels.png")
PLOT_STEP_MINUTES = 30
MICROSECONDS_PER_DAY = 86_400_000_000
BACKGROUND_RATIO_LIMIT = 1.10
RESPONSE_CORRELATION_LIMIT = 0.30


def load_event_series(source_path: Path) -> dict[str, dict[str, np.ndarray]]:
    """Input: Phase 3 prediction SQLite path. Output: {storm_id: residual series}."""
    uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
    rows_by_storm: dict[str, list[tuple]] = defaultdict(list)
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT prediction.storm_id,prediction.time_us,overview.t0_time_us,
                   prediction.h_phase_nt,
                   ln(prediction.rho_l2_phase_kg_m3
                      / prediction.rho_m1_pooled_phase_kg_m3)
            FROM phase3_prediction_minute AS prediction
            JOIN phase3_25storm_overview AS overview
              ON overview.storm_id=prediction.storm_id
            ORDER BY overview.t0_time_us,prediction.time_us
        """).fetchall()
    if not rows:
        raise ValueError("Phase 3 prediction table is empty.")
    for storm_id, time_us, t0_time_us, response_nt, residual in rows:
        if not math.isfinite(response_nt) or not math.isfinite(residual):
            raise ValueError(f"Non-finite residual input for {storm_id}.")
        rows_by_storm[storm_id].append((time_us, t0_time_us, response_nt, residual))
    if len(rows_by_storm) != 25:
        raise ValueError(f"Expected 25 storms, found {len(rows_by_storm)}.")
    return {
        storm_id: {
            "time_us": np.array([row[0] for row in storm_rows], dtype=np.int64),
            "t0_time_us": np.full(len(storm_rows), storm_rows[0][1], dtype=np.int64),
            "h_phase_nt": np.array([row[2] for row in storm_rows], dtype=float),
            "residual_ln": np.array([row[3] for row in storm_rows], dtype=float),
        }
        for storm_id, storm_rows in rows_by_storm.items()
    }


def summarize_event(storm_id: str, series: dict[str, np.ndarray]) -> dict:
    """Input: storm ID and residual series. Output: one screening summary row."""
    response_nt = series["h_phase_nt"]
    residual_ln = series["residual_ln"]
    centered_response = response_nt - np.mean(response_nt)
    centered_residual = residual_ln - np.mean(residual_ln)
    response_sum_squares = float(centered_response @ centered_response)
    residual_sum_squares = float(centered_residual @ centered_residual)
    if response_sum_squares == 0 or residual_sum_squares == 0:
        raise ValueError(f"No within-storm variation for {storm_id}.")
    mean_residual_ln = float(np.mean(residual_ln))
    residual_correlation = float(
        (centered_response @ centered_residual)
        / math.sqrt(response_sum_squares * residual_sum_squares)
    )
    residual_slope_per_nt = float(
        (centered_response @ centered_residual) / response_sum_squares
    )
    flags = []
    if abs(mean_residual_ln) >= math.log(BACKGROUND_RATIO_LIMIT):
        flags.append("background_offset")
    if abs(residual_correlation) >= RESPONSE_CORRELATION_LIMIT:
        flags.append("response_shape")
    return {
        "storm_id": storm_id,
        "valid_phase_minutes": len(residual_ln),
        "mean_residual_ln": mean_residual_ln,
        "geometric_l2_over_m1": math.exp(mean_residual_ln),
        "residual_slope_per_nt": residual_slope_per_nt,
        "residual_h_correlation": residual_correlation,
        "screening_flags": "+".join(flags) if flags else "none",
    }


def save_summary(rows: list[dict]) -> None:
    """Input: [storm screening row]. Output: Trial4 residual-screen CSV."""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if REPORT.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {REPORT}")
    with REPORT.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_panels(events: dict[str, dict[str, np.ndarray]], rows: list[dict]) -> None:
    """Input: {storm_id: series} and screening rows. Output: 25 residual panels PNG."""
    if FIGURE.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure: {FIGURE}")
    row_by_storm = {row["storm_id"]: row for row in rows}
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                                constrained_layout=True)
    for panel_index, (axis, storm_id) in enumerate(
        zip(axes.flat, events, strict=True)
    ):
        series = events[storm_id]
        summary = row_by_storm[storm_id]
        selected = slice(None, None, PLOT_STEP_MINUTES)
        days_from_t0 = (
            (series["time_us"] - series["t0_time_us"])
            / MICROSECONDS_PER_DAY
        )
        axis.plot(days_from_t0[selected], series["residual_ln"][selected],
                  color="#111827", linewidth=0.8, label="ln(L2 / M1)")
        axis.axhline(0, color="#9ca3af", linewidth=0.6)
        axis.axhline(summary["mean_residual_ln"], color="#dc2626",
                     linewidth=0.8, linestyle="--", label="storm mean")
        axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
        response_axis = axis.twinx()
        response_axis.plot(days_from_t0[selected],
                           series["h_phase_nt"][selected] / 1000,
                           color="#2563eb", linewidth=0.7, alpha=0.8,
                           label="H / 1000 nT")
        response_axis.tick_params(axis="y", labelcolor="#2563eb", labelsize=7)
        if panel_index % 5 == 4:
            response_axis.set_ylabel("H (1000 nT)", color="#2563eb")
        axis.set_title(
            f"{storm_id[1:9]}  {summary['screening_flags']}", fontsize=8
        )
        axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("ln(L2 / M1)")
    figure.suptitle(
        "Trial4 screening: residual (black), storm mean (red), H (blue)",
        fontsize=13,
    )
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen Phase 3 prediction SQLite. Output: Trial4 CSV and PNG."""
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing frozen Phase 3 input: {SOURCE}")
    events = load_event_series(SOURCE)
    rows = [summarize_event(storm_id, series)
            for storm_id, series in events.items()]
    if sum(row["valid_phase_minutes"] for row in rows) != 214_907:
        raise ValueError("Residual screening lost Phase 3 prediction rows.")
    save_summary(rows)
    draw_panels(events, rows)
    print(f"Saved residual screens for {len(rows)} storms")


if __name__ == "__main__":
    main()
