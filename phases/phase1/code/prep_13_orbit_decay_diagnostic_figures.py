"""Render read-only diagnostics for complete-orbit decay estimates."""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from phases.phase1.code.calc_orbit_decay_diagnostics import (
    HarmonicFitConfig,
    MICROSECONDS_PER_SECOND,
    OrbitDecayFit,
    PhaseHarmonicFit,
    PhaseHarmonicSample,
    TwoScaleHarmonicConfig,
    TwoScaleHarmonicFit,
    calculate_periodogram,
    phase_harmonic_orbit_fits,
    raw_phase_orbit_fits,
    strongest_periodogram_peaks,
    trailing_orbit_fits,
    two_scale_phase_harmonic_fits,
)
from phases.phase1.code.prep_12_orbit_decay_diagnostics import (
    DEFAULT_DATABASE,
    MEAN_ORBIT_TABLE,
    ORBIT_WINDOWS,
    POD_QUALITY_TABLE,
    QUIET_START_UTC,
    QUIET_STOP_UTC,
    read_complete_orbit_means,
    read_quiet_mean_elements,
)
from phases.phase1.code.prep_10_phase_orbit_mean import TWO_PI


DEFAULT_OUTPUT_DIRECTORY = Path("images")
STORM_START_UTC = datetime(2024, 5, 4, tzinfo=timezone.utc)
STORM_STOP_UTC = datetime(2024, 5, 12, tzinfo=timezone.utc)
PHASE_FIT_PADDING = timedelta(hours=36)
HARMONIC_FIT_ORBIT_COUNT = 20
RATE_FIT_ORBIT_COUNT = 3
H2_H3_ORDERS = (2, 3)
H1_TO_H5_ORDERS = (1, 2, 3, 4, 5)
FIGURE_DPI = 180
RAW_MARKER_SIZE = 2
ORBIT_MARKER_SIZE = 9


def connect_read_only(database_path: Path) -> sqlite3.Connection:
    """Input: existing SQLite database path.
    Output: read-only SQLite connection that does not request a write lock."""
    database_uri = database_path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True)


def utc_datetimes(time_us_values: list[int]) -> list[datetime]:
    """Input: Unix microsecond timestamps.
    Output: matching timezone-aware UTC datetimes."""
    return [
        datetime.fromtimestamp(time_us / MICROSECONDS_PER_SECOND, timezone.utc)
        for time_us in time_us_values
    ]


def configure_time_axis(axis: plt.Axes) -> None:
    """Input: Matplotlib axis with UTC dates.
    Output: concise UTC labels and a light grid."""
    locator = mdates.AutoDateLocator(minticks=5, maxticks=9)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axis.grid(alpha=0.25)


