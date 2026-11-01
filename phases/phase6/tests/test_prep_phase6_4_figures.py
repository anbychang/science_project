from phases.phase6.code.prep_phase6_4_figures import event_orbit_mean_points


def test_orbit_means_use_one_pre_event_reference() -> None:
    """Input: complete event orbits. Output: one event-relative POD trend."""
    points = event_orbit_mean_points(
        reference_mean_a_m=6_800_010.0,
        orbit_means=[
            (100, 90, 6_800_000.0, 3),
            (200, 110, 6_799_995.0, 3),
            (300, 210, 6_799_990.0, 3),
        ],
    )

    assert [point.time_us for point in points] == [100, 200, 300]
    assert [point.segment_index for point in points] == [1, 1, 1]
    assert [point.delta_a_m for point in points] == [-10.0, -15.0, -20.0]


def test_pod_gap_starts_a_new_plot_segment() -> None:
    """Input: non-adjacent complete orbits. Output: POD line does not cross its gap."""
    points = event_orbit_mean_points(
        reference_mean_a_m=100.0,
        orbit_means=[
            (100_000_000, 10_000_000, 99.0, 2),
            (200_000_000, 110_000_000, 98.0, 2),
            (400_000_000, 300_000_000, 97.0, 2),
        ],
    )

    assert [point.segment_index for point in points] == [1, 1, 2]
