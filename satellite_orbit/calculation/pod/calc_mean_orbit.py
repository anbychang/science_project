"""Convert one GCRF osculating state to a Brouwer-Lyddane mean orbit."""

import os
import sys
from datetime import timezone
from math import isfinite
from pathlib import Path

_OREKIT_CONTEXT = None


def calculate_mean_semi_major_axis(state):
    """Input: {time, GCRF, position_m, velocity_m_s}
    Output: mean_semi_major_axis_m"""
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
    mean_orbit = propagator.computeMeanOrbit(
        osculating_orbit,
        provider,
        provider.onDate(orekit_date),
        0.0,
    )
    mean_semi_major_axis_m = mean_orbit.getA()
    if not isfinite(mean_semi_major_axis_m) or mean_semi_major_axis_m <= 0.0:
        raise ValueError("Brouwer-Lyddane conversion returned an invalid semi-major axis.")
    return mean_semi_major_axis_m


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
    from org.orekit.orbits import CartesianOrbit
    from org.orekit.propagation.analytical import BrouwerLyddanePropagator
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
