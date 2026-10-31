"""Write Trial4's fitted density curves, SQLite tables, and figures."""

import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from calc_trial4_joint_fit import EventFitData, event_response, tau_grid_hours
from prep_trial4_joint_fit import SOURCE, load_density_rows, prepare_events


OUTPUT = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
EXAMPLE_FIGURE = Path("phases/phase4/figures/trial4_joint_fit_tau15_examples.png")
OVERVIEW_FIGURE = Path("phases/phase4/figures/trial4_joint_fit_tau15_25storm_overview.png")
ALGORITHM_VERSION = "trial4_joint_fit_tau15_v1"
MODEL_NAME = "D_free_r_tau"
EXPECTED_STORM_COUNT = 25
EXPECTED_MINUTE_COUNT = 214_907
MICROSECONDS_PER_DAY = 86_400_000_000
PLOT_STEP_MINUTES = 30


@dataclass(frozen=True)
class FittedParameters:
    """Input: D-model SQLite rows. Output: fitted values keyed by storm."""

    gain_per_nt: float
    r_fit_by_storm: dict[str, float]
    tau_hours_by_storm: dict[str, float]
    tau_low_by_storm: dict[str, float]
    tau_high_by_storm: dict[str, float]


@dataclass(frozen=True)
class PredictionSeries:
    """Input: one event's fitted arrays. Output: one Trial4 minute-table series."""

    storm_id: str
    time_us: np.ndarray
    h_phase_nt: np.ndarray
    rho_l2_phase_kg_m3: np.ndarray
    rho_msis_quiet_phase_kg_m3: np.ndarray
    rho_msis_full_phase_kg_m3: np.ndarray
    rho_trial4_joint_phase_kg_m3: np.ndarray
    residual_log_density: np.ndarray
    r_rq: float
    r_fit: float
    tau_hours: float


@dataclass(frozen=True)
class StormOverview:
    """Input: fitted series and frozen event metadata. Output: one 25-storm row."""

    storm_id: str
    t0_time_us: int
    symh_min_nt: int
    valid_phase_minutes: int
    r_rq: float
    r_fit: float
    r_fit_over_r_rq: float
    tau_hours: float
    tau_within_1pct_low_hours: float
    tau_within_1pct_high_hours: float
    gain_per_nt: float
    trial4_joint_rmse_log_density: float
    m0_uncalibrated_rmse_log_density: float


@dataclass(frozen=True)
class JointFitOutput:
    """Input: all fitted series and rows. Output: complete Trial4 derived output."""

    gain_per_nt: float
    series: list[PredictionSeries]
    overview_rows: list[StormOverview]


