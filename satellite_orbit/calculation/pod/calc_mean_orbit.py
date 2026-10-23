"""Convert one GCRF osculating state to Brouwer-Lyddane mean elements."""

import os
import sys
from datetime import timezone
from math import isfinite
from pathlib import Path

_OREKIT_CONTEXT = None
MEAN_ORBIT_CONVERGENCE_EPSILON = 1.0e-13
MEAN_ORBIT_MAX_ITERATIONS = 5_000


def calculate_mean_orbital_elements(state):
    """Input: {time, GCRF, position_m, velocity_m_s}
    Output: {mean orbit elements and mean GCRF PV coordinates}"""
    if state["frame"] != "GCRF":
        raise ValueError("Mean-orbit state must use GCRF.")

    (
        date,
        vector_3d,
        pv_coordinates,
        cartesian_orbit,
        provider,
        utc,
        gcrf,
        propagator,
        orekit_exception,
        keplerian_orbit,
    ) = _orekit_context()
    state_time = state["time"]
    if state_time.tzinfo is None:
        raise ValueError("Mean-orbit state time must include a timezone.")

    utc_time = state_time.astimezone(timezone.utc)
    orekit_date = date(
        utc_time.year,
        utc_time.month,
        utc_time.day,
        utc_time.hour,
        utc_time.minute,
        utc_time.second + utc_time.microsecond / 1_000_000,
        utc,
    )
    position_m = state["position_m"]
    velocity_m_s = state["velocity_m_s"]
    position = vector_3d(*position_m)
    velocity = vector_3d(*velocity_m_s)
    osculating_orbit = cartesian_orbit(
        pv_coordinates(position, velocity),
        gcrf,
        orekit_date,
        provider.getMu(),
    )
    try:
        mean_orbit = propagator.computeMeanOrbit(
            osculating_orbit,
            provider,
            provider.onDate(orekit_date),
            0.0,
            MEAN_ORBIT_CONVERGENCE_EPSILON,
            MEAN_ORBIT_MAX_ITERATIONS,
        )
    except orekit_exception as error:
        raise ValueError(
            f"Brouwer-Lyddane mean-orbit conversion failed: {error}"
        ) from error
    return mean_orbit_elements(mean_orbit, keplerian_orbit)


def calculate_mean_semi_major_axis(state):
    """Input: {time, GCRF, position_m, velocity_m_s}
    Output: mean_semi_major_axis_m"""
    return calculate_mean_orbital_elements(state)["mean_semi_major_axis_m"]


def mean_orbit_elements(mean_orbit, keplerian_orbit_class):
    """Input: Orekit mean Orbit and its Keplerian converter
    Output: {mean orbit elements and mean GCRF PV coordinates}"""
    mean_semi_major_axis_m = float(mean_orbit.getA())
    if not isfinite(mean_semi_major_axis_m) or mean_semi_major_axis_m <= 0.0:
        raise ValueError("Brouwer-Lyddane conversion returned an invalid semi-major axis.")

    mean_keplerian_orbit = keplerian_orbit_class(mean_orbit)
    mean_position = mean_orbit.getPosition()
    mean_velocity = mean_orbit.getVelocity()
    elements = {
        "mean_semi_major_axis_m": mean_semi_major_axis_m,
        "mean_eccentricity": float(mean_orbit.getE()),
        "mean_inclination_rad": float(mean_orbit.getI()),
        "mean_longitude_rad": float(mean_orbit.getLM()),
        "mean_eccentric_longitude_rad": float(mean_orbit.getLE()),
        "mean_true_longitude_rad": float(mean_orbit.getLv()),
        "mean_equinoctial_ex": float(mean_orbit.getEquinoctialEx()),
        "mean_equinoctial_ey": float(mean_orbit.getEquinoctialEy()),
        "mean_equinoctial_hx": float(mean_orbit.getHx()),
        "mean_equinoctial_hy": float(mean_orbit.getHy()),
        "mean_keplerian_period_s": float(mean_orbit.getKeplerianPeriod()),
        "mean_keplerian_mean_motion_rad_s": float(mean_orbit.getKeplerianMeanMotion()),
        "mean_argument_of_perigee_rad": float(mean_keplerian_orbit.getPerigeeArgument()),
        "mean_raan_rad": float(
            mean_keplerian_orbit.getRightAscensionOfAscendingNode()
        ),
        "mean_anomaly_rad": float(mean_keplerian_orbit.getMeanAnomaly()),
        "mean_eccentric_anomaly_rad": float(
            mean_keplerian_orbit.getEccentricAnomaly()
        ),
        "mean_true_anomaly_rad": float(mean_keplerian_orbit.getTrueAnomaly()),
        "mean_x_m": float(mean_position.getX()),
        "mean_y_m": float(mean_position.getY()),
        "mean_z_m": float(mean_position.getZ()),
        "mean_vx_m_s": float(mean_velocity.getX()),
        "mean_vy_m_s": float(mean_velocity.getY()),
        "mean_vz_m_s": float(mean_velocity.getZ()),
    }
    if not all(isfinite(value) for value in elements.values()):
        raise ValueError("Brouwer-Lyddane conversion returned non-finite mean elements.")
    return elements


