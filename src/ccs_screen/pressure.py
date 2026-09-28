"""Theis radial-flow Dp for a constant-rate injection well (brine analog).

This is a screening bound on aquifer pressurization, not a two-phase CO2 plume
model. Dp is linear in rate, which is what makes the injectivity inversion in
``max_injection_rate_m3_s`` exact rather than iterative.

Scope (Phase 13 Model Contract, D1 and Final Gap Closure rule B). Nothing in
this module is part of the approved scientific model. The Theis infinite-acting
solution is an injectivity formulation the contract does not adopt, and no
fracture-gradient criterion, safety factor, evaluation radius or
bounded-aquifer solution is approved. The functions below are arithmetic only:
they take every criterion as an explicit argument and supply none. The former
defaults (15,000 Pa/m and a 0.9 safety factor) had no documented source and
have been removed; they are not retained as approved values.
"""

from __future__ import annotations

import math

from scipy.special import exp1


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")


def theis_transmissivity(permeability_m2: float, thickness_m: float, viscosity_pa_s: float) -> float:
    """Mobility-thickness product k*h/mu in m3/(Pa*s)."""
    _require_positive(
        permeability_m2=permeability_m2, thickness_m=thickness_m, viscosity_pa_s=viscosity_pa_s
    )
    return permeability_m2 * thickness_m / viscosity_pa_s


def theis_injection_delta_p_pa(
    rate_m3_s: float,
    permeability_m2: float,
    thickness_m: float,
    viscosity_pa_s: float,
    time_s: float,
    radius_m: float,
    porosity: float,
    compressibility_1_pa: float,
) -> float:
    """Pressure rise at ``radius_m`` after ``time_s`` of constant-rate injection."""
    _require_positive(
        rate_m3_s=rate_m3_s,
        permeability_m2=permeability_m2,
        thickness_m=thickness_m,
        viscosity_pa_s=viscosity_pa_s,
        time_s=time_s,
        radius_m=radius_m,
        porosity=porosity,
        compressibility_1_pa=compressibility_1_pa,
    )
    transmissivity = theis_transmissivity(permeability_m2, thickness_m, viscosity_pa_s)
    storativity = porosity * compressibility_1_pa * thickness_m
    u = (radius_m**2 * storativity) / (4 * transmissivity * time_s)
    if u <= 0:
        raise ValueError("Theis u must be positive")
    return (rate_m3_s / (4 * math.pi * transmissivity)) * float(exp1(u))


def max_injection_rate_m3_s(
    allowable_delta_p_pa: float,
    permeability_m2: float,
    thickness_m: float,
    viscosity_pa_s: float,
    time_s: float,
    radius_m: float,
    porosity: float,
    compressibility_1_pa: float,
) -> float:
    """Largest constant rate whose Dp at ``radius_m`` stays within the allowance.

    Theis Dp is proportional to rate, so the inversion is a single division.
    """
    _require_positive(allowable_delta_p_pa=allowable_delta_p_pa)
    unit_dp = theis_injection_delta_p_pa(
        rate_m3_s=1.0,
        permeability_m2=permeability_m2,
        thickness_m=thickness_m,
        viscosity_pa_s=viscosity_pa_s,
        time_s=time_s,
        radius_m=radius_m,
        porosity=porosity,
        compressibility_1_pa=compressibility_1_pa,
    )
    return allowable_delta_p_pa / unit_dp


def fracture_pressure_pa(depth_m: float, fracture_gradient_pa_m: float) -> float:
    """Formation fracture pressure from a depth and a caller-supplied gradient.

    The gradient is required: no fracture gradient is approved (D1, D2).
    """
    _require_positive(depth_m=depth_m, fracture_gradient_pa_m=fracture_gradient_pa_m)
    return depth_m * fracture_gradient_pa_m


def allowable_delta_p_pa(
    initial_pressure_pa: float,
    depth_m: float,
    fracture_gradient_pa_m: float,
    safety_factor: float,
) -> float:
    """Pressure headroom between the initial reservoir pressure and the fracture limit.

    Both the gradient and the safety factor are required, caller-supplied
    values; neither is approved (D1, rule B). The pressure convention of the
    headroom check is deferred (B2).

    Returns 0.0 when the reservoir is already at or above the derated fracture
    pressure, which is the screening signal that there is no injection window.
    """
    _require_positive(initial_pressure_pa=initial_pressure_pa)
    if not 0 < safety_factor <= 1:
        raise ValueError("safety_factor must be in (0, 1]")
    limit = safety_factor * fracture_pressure_pa(depth_m, fracture_gradient_pa_m)
    return max(limit - initial_pressure_pa, 0.0)