def load_fitted_parameters() -> FittedParameters:
    """Input: Trial4 A--D result SQLite. Output: final D parameters by storm."""
    uri = f"file:{OUTPUT.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        model_matches = database.execute("""
            SELECT gain_per_nt FROM trial4_joint_fit_models WHERE model=?
        """, (MODEL_NAME,)).fetchall()
        storm_rows = database.execute("""
            SELECT storm_id,r_fit,tau_hours,tau_within_1pct_low_hours,
                   tau_within_1pct_high_hours
            FROM trial4_joint_fit_events WHERE model=?
        """, (MODEL_NAME,)).fetchall()
    if len(model_matches) != 1 or len(storm_rows) != EXPECTED_STORM_COUNT:
        raise ValueError("Trial4 D-model SQLite rows are incomplete.")
    gain_per_nt = float(model_matches[0][0])
    if gain_per_nt <= 0:
        raise ValueError("Trial4 D-model gain must be positive.")
    r_fit_by_storm = {storm_id: float(r_fit) for storm_id, r_fit, *_ in storm_rows}
    tau_hours_by_storm = {storm_id: float(tau_hours)
                          for storm_id, _, tau_hours, *_ in storm_rows}
    if len(r_fit_by_storm) != EXPECTED_STORM_COUNT:
        raise ValueError("Trial4 D-model has duplicate storm IDs.")
    return FittedParameters(
        gain_per_nt=gain_per_nt,
        r_fit_by_storm=r_fit_by_storm,
        tau_hours_by_storm=tau_hours_by_storm,
        tau_low_by_storm={
            storm_id: float(tau_low)
            for storm_id, _, _, tau_low, _ in storm_rows
        },
        tau_high_by_storm={
            storm_id: float(tau_high)
            for storm_id, _, _, _, tau_high in storm_rows
        },
    )


def tau_index(tau_hours: float) -> int:
    """Input: one saved tau value in hours. Output: matching 0.1-hour grid index."""
    matches = np.flatnonzero(np.isclose(tau_grid_hours(), tau_hours))
    if len(matches) != 1:
        raise ValueError(f"Saved tau is not on Trial4 grid: {tau_hours}")
    return int(matches[0])


def load_event_metadata() -> dict[str, tuple[int, int]]:
    """Input: frozen Phase 2 event SQLite. Output: {storm_id: (t0_us, SYM-H)}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT storm_id,t0_time_us,symh_min_nt
            FROM storm_event_t0_phase_v5 ORDER BY t0_time_us
        """).fetchall()
    result = {storm_id: (int(t0_us), int(symh_min_nt))
              for storm_id, t0_us, symh_min_nt in rows}
    if len(result) != EXPECTED_STORM_COUNT:
        raise ValueError("Frozen Phase 2 event metadata changed.")
    return result


def build_joint_output(parameters: FittedParameters) -> JointFitOutput:
    """Input: final D parameters. Output: Trial4 fitted minute series and overview."""
    density_by_storm = load_density_rows()
    events = prepare_events(density_by_storm)
    metadata_by_storm = load_event_metadata()
    if set(parameters.r_fit_by_storm) != set(density_by_storm):
        raise ValueError("Trial4 D parameters and Phase 3 density storms differ.")
    series_rows = []
    overview_rows = []
    for event in events:
        storm_id = event.storm_id
        density = density_by_storm[storm_id]
        r_fit = parameters.r_fit_by_storm[storm_id]
        tau_hours = parameters.tau_hours_by_storm[storm_id]
        response = event_response(event, tau_index(tau_hours))
        prediction = density["rho_msis_quiet_phase_kg_m3"] * r_fit * np.exp(
            parameters.gain_per_nt * response
        )
        residual = np.log(density["rho_l2_phase_kg_m3"] / prediction)
        full_residual = np.log(
            density["rho_l2_phase_kg_m3"] / density["rho_msis_full_phase_kg_m3"]
        )
        if not np.isfinite(prediction).all() or np.any(prediction <= 0):
            raise ValueError(f"Invalid Trial4 prediction: {storm_id}")
        series = PredictionSeries(
            storm_id=storm_id,
            time_us=density["time_us"],
            h_phase_nt=response,
            rho_l2_phase_kg_m3=density["rho_l2_phase_kg_m3"],
            rho_msis_quiet_phase_kg_m3=density["rho_msis_quiet_phase_kg_m3"],
            rho_msis_full_phase_kg_m3=density["rho_msis_full_phase_kg_m3"],
            rho_trial4_joint_phase_kg_m3=prediction,
            residual_log_density=residual,
            r_rq=event.r_rq,
            r_fit=r_fit,
            tau_hours=tau_hours,
        )
        t0_time_us, symh_min_nt = metadata_by_storm[storm_id]
        series_rows.append(series)
        overview_rows.append(StormOverview(
            storm_id=storm_id,
            t0_time_us=t0_time_us,
            symh_min_nt=symh_min_nt,
            valid_phase_minutes=len(response),
            r_rq=event.r_rq,
            r_fit=r_fit,
            r_fit_over_r_rq=r_fit / event.r_rq,
            tau_hours=tau_hours,
            tau_within_1pct_low_hours=parameters.tau_low_by_storm[storm_id],
            tau_within_1pct_high_hours=parameters.tau_high_by_storm[storm_id],
            gain_per_nt=parameters.gain_per_nt,
            trial4_joint_rmse_log_density=float(np.sqrt(np.mean(residual ** 2))),
            m0_uncalibrated_rmse_log_density=float(np.sqrt(np.mean(full_residual ** 2))),
        ))
    result = JointFitOutput(parameters.gain_per_nt, series_rows, overview_rows)
    validate_joint_output(result)
    return result


def validate_joint_output(result: JointFitOutput) -> None:
    """Input: complete Trial4 output. Output: raises unless data contract holds."""
    storm_ids = {series.storm_id for series in result.series}
    minute_count = sum(len(series.time_us) for series in result.series)
    if (len(result.series) != EXPECTED_STORM_COUNT
            or len(result.overview_rows) != EXPECTED_STORM_COUNT
            or len(storm_ids) != EXPECTED_STORM_COUNT
            or minute_count != EXPECTED_MINUTE_COUNT
            or result.gain_per_nt <= 0):
        raise ValueError("Trial4 output count or gain contract failed.")
    for series in result.series:
        if (series.r_fit <= 0 or series.r_fit >= 2 or series.tau_hours < 0
                or series.tau_hours > 15 or len(series.time_us) == 0):
            raise ValueError(f"Trial4 fitted parameter contract failed: {series.storm_id}")


def create_output_schema(database: sqlite3.Connection) -> None:
    """Input: fit-parameter SQLite connection. Output: Trial4 prediction tables."""
    database.executescript("""
        CREATE TABLE trial4_joint_fit_minute (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            h_phase_nt REAL NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL,
            rho_msis_quiet_phase_kg_m3 REAL NOT NULL,
            rho_msis_full_phase_kg_m3 REAL NOT NULL,
            rho_trial4_joint_phase_kg_m3 REAL NOT NULL,
            residual_log_density REAL NOT NULL,
            r_fit REAL NOT NULL,
            tau_hours REAL NOT NULL,
            gain_per_nt REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE trial4_25storm_overview (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL UNIQUE,
            symh_min_nt INTEGER NOT NULL,
            valid_phase_minutes INTEGER NOT NULL,
            r_rq REAL NOT NULL,
            r_fit REAL NOT NULL,
            r_fit_over_r_rq REAL NOT NULL,
            tau_hours REAL NOT NULL,
            tau_within_1pct_low_hours REAL NOT NULL,
            tau_within_1pct_high_hours REAL NOT NULL,
            gain_per_nt REAL NOT NULL,
            trial4_joint_rmse_log_density REAL NOT NULL,
            m0_uncalibrated_rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE trial4_joint_fit_metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def save_sqlite(result: JointFitOutput) -> None:
    """Input: validated Trial4 output. Output: prediction tables in fit SQLite."""
    with closing(sqlite3.connect(OUTPUT)) as database:
        try:
            create_output_schema(database)
            metadata_rows = (
                ("gain_per_nt", str(result.gain_per_nt)),
                ("tau_grid_hours", "0.0..15.0 step 0.1"),
                ("evaluation", "retrospective; event-equal loss; centered phase"),
                ("source", "frozen Phase 3 prediction SQLite and Phase 2 event SQLite"),
            )
            database.executemany(
                "INSERT INTO trial4_joint_fit_metadata VALUES (?,?)", metadata_rows
            )
            for series in result.series:
                values = zip(
                    series.time_us, series.h_phase_nt, series.rho_l2_phase_kg_m3,
                    series.rho_msis_quiet_phase_kg_m3,
                    series.rho_msis_full_phase_kg_m3,
                    series.rho_trial4_joint_phase_kg_m3,
                    series.residual_log_density, strict=True
                )
                database.executemany(
                    "INSERT INTO trial4_joint_fit_minute VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    ((series.storm_id, int(time_us), *(float(value) for value in row),
                      series.r_fit, series.tau_hours, result.gain_per_nt,
                      ALGORITHM_VERSION)
                     for time_us, *row in values),
                )
            database.executemany(
                "INSERT INTO trial4_25storm_overview VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ((row.storm_id, row.t0_time_us, row.symh_min_nt,
                  row.valid_phase_minutes, row.r_rq, row.r_fit,
                  row.r_fit_over_r_rq, row.tau_hours,
                  row.tau_within_1pct_low_hours,
                  row.tau_within_1pct_high_hours, row.gain_per_nt,
                  row.trial4_joint_rmse_log_density,
                  row.m0_uncalibrated_rmse_log_density, ALGORITHM_VERSION)
                 for row in result.overview_rows),
            )
            database.commit()
            validate_saved_sqlite(database, result)
        except Exception:
            database.rollback()
            raise


