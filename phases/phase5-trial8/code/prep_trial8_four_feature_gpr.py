"""Compare the requested four-input GPR with the saved Trial8 baselines."""

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from calc_trial8_four_feature_gpr import predict_event
from prep_trial8_next_orbit_gpr import HOUR_US, ROOT, load_events, score, write_csv


PREVIOUS = ROOT / "data/analysis/trial8_next_orbit_predictions.csv"
POINTS = ROOT / "data/analysis/trial8_four_feature_predictions.csv"
METRICS = ROOT / "data/analysis/trial8_four_feature_metrics.csv"
FIGURES = ROOT / "figures/four_feature_25storm"
OVERVIEW = ROOT / "figures/trial8_four_feature_rmse.png"
VERSION = "phase4_trial8_four_density_inputs_gpr_v2"


def load_previous() -> dict[tuple[str, int], float]:
    """Input: saved one-input Trial8 CSV. Output: {(storm, time_us): GPR estimate}."""
    with PREVIOUS.open(encoding="utf-8-sig", newline="") as source:
        return {(row["storm_id"], int(row["time_us"])):
                float(row["gp_log_residual_mean"]) for row in csv.DictReader(source)}


def score_comparison(rows: list[dict], storm_id: str) -> dict:
    """Input: [same-position four-input predictions], storm ID. Output: comparable metrics."""
    result = score(rows, storm_id)
    actual = np.asarray([row["residual_log_density"] for row in rows])
    one_input = np.asarray([row["one_input_gp_log_residual_mean"] for row in rows])
    result["one_input_gpr_log_rmse"] = float(np.sqrt(np.mean((actual - one_input) ** 2)))
    result["one_input_gpr_log_mae"] = float(np.mean(np.abs(actual - one_input)))
    result["algorithm_version"] = VERSION
    return result


def draw_event(rows: list[dict], storm_id: str, t0_us: int) -> None:
    """Input: [eligible orbit predictions], storm ID, t0. Output: signed-error PNG."""
    hours = [(row["time_us"] - t0_us) / HOUR_US for row in rows]
    actual = np.asarray([row["residual_log_density"] for row in rows])
    curves = (
        (np.zeros(len(rows)), "Trial4 D-model", "#d97706"),
        (np.asarray([row["previous_log_residual"] for row in rows]),
         "Previous orbit", "#2563eb"),
        (np.asarray([row["one_input_gp_log_residual_mean"] for row in rows]),
         "One-input GPR", "#6b7280"),
        (np.asarray([row["gp_log_residual_mean"] for row in rows]),
         "Four-input GPR", "#dc2626"),
    )
    figure, axis = plt.subplots(figsize=(12, 4.5), layout="constrained")
    for estimate, label, color in curves:
        axis.plot(hours, 100 * np.expm1(estimate - actual), label=label,
                  color=color, linewidth=1)
    axis.axhline(0, color="#111827", linewidth=0.8)
    axis.axvline(0, color="#6b7280", linestyle="--", linewidth=0.9)
    axis.set_title(f"{storm_id}: next-orbit density error")
    axis.set_xlabel(r"Hours from event time $t_0$")
    axis.set_ylabel("Estimated density / L2 - 1 (%)")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, ncol=4)
    figure.savefig(FIGURES / f"{storm_id.lower()}_four_feature_error.png", dpi=160)
    plt.close(figure)


def draw_overview(metrics: list[dict]) -> None:
    """Input: [25 storm metrics]. Output: one four-method RMSE PNG."""
    positions = np.arange(len(metrics))
    figure, axis = plt.subplots(figsize=(10, 11), layout="constrained")
    for offset, field, label, color in (
        (-0.27, "trial4_log_rmse", "Trial4 D-model", "#d97706"),
        (-0.09, "previous_orbit_log_rmse", "Previous orbit", "#2563eb"),
        (0.09, "one_input_gpr_log_rmse", "One-input GPR", "#6b7280"),
        (0.27, "gpr_log_rmse", "Four-input GPR", "#dc2626"),
    ):
        axis.barh(positions + offset, [row[field] for row in metrics],
                  height=0.17, label=label, color=color)
    axis.set_yticks(positions, [row["storm_id"] for row in metrics])
    axis.invert_yaxis()
    axis.set_xlabel("Log-density RMSE on the same eligible orbit anchors")
    axis.set_title("25 storms: four available inputs for next-orbit GPR")
    axis.legend(frameon=False)
    axis.grid(axis="x", alpha=0.2)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def main() -> None:
    """Input: Trial1 anchors and saved one-input Trial8 CSV. Output: v2 CSVs and PNGs."""
    if POINTS.exists() or METRICS.exists() or OVERVIEW.exists():
        raise FileExistsError("Four-input Trial8 result already exists.")
    events, event_times = load_events()
    old = load_previous()
    predictions = []
    metrics = []
    for storm_id, event in events.items():
        scored = predict_event(event)
        if not scored:
            raise ValueError(f"No eligible orbit anchors: {storm_id}")
        for row in scored:
            key = (storm_id, row["time_us"])
            if key not in old:
                raise ValueError(f"Four-input and one-input scoring keys differ: {key}")
            row["one_input_gp_log_residual_mean"] = old[key]
            baseline = row["rho_trial4_phase_kg_m3"]
            row["rho_previous_kg_m3"] = baseline * math.exp(row["previous_log_residual"])
            row["rho_gpr_kg_m3"] = baseline * math.exp(row["gp_log_residual_mean"])
            row["algorithm_version"] = VERSION
        predictions.extend(scored)
        metrics.append(score_comparison(scored, storm_id))
        print(f"Predicted {storm_id}: {len(scored)} orbits", flush=True)
    if len(predictions) != len(old):
        raise ValueError("Four-input and one-input scored orbit counts differ.")
    overall = score_comparison(predictions, "all_eligible_orbits")
    POINTS.parent.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    write_csv(POINTS, predictions)
    write_csv(METRICS, [*metrics, overall])
    for storm_id in events:
        draw_event([row for row in predictions if row["storm_id"] == storm_id],
                   storm_id, event_times[storm_id])
    draw_overview(metrics)
    print(overall)


if __name__ == "__main__":
    main()
