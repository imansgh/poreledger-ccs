"""Theis radial-flow Δp for a constant-rate injection well (brine analog).

This is a screening bound on aquifer pressurization, not a two-phase CO2 plume model.
"""

from __future__ import annotations

import math

from scipy.special import exp1


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
    for name, value in {
        "rate_m3_s": rate_m3_s,
        "permeability_m2": permeability_m2,
        "thickness_m": thickness_m,
        "viscosity_pa_s": viscosity_pa_s,
        "time_s": time_s,
        "radius_m": radius_m,
        "porosity": porosity,
        "compressibility_1_pa": compressibility_1_pa,
    }.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    transmissivity = permeability_m2 * thickness_m / viscosity_pa_s
    storativity = porosity * compressibility_1_pa * thickness_m
    u = (radius_m**2 * storativity) / (4 * transmissivity * time_s)
    if u <= 0:
        raise ValueError("Theis u must be positive")
    return (rate_m3_s / (4 * math.pi * transmissivity)) * float(exp1(u))
