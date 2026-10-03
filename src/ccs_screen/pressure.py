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

Numerical domain. Every input must be a finite real number (``value <= 0``
alone lets ``NaN`` through). An intermediate that overflows or underflows
floating-point arithmetic raises :class:`TheisDomainError` instead of
propagating ``inf``, ``NaN`` or a division by zero. In particular, for large
``u`` the well function ``E1(u)`` underflows to exactly zero (``u`` above about
700): the unit-rate pressure response is then below floating-point resolution,
``theis_injection_delta_p_pa`` returns 0.0, and ``max_injection_rate_m3_s``
raises rather than invent a finite limit, because the Theis model sets no
resolvable rate limit at that radius and time.
"""

from __future__ import annotations

import math
from numbers import Real

from scipy.special import exp1


class TheisDomainError(ValueError):
    """The Theis calculation left floating-point range for these inputs.

    A :class:`ValueError`, so the CLI's existing error path stays controlled.
    """


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value!r}")
        if value <= 0:
            raise ValueError(f"{name} must be positive")


def _require_finite_positive_result(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise TheisDomainError(
            f"{name} is not a finite positive number ({value!r}): the inputs overflow "
            "or underflow floating-point arithmetic"
        )
    return value


def theis_transmissivity(permeability_m2: float, thickness_m: float, viscosity_pa_s: float) -> float:
    """Mobility-thickness product k*h/mu in m3/(Pa*s)."""
    _require_positive(
        permeability_m2=permeability_m2, thickness_m=thickness_m, viscosity_pa_s=viscosity_pa_s
    )
    return _require_finite_positive_result(
        "transmissivity", permeability_m2 * thickness_m / viscosity_pa_s
    )


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
    """Pressure rise at ``radius_m`` after ``time_s`` of constant-rate injection.

    Returns 0.0 when ``E1(u)`` underflows: the response is positive but below
    floating-point resolution.
    """
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
    storativity = _require_finite_positive_result(
        "storativity", porosity * compressibility_1_pa * thickness_m
    )
    u = _require_finite_positive_result(
        "Theis u", (radius_m**2 * storativity) / (4 * transmissivity * time_s)
    )
    delta_p = (rate_m3_s / (4 * math.pi * transmissivity)) * float(exp1(u))
    if not math.isfinite(delta_p):
        raise TheisDomainError(f"Theis pressure rise overflows floating-point range ({delta_p!r})")
    return delta_p


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

    Raises :class:`TheisDomainError` when the unit-rate response underflows to
    zero (``E1(u)`` below floating-point resolution). The model then sets no
    resolvable limit at this radius and time; no finite rate is substituted.
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
    if unit_dp == 0.0:
        raise TheisDomainError(
            "Theis unit-rate pressure response underflows to zero at this radius and "
            "time (E1(u) below floating-point resolution), so no finite injection-rate "
            "limit can be derived from the pressure allowance"
        )
    rate = allowable_delta_p_pa / unit_dp
    if not math.isfinite(rate):
        raise TheisDomainError(
            f"maximum injection rate overflows floating-point range ({rate!r})"
        )
    return rate


def fracture_pressure_pa(depth_m: float, fracture_gradient_pa_m: float) -> float:
    """Formation fracture pressure from a depth and a caller-supplied gradient.

    The gradient is required: no fracture gradient is approved (D1, D2).
    """
    _require_positive(depth_m=depth_m, fracture_gradient_pa_m=fracture_gradient_pa_m)
    return _require_finite_positive_result("fracture pressure", depth_m * fracture_gradient_pa_m)


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