def validate_saved_sqlite(database: sqlite3.Connection, result: JointFitOutput) -> None:
    """Input: open Trial4 SQLite and expected output. Output: raises on audit failure."""
    storm_count, overview_minutes = database.execute("""
        SELECT count(*),sum(valid_phase_minutes) FROM trial4_25storm_overview
    """).fetchone()
    minute_count = database.execute(
        "SELECT count(*) FROM trial4_joint_fit_minute"
    ).fetchone()[0]
    mismatched = database.execute("""
        SELECT count(*) FROM trial4_25storm_overview AS overview
        WHERE valid_phase_minutes <> (
            SELECT count(*) FROM trial4_joint_fit_minute AS minute
            WHERE minute.storm_id=overview.storm_id
        )
    """).fetchone()[0]
    invalid = database.execute("""
        SELECT count(*) FROM trial4_joint_fit_minute
        WHERE r_fit <= 0 OR r_fit >= 2 OR tau_hours < 0 OR tau_hours > 15
           OR gain_per_nt <= 0
    """).fetchone()[0]
    if (storm_count != len(result.overview_rows)
            or overview_minutes != minute_count
            or minute_count != EXPECTED_MINUTE_COUNT or mismatched or invalid
            or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
        raise ValueError("Trial4 SQLite output failed its key audit.")


def draw_examples(result: JointFitOutput) -> None:
    """Input: Trial4 fitted series. Output: two-event retrospective PNG."""
    selected_storms = ("S20240511T0214", "S20240804T1704")
    series_by_storm = {series.storm_id: series for series in result.series}
    figure, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    for axis, storm_id in zip(axes, selected_storms, strict=True):
        series = series_by_storm[storm_id]
        selected = slice(None, None, PLOT_STEP_MINUTES)
        for values, label, color in (
            (series.rho_l2_phase_kg_m3, "Swarm L2", "#111827"),
            (series.rho_msis_full_phase_kg_m3, "M0 raw", "#64748b"),
            (series.rho_trial4_joint_phase_kg_m3, "Trial4 joint fit", "#2563eb"),
        ):
            axis.plot(
                (series.time_us[selected] - series.time_us[0]) / MICROSECONDS_PER_DAY,
                values[selected] * 1e12, color=color, label=label, linewidth=1
            )
        axis.set(
            ylabel="Density (1e-12 kg/m3)",
            title=f"{storm_id[1:9]}: tau={series.tau_hours:.1f} h, R={series.r_fit:.3f}",
        )
        axis.grid(alpha=0.2)
    axes[0].legend()
    axes[-1].set_xlabel("Days from first valid phase minute")
    EXAMPLE_FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(EXAMPLE_FIGURE, dpi=180)
    plt.close(figure)


def draw_overview(result: JointFitOutput) -> None:
    """Input: Trial4 fitted series. Output: 5x5 all-storm retrospective PNG."""
    overview_by_storm = {row.storm_id: row for row in result.overview_rows}
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                                constrained_layout=True)
    for axis, series in zip(axes.flat, result.series, strict=True):
        overview = overview_by_storm[series.storm_id]
        selected = slice(None, None, PLOT_STEP_MINUTES)
        days_from_t0 = (series.time_us - overview.t0_time_us) / MICROSECONDS_PER_DAY
        for values, label, color in (
            (series.rho_l2_phase_kg_m3, "Swarm L2", "#111827"),
            (series.rho_msis_full_phase_kg_m3, "M0 raw", "#64748b"),
            (series.rho_trial4_joint_phase_kg_m3, "Trial4 joint", "#2563eb"),
        ):
            axis.plot(days_from_t0[selected], values[selected] * 1e12,
                      linewidth=0.9, color=color, label=label)
        axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
        axis.set_title(
            f"{series.storm_id[1:9]}  tau={series.tau_hours:.1f} h", fontsize=8
        )
        axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("Density (1e-12 kg/m3)")
    figure.suptitle("25 storms: L2 (black), M0 raw (gray), Trial4 joint fit (blue)",
                    fontsize=13)
    OVERVIEW_FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OVERVIEW_FIGURE, dpi=180)
    plt.close(figure)


