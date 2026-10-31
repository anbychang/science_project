"""Draw one-question figures for the consolidated Phase 5 report."""

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


ROOT = Path("phases")
FIGURES = ROOT / "phase5/figures"
TRIAL1_METRICS = ROOT / "phase5-trial1/data/analysis/phase4_trial4_altitude_event_metrics.csv"
TRIAL2_GEOMETRY = ROOT / "phase5-trial2/data/analysis/phase4_trial4_groupcv20_5_fold_geometry.csv"
TRIAL4_FOLDS = ROOT / "phase5-trial4/data/analysis/phase4_trial4_time_tau_season_fold_metrics.csv"
HELDOUT_FILES = (
    ("Trial 2", ROOT / "phase5-trial2/data/analysis/phase4_trial4_groupcv20_5_event_metrics.csv"),
    ("Trial 3", ROOT / "phase5-trial3/data/analysis/phase4_trial4_trial3_event_metrics.csv"),
    ("Trial 4", ROOT / "phase5-trial4/data/analysis/phase4_trial4_time_tau_season_event_metrics.csv"),
    ("Trial 5", ROOT / "phase5-trial5/data/analysis/phase4_trial5_event_metrics.csv"),
)
GPR_FIGURE = FIGURES / "phase4_gpr_heldout_rmse.png"
GAP_FIGURE = FIGURES / "phase4_trial6_gap_rmse.png"
TRIAL6_SUMMARY = ROOT / "phase5-trial6/data/analysis/trial6_interpolation_rule_summary.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    """Input: saved metric CSV. Output: [{column: value, ...}, ...]."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def heldout_rows(path: Path) -> list[dict[str, str]]:
    """Input: per-storm metric CSV. Output: 25 tested storm rows."""
    rows = [row for row in read_rows(path) if row["storm_id"] != "all_anchors"]
    if (len(rows) != 25 or len({row["storm_id"] for row in rows}) != 25
            or sum(int(row["test_anchor_count"]) for row in rows) != 2295):
        raise ValueError(f"Held-out metric contract failed: {path}")
    return rows


def heldout_rmse(path: Path, column: str) -> float:
    """Input: per-storm metric CSV and RMSE field. Output: pooled log RMSE."""
    rows = heldout_rows(path)
    squared_error = math.fsum(
        int(row["test_anchor_count"]) * float(row[column]) ** 2 for row in rows
    )
    return math.sqrt(squared_error / 2295)


def draw_trial1() -> None:
    """Input: Trial1 saved all-anchor metrics. Output: in-sample RMSE PNG."""
    summaries = [row for row in read_rows(TRIAL1_METRICS)
                 if row["storm_id"] == "all_anchors"]
    if len(summaries) != 1 or int(summaries[0]["anchor_count"]) != 2295:
        raise ValueError("Expected one Trial1 all-anchor metric row.")
    row = summaries[0]
    values = [float(row["trial4_rmse_log_density"]),
              float(row["gpr_rmse_log_density"])]
    figure, axis = plt.subplots(figsize=(7, 5), layout="constrained")
    bars = axis.bar(("Fixed P3 Trial 4", "Trial 1 GPR"), values,
                    color=("#777777", "#496b91"), width=0.55)
    for bar, value in zip(bars, values, strict=True):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 0.002,
                  f"{value:.5f}", ha="center", va="bottom")
    axis.set_ylim(0, 0.13)
    axis.set_ylabel("Log-density RMSE")
    axis.set_title("Trial 1: fitted and scored on the same 2,295 anchors")
    axis.grid(axis="y", alpha=0.2)
    figure.savefig(FIGURES / "phase4_trial1_insample_rmse.png", dpi=180)
    plt.close(figure)


def draw_trial2() -> None:
    """Input: Trial2 five-fold geometry CSV. Output: ARD distance PNG."""
    rows = read_rows(TRIAL2_GEOMETRY)
    if len(rows) != 5 or {int(row["fold_index"]) for row in rows} != set(range(1, 6)):
        raise ValueError("Expected five Trial2 geometry folds.")
    rows.sort(key=lambda row: int(row["fold_index"]))
    folds = [int(row["fold_index"]) for row in rows]
    no_altitude = [float(row["median_nearest_non_altitude_ard_distance"])
                   for row in rows]
    with_altitude = [float(row["median_nearest_ard_distance"]) for row in rows]
    figure, axis = plt.subplots(figsize=(8, 5), layout="constrained")
    axis.scatter(folds, no_altitude, marker="o", s=75, color="#3c8d74",
                 label="Four axes (same fitted GPR)")
    axis.scatter(folds, with_altitude, marker="s", s=75, color="#9b7539",
                 label="All five axes")
    axis.set_yscale("log")
    axis.set_xticks(folds)
    axis.set_ylim(0.1, 15)
    axis.set_xlabel("Held-out fold")
    axis.set_ylabel("Median nearest training distance (ARD units; log scale)")
    axis.set_title("Trial 2: altitude pushes held-out storms far from training anchors")
    axis.grid(axis="y", alpha=0.2)
    axis.legend(frameon=False)
    figure.savefig(FIGURES / "phase4_trial2_altitude_ard_distance.png", dpi=180)
    plt.close(figure)