def initialize_mean_orbit_context():
    """Input: none
    Output: Orekit context initialized before threaded calculations"""
    _orekit_context()


def _orekit_context():
    """Input: none
    Output: cached Orekit classes and configured model objects"""
    global _OREKIT_CONTEXT
    if _OREKIT_CONTEXT is not None:
        return _OREKIT_CONTEXT

    try:
        import orekit_jpype as orekit
    except ImportError as error:
        add_project_orekit_site_packages()
        try:
            import orekit_jpype as orekit
        except ImportError as retry_error:
            raise RuntimeError(
                "Mean-orbit conversion requires the project's .orekitvenv environment."
            ) from retry_error

    _set_bundled_java_home(orekit)
    orekit_data_path = _orekit_environment_root(orekit) / "orekit-data"
    if not orekit_data_path.is_dir():
        raise RuntimeError(f"Orekit data directory is missing: {orekit_data_path}")

    orekit.initVM()
    from orekit_jpype.pyhelpers import setup_orekit_data

    setup_orekit_data(filenames=str(orekit_data_path), from_pip_library=False)

    from org.hipparchus.geometry.euclidean.threed import Vector3D
    from org.orekit.forces.gravity.potential import GravityFieldFactory
    from org.orekit.frames import FramesFactory
    from org.orekit.orbits import CartesianOrbit, KeplerianOrbit
    from org.orekit.propagation.analytical import BrouwerLyddanePropagator
    from org.orekit.errors import OrekitException
    from org.orekit.time import AbsoluteDate, TimeScalesFactory
    from org.orekit.utils import PVCoordinates

    _OREKIT_CONTEXT = (
        AbsoluteDate,
        Vector3D,
        PVCoordinates,
        CartesianOrbit,
        GravityFieldFactory.getUnnormalizedProvider(5, 0),
        TimeScalesFactory.getUTC(),
        FramesFactory.getGCRF(),
        BrouwerLyddanePropagator,
        OrekitException,
        KeplerianOrbit,
    )
    return _OREKIT_CONTEXT


def add_project_orekit_site_packages():
    """Input: none
    Output: project Orekit venv is available for import when present"""
    site_packages = _project_orekit_venv() / "Lib" / "site-packages"
    if site_packages.is_dir() and str(site_packages) not in sys.path:
        sys.path.append(str(site_packages))


def _orekit_environment_root(orekit):
    """Input: imported orekit_jpype package
    Output: its virtual-environment root"""
    package_path = Path(orekit.__file__).resolve()
    if package_path.parents[3].name == ".orekitvenv":
        return package_path.parents[3]
    return Path(sys.prefix)


def _project_orekit_venv():
    """Input: none
    Output: repository-local Orekit virtual-environment path"""
    return Path(__file__).resolve().parents[3] / ".orekitvenv"


def _set_bundled_java_home(orekit):
    """Input: imported orekit_jpype package
    Output: JAVA_HOME points at the bundled runtime when needed"""
    if os.environ.get("JAVA_HOME"):
        return

    site_packages = Path(orekit.__file__).resolve().parents[1]
    bundled_java_home = site_packages / "jdk4py" / "java-runtime"
    if bundled_java_home.is_dir():
        os.environ["JAVA_HOME"] = str(bundled_java_home)
