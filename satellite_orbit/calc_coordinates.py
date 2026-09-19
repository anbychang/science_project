"""Change satellite states between GCRF and ITRF.

Astropy calls these systems GCRS and ITRS. GCRF and ITRF are their practical
reference frames.
"""

import astropy.units as u
import numpy as np
from astropy.coordinates import (
    EarthLocation,
    GCRS,
    ITRS,
    CartesianDifferential,
    CartesianRepresentation,
)
from astropy.time import Time


def gcrf_to_itrf(time_utc, position_gcrf_km, velocity_gcrf_km_s):
    """Input: {time_utc, position_gcrf_km, velocity_gcrf_km_s}
    Output: {position_itrf_km, velocity_itrf_km_s}"""
    time = Time(time_utc, scale="utc")
    position = np.asarray(position_gcrf_km) * u.km
    velocity = np.asarray(velocity_gcrf_km_s) * u.km / u.s

    state = CartesianRepresentation(
        position,
        differentials=CartesianDifferential(velocity),
    )
    gcrf_state = GCRS(state, obstime=time)
    itrf_state = gcrf_state.transform_to(ITRS(obstime=time))

    position_itrf_km = itrf_state.cartesian.xyz.to_value(u.km)
    velocity_itrf = itrf_state.cartesian.differentials["s"].d_xyz
    velocity_itrf_km_s = velocity_itrf.to_value(u.km / u.s)

    return {
        "position_itrf_km": position_itrf_km,
        "velocity_itrf_km_s": velocity_itrf_km_s,
    }


def itrf_to_gcrf(time_utc, position_itrf_km, velocity_itrf_km_s):
    """Input: {time_utc, position_itrf_km, velocity_itrf_km_s}
    Output: {position_gcrf_km, velocity_gcrf_km_s}"""
    time = Time(time_utc, scale="utc")
    position = np.asarray(position_itrf_km) * u.km
    velocity = np.asarray(velocity_itrf_km_s) * u.km / u.s

    state = CartesianRepresentation(
        position,
        differentials=CartesianDifferential(velocity),
    )
    itrf_state = ITRS(state, obstime=time)
    gcrf_state = itrf_state.transform_to(GCRS(obstime=time))

    position_gcrf_km = gcrf_state.cartesian.xyz.to_value(u.km)
    velocity_gcrf = gcrf_state.cartesian.differentials["s"].d_xyz
    velocity_gcrf_km_s = velocity_gcrf.to_value(u.km / u.s)

    return {
        "position_gcrf_km": position_gcrf_km,
        "velocity_gcrf_km_s": velocity_gcrf_km_s,
    }


def gcrf_vector_to_itrf(time_utc, vector_gcrf):
    """Input: {time_utc, vector_gcrf = [x, y, z]}
    Output: vector_itrf = [x, y, z] with the same unit"""
    time = Time(time_utc, scale="utc")
    vector = CartesianRepresentation(np.asarray(vector_gcrf) * u.km)
    gcrf_vector = GCRS(vector, obstime=time)
    itrf_vector = gcrf_vector.transform_to(ITRS(obstime=time))
    return itrf_vector.cartesian.xyz.to_value(u.km)


def itrf_vector_to_gcrf(time_utc, vector_itrf):
    """Input: {time_utc, vector_itrf = [x, y, z]}
    Output: vector_gcrf = [x, y, z] with the same unit"""
    time = Time(time_utc, scale="utc")
    vector = CartesianRepresentation(np.asarray(vector_itrf) * u.km)
    itrf_vector = ITRS(vector, obstime=time)
    gcrf_vector = itrf_vector.transform_to(GCRS(obstime=time))
    return gcrf_vector.cartesian.xyz.to_value(u.km)


def itrf_to_geodetic(position_itrf_km):
    """Input: position_itrf_km = [x, y, z]
    Output: {longitude_deg, latitude_deg, altitude_km}"""
    x_km, y_km, z_km = position_itrf_km
    location = EarthLocation.from_geocentric(
        x_km * u.km,
        y_km * u.km,
        z_km * u.km,
    )

    return {
        "longitude_deg": float(location.lon.to_value(u.deg)),
        "latitude_deg": float(location.lat.to_value(u.deg)),
        "altitude_km": float(location.height.to_value(u.km)),
    }