def linear_residuals(rows: list[tuple[int, float]]) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Input: [(time_us, semi_major_axis_m), ...].
    Output: (relative time s, residual m, slope m/s, intercept m)."""
    if len(rows) < 3:
        raise ValueError("A linear residual series needs at least three rows.")
    time_us = np.asarray([row[0] for row in rows], dtype=float)
    values_m = np.asarray([row[1] for row in rows], dtype=float)
    relative_time_s = (time_us - time_us[0]) / MICROSECONDS_PER_SECOND
    slope_m_s, intercept_m = np.polyfit(relative_time_s, values_m, 1)
    residual_m = values_m - (intercept_m + slope_m_s * relative_time_s)
    return relative_time_s, residual_m, float(slope_m_s), float(intercept_m)


def read_phase_harmonic_samples(
    connection: sqlite3.Connection, start_time_us: int, stop_time_us: int,
) -> list[PhaseHarmonicSample]:
    """Input: SQLite connection and UTC [start, stop) bounds.
    Output: usable B-L samples with raw phase u in the requested interval."""
    rows = connection.execute(f"""
        SELECT mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad,
               quality.chunk_id
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {POD_QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1
          AND quality.chunk_id IS NOT NULL
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
          AND mean.time_us >= ? AND mean.time_us < ?
        ORDER BY mean.time_us
    """, (start_time_us, stop_time_us)).fetchall()
    return [
        PhaseHarmonicSample(
            time_us, semi_major_axis_m,
            (argument_of_perigee_rad + mean_anomaly_rad) % TWO_PI,
            chunk_id,
        )
        for (
            time_us, semi_major_axis_m, argument_of_perigee_rad,
            mean_anomaly_rad, chunk_id,
        ) in rows
    ]


def time_window_orbit_means(orbit_means, start_utc: datetime, stop_utc: datetime):
    """Input: complete orbit means and UTC [start, stop) bounds.
    Output: complete orbit means ending inside the requested interval."""
    start_us = int(start_utc.timestamp() * MICROSECONDS_PER_SECOND)
    stop_us = int(stop_utc.timestamp() * MICROSECONDS_PER_SECOND)
    return [
        orbit_mean for orbit_mean in orbit_means
        if start_us <= orbit_mean.time_us < stop_us
    ]


def calculate_storm_harmonic_fits(orbit_means, samples):
    """Input: padded May-2024 complete orbits and raw phase samples.
    Output: {orbit window: {harmonic orders: storm-ending joint OLS fits}}."""
    configurations = [
        HarmonicFitConfig(orbit_window, H2_H3_ORDERS)
        for orbit_window in ORBIT_WINDOWS
    ] + [
        HarmonicFitConfig(orbit_window, H1_TO_H5_ORDERS)
        for orbit_window in ORBIT_WINDOWS
    ]
    return {
        orbit_window: {
            configuration.harmonic_orders: time_window_fits(
                phase_harmonic_orbit_fits(orbit_means, samples, configuration),
                STORM_START_UTC, STORM_STOP_UTC,
            )
            for configuration in configurations
            if configuration.orbit_count == orbit_window
        }
        for orbit_window in ORBIT_WINDOWS
    }


def calculate_storm_two_scale_fits(orbit_means, samples):
    """Input: padded May-2024 complete orbits and raw phase samples.
    Output: May-ending 20-orbit H2/H3 then 3-orbit OLS fits."""
    configuration = TwoScaleHarmonicConfig(
        HARMONIC_FIT_ORBIT_COUNT, RATE_FIT_ORBIT_COUNT, H2_H3_ORDERS,
    )
    return time_window_fits(
        two_scale_phase_harmonic_fits(orbit_means, samples, configuration),
        STORM_START_UTC, STORM_STOP_UTC,
    )


def calculate_storm_raw_fits(orbit_means, samples):
    """Input: padded May-2024 complete orbits and raw phase samples.
    Output: {orbit window: May-ending raw B-L OLS fits without H2/H3}."""
    return {
        orbit_window: time_window_fits(
            raw_phase_orbit_fits(orbit_means, samples, orbit_window),
            STORM_START_UTC, STORM_STOP_UTC,
        )
        for orbit_window in ORBIT_WINDOWS
    }


def save_phase_harmonic_comparison(
    fits_by_window: dict[int, dict[tuple[int, ...], list[PhaseHarmonicFit]]],
    output_path: Path,
) -> None:
    """Input: May-2024 H2/H3 and H1--H5 joint fits with PNG destination.
    Output: saved decay-rate and residual comparison figure."""
    figure, axes = plt.subplots(
        len(ORBIT_WINDOWS), 2, figsize=(15, 8), sharex="col", constrained_layout=True,
    )
    colors = {H2_H3_ORDERS: "tab:blue", H1_TO_H5_ORDERS: "tab:orange"}
    labels = {H2_H3_ORDERS: "joint trend + H2/H3", H1_TO_H5_ORDERS: "joint trend + H1-H5"}
    for row_index, orbit_window in enumerate(ORBIT_WINDOWS):
        rate_axis, residual_axis = axes[row_index]
        for harmonic_orders in (H2_H3_ORDERS, H1_TO_H5_ORDERS):
            fits = fits_by_window[orbit_window][harmonic_orders]
            dates = utc_datetimes([fit.time_us for fit in fits])
            rate_axis.plot(
                dates, [fit.rate_m_day for fit in fits],
                color=colors[harmonic_orders], linewidth=1.0,
                label=labels[harmonic_orders],
            )
            residual_axis.plot(
                dates, [fit.residual_std_m for fit in fits],
                color=colors[harmonic_orders], linewidth=1.0,
                label=labels[harmonic_orders],
            )
        rate_axis.set_title(f"{orbit_window}-orbit local trend")
        rate_axis.set_ylabel("Decay rate (m/day)")
        residual_axis.set_title(f"{orbit_window}-orbit fit residual")
        residual_axis.set_ylabel("Residual standard deviation (m)")
        rate_axis.legend(loc="lower left")
        residual_axis.legend(loc="upper right")
        configure_time_axis(rate_axis)
        configure_time_axis(residual_axis)
    figure.suptitle("May 2024: joint phase-harmonic OLS sensitivity")
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_two_scale_harmonic_comparison(
    joint_fits: list[PhaseHarmonicFit],
    two_scale_fits: list[TwoScaleHarmonicFit],
    output_path: Path,
) -> None:
    """Input: 3-orbit joint and 20-orbit-H2/H3 then 3-orbit OLS fits.
    Output: saved two-scale rate and residual comparison figure."""
    figure, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, constrained_layout=True)
    joint_dates = utc_datetimes([fit.time_us for fit in joint_fits])
    two_scale_dates = utc_datetimes([fit.time_us for fit in two_scale_fits])
    axes[0].plot(
        joint_dates, [fit.rate_m_day for fit in joint_fits], color="tab:blue",
        linewidth=1.0, label="3-orbit joint trend + H2/H3",
    )
    axes[0].plot(
        two_scale_dates, [fit.rate_m_day for fit in two_scale_fits], color="tab:purple",
        linewidth=1.0, label="trailing 20-orbit H2/H3, then 3-orbit OLS",
    )
    axes[0].set_title("May 2024: two-scale H2/H3 sensitivity")
    axes[0].set_ylabel("Decay rate (m/day)")
    axes[0].legend(loc="lower left")
    axes[1].plot(
        joint_dates, [fit.residual_std_m for fit in joint_fits], color="tab:blue",
        linewidth=1.0, label="3-orbit joint fit residual",
    )
    axes[1].plot(
        two_scale_dates, [fit.residual_std_m for fit in two_scale_fits], color="tab:purple",
        linewidth=1.0, label="3-orbit residual OLS after 20-orbit H2/H3",
    )
    axes[1].set_ylabel("Residual standard deviation (m)")
    axes[1].legend(loc="upper right")
    for axis in axes:
        configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_raw_harmonic_comparison(
    raw_fits: list[OrbitDecayFit],
    joint_fits: list[PhaseHarmonicFit],
    output_path: Path,
) -> None:
    """Input: raw-only and joint H2/H3 three-orbit May fits.
    Output: saved rate and residual effect of H2/H3 figure."""
    figure, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, constrained_layout=True)
    raw_dates = utc_datetimes([fit.time_us for fit in raw_fits])
    joint_dates = utc_datetimes([fit.time_us for fit in joint_fits])
    axes[0].plot(
        raw_dates, [fit.rate_m_day for fit in raw_fits], color="tab:gray",
        linewidth=1.0, label="raw B-L a, 3-orbit OLS",
    )
    axes[0].plot(
        joint_dates, [fit.rate_m_day for fit in joint_fits], color="tab:blue",
        linewidth=1.0, label="joint trend + H2/H3, 3-orbit OLS",
    )
    axes[0].set_title("May 2024: effect of H2/H3 on a three-orbit slope")
    axes[0].set_ylabel("Decay rate (m/day)")
    axes[0].legend(loc="lower left")
    axes[1].plot(
        raw_dates, [fit.residual_std_m for fit in raw_fits], color="tab:gray",
        linewidth=1.0, label="raw-only OLS residual",
    )
    axes[1].plot(
        joint_dates, [fit.residual_std_m for fit in joint_fits], color="tab:blue",
        linewidth=1.0, label="joint H2/H3 residual",
    )
    axes[1].set_ylabel("Residual standard deviation (m)")
    axes[1].legend(loc="upper right")
    for axis in axes:
        configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_four_candidate_comparison(
    raw_fits_by_window: dict[int, list[OrbitDecayFit]],
    harmonic_fits_by_window: dict[int, dict[tuple[int, ...], list[PhaseHarmonicFit]]],
    output_path: Path,
) -> None:
    """Input: raw and joint-H2/H3 3/5-orbit May fits.
    Output: saved four-candidate rate and residual comparison figure."""
    figure, axes = plt.subplots(
        len(ORBIT_WINDOWS), 2, figsize=(15, 8), sharex="col", constrained_layout=True,
    )
    for row_index, orbit_window in enumerate(ORBIT_WINDOWS):
        raw_fits = raw_fits_by_window[orbit_window]
        harmonic_fits = harmonic_fits_by_window[orbit_window][H2_H3_ORDERS]
        raw_dates = utc_datetimes([fit.time_us for fit in raw_fits])
        harmonic_dates = utc_datetimes([fit.time_us for fit in harmonic_fits])
        rate_axis, residual_axis = axes[row_index]
        rate_axis.plot(
            raw_dates, [fit.rate_m_day for fit in raw_fits], color="tab:gray",
            linewidth=1.0, label="raw B-L a",
        )
        rate_axis.plot(
            harmonic_dates, [fit.rate_m_day for fit in harmonic_fits], color="tab:blue",
            linewidth=1.0, label="joint H2/H3",
        )
        rate_axis.set_title(f"{orbit_window}-orbit decay rate")
        rate_axis.set_ylabel("Decay rate (m/day)")
        rate_axis.legend(loc="lower left")
        residual_axis.plot(
            raw_dates, [fit.residual_std_m for fit in raw_fits], color="tab:gray",
            linewidth=1.0, label="raw-only OLS residual",
        )
        residual_axis.plot(
            harmonic_dates, [fit.residual_std_m for fit in harmonic_fits], color="tab:blue",
            linewidth=1.0, label="joint H2/H3 residual",
        )
        residual_axis.set_title(f"{orbit_window}-orbit residual")
        residual_axis.set_ylabel("Residual standard deviation (m)")
        residual_axis.legend(loc="upper right")
        configure_time_axis(rate_axis)
        configure_time_axis(residual_axis)
    figure.suptitle("May 2024: four retained local-decay candidates")
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_quiet_periodogram(rows: list[tuple[int, float]], output_path: Path) -> None:
    """Input: uniform quiet raw B-L mean-element rows and PNG destination.
    Output: saved residual periodogram figure."""
    spectrum = calculate_periodogram(rows)
    frequencies_hz = spectrum.frequencies_hz[1:]
    periods_min = 1.0 / frequencies_hz / 60.0
    powers_m2 = spectrum.powers_m2[1:]
    selected = (periods_min >= 15.0) & (periods_min <= 36.0 * 60.0)
    peaks = strongest_periodogram_peaks(spectrum)
    figure, axis = plt.subplots(figsize=(11, 4.5), constrained_layout=True)
    axis.semilogx(periods_min[selected], powers_m2[selected], color="tab:blue", linewidth=0.9)
    for peak in peaks[:5]:
        period_min = peak.period_s / 60.0
        axis.axvline(period_min, color="tab:orange", linewidth=0.8, alpha=0.75)
    peak_text = "\n".join(
        f"peak {index}: {peak.period_s / 60.0:.1f} min"
        for index, peak in enumerate(peaks[:5], start=1)
    )
    axis.text(
        0.01, 0.98, peak_text, transform=axis.transAxes,
        va="top", ha="left", fontsize=8,
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
    )
    axis.invert_xaxis()
    axis.set_title("Quiet period residual spectrum: 2023-12-25 to 2024-01-01")
    axis.set_xlabel("Period (minutes; longer periods at left)")
    axis.set_ylabel("Power (m^2)")
    axis.grid(alpha=0.25)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_quiet_orbit_mean(
    raw_rows: list[tuple[int, float]], orbit_rows, output_path: Path,
) -> None:
    """Input: quiet raw rows, all complete-orbit means, and PNG destination.
    Output: saved raw-versus-complete-orbit residual figure."""
    _, raw_residual_m, slope_m_s, intercept_m = linear_residuals(raw_rows)
    raw_start_time_us = raw_rows[0][0]
    quiet_start_us = int(QUIET_START_UTC.timestamp() * MICROSECONDS_PER_SECOND)
    quiet_stop_us = int(QUIET_STOP_UTC.timestamp() * MICROSECONDS_PER_SECOND)
    quiet_orbits = [
        orbit for orbit in orbit_rows
        if quiet_start_us <= orbit.time_us < quiet_stop_us
    ]
    orbit_dates = utc_datetimes([orbit.time_us for orbit in quiet_orbits])
    orbit_residual_m = [
        orbit.semi_major_axis_m - (
            intercept_m + slope_m_s * (orbit.time_us - raw_start_time_us) / MICROSECONDS_PER_SECOND
        )
        for orbit in quiet_orbits
    ]
    figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    axis.scatter(
        utc_datetimes([row[0] for row in raw_rows]), raw_residual_m,
        s=RAW_MARKER_SIZE, alpha=0.3, label="10-minute B-L mean a after linear trend",
    )
    axis.scatter(
        orbit_dates, orbit_residual_m, s=ORBIT_MARKER_SIZE,
        color="tab:orange", label="complete-orbit phase mean",
    )
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_title("Quiet period: raw B-L residual and complete-orbit mean")
    axis.set_ylabel("Residual semi-major axis (m)")
    axis.legend(loc="upper right")
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def time_window_fits(
    fits: list[OrbitDecayFit], start_utc: datetime, stop_utc: datetime,
) -> list[OrbitDecayFit]:
    """Input: trailing fits and UTC [start, stop) bounds.
    Output: fits ending inside the requested interval."""
    start_us = int(start_utc.timestamp() * MICROSECONDS_PER_SECOND)
    stop_us = int(stop_utc.timestamp() * MICROSECONDS_PER_SECOND)
    return [fit for fit in fits if start_us <= fit.time_us < stop_us]


def quiet_rate_summary(fits: list[OrbitDecayFit]) -> tuple[float, float]:
    """Input: trailing fits ending in the configured quiet period.
    Output: (mean m/day, sample standard deviation m/day)."""
    quiet_fits = time_window_fits(fits, QUIET_START_UTC, QUIET_STOP_UTC)
    if len(quiet_fits) < 2:
        raise ValueError("Quiet period has too few trailing fits.")
    rates_m_day = [fit.rate_m_day for fit in quiet_fits]
    return mean(rates_m_day), stdev(rates_m_day)


def save_storm_decay(
    fits_by_window: dict[int, list[OrbitDecayFit]], output_path: Path,
) -> None:
    """Input: {orbit window: trailing fits} and PNG destination.
    Output: saved May-2024 storm decay-rate figure with quiet 3-sigma bands."""
    figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    colors = {3: "tab:blue", 5: "tab:orange"}
    for orbit_window in ORBIT_WINDOWS:
        fits = fits_by_window[orbit_window]
        storm_fits = time_window_fits(fits, STORM_START_UTC, STORM_STOP_UTC)
        quiet_mean_m_day, quiet_std_m_day = quiet_rate_summary(fits)
        color = colors[orbit_window]
        axis.plot(
            utc_datetimes([fit.time_us for fit in storm_fits]),
            [fit.rate_m_day for fit in storm_fits], color=color, linewidth=1.1,
            label=f"{orbit_window}-orbit trailing OLS",
        )
        axis.axhline(quiet_mean_m_day, color=color, linewidth=0.7, alpha=0.7)
        axis.axhspan(
            quiet_mean_m_day - 3.0 * quiet_std_m_day,
            quiet_mean_m_day + 3.0 * quiet_std_m_day,
            color=color, alpha=0.08,
        )
    axis.set_title("May 2024 storm: complete-orbit trailing decay rate")
    axis.set_ylabel("Decay rate (m/day)")
    axis.legend(loc="lower left")
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_orbit_decay_diagnostic_figures(
    database_path: Path = DEFAULT_DATABASE,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
) -> dict[str, Path]:
    """Input: existing P1.5 SQLite path and output directory.
    Output: {periodogram_png, quiet_mean_png, storm_decay_png}."""
    if not database_path.exists():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    connection = connect_read_only(database_path)
    try:
        quiet_rows = read_quiet_mean_elements(connection)
        orbit_rows = read_complete_orbit_means(connection)
        phase_fit_start_utc = STORM_START_UTC - PHASE_FIT_PADDING
        phase_fit_orbits = time_window_orbit_means(
            orbit_rows, phase_fit_start_utc, STORM_STOP_UTC,
        )
        phase_fit_samples = read_phase_harmonic_samples(
            connection,
            int(phase_fit_start_utc.timestamp() * MICROSECONDS_PER_SECOND),
            int(STORM_STOP_UTC.timestamp() * MICROSECONDS_PER_SECOND),
        )
    finally:
        connection.close()
    output_directory.mkdir(parents=True, exist_ok=True)
    fits_by_window = {
        orbit_window: trailing_orbit_fits(orbit_rows, orbit_window)
        for orbit_window in ORBIT_WINDOWS
    }
    harmonic_fits_by_window = calculate_storm_harmonic_fits(
        phase_fit_orbits, phase_fit_samples,
    )
    two_scale_fits = calculate_storm_two_scale_fits(
        phase_fit_orbits, phase_fit_samples,
    )
    raw_fits_by_window = calculate_storm_raw_fits(
        phase_fit_orbits, phase_fit_samples,
    )
    figure_paths = {
        "periodogram_png": output_directory / "orbit-decay-quiet-periodogram-2023-12-25.png",
        "quiet_mean_png": output_directory / "orbit-decay-quiet-complete-orbit-2023-12-25.png",
        "storm_decay_png": output_directory / "orbit-decay-storm-3-5-orbit-2024-05.png",
        "phase_harmonic_png": output_directory / "orbit-decay-storm-h2h3-h1h5-2024-05.png",
        "two_scale_png": output_directory / "orbit-decay-storm-h2h3-20orbit-3orbit-2024-05.png",
        "raw_harmonic_png": output_directory / "orbit-decay-storm-raw-h2h3-3orbit-2024-05.png",
        "four_candidates_png": output_directory / "orbit-decay-storm-four-candidates-2024-05.png",
    }
    save_quiet_periodogram(quiet_rows, figure_paths["periodogram_png"])
    save_quiet_orbit_mean(quiet_rows, orbit_rows, figure_paths["quiet_mean_png"])
    save_storm_decay(fits_by_window, figure_paths["storm_decay_png"])
    save_phase_harmonic_comparison(
        harmonic_fits_by_window, figure_paths["phase_harmonic_png"],
    )
    save_two_scale_harmonic_comparison(
        harmonic_fits_by_window[RATE_FIT_ORBIT_COUNT][H2_H3_ORDERS],
        two_scale_fits, figure_paths["two_scale_png"],
    )
    save_raw_harmonic_comparison(
        raw_fits_by_window[RATE_FIT_ORBIT_COUNT],
        harmonic_fits_by_window[RATE_FIT_ORBIT_COUNT][H2_H3_ORDERS],
        figure_paths["raw_harmonic_png"],
    )
    save_four_candidate_comparison(
        raw_fits_by_window, harmonic_fits_by_window,
        figure_paths["four_candidates_png"],
    )
    return figure_paths


def main() -> None:
    """Input: python -m ...prep_13_orbit_decay_diagnostic_figures [DATABASE] [OUTPUT_DIR].
    Output: paths of three read-only diagnostic PNG files."""
    arguments = sys.argv[1:]
    if len(arguments) > 2:
        raise ValueError("Usage: [DATABASE] [OUTPUT_DIR]")
    database_path = Path(arguments[0]) if arguments else DEFAULT_DATABASE
    output_directory = Path(arguments[1]) if len(arguments) == 2 else DEFAULT_OUTPUT_DIRECTORY
    for figure_path in save_orbit_decay_diagnostic_figures(database_path, output_directory).values():
        print(figure_path)


if __name__ == "__main__":
    main()
