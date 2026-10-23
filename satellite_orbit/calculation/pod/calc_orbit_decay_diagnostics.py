"""Calculate periodogram and complete-orbit decay diagnostics."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from math import sqrt

import numpy as np


MICROSECONDS_PER_SECOND = 1_000_000
SECONDS_PER_DAY = 86_400
MAXIMUM_ORBIT_BOUNDARY_GAP_S = 20.0
MINIMUM_PERIOD_S = 15 * 60
MAXIMUM_PERIOD_S = 36 * 60 * 60
MAXIMUM_SPECTRUM_PEAKS = 12
RAW_B_L_METHOD = "raw_b_l_local_ols"
JOINT_H2_H3_METHOD = "joint_h2_h3_local_ols"
H2_H3_ORDERS = (2, 3)


@dataclass(frozen=True)
class OrbitMean:
    """Input: one complete orbit {end time, mean a, start time, chunk}.
    Output: immutable complete-orbit mean record."""

    time_us: int
    semi_major_axis_m: float
    orbit_start_time_us: int
    chunk_id: int


@dataclass(frozen=True)
class Spectrum:
    """Input: uniformly sampled, detrended mean-element series.
    Output: one-sided frequency and power arrays."""

    frequencies_hz: np.ndarray
    powers_m2: np.ndarray
    cadence_s: float


@dataclass(frozen=True)
class SpectrumPeak:
    """Input: one local maximum in a Spectrum.
    Output: {frequency_hz, period_s, power_m2}."""

    frequency_hz: float
    period_s: float
    power_m2: float


@dataclass(frozen=True)
class OrbitDecayFit:
    """Input: one trailing window of complete orbit means.
    Output: rate, OLS uncertainty, residual spread, and support bounds."""

    time_us: int
    window_start_time_us: int
    rate_m_day: float
    rate_1sigma_m_day: float
    residual_std_m: float
    orbit_count: int
    chunk_id: int


@dataclass(frozen=True)
class PhaseHarmonicSample:
    """Input: one raw mean-element value with its orbital phase.
    Output: immutable sample for a local phase-harmonic fit."""

    time_us: int
    semi_major_axis_m: float
    phase_rad: float
    chunk_id: int


@dataclass(frozen=True)
class PhaseHarmonicFit:
    """Input: one local trend plus phase-harmonic OLS window.
    Output: decay slope, uncertainty, residual spread, and conditioning."""

    time_us: int
    window_start_time_us: int
    rate_m_day: float
    rate_1sigma_m_day: float
    residual_std_m: float
    sample_count: int
    harmonic_orders: tuple[int, ...]
    harmonic_coefficients_m: tuple[tuple[int, float, float], ...]
    condition_number: float
    chunk_id: int


@dataclass(frozen=True)
class HarmonicFitConfig:
    """Input: complete-orbit count and included phase-harmonic orders.
    Output: immutable local phase-harmonic fit configuration."""

    orbit_count: int
    harmonic_orders: tuple[int, ...]


@dataclass(frozen=True)
class TwoScaleHarmonicFit:
    """Input: one long harmonic fit and short residual-rate window.
    Output: two-scale H2/H3 removal plus local OLS result."""

    time_us: int
    harmonic_window_start_time_us: int
    rate_window_start_time_us: int
    rate_m_day: float
    rate_1sigma_m_day: float
    residual_std_m: float
    sample_count: int
    harmonic_condition_number: float
    chunk_id: int


@dataclass(frozen=True)
class TwoScaleHarmonicConfig:
    """Input: long harmonic and short decay orbit counts plus H orders.
    Output: immutable two-scale local-decay fit configuration."""

    harmonic_orbit_count: int
    rate_orbit_count: int
    harmonic_orders: tuple[int, ...]


@dataclass(frozen=True)
class LocalRateCandidate:
    """Input: one local raw or joint-H2/H3 fit.
    Output: named candidate with rate, uncertainty, and residual spread."""

    method: str
    rate_m_day: float
    rate_1sigma_m_day: float
    residual_std_m: float
    sample_count: int
    window_start_time_us: int
    chunk_id: int


@dataclass(frozen=True)
class LocalRateStatistics:
    """Input: sufficient statistics for raw and H2/H3 local fits.
    Output: immutable normal equations for one complete orbit."""

    normal_matrix: np.ndarray
    response_vector: np.ndarray
    centered_value_sum_squares_m2: float
    sample_count: int


def ordinary_least_squares(points):
    """Input: [(time_us, semi_major_axis_m), ...].
    Output: {rate_m_day, rate_1sigma_m_day, residual_std_m}."""
    if len(points) < 3:
        raise ValueError("An OLS fit needs at least three orbit means.")
    reference_time_us = points[0][0]
    times_s = [
        (time_us - reference_time_us) / MICROSECONDS_PER_SECOND
        for time_us, _ in points
    ]
    values_m = [value_m for _, value_m in points]
    mean_time_s = sum(times_s) / len(times_s)
    mean_value_m = sum(values_m) / len(values_m)
    time_sum_s2 = sum(
        (time_s - mean_time_s) ** 2 for time_s in times_s
    )
    if time_sum_s2 == 0.0:
        raise ValueError("OLS fit has no time span.")
    slope_m_s = sum(
        (time_s - mean_time_s) * (value_m - mean_value_m)
        for time_s, value_m in zip(times_s, values_m)
    ) / time_sum_s2
    intercept_m = mean_value_m - slope_m_s * mean_time_s
    residual_sum_m2 = sum(
        (value_m - (intercept_m + slope_m_s * time_s)) ** 2
        for time_s, value_m in zip(times_s, values_m)
    )
    residual_variance_m2 = residual_sum_m2 / (len(points) - 2)
    return {
        "rate_m_day": slope_m_s * SECONDS_PER_DAY,
        "rate_1sigma_m_day": sqrt(
            residual_variance_m2 / time_sum_s2
        ) * SECONDS_PER_DAY,
        "residual_std_m": sqrt(residual_variance_m2),
    }


def phase_harmonic_ols(samples, harmonic_orders):
    """Input: one continuous [PhaseHarmonicSample, ...] window and H orders.
    Output: local trend plus selected phase harmonics PhaseHarmonicFit."""
    harmonic_orders = tuple(harmonic_orders)
    parameter_count = 2 + 2 * len(harmonic_orders)
    if not harmonic_orders or any(order < 1 for order in harmonic_orders):
        raise ValueError("Phase fit needs positive harmonic orders.")
    if len(set(harmonic_orders)) != len(harmonic_orders):
        raise ValueError("Phase fit harmonic orders must be unique.")
    if len(samples) <= parameter_count:
        raise ValueError("Phase fit needs more samples than parameters.")
    if not phase_samples_are_continuous(samples):
        raise ValueError("Phase fit samples must be continuous within one chunk.")
    reference_time_us = samples[0].time_us
    time_s = np.asarray([
        (sample.time_us - reference_time_us) / MICROSECONDS_PER_SECOND
        for sample in samples
    ])
    centered_time_day = (time_s - time_s.mean()) / SECONDS_PER_DAY
    phase_rad = np.asarray([sample.phase_rad for sample in samples])
    design_columns = [np.ones(len(samples)), centered_time_day]
    for harmonic_order in harmonic_orders:
        design_columns.extend((
            np.cos(harmonic_order * phase_rad),
            np.sin(harmonic_order * phase_rad),
        ))
    design_matrix = np.column_stack(design_columns)
    values_m = np.asarray([sample.semi_major_axis_m for sample in samples])
    coefficients, _, _, _ = np.linalg.lstsq(design_matrix, values_m, rcond=None)
    residual_m = values_m - design_matrix @ coefficients
    residual_variance_m2 = float(residual_m @ residual_m) / (
        len(samples) - parameter_count
    )
    covariance_m2 = residual_variance_m2 * np.linalg.inv(
        design_matrix.T @ design_matrix,
    )
    harmonic_coefficients_m = tuple(
        (
            harmonic_order,
            float(coefficients[2 + 2 * index]),
            float(coefficients[3 + 2 * index]),
        )
        for index, harmonic_order in enumerate(harmonic_orders)
    )
    return PhaseHarmonicFit(
        samples[-1].time_us,
        samples[0].time_us,
        float(coefficients[1]),
        sqrt(float(covariance_m2[1, 1])),
        sqrt(residual_variance_m2),
        len(samples),
        harmonic_orders,
        harmonic_coefficients_m,
        float(np.linalg.cond(design_matrix)),
        samples[-1].chunk_id,
    )


def phase_samples_are_continuous(samples):
    """Input: ordered [PhaseHarmonicSample, ...].
    Output: whether one chunk has no source gap above the accepted maximum."""
    first_chunk_id = samples[0].chunk_id
    return all(
        later.chunk_id == first_chunk_id
        and 0 < (later.time_us - earlier.time_us) / MICROSECONDS_PER_SECOND
        <= MAXIMUM_ORBIT_BOUNDARY_GAP_S
        for earlier, later in zip(samples, samples[1:])
    )


def phase_harmonic_orbit_fits(orbit_means, samples, configuration):
    """Input: complete OrbitMean values, raw phase samples, and fit configuration.
    Output: selected-H fits over consecutive complete-orbit windows."""
    if configuration.orbit_count < 3:
        raise ValueError("Phase-harmonic fit needs at least three complete orbits.")
    sample_times_us = [sample.time_us for sample in samples]
    fits = []
    current_orbits = []
    for orbit_mean in orbit_means:
        if current_orbits and not is_contiguous_orbit(current_orbits[-1], orbit_mean):
            current_orbits = []
        current_orbits.append(orbit_mean)
        if len(current_orbits) < configuration.orbit_count:
            continue
        if len(current_orbits) > configuration.orbit_count:
            current_orbits.pop(0)
        first_time_us = current_orbits[0].orbit_start_time_us
        last_time_us = current_orbits[-1].time_us
        first_index = bisect_left(sample_times_us, first_time_us)
        last_index = bisect_right(sample_times_us, last_time_us)
        fit_samples = samples[first_index:last_index]
        if not fit_samples:
            continue
        fits.append(phase_harmonic_ols(
            fit_samples, configuration.harmonic_orders,
        ))
    return fits


def raw_phase_orbit_fits(orbit_means, samples, orbit_count):
    """Input: complete OrbitMean values, raw phase samples, and orbit count.
    Output: trailing raw-a OLS fits over consecutive complete-orbit windows."""
    if orbit_count < 3:
        raise ValueError("Raw phase fit needs at least three complete orbits.")
    sample_times_us = [sample.time_us for sample in samples]
    fits = []
    current_orbits = []
    for orbit_mean in orbit_means:
        if current_orbits and not is_contiguous_orbit(current_orbits[-1], orbit_mean):
            current_orbits = []
        current_orbits.append(orbit_mean)
        if len(current_orbits) < orbit_count:
            continue
        if len(current_orbits) > orbit_count:
            current_orbits.pop(0)
        fit_samples = samples_for_orbit_window(
            current_orbits, samples, sample_times_us,
        )
        fit = ordinary_least_squares([
            (sample.time_us, sample.semi_major_axis_m)
            for sample in fit_samples
        ])
        fits.append(OrbitDecayFit(
            orbit_mean.time_us,
            current_orbits[0].orbit_start_time_us,
            fit["rate_m_day"],
            fit["rate_1sigma_m_day"],
            fit["residual_std_m"],
            orbit_count,
            orbit_mean.chunk_id,
        ))
    return fits


def local_rate_candidates(samples):
    """Input: continuous raw phase samples from a complete-orbit window.
    Output: raw-B-L and joint-H2/H3 local rate candidates for the same window."""
    raw_fit = ordinary_least_squares([
        (sample.time_us, sample.semi_major_axis_m)
        for sample in samples
    ])
    harmonic_fit = phase_harmonic_ols(samples, H2_H3_ORDERS)
    return (
        LocalRateCandidate(
            RAW_B_L_METHOD,
            raw_fit["rate_m_day"],
            raw_fit["rate_1sigma_m_day"],
            raw_fit["residual_std_m"],
            len(samples),
            samples[0].time_us,
            samples[-1].chunk_id,
        ),
        LocalRateCandidate(
            JOINT_H2_H3_METHOD,
            harmonic_fit.rate_m_day,
            harmonic_fit.rate_1sigma_m_day,
            harmonic_fit.residual_std_m,
            harmonic_fit.sample_count,
            harmonic_fit.window_start_time_us,
            harmonic_fit.chunk_id,
        ),
    )


def local_rate_statistics(samples, reference_time_us, reference_value_m):
    """Input: one orbit of samples plus chunk time and value references.
    Output: LocalRateStatistics for exact rolling raw and H2/H3 fits."""
    time_day = np.asarray([
        (sample.time_us - reference_time_us)
        / MICROSECONDS_PER_SECOND / SECONDS_PER_DAY
        for sample in samples
    ])
    phase_rad = np.asarray([sample.phase_rad for sample in samples])
    design_matrix = np.column_stack((
        np.ones(len(samples)),
        time_day,
        np.cos(2 * phase_rad),
        np.sin(2 * phase_rad),
        np.cos(3 * phase_rad),
        np.sin(3 * phase_rad),
    ))
    centered_values_m = np.asarray([
        sample.semi_major_axis_m - reference_value_m
        for sample in samples
    ])
    return LocalRateStatistics(
        design_matrix.T @ design_matrix,
        design_matrix.T @ centered_values_m,
        float(centered_values_m @ centered_values_m),
        len(samples),
    )


def combine_local_rate_statistics(statistics):
    """Input: [LocalRateStatistics, ...] from consecutive complete orbits.
    Output: combined sufficient statistics for one local fit window."""
    if not statistics:
        raise ValueError("Local-rate statistics need at least one complete orbit.")
    return LocalRateStatistics(
        sum((statistic.normal_matrix for statistic in statistics)),
        sum((statistic.response_vector for statistic in statistics)),
        sum(statistic.centered_value_sum_squares_m2 for statistic in statistics),
        sum(statistic.sample_count for statistic in statistics),
    )


def local_rate_candidates_from_statistics(statistics, window_start_time_us, chunk_id):
    """Input: combined LocalRateStatistics and window identity.
    Output: raw-B-L and joint-H2/H3 LocalRateCandidate values."""
    raw_fit = _normal_equation_fit(statistics, 2)
    harmonic_fit = _normal_equation_fit(statistics, 6)
    return (
        LocalRateCandidate(
            RAW_B_L_METHOD,
            raw_fit["rate_m_day"],
            raw_fit["rate_1sigma_m_day"],
            raw_fit["residual_std_m"],
            statistics.sample_count,
            window_start_time_us,
            chunk_id,
        ),
        LocalRateCandidate(
            JOINT_H2_H3_METHOD,
            harmonic_fit["rate_m_day"],
            harmonic_fit["rate_1sigma_m_day"],
            harmonic_fit["residual_std_m"],
            statistics.sample_count,
            window_start_time_us,
            chunk_id,
        ),
    )


def _normal_equation_fit(statistics, parameter_count):
    """Input: combined LocalRateStatistics and fitted parameter count.
    Output: {rate_m_day, rate_1sigma_m_day, residual_std_m}."""
    if statistics.sample_count <= parameter_count:
        raise ValueError("Local-rate fit needs more samples than parameters.")
    normal_matrix = statistics.normal_matrix[:parameter_count, :parameter_count].copy()
    response_vector = statistics.response_vector[:parameter_count].copy()
    mean_time_day = normal_matrix[0, 1] / statistics.sample_count
    _center_time_column(normal_matrix, response_vector, mean_time_day)
    coefficients = np.linalg.solve(normal_matrix, response_vector)
    residual_sum_m2 = max(
        0.0,
        statistics.centered_value_sum_squares_m2 - coefficients @ response_vector,
    )
    residual_variance_m2 = residual_sum_m2 / (statistics.sample_count - parameter_count)
    covariance_m2 = residual_variance_m2 * np.linalg.inv(normal_matrix)
    return {
        "rate_m_day": float(coefficients[1]),
        "rate_1sigma_m_day": sqrt(max(0.0, float(covariance_m2[1, 1]))),
        "residual_std_m": sqrt(residual_variance_m2),
    }


def _center_time_column(normal_matrix, response_vector, mean_time_day):
    """Input: normal matrix, response vector, and local time mean in days.
    Output: equations transformed to a zero-mean time column in place."""
    original_constant_cross = normal_matrix[0].copy()
    normal_matrix[1, 1] = (
        normal_matrix[1, 1]
        - 2 * mean_time_day * original_constant_cross[1]
        + mean_time_day ** 2 * original_constant_cross[0]
    )
    normal_matrix[0, 1] = 0.0
    normal_matrix[1, 0] = 0.0
    for index in range(2, len(response_vector)):
        centered_cross = normal_matrix[1, index] - mean_time_day * original_constant_cross[index]
        normal_matrix[1, index] = centered_cross
        normal_matrix[index, 1] = centered_cross
    response_vector[1] -= mean_time_day * response_vector[0]


def subtract_phase_harmonics(samples, harmonic_fit):
    """Input: phase samples and a fitted set of harmonic coefficients.
    Output: samples with only the fitted phase harmonics subtracted."""
    return [
        PhaseHarmonicSample(
            sample.time_us,
            sample.semi_major_axis_m - sum(
                cosine_m * np.cos(order * sample.phase_rad)
                + sine_m * np.sin(order * sample.phase_rad)
                for order, cosine_m, sine_m in harmonic_fit.harmonic_coefficients_m
            ),
            sample.phase_rad,
            sample.chunk_id,
        )
        for sample in samples
    ]


def two_scale_phase_harmonic_fits(orbit_means, samples, configuration):
    """Input: complete orbits, raw phase samples, and two-scale configuration.
    Output: trailing long-harmonic, short-rate TwoScaleHarmonicFit values."""
    validate_two_scale_configuration(configuration)
    sample_times_us = [sample.time_us for sample in samples]
    fits = []
    current_orbits = []
    for orbit_mean in orbit_means:
        if current_orbits and not is_contiguous_orbit(current_orbits[-1], orbit_mean):
            current_orbits = []
        current_orbits.append(orbit_mean)
        if len(current_orbits) < configuration.harmonic_orbit_count:
            continue
        if len(current_orbits) > configuration.harmonic_orbit_count:
            current_orbits.pop(0)
        harmonic_samples = samples_for_orbit_window(
            current_orbits, samples, sample_times_us,
        )
        harmonic_fit = phase_harmonic_ols(
            harmonic_samples, configuration.harmonic_orders,
        )
        rate_orbits = current_orbits[-configuration.rate_orbit_count:]
        rate_samples = samples_for_orbit_window(
            rate_orbits, samples, sample_times_us,
        )
        residual_samples = subtract_phase_harmonics(rate_samples, harmonic_fit)
        rate_fit = ordinary_least_squares([
            (sample.time_us, sample.semi_major_axis_m)
            for sample in residual_samples
        ])
        fits.append(TwoScaleHarmonicFit(
            orbit_mean.time_us,
            current_orbits[0].orbit_start_time_us,
            rate_orbits[0].orbit_start_time_us,
            rate_fit["rate_m_day"],
            rate_fit["rate_1sigma_m_day"],
            rate_fit["residual_std_m"],
            len(residual_samples),
            harmonic_fit.condition_number,
            orbit_mean.chunk_id,
        ))
    return fits


def validate_two_scale_configuration(configuration):
    """Input: TwoScaleHarmonicConfig.
    Output: valid long-harmonic and short-rate window relationship."""
    if configuration.rate_orbit_count < 3:
        raise ValueError("Two-scale rate fit needs at least three complete orbits.")
    if configuration.harmonic_orbit_count < configuration.rate_orbit_count:
        raise ValueError("Harmonic window cannot be shorter than rate window.")


def samples_for_orbit_window(orbit_window, samples, sample_times_us):
    """Input: consecutive OrbitMean values, ordered phase samples, and their times.
    Output: phase samples from the first orbit start through final orbit endpoint."""
    first_index = bisect_left(sample_times_us, orbit_window[0].orbit_start_time_us)
    last_index = bisect_right(sample_times_us, orbit_window[-1].time_us)
    fit_samples = samples[first_index:last_index]
    if not fit_samples:
        raise ValueError("No phase samples cover the requested orbit window.")
    return fit_samples


def detrended_values(samples):
    """Input: uniformly sampled [(time_us, semi_major_axis_m), ...].
    Output: (time_s, linear-detrended a values in m, cadence_s)."""
    if len(samples) < 3:
        raise ValueError("A periodogram needs at least three samples.")
    time_us = np.asarray([sample[0] for sample in samples], dtype=float)
    values_m = np.asarray([sample[1] for sample in samples], dtype=float)
    intervals_s = np.diff(time_us) / MICROSECONDS_PER_SECOND
    cadence_s = float(intervals_s[0])
    if cadence_s <= 0.0 or not np.allclose(intervals_s, cadence_s):
        raise ValueError("Periodogram input must have a fixed sample cadence.")
    time_s = (time_us - time_us[0]) / MICROSECONDS_PER_SECOND
    slope_m_s, intercept_m = np.polyfit(time_s, values_m, 1)
    return time_s, values_m - (intercept_m + slope_m_s * time_s), cadence_s


def calculate_periodogram(samples):
    """Input: uniformly sampled [(time_us, semi_major_axis_m), ...].
    Output: one-sided periodogram of linearly detrended values."""
    _, residual_m, cadence_s = detrended_values(samples)
    frequencies_hz = np.fft.rfftfreq(len(residual_m), d=cadence_s)
    powers_m2 = np.abs(np.fft.rfft(residual_m)) ** 2 / len(residual_m) ** 2
    return Spectrum(frequencies_hz, powers_m2, cadence_s)


def strongest_periodogram_peaks(spectrum):
    """Input: Spectrum from calculate_periodogram.
    Output: strongest separated local peaks in the diagnostic period range."""
    candidates = []
    frequencies_hz = spectrum.frequencies_hz
    powers_m2 = spectrum.powers_m2
    for index in range(1, len(frequencies_hz) - 1):
        frequency_hz = frequencies_hz[index]
        if frequency_hz == 0.0:
            continue
        period_s = 1.0 / frequency_hz
        if not MINIMUM_PERIOD_S <= period_s <= MAXIMUM_PERIOD_S:
            continue
        if powers_m2[index] > powers_m2[index - 1] and powers_m2[index] >= powers_m2[index + 1]:
            candidates.append(SpectrumPeak(
                float(frequency_hz), float(period_s), float(powers_m2[index]),
            ))
    candidates.sort(key=lambda peak: peak.power_m2, reverse=True)
    selected_peaks = []
    for candidate in candidates:
        close_to_selected = any(
            abs(candidate.period_s - peak.period_s) / peak.period_s < 0.1
            for peak in selected_peaks
        )
        if not close_to_selected:
            selected_peaks.append(candidate)
        if len(selected_peaks) == MAXIMUM_SPECTRUM_PEAKS:
            break
    return selected_peaks


def trailing_orbit_fits(orbit_means, orbit_count):
    """Input: ordered OrbitMean values from one or more chunks and window count.
    Output: complete-orbit trailing OLS fits without boundary crossings."""
    if orbit_count < 3:
        raise ValueError("Trailing orbit OLS needs at least three complete orbits.")
    fits = []
    current_chunk = []
    for orbit_mean in orbit_means:
        if current_chunk and not is_contiguous_orbit(current_chunk[-1], orbit_mean):
            current_chunk = []
        current_chunk.append(orbit_mean)
        if len(current_chunk) < orbit_count:
            continue
        if len(current_chunk) > orbit_count:
            current_chunk.pop(0)
        fit = ordinary_least_squares([
            (mean.time_us, mean.semi_major_axis_m) for mean in current_chunk
        ])
        fits.append(OrbitDecayFit(
            orbit_mean.time_us,
            current_chunk[0].orbit_start_time_us,
            fit["rate_m_day"],
            fit["rate_1sigma_m_day"],
            fit["residual_std_m"],
            orbit_count,
            orbit_mean.chunk_id,
        ))
    return fits


def is_contiguous_orbit(previous_orbit, next_orbit):
    """Input: adjacent OrbitMean values.
    Output: whether their chunk and source boundary are continuous."""
    if previous_orbit.chunk_id != next_orbit.chunk_id:
        return False
    boundary_gap_s = (
        next_orbit.orbit_start_time_us - previous_orbit.time_us
    ) / MICROSECONDS_PER_SECOND
    return 0.0 <= boundary_gap_s <= MAXIMUM_ORBIT_BOUNDARY_GAP_S
