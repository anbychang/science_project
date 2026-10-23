"""Match density observations to earlier, comparable orbit environments."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from math import isfinite
from statistics import median


ASCENDING = "ascending"
DESCENDING = "descending"
LOCAL_SOLAR_TIME_HOURS = 24.0
MAX_ORBIT_CLASSIFICATION_GAP_US = 60_000_000


@dataclass(frozen=True)
class DensityObservation:
    """Input: one raw density observation
    Output: {time_us, density_kg_m3, altitude_m, latitude_deg, local_solar_time_h, orbit_id, direction}"""

    time_us: int
    density_kg_m3: float
    altitude_m: float
    latitude_deg: float
    local_solar_time_h: float
    orbit_id: int | None = None
    direction: str | None = None


@dataclass(frozen=True)
class EnvironmentTolerance:
    """Input: allowed differences for one orbit-environment match
    Output: {altitude_m, latitude_deg, local_solar_time_h}"""

    altitude_m: float
    latitude_deg: float
    local_solar_time_h: float


@dataclass(frozen=True)
class DensityBaseline:
    """Input: one matched reference-orbit density set
    Output: {density_median_kg_m3, reference_orbit_count}"""

    density_median_kg_m3: float
    reference_orbit_count: int


@dataclass(frozen=True)
class SortedObservationIndex:
    """Input: sorted field values and observation positions
    Output: binary-search index for one density-observation field"""

    values: tuple[float, ...]
    observation_indices: tuple[int, ...]


@dataclass(frozen=True)
class DirectionEnvironmentIndex:
    """Input: classified references for one orbit direction
    Output: binary-search indexes for comparable density environments"""

    observations: tuple[DensityObservation, ...]
    altitude_index: SortedObservationIndex
    latitude_index: SortedObservationIndex
    local_solar_time_index: SortedObservationIndex


def classify_orbit_observations(
    observations: list[DensityObservation],
) -> list[DensityObservation]:
    """Input: time-ordered raw density observations
    Output: observations with orbit_id and ascending or descending direction"""
    if not observations:
        return []
    if any(
        later.time_us <= earlier.time_us
        for earlier, later in zip(observations, observations[1:])
    ):
        raise ValueError("Density observations must be strictly time ordered.")

    classified = []
    orbit_id: int | None = 0
    next_orbit_id = 1
    for index, observation in enumerate(observations):
        previous_observation = observations[index - 1] if index else None
        next_observation = observations[index + 1] if index + 1 < len(observations) else None
        previous_is_continuous = observations_are_continuous(
            previous_observation,
            observation,
        )
        next_is_continuous = observations_are_continuous(observation, next_observation)
        if previous_observation is not None and not previous_is_continuous:
            orbit_id = None
        if (
            previous_is_continuous
            and previous_observation.latitude_deg < 0.0 <= observation.latitude_deg
        ):
            orbit_id = next_orbit_id
            next_orbit_id += 1
        direction = classified_direction(
            observation,
            previous_observation if previous_is_continuous else next_observation,
        )
        if next_is_continuous:
            direction = orbit_direction(observation, next_observation)
        classified.append(replace(observation, orbit_id=orbit_id, direction=direction))
    return classified


def observations_are_continuous(
    first_observation: DensityObservation | None,
    second_observation: DensityObservation | None,
) -> bool:
    """Input: two adjacent density observations, possibly absent
    Output: whether their source-time gap permits orbit inference"""
    return (
        first_observation is not None
        and second_observation is not None
        and second_observation.time_us - first_observation.time_us
        <= MAX_ORBIT_CLASSIFICATION_GAP_US
    )


def classified_direction(
    observation: DensityObservation,
    adjacent_observation: DensityObservation | None,
) -> str | None:
    """Input: one density observation and a continuous neighbor
    Output: inferred orbit direction, or None when no neighbor is usable"""
    if adjacent_observation is None:
        return None
    if adjacent_observation.time_us < observation.time_us:
        return orbit_direction(adjacent_observation, observation)
    return orbit_direction(observation, adjacent_observation)


def orbit_direction(
    first_observation: DensityObservation,
    second_observation: DensityObservation,
) -> str:
    """Input: two consecutive density observations
    Output: ascending or descending latitude direction"""
    if second_observation.latitude_deg >= first_observation.latitude_deg:
        return ASCENDING
    return DESCENDING


def local_solar_time_difference(
    first_hour: float,
    second_hour: float,
) -> float:
    """Input: two local solar times in hours
    Output: smallest cyclic difference in hours"""
    direct_difference = abs(first_hour - second_hour)
    return min(direct_difference, LOCAL_SOLAR_TIME_HOURS - direct_difference)


def density_baseline(
    observation: DensityObservation,
    references: list[DensityObservation],
    tolerance: EnvironmentTolerance,
) -> DensityBaseline | None:
    """Input: one target observation, earlier classified references, match tolerance
    Output: median of one density median per matching earlier orbit, or None"""
    matching_references = [
        reference
        for reference in references
        if reference.time_us < observation.time_us
        and reference_matches_environment(observation, reference, tolerance)
    ]
    return baseline_from_matching_orbits(matching_references)


def build_reference_environment_index(
    references: list[DensityObservation],
) -> dict[str, DirectionEnvironmentIndex]:
    """Input: classified raw density references
    Output: direction-partitioned binary-search indexes"""
    references_by_direction = {ASCENDING: [], DESCENDING: []}
    for reference in references:
        if reference_matches_classified_reference(reference):
            references_by_direction[reference.direction].append(reference)
    return {
        direction: build_direction_environment_index(observations)
        for direction, observations in references_by_direction.items()
    }


def density_baseline_from_index(
    observation: DensityObservation,
    reference_index: dict[str, DirectionEnvironmentIndex],
    tolerance: EnvironmentTolerance,
) -> DensityBaseline | None:
    """Input: target observation, binary-search reference index, match tolerance
    Output: median of one density median per matching earlier orbit, or None"""
    if observation.direction not in (ASCENDING, DESCENDING):
        raise ValueError("Target observation needs an orbit direction.")
    direction_index = reference_index[observation.direction]
    candidate_sets = [
        observation_indices_in_range(
            direction_index.altitude_index,
            observation.altitude_m - tolerance.altitude_m,
            observation.altitude_m + tolerance.altitude_m,
        ),
        observation_indices_in_range(
            direction_index.latitude_index,
            observation.latitude_deg - tolerance.latitude_deg,
            observation.latitude_deg + tolerance.latitude_deg,
        ),
        local_solar_time_indices(
            direction_index.local_solar_time_index,
            observation.local_solar_time_h,
            tolerance.local_solar_time_h,
        ),
    ]
    matching_indices = intersect_candidate_indices(candidate_sets)
    matching_references = [
        direction_index.observations[index]
        for index in matching_indices
        if direction_index.observations[index].time_us < observation.time_us
    ]
    return baseline_from_matching_orbits(matching_references)


def baseline_from_matching_orbits(
    references: list[DensityObservation],
) -> DensityBaseline | None:
    """Input: matching classified references
    Output: median density with one equal-weight value per reference orbit"""
    orbit_densities = {}
    for reference in references:
        orbit_densities.setdefault(reference.orbit_id, []).append(reference.density_kg_m3)
    if not orbit_densities:
        return None

    orbit_medians = [median(densities) for densities in orbit_densities.values()]
    return DensityBaseline(median(orbit_medians), len(orbit_medians))


def build_direction_environment_index(
    observations: list[DensityObservation],
) -> DirectionEnvironmentIndex:
    """Input: classified references from one ascending or descending direction
    Output: binary-search indexes for time and matching environment fields"""
    immutable_observations = tuple(observations)
    return DirectionEnvironmentIndex(
        observations=immutable_observations,
        altitude_index=build_sorted_observation_index(
            immutable_observations,
            lambda observation: observation.altitude_m,
        ),
        latitude_index=build_sorted_observation_index(
            immutable_observations,
            lambda observation: observation.latitude_deg,
        ),
        local_solar_time_index=build_sorted_observation_index(
            immutable_observations,
            lambda observation: observation.local_solar_time_h,
        ),
    )


def build_sorted_observation_index(
    observations: tuple[DensityObservation, ...],
    value_of,
) -> SortedObservationIndex:
    """Input: immutable observations and one field-value function
    Output: one binary-search field index"""
    indexed_values = sorted(
        (value_of(observation), index) for index, observation in enumerate(observations)
    )
    values, observation_indices = zip(*indexed_values, strict=True) if indexed_values else ((), ())
    return SortedObservationIndex(values, observation_indices)


def observation_indices_in_range(
    observation_index: SortedObservationIndex,
    lower_value: float,
    upper_value: float,
) -> set[int]:
    """Input: field index and inclusive numeric range
    Output: observation positions with values inside the range"""
    start = bisect_left(observation_index.values, lower_value)
    end = bisect_right(observation_index.values, upper_value)
    return set(observation_index.observation_indices[start:end])


def local_solar_time_indices(
    observation_index: SortedObservationIndex,
    target_hour: float,
    tolerance_h: float,
) -> set[int]:
    """Input: local-solar-time index, target hour, cyclic tolerance
    Output: observation positions inside the cyclic local-solar-time range"""
    lower_hour = target_hour - tolerance_h
    upper_hour = target_hour + tolerance_h
    if lower_hour >= 0.0 and upper_hour < LOCAL_SOLAR_TIME_HOURS:
        return observation_indices_in_range(observation_index, lower_hour, upper_hour)
    return observation_indices_in_range(
        observation_index,
        lower_hour % LOCAL_SOLAR_TIME_HOURS,
        LOCAL_SOLAR_TIME_HOURS,
    ) | observation_indices_in_range(
        observation_index,
        0.0,
        upper_hour % LOCAL_SOLAR_TIME_HOURS,
    )


def intersect_candidate_indices(candidate_sets: list[set[int]]) -> set[int]:
    """Input: candidate observation-index sets from independent conditions
    Output: indexes that satisfy every condition"""
    if not candidate_sets:
        return set()
    ordered_sets = sorted(candidate_sets, key=len)
    matching_indices = ordered_sets[0].copy()
    for candidate_set in ordered_sets[1:]:
        matching_indices.intersection_update(candidate_set)
        if not matching_indices:
            break
    return matching_indices


def reference_matches_classified_reference(reference: DensityObservation) -> bool:
    """Input: one classified density reference
    Output: whether it can enter a binary-search reference index"""
    return (
        reference.direction in (ASCENDING, DESCENDING)
        and reference.orbit_id is not None
        and isfinite(reference.density_kg_m3)
        and reference.density_kg_m3 > 0.0
    )


def reference_matches_environment(
    observation: DensityObservation,
    reference: DensityObservation,
    tolerance: EnvironmentTolerance,
) -> bool:
    """Input: target observation, earlier reference, environment tolerance
    Output: whether direction, altitude, latitude, and local solar time match"""
    if observation.direction not in (ASCENDING, DESCENDING):
        raise ValueError("Target observation needs an orbit direction.")
    if reference.direction not in (ASCENDING, DESCENDING) or reference.orbit_id is None:
        raise ValueError("Reference observation needs orbit classification.")
    if not isfinite(reference.density_kg_m3) or reference.density_kg_m3 <= 0.0:
        return False
    return (
        observation.direction == reference.direction
        and abs(observation.altitude_m - reference.altitude_m) <= tolerance.altitude_m
        and abs(observation.latitude_deg - reference.latitude_deg) <= tolerance.latitude_deg
        and local_solar_time_difference(
            observation.local_solar_time_h,
            reference.local_solar_time_h,
        ) <= tolerance.local_solar_time_h
    )
