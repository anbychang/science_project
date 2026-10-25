"""Centered means for offline Phase 2 quality checks."""

import math


def centered_mean(
    coordinates: list[float], values: list[float | None], half_width: float
) -> list[float]:
    """Input: sorted coordinates, values, half-width. Output: centered means."""
    if len(coordinates) != len(values):
        raise ValueError("Coordinates and values must have the same length.")
    if not coordinates:
        return []
    if half_width <= 0:
        raise ValueError("Half-width must be positive.")
    if any(left >= right for left, right in zip(coordinates, coordinates[1:])):
        raise ValueError("Coordinates must be strictly increasing.")

    smoothed_values = []
    left_index = 0
    right_index = 0
    valid_sum = 0.0
    valid_count = 0
    first_coordinate = coordinates[0]
    last_coordinate = coordinates[-1]

    for center in coordinates:
        lower_bound = center - half_width
        upper_bound = center + half_width
        while right_index < len(coordinates) and coordinates[right_index] <= upper_bound:
            value = values[right_index]
            if value is not None and math.isfinite(value):
                valid_sum += value
                valid_count += 1
            right_index += 1
        while left_index < right_index and coordinates[left_index] < lower_bound:
            value = values[left_index]
            if value is not None and math.isfinite(value):
                valid_sum -= value
                valid_count -= 1
            left_index += 1

        window_count = right_index - left_index
        has_full_window = lower_bound >= first_coordinate and upper_bound <= last_coordinate
        has_enough_values = window_count > 0 and valid_count / window_count >= 0.80
        smoothed_values.append(
            valid_sum / valid_count
            if has_full_window and has_enough_values and valid_count else math.nan
        )
    return smoothed_values