def draw_event_deltas(trial: int, path: Path, output: Path) -> None:
    """Input: trial number, event CSV, PNG path. Output: per-storm RMSE change PNG."""
    rows = heldout_rows(path)
    changes = sorted(
        ((row["storm_id"], float(row["gpr_rmse_log_density"])
          - float(row["trial4_rmse_log_density"])) for row in rows),
        key=lambda item: item[1],
    )
    improved = sum(change < 0 for _, change in changes)
    figure, axis = plt.subplots(figsize=(10, 9), layout="constrained")
    axis.barh(range(len(changes)), [change for _, change in changes],
              color=["#3c8d74" if change < 0 else "#b26950" for _, change in changes])
    axis.set_yticks(range(len(changes)), [
        f"{storm_id[1:5]}-{storm_id[5:7]}-{storm_id[7:9]} "
        f"{storm_id[10:12]}:{storm_id[12:14]}"
        for storm_id, _ in changes
    ])
    axis.axvline(0, color="#444444", linewidth=1)
    axis.set_xlabel("GPR RMSE minus fixed P3 Trial 4 RMSE (negative means better)")
    axis.set_title(f"Trial {trial}: {improved}/25 held-out storms improve")
    axis.grid(axis="x", alpha=0.2)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def draw_trial4() -> None:
    """Input: Trial4 five-fold metrics. Output: fold RMSE change PNG."""
    rows = read_rows(TRIAL4_FOLDS)
    if len(rows) != 5 or {int(row["outer_fold_index"]) for row in rows} != set(range(1, 6)):
        raise ValueError("Expected five Trial4 metric folds.")
    rows.sort(key=lambda row: int(row["outer_fold_index"]))
    changes = [float(row["gpr_rmse_log_density"])
               - float(row["trial4_rmse_log_density"]) for row in rows]
    figure, axis = plt.subplots(figsize=(8, 5), layout="constrained")
    axis.bar([f"Fold {index}" for index in range(1, 6)], changes,
             color=["#3c8d74" if change < 0 else "#b26950" for change in changes])
    axis.axhline(0, color="#444444", linewidth=1)
    axis.set_ylabel("GPR RMSE minus fixed P3 Trial 4 RMSE")
    axis.set_title("Trial 4: time, tau, and season have mixed fold results")
    axis.grid(axis="y", alpha=0.2)
    figure.savefig(FIGURES / "phase4_trial4_fold_rmse_change.png", dpi=180)
    plt.close(figure)


def draw_gpr() -> None:
    """Input: four held-out trial CSVs. Output: one GPR comparison PNG."""
    labels = []
    values = []
    baselines = []
    for label, path in HELDOUT_FILES:
        labels.append(label)
        values.append(heldout_rmse(path, "gpr_rmse_log_density"))
        baselines.append(heldout_rmse(path, "trial4_rmse_log_density"))
    if max(baselines) - min(baselines) > 1e-10:
        raise ValueError("Held-out trials do not share the Trial4 baseline.")
    figure, axis = plt.subplots(figsize=(9, 5), layout="constrained")
    bars = axis.bar(labels, values, color="#496b91", width=0.58)
    axis.axhline(baselines[0], color="#444444", linewidth=1.4,
                 linestyle="--", label=f"Fixed Phase 4: {baselines[0]:.5f}")
    for bar, value in zip(bars, values, strict=True):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 0.001,
                  f"{value:.5f}", ha="center", va="bottom", fontsize=10)
    axis.set_ylim(0, 0.145)
    axis.set_ylabel("Held-out log-density RMSE (lower is better)")
    axis.set_title("Can a GPR residual correction transfer to another storm?")
    axis.legend(frameon=False)
    axis.grid(axis="y", alpha=0.2)
    figure.savefig(GPR_FIGURE, dpi=180)
    plt.close(figure)


def draw_gap() -> None:
    """Input: Trial6 regular-gap summary CSV. Output: one gap-method PNG."""
    with TRIAL6_SUMMARY.open(encoding="utf-8-sig", newline="") as source:
        matches = [row for row in csv.DictReader(source)
                   if row["selection"] == "regular_grid"]
    if len(matches) != 1 or int(matches[0]["block_count"]) != 275:
        raise ValueError("Expected one Trial6 regular-gap summary row.")
    row = matches[0]
    labels = ("Fixed P3 Trial 4", "All gaps", "Same-sign ends", "Two shadow checks")
    fields = ("trial4_rmse", "always_interpolate_rmse", "same_sign_rmse",
              "rule_rmse")
    values = [float(row[field]) for field in fields]
    figure, axis = plt.subplots(figsize=(10, 5), layout="constrained")
    bars = axis.bar(labels, values, color=("#777777", "#1261a0", "#3c8d74", "#9b7539"),
                    width=0.6)
    for bar, value in zip(bars, values, strict=True):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 0.002,
                  f"{value:.5f}", ha="center", va="bottom", fontsize=10)
    axis.set_ylim(0, 0.125)
    axis.set_ylabel("Log-density RMSE (lower is better)")
    axis.set_title("Trial 6: the same 275 artificial six-hour gaps")
    axis.grid(axis="y", alpha=0.2)
    figure.savefig(GAP_FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: saved Phase5 trial metrics. Output: seven separate report PNGs."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    draw_trial1()
    draw_trial2()
    draw_event_deltas(3, HELDOUT_FILES[1][1], FIGURES / "phase4_trial3_event_rmse_change.png")
    draw_trial4()
    draw_event_deltas(5, HELDOUT_FILES[3][1], FIGURES / "phase4_trial5_event_rmse_change.png")
    draw_gpr()
    draw_gap()
    print(f"Saved seven Phase 5 report figures in {FIGURES}")


if __name__ == "__main__":
    main()
