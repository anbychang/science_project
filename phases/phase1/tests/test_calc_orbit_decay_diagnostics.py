"""Check quiet-spectrum and complete-orbit decay calculations."""

import unittest
from math import pi, sin

from phases.phase1.code.calc_orbit_decay_diagnostics import (
    PhaseHarmonicSample,
    JOINT_H2_H3_METHOD,
    RAW_B_L_METHOD,
    TwoScaleHarmonicConfig,
    MICROSECONDS_PER_SECOND,
    OrbitMean,
    calculate_periodogram,
    combine_local_rate_statistics,
    local_rate_candidates_from_statistics,
    local_rate_statistics,
    phase_harmonic_ols,
    local_rate_candidates,
    raw_phase_orbit_fits,
    strongest_periodogram_peaks,
    trailing_orbit_fits,
    two_scale_phase_harmonic_fits,
)


START_TIME_US = 1_700_000_000_000_000
TWO_PI = 2.0 * pi


class OrbitDecayDiagnosticsTest(unittest.TestCase):
    """Input: synthetic quiet and complete-orbit signals.
    Output: spectrum peaks and trailing OLS fits."""

    def test_periodogram_finds_known_orbit_harmonic(self):
        """Input: fixed-cadence series with one known FFT harmonic.
        Output: its dominant periodogram peak."""
        sample_count = 8_192
        cadence_s = 10
        harmonic_index = 29
        samples = [
            (
                START_TIME_US + index * cadence_s * MICROSECONDS_PER_SECOND,
                6_800_000.0 + 25.0 * sin(2.0 * pi * harmonic_index * index / sample_count),
            )
            for index in range(sample_count)
        ]

        peaks = strongest_periodogram_peaks(calculate_periodogram(samples))

        self.assertAlmostEqual(
            peaks[0].period_s,
            sample_count * cadence_s / harmonic_index,
            places=6,
        )

    def test_trailing_orbit_fit_recovers_linear_decay(self):
        """Input: complete orbit means with linear decay.
        Output: matching five-orbit trailing rate."""
        orbit_period_s = 5_640
        orbit_means = [
            OrbitMean(
                START_TIME_US + index * orbit_period_s * MICROSECONDS_PER_SECOND,
                6_800_000.0 - index * orbit_period_s / 86_400 * 48.0,
                START_TIME_US + (index - 1) * orbit_period_s * MICROSECONDS_PER_SECOND,
                1,
            )
            for index in range(8)
        ]

        fits = trailing_orbit_fits(orbit_means, 5)

        self.assertAlmostEqual(fits[0].rate_m_day, -48.0, places=9)

    def test_trailing_orbit_fit_resets_after_gap(self):
        """Input: two complete-orbit runs separated by a source gap.
        Output: no fit window crosses the gap."""
        orbit_period_s = 5_640
        orbit_means = [
            OrbitMean(
                START_TIME_US + index * orbit_period_s * MICROSECONDS_PER_SECOND,
                6_800_000.0 - index,
                START_TIME_US + (index - 1) * orbit_period_s * MICROSECONDS_PER_SECOND,
                1,
            )
            for index in range(3)
        ]
        restart_time_us = START_TIME_US + 10 * orbit_period_s * MICROSECONDS_PER_SECOND
        orbit_means.extend(
            OrbitMean(
                restart_time_us + index * orbit_period_s * MICROSECONDS_PER_SECOND,
                6_799_990.0 - index,
                restart_time_us + (index - 1) * orbit_period_s * MICROSECONDS_PER_SECOND,
                1,
            )
            for index in range(3)
        )

        fits = trailing_orbit_fits(orbit_means, 3)

        self.assertEqual(len(fits), 2)

    def test_h1_to_h5_fit_recovers_linear_decay(self):
        """Input: linear decay plus phase H1--H5.
        Output: exact joint-fit decay rate."""
        samples = phase_harmonic_samples()

        fit = phase_harmonic_ols(samples, (1, 2, 3, 4, 5))

        self.assertAlmostEqual(fit.rate_m_day, -48.0, places=8)

    def test_h1_to_h5_fit_removes_residual_left_by_h2_h3(self):
        """Input: linear decay plus phase H1--H5.
        Output: H1--H5 residual below H2/H3 residual."""
        samples = phase_harmonic_samples()

        h2_h3_fit = phase_harmonic_ols(samples, (2, 3))
        h1_to_h5_fit = phase_harmonic_ols(samples, (1, 2, 3, 4, 5))

        self.assertLess(h1_to_h5_fit.residual_std_m, h2_h3_fit.residual_std_m)

    def test_twenty_orbit_h2_h3_fit_with_three_orbit_rate_recovers_decay(self):
        """Input: constant H2/H3 over 22 complete orbits.
        Output: 20-orbit H2/H3 plus 3-orbit rate recovers the linear decay."""
        orbit_means, samples = two_scale_samples()
        configuration = TwoScaleHarmonicConfig(20, 3, (2, 3))

        fits = two_scale_phase_harmonic_fits(orbit_means, samples, configuration)

        self.assertAlmostEqual(fits[-1].rate_m_day, -48.0, places=8)

    def test_raw_three_orbit_fit_retains_h2_h3_residual(self):
        """Input: raw samples with H2/H3 over three complete orbits.
        Output: raw-only OLS residual remains positive."""
        orbit_means, samples = two_scale_samples()

        fits = raw_phase_orbit_fits(orbit_means, samples, 3)

        self.assertGreater(fits[-1].residual_std_m, 1.0)

    def test_local_candidates_keep_raw_and_h2_h3_methods(self):
        """Input: raw samples with H2/H3.
        Output: both requested candidate method names."""
        _, samples = two_scale_samples()

        candidates = local_rate_candidates(samples[-300:])

        self.assertEqual(
            {candidate.method for candidate in candidates},
            {RAW_B_L_METHOD, JOINT_H2_H3_METHOD},
        )

    def test_rolling_normal_equations_keep_positive_harmonic_uncertainty(self):
        """Input: H1--H5 signal summarized as complete-orbit statistics.
        Output: H2/H3 residual creates a non-zero joint uncertainty."""
        samples = phase_harmonic_samples()
        statistics = combine_local_rate_statistics([
            local_rate_statistics(
                samples,
                samples[0].time_us,
                samples[0].semi_major_axis_m,
            ),
        ])

        candidates = local_rate_candidates_from_statistics(
            statistics, samples[0].time_us, samples[-1].chunk_id,
        )
        joint_candidate = next(
            candidate for candidate in candidates
            if candidate.method == JOINT_H2_H3_METHOD
        )

        self.assertGreater(joint_candidate.rate_1sigma_m_day, 0.0)


