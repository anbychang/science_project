"""Draw pooled and per-storm held-out GPR shape-error comparisons."""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path("phases/phase5-trial13")
SOURCE = ROOT / "data/sqlite/swarm_a_phase5_m1_gpr_comparison_v1.sqlite"
OVERALL = ROOT / "figures/m1_gpr_shape_comparison.png"
EVENTS = ROOT / "figures/m1_gpr_event_shape_changes.png"
MODELS = ("Trial10", "Trial11", "Trial12")
COLORS = ("#a855f7", "#d97706", "#2563eb")


def load_metrics() -> tuple[list[tuple], list[tuple]]:
    """Input: saved comparison SQLite. Output: summary and per-storm shape RMSE rows."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        summary = database.execute("""
            SELECT model_name,shape_rmse,shape_delta_ci_low,shape_delta_ci_high
            FROM summary ORDER BY model_name
        """).fetchall()
        events = database.execute("""
            SELECT model_name,storm_id,shape_rmse
            FROM event_metric ORDER BY storm_id,model_name
        """).fetchall()
    if len(summary) != 4 or len(events) != 100:
        raise ValueError("Figures require four model summaries and 25 storms each.")
    return summary, events


def draw_overall(summary: list[tuple]) -> None:
    """Input: four pooled shape RMSE rows. Output: GP-minus-M1 CI comparison PNG."""
    by_model = {row[0]: row for row in summary}
    baseline = by_model["M1"][1]
    figure, axis = plt.subplots(figsize=(9, 4.3), layout="constrained")
    axis.axvline(0, color="#111827", linewidth=1)
    for index, (model, color) in enumerate(zip(MODELS, COLORS, strict=True)):
        _, value, lower, upper = by_model[model]
        difference = value - baseline
        axis.errorbar(difference, index, xerr=[[difference - lower], [upper - difference]],
                      fmt="o", capsize=5, markersize=8, color=color, linewidth=2)
        axis.text(0.037, index, f"{difference:+.4f}", fontsize=9, va="center")
    axis.set_yticks(range(len(MODELS)), MODELS)
    axis.invert_yaxis()
    axis.set_xlabel("Shape log-RMSE change vs M1 (negative is better)")
    axis.set_title("Same 25 held-out storms: storm-bootstrap 95% intervals")
    axis.set_xlim(-0.005, 0.042)
    axis.grid(axis="x", alpha=0.2)
    OVERALL.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OVERALL, dpi=180)
    plt.close(figure)


def draw_events(events: list[tuple]) -> None:
    """Input: four models x 25 event shape scores. Output: per-storm change PNG."""
    by_storm = {}
    for model, storm, shape_rmse in events:
        by_storm.setdefault(storm, {})[model] = shape_rmse
    if len(by_storm) != 25 or any(len(values) != 4 for values in by_storm.values()):
        raise ValueError("Each storm needs M1 and three GP scores.")
    figure, axis = plt.subplots(figsize=(10, 10), layout="constrained")
    axis.axvline(0, color="#111827", linewidth=1)
    for model_index, (model, color) in enumerate(zip(MODELS, COLORS, strict=True)):
        values = [scores[model] - scores["M1"] for scores in by_storm.values()]
        positions = [index + (model_index - 1) * 0.19
                     for index in range(len(by_storm))]
        axis.scatter(values, positions, label=model, color=color, s=28, zorder=3)
    axis.set_yticks(range(len(by_storm)), [storm[1:9] for storm in by_storm])
    axis.invert_yaxis()
    axis.set_xlabel("Event shape log-RMSE change vs M1 (negative is better)")
    axis.set_title("Same 25 held-out storms: per-storm GP changes")
    axis.grid(axis="x", alpha=0.2)
    axis.legend(loc="lower right")
    figure.savefig(EVENTS, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: saved Trial 13 comparison SQLite. Output: two separate PNGs."""
    summary, events = load_metrics()
    draw_overall(summary)
    draw_events(events)
    print(f"Saved {OVERALL} and {EVENTS}")


if __name__ == "__main__":
    main()
