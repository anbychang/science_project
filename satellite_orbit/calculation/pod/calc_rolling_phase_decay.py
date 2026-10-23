"""Calculate rolling raw and H2/H3 orbital-decay estimators."""

from dataclasses import dataclass
from math import pi

import numpy as np
from numba import njit


MICROSECONDS_PER_SECOND = 1_000_000
HARMONIC_ORDERS = (2, 3)
PARAMETER_COUNT_RAW = 2
PARAMETER_COUNT_JOINT_H2_H3 = 6
STATISTIC_COLUMN_COUNT = 6
RESULT_COLUMN_COUNT = 14
RESULT_RAW_RATE = 0
RESULT_RAW_SIGMA = 1
RESULT_RAW_RESIDUAL = 2
RESULT_JOINT_RATE = 3
RESULT_JOINT_SIGMA = 4
RESULT_JOINT_RESIDUAL = 5
RESULT_SAMPLE_COUNT = 6
RESULT_START_TIME_US = 7
RESULT_PHASE_SPAN_RAD = 8
RESULT_H2_COS_M = 9
RESULT_H2_SIN_M = 10
RESULT_H3_COS_M = 11
RESULT_H3_SIN_M = 12
RESULT_VALID = 13


@dataclass(frozen=True)
class PhaseSeries:
    """Input: one continuous {time_us[], a_m[], unwrapped_u_rad[]} series.
    Output: immutable rolling-estimator source values for one segment."""

    time_us: np.ndarray
    values: np.ndarray


@dataclass(frozen=True)
class WindowEstimate:
    """Input: one phase-orbit count and a PhaseSeries.
    Output: aligned raw and joint-H2/H3 rolling fit arrays in SI units."""

    orbit_count: int
    values: np.ndarray


def calculate_window_estimate(series, orbit_count):
    """Input: PhaseSeries and 3 or 5 complete phase-orbit count.
    Output: WindowEstimate with one raw/joint result per source time."""
    if orbit_count not in (3, 5):
        raise ValueError("Rolling phase decay supports only 3 or 5 orbits.")
    if len(series.time_us) != len(series.values):
        raise ValueError("Phase series time and value arrays must align.")
    if len(series.values) and np.any(np.diff(series.values[:, 1]) <= 0.0):
        raise ValueError("Phase series must be strictly increasing.")
    phase_span_rad = orbit_count * 2.0 * pi
    return WindowEstimate(
        orbit_count,
        _window_statistics(series.time_us, series.values, phase_span_rad),
    )


def solve_window_estimate(estimate):
    """Input: WindowEstimate sufficient statistics for one orbit count.
    Output: {raw, joint} regression arrays with slope and uncertainty in m/s."""
    statistics = estimate.values
    valid = statistics[:, RESULT_VALID] == 1.0
    result = np.full((len(statistics), RESULT_COLUMN_COUNT), np.nan)
    result[:, RESULT_SAMPLE_COUNT] = statistics[:, RESULT_SAMPLE_COUNT]
    result[:, RESULT_START_TIME_US] = statistics[:, RESULT_START_TIME_US]
    result[:, RESULT_PHASE_SPAN_RAD] = statistics[:, RESULT_PHASE_SPAN_RAD]
    result[:, RESULT_VALID] = statistics[:, RESULT_VALID]
    if not np.any(valid):
        return result
    normal, response, value_sum_squares = _stored_statistics(statistics[valid])
    raw = _solve_statistics(
        normal[:, :PARAMETER_COUNT_RAW, :PARAMETER_COUNT_RAW],
        response[:, :PARAMETER_COUNT_RAW],
        value_sum_squares,
        statistics[valid, RESULT_SAMPLE_COUNT],
    )
    joint = _solve_statistics(normal, response, value_sum_squares,
                              statistics[valid, RESULT_SAMPLE_COUNT])
    result[valid, RESULT_RAW_RATE] = raw[0][:, 1]
    result[valid, RESULT_RAW_SIGMA] = raw[1]
    result[valid, RESULT_RAW_RESIDUAL] = raw[2]
    result[valid, RESULT_JOINT_RATE] = joint[0][:, 1]
    result[valid, RESULT_JOINT_SIGMA] = joint[1]
    result[valid, RESULT_JOINT_RESIDUAL] = joint[2]
    result[valid, RESULT_H2_COS_M] = joint[0][:, 2]
    result[valid, RESULT_H2_SIN_M] = joint[0][:, 3]
    result[valid, RESULT_H3_COS_M] = joint[0][:, 4]
    result[valid, RESULT_H3_SIN_M] = joint[0][:, 5]
    return result


