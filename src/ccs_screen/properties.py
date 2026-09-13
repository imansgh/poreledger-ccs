"""Peng-Robinson density for pure CO2. Screening-grade, not a custody-transfer EOS."""

from __future__ import annotations

import math

CO2_TC_K = 304.1282
CO2_PC_PA = 7.3773e6
CO2_OMEGA = 0.225
CO2_R_J_MOL_K = 8.314462618
CO2_MW_KG_MOL = 0.0440095


def co2_density_kg_m3(pressure_pa: float, temperature_k: float) -> float:
    if pressure_pa <= 0 or temperature_k <= 0:
        raise ValueError("pressure and temperature must be positive")
    z = _peng_robinson_z(pressure_pa, temperature_k)
    molar_volume = z * CO2_R_J_MOL_K * temperature_k / pressure_pa
    return CO2_MW_KG_MOL / molar_volume


def _peng_robinson_z(pressure_pa: float, temperature_k: float) -> float:
    tr = temperature_k / CO2_TC_K
    kappa = 0.37464 + 1.54226 * CO2_OMEGA - 0.26992 * CO2_OMEGA**2
    alpha = (1 + kappa * (1 - math.sqrt(tr))) ** 2
    a = 0.45724 * (CO2_R_J_MOL_K * CO2_TC_K) ** 2 / CO2_PC_PA * alpha
    b = 0.07780 * CO2_R_J_MOL_K * CO2_TC_K / CO2_PC_PA
    a_dim = a * pressure_pa / (CO2_R_J_MOL_K * temperature_k) ** 2
    b_dim = b * pressure_pa / (CO2_R_J_MOL_K * temperature_k)
    # Z^3 - (1-B)Z^2 + (A-2B-3B^2)Z - (AB - B^2 - B^3) = 0
    c2 = -(1 - b_dim)
    c1 = a_dim - 2 * b_dim - 3 * b_dim**2
    c0 = -(a_dim * b_dim - b_dim**2 - b_dim**3)
    roots = _real_cubic_roots(1.0, c2, c1, c0)
    liquid_like = [z for z in roots if z > b_dim]
    if not liquid_like:
        raise ValueError("Peng-Robinson failed to find a physical Z-factor")
    # Prefer the densest (smallest Z) root in the compressed-liquid / dense-phase region.
    return min(liquid_like)


def _real_cubic_roots(a: float, b: float, c: float, d: float) -> list[float]:
    # Depress to x^3 + px + q = 0
    b_n, c_n, d_n = b / a, c / a, d / a
    p = c_n - b_n**2 / 3
    q = d_n + (2 * b_n**3 - 9 * b_n * c_n) / 27
    disc = (q / 2) ** 2 + (p / 3) ** 3
    offset = b_n / 3
    roots: list[float] = []
    if disc > 1e-16:
        sqrt_d = math.sqrt(disc)
        u = math.copysign(abs(-q / 2 + sqrt_d) ** (1 / 3), -q / 2 + sqrt_d)
        v = math.copysign(abs(-q / 2 - sqrt_d) ** (1 / 3), -q / 2 - sqrt_d)
        roots.append(u + v - offset)
    else:
        r = math.sqrt(max(-p / 3, 0.0))
        if abs(r) < 1e-15:
            roots.append(-offset)
        else:
            arg = max(min(-q / (2 * r**3), 1.0), -1.0)
            phi = math.acos(arg)
            for k in range(3):
                roots.append(2 * r * math.cos((phi + 2 * math.pi * k) / 3) - offset)
    return roots
