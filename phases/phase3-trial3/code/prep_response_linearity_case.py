"""Inspect the observed log-density response against filtered SME."""

import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as dates
import matplotlib.pyplot as plt
import numpy as np


SOURCE = Path(
    "phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite"
)
FIGURE = Path("phases/phase3-trial3/figures/s20250101_response_linearity.png")
STORM_ID = "S20250101T1640"
MAINLINE_GAIN_PER_NT = 0.0007032326071208369


def load_response() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Input: frozen P3 M1 SQLite. Output: [UTC times], [H nT], [log ratio]."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        r_value = database.execute(
            "SELECT r_candidate FROM phase3_25storm_overview WHERE storm_id=?",
            (STORM_ID,),
        ).fetchone()[0]
        rows = database.execute(
            "SELECT time_us,h_phase_nt,rho_l2_phase_kg_m3,"
            "rho_msis_quiet_phase_kg_m3 FROM phase3_prediction_minute "
            "WHERE storm_id=? ORDER BY time_us",
            (STORM_ID,),
        ).fetchall()
    values = np.asarray(rows, dtype=float)
    times = np.array([
        datetime.fromtimestamp(value / 1_000_000, timezone.utc)
        for value in values[:, 0]
    ])
    response = values[:, 1]
    log_ratio = np.log(values[:, 2] / values[:, 3]) - math.log(r_value)
    return times, response, log_ratio


def draw_case() -> Path:
    """Input: frozen P3 M1 SQLite. Output: response-linearity PNG path."""
    times, response, log_ratio = load_response()
    gain = float(response @ log_ratio / (response @ response))
    residual = log_ratio - gain * response
    explained = 1 - float((residual @ residual)
                          / np.sum((log_ratio - np.mean(log_ratio)) ** 2))
    t0 = datetime(2025, 1, 1, 16, 40, tzinfo=timezone.utc)
    before = times < t0

    figure, (relation_axis, residual_axis) = plt.subplots(
        1, 2, figsize=(13, 5.6), constrained_layout=True
    )
    relation_axis.scatter(response[before], log_ratio[before], s=4, alpha=0.17,
                          color="#176d8a", label="Before event t0")
    relation_axis.scatter(response[~before], log_ratio[~before], s=4, alpha=0.17,
                          color="#c35a2b", label="After event t0")
    input_grid = np.linspace(0, response.max(), 200)
    relation_axis.plot(input_grid, gain * input_grid, color="black", linewidth=1.6,
                       label=f"One-event linear fit; R²={explained:.3f}")
    relation_axis.plot(input_grid, MAINLINE_GAIN_PER_NT * input_grid,
                       color="#555555", linestyle="--", linewidth=1,
                       label="Phase 3 common G")
    relation_axis.set(xlabel="H at τ=4.65 h, δ=0 (nT)",
                      ylabel="z = ln(L2 / quiet MSIS) - ln(R)")
    relation_axis.legend(loc="upper left")
    relation_axis.grid(alpha=0.2)

    residual_axis.plot(times, residual, color="#174d9d", linewidth=0.75)
    residual_axis.axhline(0, color="black", linewidth=1)
    residual_axis.axvline(t0, color="#9d2222", linestyle="--", linewidth=1)
    residual_axis.set(xlabel="UTC", ylabel="z - fitted G × H")
    residual_axis.xaxis.set_major_locator(dates.DayLocator())
    residual_axis.xaxis.set_major_formatter(dates.DateFormatter("%m-%d", tz=timezone.utc))
    residual_axis.grid(alpha=0.2)
    figure.suptitle("2025-01-01: density-response linearity, not direct heating")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)
    return FIGURE


if __name__ == "__main__":
    print(draw_case())
