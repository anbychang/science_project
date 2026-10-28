"""Draw one retrospective fixed-tau gain diagnostic for each Phase 3 storm."""

import math
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from research_workspace.phases.phase3.code.prep_event_gain_tau465 import OUTPUT as GAIN_DATABASE
from research_workspace.phases.phase3.code.prep_prediction_tau465 import OUTPUT as PREDICTIONS


FIGURE_DIRECTORY = Path("research_workspace/phases/phase3/figures/event_gain_tau465_25storm")
MICROSECONDS_PER_DAY = 86_400_000_000
DENSITY_DISPLAY_SCALE = 1e12


def load_storms() -> list[dict]:
    """Input: read-only gain and prediction SQLite. Output: 25 aligned storm records."""
    gain_uri = f"file:{GAIN_DATABASE.resolve().as_posix()}?mode=ro"
    prediction_uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(gain_uri, uri=True)) as gains:
        summaries = gains.execute("""
            SELECT storm_id,t0_time_us,symh_min_nt,valid_phase_minutes,
                   r_candidate,gain_pooled_per_nt,gain_event_fit_per_nt,
                   rmse_pooled_log_density,rmse_event_fit_log_density
            FROM phase3_event_gain_tau465_diagnostic ORDER BY t0_time_us
        """).fetchall()
    if len(summaries) != 25:
        raise ValueError("Expected 25 event gain summaries.")
    storms = []
    with closing(sqlite3.connect(prediction_uri, uri=True)) as predictions:
        for summary in summaries:
            (storm_id, t0_us, symh_nt, expected, quiet_ratio, pooled_gain,
             event_gain, pooled_rmse, event_rmse) = summary
            samples = predictions.execute("""
                SELECT time_us,h_phase_nt,rho_l2_phase_kg_m3,
                       rho_msis_quiet_phase_kg_m3,rho_m1_pooled_phase_kg_m3
                FROM phase3_prediction_minute WHERE storm_id=? ORDER BY time_us
            """, (storm_id,)).fetchall()
            if len(samples) != expected:
                raise ValueError(f"Prediction count differs for {storm_id}.")
            values = np.asarray(samples, dtype=float)
            time_us, response_nt, observed, quiet, pooled = values.T
            event_fit = quiet * quiet_ratio * np.exp(event_gain * response_nt)
            if (not np.isfinite(values).all() or not np.isfinite(event_fit).all()
                    or np.any(observed <= 0) or np.any(pooled <= 0)
                    or np.any(event_fit <= 0)):
                raise ValueError(f"Invalid density for {storm_id}.")
            if not np.allclose(quiet * quiet_ratio * np.exp(pooled_gain * response_nt),
                               pooled, rtol=1e-10, atol=0):
                raise ValueError(f"Shared-gain prediction differs for {storm_id}.")
            for predicted, expected_rmse in ((pooled, pooled_rmse),
                                             (event_fit, event_rmse)):
                rmse = float(np.sqrt(np.mean(np.log(observed / predicted) ** 2)))
                if not math.isclose(rmse, expected_rmse, rel_tol=1e-10):
                    raise ValueError(f"Diagnostic RMSE differs for {storm_id}.")
            storms.append({
                "storm_id": storm_id,
                "t0_us": t0_us,
                "symh_nt": symh_nt,
                "gain_ratio": event_gain / pooled_gain,
                "pooled_rmse": pooled_rmse,
                "event_rmse": event_rmse,
                "days_from_t0": (time_us - t0_us) / MICROSECONDS_PER_DAY,
                "observed": observed,
                "pooled": pooled,
                "event_fit": event_fit,
            })
    return storms


def draw_storm(storm: dict) -> Path:
    """Input: one aligned storm record. Output: its density and residual PNG."""
    destination = FIGURE_DIRECTORY / f"{storm['storm_id']}_gain_diagnostic.png"
    if destination.exists():
        raise FileExistsError(destination)
    figure, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               constrained_layout=True,
                               gridspec_kw={"height_ratios": [2, 1]})
    x_days = storm["days_from_t0"]
    for density, label, color in (
        (storm["observed"], "Swarm L2", "#111827"),
        (storm["pooled"], "Shared G", "#2563eb"),
        (storm["event_fit"], "Event-fitted Gk", "#d97706"),
    ):
        axes[0].plot(x_days, density * DENSITY_DISPLAY_SCALE,
                     label=label, color=color, linewidth=1)
    for predicted, label, color in (
        (storm["pooled"], "L2 / shared G", "#2563eb"),
        (storm["event_fit"], "L2 / event-fitted Gk", "#d97706"),
    ):
        axes[1].plot(x_days, np.log(storm["observed"] / predicted),
                     label=label, color=color, linewidth=1)
    for axis in axes:
        axis.axvline(0, color="#64748b", linestyle="--", linewidth=0.8)
        axis.grid(alpha=0.2)
        axis.legend(loc="upper right")
    axes[1].axhline(0, color="#111827", linewidth=0.7)
    axes[0].set_ylabel("Density (1e-12 kg/m3)")
    axes[1].set(ylabel="ln(L2 / prediction)", xlabel="Days from SYM-H minimum")
    figure.suptitle(
        f"{storm['storm_id'][1:9]}  |  SYM-H {storm['symh_nt']} nT"
        f"  |  Gk / G {storm['gain_ratio']:.2f}\n"
        f"Fixed tau=4.65 h; in-sample log RMSE "
        f"{storm['pooled_rmse']:.3f} -> {storm['event_rmse']:.3f}"
    )
    figure.savefig(destination, dpi=160)
    plt.close(figure)
    return destination


def main() -> None:
    """Input: existing Phase 3 derived SQLite. Output: 25 separate PNGs."""
    storms = load_storms()
    FIGURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    destinations = [draw_storm(storm) for storm in storms]
    if len(destinations) != 25 or len(set(destinations)) != 25:
        raise ValueError("Expected 25 distinct storm figures.")
    print(f"Saved {len(destinations)} fixed-tau storm diagnostics in {FIGURE_DIRECTORY}")


if __name__ == "__main__":
    main()
