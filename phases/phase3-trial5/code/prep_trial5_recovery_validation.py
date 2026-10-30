"""Run leave-one-event recovery validation and draw its compact diagnostics."""

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from calc_trial5_recovery_validation import ValidationScore, validate_leave_one_event_out
from prep_trial5_recovery import read_trial4_events


EVENT_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_loo_events.csv")
MODEL_REPORT = Path("phases/phase3-trial5/data/analysis/trial5_recovery_loo_models.csv")
FIGURE = Path("phases/phase3-trial5/figures/trial5_recovery_loo_validation.png")


def score_row(score: ValidationScore) -> dict:
    """Input: one leave-one-event score. Output: one validation analysis row."""
    return {
        "storm_id": score.storm_id,
        "selected_recovery_time_hours": score.selected_recovery_time_hours,
        "nonnegative_amplitude": score.nonnegative_amplitude,
        "signed_amplitude_diagnostic": score.signed_amplitude,
        "baseline_tail_rmse_log_density": math.sqrt(score.baseline_tail_mse_log_density),
        "nonnegative_tail_rmse_log_density": math.sqrt(
            score.nonnegative_tail_mse_log_density
        ),
        "signed_tail_rmse_log_density": math.sqrt(score.signed_tail_mse_log_density),
        "nonnegative_improves_tail": int(
            score.nonnegative_tail_mse_log_density < score.baseline_tail_mse_log_density
        ),
        "signed_improves_tail": int(
            score.signed_tail_mse_log_density < score.baseline_tail_mse_log_density
        ),
    }


def model_rows(scores: list[ValidationScore]) -> list[dict]:
    """Input: leave-one-event validation scores. Output: equal-event model comparison."""
    baseline_mse = float(np.mean([score.baseline_tail_mse_log_density for score in scores]))
    nonnegative_mse = float(np.mean([
        score.nonnegative_tail_mse_log_density for score in scores
    ]))
    signed_mse = float(np.mean([score.signed_tail_mse_log_density for score in scores]))
    return [
        {
            "model": "D_trial4_tail_baseline",
            "event_equal_tail_mse_log_density": baseline_mse,
            "event_equal_tail_rmse_log_density": math.sqrt(baseline_mse),
            "events_improved": 0,
        },
        {
            "model": "E_positive_recovery_tail",
            "event_equal_tail_mse_log_density": nonnegative_mse,
            "event_equal_tail_rmse_log_density": math.sqrt(nonnegative_mse),
            "events_improved": sum(
                score.nonnegative_tail_mse_log_density < score.baseline_tail_mse_log_density
                for score in scores
            ),
        },
        {
            "model": "signed_recovery_diagnostic",
            "event_equal_tail_mse_log_density": signed_mse,
            "event_equal_tail_rmse_log_density": math.sqrt(signed_mse),
            "events_improved": sum(
                score.signed_tail_mse_log_density < score.baseline_tail_mse_log_density
                for score in scores
            ),
        },
    ]


def write_csv(rows: list[dict], path: Path) -> None:
    """Input: [{field: value}], new CSV path. Output: saved Trial5 validation CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_validation(scores: list[ValidationScore]) -> None:
    """Input: leave-one-event scores. Output: recovery-time and tail-RMSE PNG."""
    ordered = sorted(scores, key=lambda score: score.storm_id)
    labels = [score.storm_id[1:9] for score in ordered]
    indices = np.arange(len(ordered))
    figure, axes = plt.subplots(2, 1, figsize=(12, 7), constrained_layout=True)
    axes[0].plot(indices, [score.selected_recovery_time_hours for score in ordered],
                 color="#2563eb", marker="o", markersize=3)
    axes[0].set(ylabel="Selected T_rec (h)", title="Leave-one-event recovery-time selection")
    axes[0].grid(alpha=0.2)
    for values, label, color in (
        ([math.sqrt(score.baseline_tail_mse_log_density) for score in ordered],
         "Trial4 tail", "#111827"),
        ([math.sqrt(score.nonnegative_tail_mse_log_density) for score in ordered],
         "Positive recovery tail", "#2563eb"),
        ([math.sqrt(score.signed_tail_mse_log_density) for score in ordered],
         "Signed diagnostic tail", "#dc2626"),
    ):
        axes[1].plot(indices, values, color=color, marker="o", markersize=3, label=label)
    axes[1].set(ylabel="Tail RMSE (log density)", title="First 24 h fit; evaluate t >= 24 h")
    axes[1].grid(alpha=0.2)
    axes[1].legend()
    axes[1].set_xticks(indices, labels, rotation=45, ha="right")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def ensure_outputs_are_new() -> None:
    """Input: planned validation outputs. Output: raises before an overwrite."""
    existing = [path for path in (EVENT_REPORT, MODEL_REPORT, FIGURE) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite Trial5 validation outputs: {existing}")


def main() -> None:
    """Input: read-only Trial4 SQLite. Output: leave-one-event recovery validation."""
    ensure_outputs_are_new()
    trial4_events = read_trial4_events()
    scores = validate_leave_one_event_out([
        event.recovery_event for event in trial4_events
    ])
    write_csv([score_row(score) for score in scores], EVENT_REPORT)
    write_csv(model_rows(scores), MODEL_REPORT)
    draw_validation(scores)
    print(f"Saved leave-one-event validation for {len(scores)} storms")


if __name__ == "__main__":
    main()
