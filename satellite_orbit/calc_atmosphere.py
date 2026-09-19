"""Atmospheric density from NRLMSIS 2.0."""

from datetime import timezone

import numpy as np
from pymsis import Variable, calculate

from satellite_orbit.calc_coordinates import gcrf_to_itrf, itrf_to_geodetic


def add_atmospheric_density(state):
    """Input: GCRF state + {f107_sfu, f107a_sfu, ap_values}
    Output: same state + {density_kg_m3}

    ap_values = [daily, now, -3h, -6h, -9h, avg_12_to_33h, avg_36_to_57h]
    """
    if state["frame"] != "GCRF":
        raise ValueError("Atmosphere state must use GCRF.")

    ap_values = state["ap_values"]
    if len(ap_values) != 7:
        raise ValueError("ap_values must contain 7 values.")

    state_itrf = gcrf_to_itrf(state)
    location = itrf_to_geodetic(state_itrf)

    model_time_utc = state["time"]
    if model_time_utc.tzinfo is not None:
        model_time_utc = model_time_utc.astimezone(timezone.utc).replace(tzinfo=None)

    # pymsis requires degrees and kilometres.
    longitude_deg = np.degrees(location["longitude_rad"])
    latitude_deg = np.degrees(location["latitude_rad"])
    altitude_km = location["altitude_m"] / 1000.0

    result = calculate(
        dates=np.array([model_time_utc]),
        lons=np.array([longitude_deg]),
        lats=np.array([latitude_deg]),
        alts=np.array([altitude_km]),
        f107s=np.array([state["f107_sfu"]]),
        f107as=np.array([state["f107a_sfu"]]),
        aps=np.array([ap_values]),
        version=2.0,
        geomagnetic_activity=-1,
    )

    state_with_density = state.copy()
    state_with_density["density_kg_m3"] = float(
        result[0, Variable.MASS_DENSITY]
    )
    return state_with_density
