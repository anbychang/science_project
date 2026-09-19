"""Calculate orbit size and decay from evenly spaced orbit points."""

from math import pi, sqrt

from satellite_orbit.calc_forces import MU_M3_S2


def calculate_semi_major_axis(point):
    """Input: {time, x_gcrf_m, ..., vz_gcrf_m_s}
    Output: semi_major_axis_m"""
    x_m = point["x_gcrf_m"]
    y_m = point["y_gcrf_m"]
    z_m = point["z_gcrf_m"]
    vx_m_s = point["vx_gcrf_m_s"]
    vy_m_s = point["vy_gcrf_m_s"]
    vz_m_s = point["vz_gcrf_m_s"]

    distance_m = sqrt(x_m**2 + y_m**2 + z_m**2)
    speed_m_s = sqrt(vx_m_s**2 + vy_m_s**2 + vz_m_s**2)
    return 1.0 / (2.0 / distance_m - speed_m_s**2 / MU_M3_S2)


def calculate_orbital_response(orbit_points):
    """Input: [{time, x_gcrf_m, ..., vz_gcrf_m_s}, ...]
    Output: [{time, instantaneous_a_m, a_mean_m, a_dot_m_s}, ...]"""
    if len(orbit_points) < 2:
        raise ValueError("At least two orbit points are required.")

    times = []
    instantaneous_a_m = []

    for point in orbit_points:
        times.append(point["time"])
        instantaneous_a_m.append(calculate_semi_major_axis(point))

    sample_interval_s = (times[1] - times[0]).total_seconds()
    orbit_period_s = 2.0 * pi * sqrt(instantaneous_a_m[0] ** 3 / MU_M3_S2)
    points_per_orbit = round(orbit_period_s / sample_interval_s) + 1

    a_mean_m = [None] * len(orbit_points)
    a_dot_m_s = [None] * len(orbit_points)

    for index in range(points_per_orbit - 1, len(orbit_points)):
        one_orbit_a = instantaneous_a_m[index - points_per_orbit + 1 : index + 1]
        a_mean_m[index] = sum(one_orbit_a) / len(one_orbit_a)

        previous_mean = a_mean_m[index - 1]
        if previous_mean is not None:
            a_dot_m_s[index] = (a_mean_m[index] - previous_mean) / sample_interval_s

    response_points = []

    for index in range(len(orbit_points)):
        response_points.append(
            {
                "time": times[index],
                "instantaneous_a_m": instantaneous_a_m[index],
                "a_mean_m": a_mean_m[index],
                "a_dot_m_s": a_dot_m_s[index],
            }
        )

    return response_points
