"""Calculate orbit size and decay from evenly spaced orbit points."""

from math import pi, sqrt

from satellite_orbit.calc_forces import MU


def calculate_semi_major_axis(point):
    """Input: {position_km, velocity_km_s}
    Output: semi_major_axis_km"""
    x_km, y_km, z_km = point["position_km"]
    vx_km_s, vy_km_s, vz_km_s = point["velocity_km_s"]

    distance_km = sqrt(x_km**2 + y_km**2 + z_km**2)
    speed_km_s = sqrt(vx_km_s**2 + vy_km_s**2 + vz_km_s**2)
    return 1.0 / (2.0 / distance_km - speed_km_s**2 / MU)


def calculate_orbital_response(orbit_points):
    """Input: [{time, position_km, velocity_km_s}, ...]
    Output: {time, instantaneous_a_km, a_mean_km, a_dot_km_s}"""
    if len(orbit_points) < 2:
        raise ValueError("At least two orbit points are required.")

    times = []
    instantaneous_a_km = []

    for point in orbit_points:
        times.append(point["time"])
        instantaneous_a_km.append(calculate_semi_major_axis(point))

    sample_interval_s = (times[1] - times[0]).total_seconds()
    orbit_period_s = 2.0 * pi * sqrt(instantaneous_a_km[0] ** 3 / MU)
    points_per_orbit = round(orbit_period_s / sample_interval_s) + 1

    a_mean_km = [None] * len(orbit_points)
    a_dot_km_s = [None] * len(orbit_points)

    for index in range(points_per_orbit - 1, len(orbit_points)):
        one_orbit_a = instantaneous_a_km[index - points_per_orbit + 1 : index + 1]
        a_mean_km[index] = sum(one_orbit_a) / len(one_orbit_a)

        previous_mean = a_mean_km[index - 1]
        if previous_mean is not None:
            a_dot_km_s[index] = (a_mean_km[index] - previous_mean) / sample_interval_s

    return {
        "time": times,
        "instantaneous_a_km": instantaneous_a_km,
        "a_mean_km": a_mean_km,
        "a_dot_km_s": a_dot_km_s,
    }
