from datetime import date

from phases.phase6.code.calc_phase6_paper_msis_scale_check import (
    DailyQuietModel,
    conversion_scale_m2_kg,
    predicted_rate_m_day,
)


def model(mean_density: float, factor: float, rate: float) -> DailyQuietModel:
    """Input: test density, density-orbit factor, and published rate.
    Output: minimal daily quiet-model fixture."""
    return DailyQuietModel(
        day=date(2024, 5, 4),
        day_start_time_us=0,
        source_file="source.zip",
        density_sample_count=1,
        orbit_count=1,
        f107_sfu=100.0,
        f107a_sfu=100.0,
        mean_altitude_m=400_000.0,
        mean_semi_major_axis_m=6_800_000.0,
        mean_quiet_density_kg_m3=mean_density,
        density_orbit_factor=factor,
        published_rate_m_day=rate,
    )


def test_calibration_reproduces_reference_rate():
    """Input: one reference density-orbit factor and paper rate.
    Output: calibrated model reproduces the reference exactly."""
    reference = model(1.0, 4.0, 20.0)
    scale = conversion_scale_m2_kg(reference)
    assert predicted_rate_m_day(scale, reference) == 20.0


def test_fixed_scale_tracks_density_orbit_factor_ratio():
    """Input: target factor twice the reference factor.
    Output: predicted rate doubles without recalibration."""
    reference = model(1.0, 4.0, 20.0)
    target = model(2.0, 8.0, 80.0)
    scale = conversion_scale_m2_kg(reference)
    assert predicted_rate_m_day(scale, target) == 40.0