def ensure_outputs_are_new() -> None:
    """Input: planned prediction outputs. Output: raises before any overwrite."""
    existing = [path for path in (EXAMPLE_FIGURE, OVERVIEW_FIGURE) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite Trial4 outputs: {existing}")
    if not OUTPUT.exists():
        raise FileNotFoundError(f"Missing Trial4 fit SQLite: {OUTPUT}")
    with closing(sqlite3.connect(OUTPUT)) as database:
        existing_tables = database.execute("""
            SELECT count(*) FROM sqlite_master
            WHERE type='table' AND name IN (
                'trial4_joint_fit_minute',
                'trial4_25storm_overview',
                'trial4_joint_fit_metadata'
            )
        """).fetchone()[0]
    if existing_tables:
        raise FileExistsError("Trial4 prediction tables already exist.")


def main() -> None:
    """Input: frozen Phase 2/3 data and fit SQLite. Output: prediction SQLite and PNGs."""
    ensure_outputs_are_new()
    result = build_joint_output(load_fitted_parameters())
    save_sqlite(result)
    draw_examples(result)
    draw_overview(result)
    print(f"Saved Trial4 SQLite for {len(result.series)} storms and "
          f"{sum(len(series.time_us) for series in result.series)} phase minutes")


if __name__ == "__main__":
    main()