def phase_harmonic_samples():
    """Input: no arguments.
    Output: synthetic continuous samples with linear trend and H1--H5."""
    harmonic_amplitudes_m = (12.0, 18.0, 9.0, 7.0, 5.0)
    sample_count = 3_000
    phase_cycles = 5
    sample_period_s = 10
    decay_rate_m_s = -48.0 / 86_400
    return [
        PhaseHarmonicSample(
            START_TIME_US + index * sample_period_s * MICROSECONDS_PER_SECOND,
            6_800_000.0
            + decay_rate_m_s * index * sample_period_s
            + sum(
                amplitude_m * sin((order + 1) * 2.0 * pi * phase_cycles * index / sample_count)
                for order, amplitude_m in enumerate(harmonic_amplitudes_m)
            ),
            2.0 * pi * phase_cycles * index / sample_count,
            1,
        )
        for index in range(sample_count)
    ]


def two_scale_samples():
    """Input: no arguments.
    Output: complete orbit means and raw samples with constant H2/H3."""
    sample_period_s = 10
    samples_per_orbit = 100
    orbit_count = 22
    decay_rate_m_s = -48.0 / 86_400
    samples = []
    orbit_means = []
    for orbit_index in range(orbit_count):
        orbit_start_time_us = (
            START_TIME_US
            + orbit_index * samples_per_orbit * sample_period_s * MICROSECONDS_PER_SECOND
        )
        for sample_index in range(samples_per_orbit):
            time_us = orbit_start_time_us + sample_index * sample_period_s * MICROSECONDS_PER_SECOND
            phase_rad = TWO_PI * sample_index / samples_per_orbit
            elapsed_s = (time_us - START_TIME_US) / MICROSECONDS_PER_SECOND
            samples.append(PhaseHarmonicSample(
                time_us,
                6_800_000.0 + decay_rate_m_s * elapsed_s
                + 30.0 * sin(2.0 * phase_rad)
                + 20.0 * sin(3.0 * phase_rad),
                phase_rad,
                1,
            ))
        orbit_means.append(OrbitMean(
            samples[-1].time_us,
            6_800_000.0 + decay_rate_m_s * (samples[-1].time_us - START_TIME_US) / MICROSECONDS_PER_SECOND,
            orbit_start_time_us,
            1,
        ))
    return orbit_means, samples