def _stored_statistics(rows):
    """Input: valid estimator rows containing flattened normal equations.
    Output: {normal, response, value_sum_squares} arrays for vectorized OLS."""
    normal_stop = RESULT_COLUMN_COUNT + STATISTIC_COLUMN_COUNT ** 2
    normal = rows[:, RESULT_COLUMN_COUNT:normal_stop].reshape(
        -1, STATISTIC_COLUMN_COUNT, STATISTIC_COLUMN_COUNT,
    )
    response_stop = normal_stop + STATISTIC_COLUMN_COUNT
    response = rows[:, normal_stop:response_stop]
    value_sum_squares = rows[:, response_stop]
    return normal, response, value_sum_squares


def _solve_statistics(normal, response, value_sum_squares, sample_count):
    """Input: batched normal equations for linear or H2/H3 OLS.
    Output: {coefficients, slope_1sigma_m_s, residual_std_m}."""
    parameter_count = normal.shape[1]
    centered_normal = normal.copy()
    centered_response = response.copy()
    mean_time_s = centered_normal[:, 0, 1] / sample_count
    original_constant_cross = centered_normal[:, 0, :].copy()
    centered_normal[:, 1, 1] -= (
        2.0 * mean_time_s * original_constant_cross[:, 1]
        - mean_time_s ** 2 * original_constant_cross[:, 0]
    )
    centered_normal[:, 0, 1] = 0.0
    centered_normal[:, 1, 0] = 0.0
    for column_index in range(2, parameter_count):
        cross = (
            centered_normal[:, 1, column_index]
            - mean_time_s * original_constant_cross[:, column_index]
        )
        centered_normal[:, 1, column_index] = cross
        centered_normal[:, column_index, 1] = cross
    centered_response[:, 1] -= mean_time_s * centered_response[:, 0]
    coefficients = np.linalg.solve(
        centered_normal,
        centered_response[..., np.newaxis],
    )[..., 0]
    residual_sum_squares = np.maximum(
        0.0,
        value_sum_squares - np.sum(coefficients * centered_response, axis=1),
    )
    residual_variance = residual_sum_squares / (sample_count - parameter_count)
    slope_unit = np.zeros(parameter_count)
    slope_unit[1] = 1.0
    slope_inverse_column = np.linalg.solve(
        centered_normal,
        np.broadcast_to(slope_unit, centered_response.shape)[..., np.newaxis],
    )[..., 0][:, 1]
    slope_1sigma = np.sqrt(residual_variance * slope_inverse_column)
    return coefficients, slope_1sigma, np.sqrt(residual_variance)


