import pytest

from ccs_screen.pressure import (
    allowable_delta_p_pa,
    fracture_pressure_pa,
    max_injection_rate_m3_s,
    theis_injection_delta_p_pa,
    theis_transmissivity,
)

AQUIFER = dict(
    permeability_m2=8e-14,
    thickness_m=40.0,
    viscosity_pa_s=4.5e-4,
    time_s=10 * 365 * 24 * 3600,
    radius_m=500.0,
    porosity=0.18,
    compressibility_1_pa=1.2e-9,
)


def test_rate_inversion_round_trips_through_the_forward_model():
    target = 5.0e6
    rate = max_injection_rate_m3_s(allowable_delta_p_pa=target, **AQUIFER)
    assert rate > 0
    assert theis_injection_delta_p_pa(rate_m3_s=rate, **AQUIFER) == pytest.approx(target, rel=1e-9)


def test_allowable_rate_scales_linearly_with_the_allowance():
    r1 = max_injection_rate_m3_s(allowable_delta_p_pa=2e6, **AQUIFER)
    r2 = max_injection_rate_m3_s(allowable_delta_p_pa=4e6, **AQUIFER)
    assert r2 == pytest.approx(2 * r1)


def test_better_permeability_allows_a_higher_rate():
    base = max_injection_rate_m3_s(allowable_delta_p_pa=5e6, **AQUIFER)
    better = max_injection_rate_m3_s(allowable_delta_p_pa=5e6, **{**AQUIFER, "permeability_m2": 2.4e-13})
    assert better > base


def test_fracture_pressure_follows_the_gradient():
    assert fracture_pressure_pa(2000.0) == pytest.approx(2000.0 * 15_000.0)
    assert fracture_pressure_pa(2000.0, fracture_gradient_pa_m=16_000.0) > fracture_pressure_pa(2000.0)


def test_headroom_is_the_derated_fracture_pressure_minus_initial():
    headroom = allowable_delta_p_pa(initial_pressure_pa=20e6, depth_m=2000.0, safety_factor=0.9)
    assert headroom == pytest.approx(0.9 * 30e6 - 20e6)


def test_overpressured_reservoir_has_no_injection_window():
    assert allowable_delta_p_pa(initial_pressure_pa=30e6, depth_m=2000.0) == 0.0


def test_transmissivity_matches_kh_over_mu():
    assert theis_transmissivity(1e-13, 50.0, 5e-4) == pytest.approx(1e-13 * 50.0 / 5e-4)


@pytest.mark.parametrize("bad", [{"safety_factor": 0.0}, {"safety_factor": 1.5}])
def test_rejects_invalid_safety_factor(bad):
    with pytest.raises(ValueError):
        allowable_delta_p_pa(initial_pressure_pa=20e6, depth_m=2000.0, **bad)


def test_rejects_non_positive_allowance():
    with pytest.raises(ValueError):
        max_injection_rate_m3_s(allowable_delta_p_pa=0.0, **AQUIFER)
