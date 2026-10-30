"""Check recovery-tail performance at several independent fit horizons."""

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from calc_trial5_recovery_validation import (
    RecoveryValidationPlan,
    fit_nonnegative_amplitude_before,
    fit_signed_amplitude_before,
    mean_tail_square_after,
)
from prep_trial5_recovery import read_trial4_events


LOO_EVENT_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_loo_events.csv")
EVENT_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_horizon_events.csv")
MODEL_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_horizon_models.csv")
FIGURE = Path("phases/phase3-trial5/figures/trial5_recovery_horizon_validation.png")
FIT_END_HOURS = (6.0, 12.0, 24.0, 36.0)


def read_selected_times() -> dict[str, float]:
    """Input: leave-one-event CSV. Output: independently selected recovery time by storm."""
    with LOO_EVENT_REPORT.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    result = {
        row["storm_id"]: float(row["selected_recovery_time_hours"])
        for row in rows
    }
    if len(result) != 25 or len(rows) != 25:
        raise ValueError("Expected 25 unique leave-one-event recovery times.")
    return result


def event_rows() -> list[dict]:
    """Input: Trial4 rows and leave-one-event times. Output: all horizon validation rows."""
    selected_time_by_storm = read_selected_times()
    rows = []
    for trial4_event in read_trial4_events():
        event = trial4_event.recovery_event
        selected_time = selected_time_by_storm[event.storm_id]
        for fit_end_hours in FIT_END_HOURS:
            plan = RecoveryValidationPlan(selected_time, fit_end_hours)
            nonnegative_amplitude = fit_nonnegative_amplitude_before(event, plan)
            signed_amplitude = fit_signed_amplitude_before(event, plan)
            baseline_mse = mean_tail_square_after(event, plan, 0.0)
            nonnegative_mse = mean_tail_square_after(event, plan, nonnegative_amplitude)
            signed_mse = mean_tail_square_after(event, plan, signed_amplitude)
            rows.append({
                "storm_id": event.storm_id,
                "fit_end_hours": fit_end_hours,
                "selected_recovery_time_hours": selected_time,
                "nonnegative_amplitude": nonnegative_amplitude,
                "signed_amplitude_diagnostic": signed_amplitude,
                "baseline_tail_rmse_log_density": math.sqrt(baseline_mse),
                "nonnegative_tail_rmse_log_density": math.sqrt(nonnegative_mse),
                "signed_tail_rmse_log_density": math.sqrt(signed_mse),
            })
    return rows


def model_rows(rows: list[dict]) -> list[dict]:
    """Input: horizon validation rows. Output: equal-event comparison by horizon."""
    output = []
    for fit_end_hours in FIT_END_HOURS:
        selected = [row for row in rows if row["fit_end_hours"] == fit_end_hours]
        for model_name, field in (
            ("D_trial4_tail_baseline", "baseline_tail_rmse_log_density"),
            ("E_positive_recovery_tail", "nonnegative_tail_rmse_log_density"),
            ("signed_recovery_diagnostic", "signed_tail_rmse_log_density"),
        ):
            squared = [row[field] ** 2 for row in selected]
            output.append({
                "fit_end_hours": fit_end_hours,
                "model": model_name,
                "event_equal_tail_mse_log_density": float(np.mean(squared)),
                "event_equal_tail_rmse_log_density": float(math.sqrt(np.mean(squared))),
                "events_improved": sum(
                    row[field] < row["baseline_tail_rmse_log_density"]
                    for row in selected
                ) if model_name != "D_trial4_tail_baseline" else 0,
            })
    return output


def write_csv(rows: list[dict], path: Path) -> None:
    """Input: [{field: value}], new CSV path. Output: saved horizon-validation CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_horizon_comparison(rows: list[dict]) -> None:
    """Input: horizon model rows. Output: validation-RMSE versus fit-horizon PNG."""
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    for model_name, label, color in (
        ("D_trial4_tail_baseline", "Trial4 tail", "#111827"),
        ("E_positive_recovery_tail", "Positive recovery tail", "#2563eb"),
        ("signed_recovery_diagnostic", "Signed diagnostic tail", "#dc2626"),
    ):
        selected = [row for row in rows if row["model"] == model_name]
        axis.plot([row["fit_end_hours"] for row in selected],
                  [row["event_equal_tail_rmse_log_density"] for row in selected],
                  color=color, marker="o", label=label)
    axis.set(xlabel="Amplitude fit horizon (h)", ylabel="Later-tail RMSE (log density)",
             title="Independent recovery-tail validation")
    axis.grid(alpha=0.2)
    axis.legend()
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def ensure_outputs_are_new() -> None:
    """Input: planned horizon outputs. Output: raises before an overwrite."""
    existing = [path for path in (EVENT_REPORT, MODEL_REPORT, FIGURE) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite Trial5 horizon outputs: {existing}")


def main() -> None:
    """Input: Trial4 SQLite and leave-one-event T values. Output: horizon sensitivity files."""
    ensure_outputs_are_new()
    rows = event_rows()
    summary = model_rows(rows)
    write_csv(rows, EVENT_REPORT)
    write_csv(summary, MODEL_REPORT)
    draw_horizon_comparison(summary)
    print(f"Saved Trial5 recovery horizons for {len(FIT_END_HOURS)} fit endpoints")


if __name__ == "__main__":
    main()
