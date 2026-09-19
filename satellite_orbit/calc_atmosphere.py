"""Atmospheric density from NRLMSIS 2.0."""

from datetime import timezone

import numpy as np
from pymsis import Variable, calculate


def nrlmsis_density_kg_m3(
    time_utc,
    longitude_deg,
    latitude_deg,
    altitude_km,
    f107_sfu,
    f107a_sfu,
    ap_values,
):
    """Input: {time_utc, longitude_deg, latitude_deg, altitude_km,
    f107_sfu, f107a_sfu, ap_values}
    Output: density_kg_m3

    ap_values = [daily, now, -3h, -6h, -9h, avg_12_to_33h, avg_36_to_57h]
    """
    if len(ap_values) != 7:
        raise ValueError("ap_values must contain 7 values.")

    model_time_utc = time_utc
    if time_utc.tzinfo is not None:
        model_time_utc = time_utc.astimezone(timezone.utc).replace(tzinfo=None)

    result = calculate(
        dates=np.array([model_time_utc]),
        lons=np.array([longitude_deg]),
        lats=np.array([latitude_deg]),
        alts=np.array([altitude_km]),
        f107s=np.array([f107_sfu]),
        f107as=np.array([f107a_sfu]),
        aps=np.array([ap_values]),
        version=2.0,
        geomagnetic_activity=-1,
    )

    return float(result[0, Variable.MASS_DENSITY])