@njit(cache=True)
def _window_statistics(time_us, values, phase_span_rad):
    """Input: aligned time/value arrays and exact trailing phase span.
    Output: rows carrying rolling normal equations plus boundary metadata."""
    row_count = len(time_us)
    stored_column_count = (
        RESULT_COLUMN_COUNT
        + STATISTIC_COLUMN_COUNT * STATISTIC_COLUMN_COUNT
        + STATISTIC_COLUMN_COUNT
        + 1
    )
    output = np.empty((row_count, stored_column_count))
    output[:] = np.nan
    normal = np.zeros((STATISTIC_COLUMN_COUNT, STATISTIC_COLUMN_COUNT))
    response = np.zeros(STATISTIC_COLUMN_COUNT)
    value_sum_squares = 0.0
    sample_count = 0
    first_time_us = time_us[0]
    reference_value_m = values[0, 0]
    first_actual_index = 0
    for end_index in range(row_count):
        time_s = (time_us[end_index] - first_time_us) / MICROSECONDS_PER_SECOND
        value_m = values[end_index, 0] - reference_value_m
        phase_rad = values[end_index, 1]
        _add_sample(normal, response, time_s, value_m, phase_rad, 1.0)
        value_sum_squares += value_m * value_m
        sample_count += 1
        target_phase_rad = phase_rad - phase_span_rad
        if target_phase_rad < values[0, 1]:
            continue
        boundary_index = first_actual_index
        while (
            boundary_index < row_count
            and values[boundary_index, 1] < target_phase_rad
        ):
            boundary_index += 1
        while first_actual_index < boundary_index:
            removed_time_s = (
                time_us[first_actual_index] - first_time_us
            ) / MICROSECONDS_PER_SECOND
            removed_value_m = values[first_actual_index, 0] - reference_value_m
            _add_sample(
                normal,
                response,
                removed_time_s,
                removed_value_m,
                values[first_actual_index, 1],
                -1.0,
            )
            value_sum_squares -= removed_value_m * removed_value_m
            sample_count -= 1
            first_actual_index += 1
        exact_boundary = values[boundary_index, 1] == target_phase_rad
        boundary_time_us = time_us[boundary_index]
        if not exact_boundary:
            lower_index = boundary_index - 1
            phase_fraction = (
                (target_phase_rad - values[lower_index, 1])
                / (values[boundary_index, 1] - values[lower_index, 1])
            )
            boundary_time_us = int(round(
                time_us[lower_index]
                + phase_fraction * (time_us[boundary_index] - time_us[lower_index])
            ))
            boundary_time_s = (
                boundary_time_us - first_time_us
            ) / MICROSECONDS_PER_SECOND
            boundary_value_m = (
                values[lower_index, 0]
                + phase_fraction * (values[boundary_index, 0] - values[lower_index, 0])
                - reference_value_m
            )
            _add_sample(
                normal,
                response,
                boundary_time_s,
                boundary_value_m,
                target_phase_rad,
                1.0,
            )
            value_sum_squares += boundary_value_m * boundary_value_m
            sample_count += 1
        if sample_count > PARAMETER_COUNT_JOINT_H2_H3:
            output[end_index, RESULT_SAMPLE_COUNT] = sample_count
            output[end_index, RESULT_START_TIME_US] = boundary_time_us
            output[end_index, RESULT_PHASE_SPAN_RAD] = phase_rad - target_phase_rad
            output[end_index, RESULT_VALID] = 1.0
            _store_statistics(
                output[end_index], normal, response, value_sum_squares,
            )
        if not exact_boundary:
            _add_sample(
                normal,
                response,
                boundary_time_s,
                boundary_value_m,
                target_phase_rad,
                -1.0,
            )
            value_sum_squares -= boundary_value_m * boundary_value_m
            sample_count -= 1
    return output


@njit(cache=True)
def _add_sample(normal, response, time_s, value_m, phase_rad, factor):
    """Input: normal equations, one phase sample, and +/- update factor.
    Output: normal equations updated in place."""
    row = np.empty(STATISTIC_COLUMN_COUNT)
    row[0] = 1.0
    row[1] = time_s
    row[2] = np.cos(2.0 * phase_rad)
    row[3] = np.sin(2.0 * phase_rad)
    row[4] = np.cos(3.0 * phase_rad)
    row[5] = np.sin(3.0 * phase_rad)
    for left_index in range(STATISTIC_COLUMN_COUNT):
        response[left_index] += factor * row[left_index] * value_m
        for right_index in range(STATISTIC_COLUMN_COUNT):
            normal[left_index, right_index] += (
                factor * row[left_index] * row[right_index]
            )


@njit(cache=True)
def _store_statistics(output_row, normal, response, value_sum_squares):
    """Input: one output row and current rolling normal equations.
    Output: flattened equations stored in that row."""
    normal_start = RESULT_COLUMN_COUNT
    for left_index in range(STATISTIC_COLUMN_COUNT):
        for right_index in range(STATISTIC_COLUMN_COUNT):
            output_row[
                normal_start
                + left_index * STATISTIC_COLUMN_COUNT
                + right_index
            ] = normal[left_index, right_index]
    response_start = normal_start + STATISTIC_COLUMN_COUNT ** 2
    for index in range(STATISTIC_COLUMN_COUNT):
        output_row[response_start + index] = response[index]
    output_row[response_start + STATISTIC_COLUMN_COUNT] = value_sum_squares
