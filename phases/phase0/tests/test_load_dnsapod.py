from phases.phase0.code.data.density.load_dnsapod import valid_density_value


def test_density_fill_value_is_not_valid_data():
    """Input: positive CDF fill value. Output: rejected density sample."""
    assert not valid_density_value(9.99e32, 9.99e32)


def test_positive_non_fill_density_is_valid():
    """Input: positive finite L2 density. Output: accepted density sample."""
    assert valid_density_value(2.0e-12, 9.99e32)
