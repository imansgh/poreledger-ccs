from ccs_screen.pressure import theis_injection_delta_p_pa


def test_pressure_rises_with_rate_and_falls_with_permeability():
    base = dict(
        time_s=365 * 24 * 3600,
        radius_m=100.0,
        thickness_m=40.0,
        porosity=0.2,
        compressibility_1_pa=1e-9,
        viscosity_pa_s=5e-4,
        rate_m3_s=0.05,
        permeability_m2=1e-13,
    )
    p_base = theis_injection_delta_p_pa(**base)
    p_fast = theis_injection_delta_p_pa(**{**base, "rate_m3_s": 0.10})
    p_perm = theis_injection_delta_p_pa(**{**base, "permeability_m2": 2e-13})
    assert p_base > 0
    assert p_fast > p_base
    assert p_perm < p_base
