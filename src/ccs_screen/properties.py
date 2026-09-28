"""Peng-Robinson density for pure CO2. Screening-grade, not a custody-transfer EOS.

Two details matter for CCS screening and are handled explicitly here:

1. **Root selection.** Below the saturation pressure the cubic has three real
   roots. Picking the densest one unconditionally returns a liquid density in
   the vapour region (an order-of-magnitude error). The physical root is the
   one with the lower fugacity, i.e. the lower molar Gibbs energy.
2. **Volume translation.** Untranslated Peng-Robinson under-predicts CO2 density
   at moderate pressure, and storage mass is linear in density, so a constant
   Peneloux shift is applied.

   Measured envelope against Span & Wagner (1996) over 140 points,
   P = 1-35 MPa and T = 280-400 K (see ``docs/scientific-validation-audit.md``,
   Phase 1):

   ===========================  ==========  ========  =======
   Configuration                mean |err|  median    max
   ===========================  ==========  ========  =======
   Peneloux shift applied            4.06%     2.86%   13.98%
   No volume translation             2.59%     1.99%   16.67%
   ===========================  ==========  ========  =======

   The shift lowers the worst case but raises the typical error: untranslated
   PR is closer at 108 of the 140 points. It helps below roughly 15 MPa and
   degrades above 20 MPa, where a constant shift over-corrects -- at
   35 MPa / 300 K it turns a +3.8% error into +11.8%.

   It is kept by owner decision E1 of the Phase 13 Model Contract
   (``docs/phase13-owner-decision-record.md``), together with a declared and
   enforced operating envelope (see ``VALIDATED_ENVELOPE_PRESSURE_PA`` and
   ``VALIDATED_ENVELOPE_TEMPERATURE_K``). The earlier justification -- that
   most Italian pilot reservoirs sit below 20 MPa -- is not supported: the
   audit found 14 of 45 pilot wells below 20 MPa under the pre-Phase-13 state
   definition (Finding 11.1; decision E2). This is a screening-grade
   compromise, not an accuracy improvement everywhere. Flagged REVIEW REQUIRED
   in the Phase 1 audit; a temperature-dependent shift is the standard remedy
   and has not been implemented.

3. **Validated operating envelope.** 1-35 MPa and 280-400 K, the Phase 1
   comparison range (E1, M4). The approved model checks it on the absolute EOS
   pressure for every Monte Carlo realisation and blocks validated outputs when
   any realisation lies outside it. ``co2_density_kg_m3`` itself still
   evaluates such states: outside the validated envelope is not the same as
   physically impossible.
"""

from __future__ import annotations

import math

CO2_TC_K = 304.1282
CO2_PC_PA = 7.3773e6
CO2_OMEGA = 0.225
CO2_R_J_MOL_K = 8.314462618
CO2_MW_KG_MOL = 0.0440095

# Rackett compressibility for CO2, used by the Peneloux volume shift.
CO2_Z_RA = 0.2722

#: Validated operating envelope (E1, M4; closed bounds). Pressure is the
#: absolute EOS pressure P_EOS = P_gauge + P_atm, never gauge pressure (C1).
VALIDATED_ENVELOPE_PRESSURE_PA = (1.0e6, 35.0e6)
VALIDATED_ENVELOPE_TEMPERATURE_K = (280.0, 400.0)

SQRT2 = math.sqrt(2.0)


def co2_density_kg_m3(pressure_pa: float, temperature_k: float) -> float:
    """Dense-phase CO2 density rho(P, T) in kg/m3."""
    if pressure_pa <= 0 or temperature_k <= 0:
        raise ValueError("pressure and temperature must be positive")
    molar_volume = co2_molar_volume_m3_mol(pressure_pa, temperature_k)
    return CO2_MW_KG_MOL / molar_volume


def co2_molar_volume_m3_mol(pressure_pa: float, temperature_k: float) -> float:
    """Volume-translated molar volume in m3/mol."""
    if pressure_pa <= 0 or temperature_k <= 0:
        raise ValueError("pressure and temperature must be positive")
    z = co2_compressibility(pressure_pa, temperature_k)
    v_eos = z * CO2_R_J_MOL_K * temperature_k / pressure_pa
    v = v_eos - peneloux_shift_m3_mol()
    if v <= 0:
        raise ValueError("volume translation produced a non-physical molar volume")
    return v


def co2_compressibility(pressure_pa: float, temperature_k: float) -> float:
    """Untranslated Peng-Robinson Z-factor of the thermodynamically stable phase."""
    if pressure_pa <= 0 or temperature_k <= 0:
        raise ValueError("pressure and temperature must be positive")
    return _peng_robinson_z(pressure_pa, temperature_k)


def peneloux_shift_m3_mol() -> float:
    """Peneloux (1982) constant volume shift c for CO2."""
    return 0.40768 * (CO2_R_J_MOL_K * CO2_TC_K / CO2_PC_PA) * (0.29441 - CO2_Z_RA)


def _peng_robinson_ab(pressure_pa: float, temperature_k: float) -> tuple[float, float]:
    """Dimensionless attraction (A) and covolume (B) parameters."""
    tr = temperature_k / CO2_TC_K
    kappa = 0.37464 + 1.54226 * CO2_OMEGA - 0.26992 * CO2_OMEGA**2
    alpha = (1 + kappa * (1 - math.sqrt(tr))) ** 2
    a = 0.45724 * (CO2_R_J_MOL_K * CO2_TC_K) ** 2 / CO2_PC_PA * alpha
    b = 0.07780 * CO2_R_J_MOL_K * CO2_TC_K / CO2_PC_PA
    a_dim = a * pressure_pa / (CO2_R_J_MOL_K * temperature_k) ** 2
    b_dim = b * pressure_pa / (CO2_R_J_MOL_K * temperature_k)
    return a_dim, b_dim


def _ln_fugacity_coefficient(z: float, a_dim: float, b_dim: float) -> float:
    """ln(phi) for a Peng-Robinson root; the stable phase minimises it."""
    inner = (z + (1 + SQRT2) * b_dim) / (z + (1 - SQRT2) * b_dim)
    if z <= b_dim or inner <= 0:
        return math.inf
    return (
        z
        - 1.0
        - math.log(z - b_dim)
        - a_dim / (2 * SQRT2 * b_dim) * math.log(inner)
    )


def _peng_robinson_z(pressure_pa: float, temperature_k: float) -> float:
    a_dim, b_dim = _peng_robinson_ab(pressure_pa, temperature_k)
    # Z^3 - (1-B)Z^2 + (A-2B-3B^2)Z - (AB - B^2 - B^3) = 0
    c2 = -(1 - b_dim)
    c1 = a_dim - 2 * b_dim - 3 * b_dim**2
    c0 = -(a_dim * b_dim - b_dim**2 - b_dim**3)
    roots = _real_cubic_roots(1.0, c2, c1, c0)
    candidates = [z for z in roots if z > b_dim]
    if not candidates:
        raise ValueError("Peng-Robinson failed to find a physical Z-factor")
    if len(candidates) == 1:
        return candidates[0]
    # Three roots: the middle one is mechanically unstable, and the stable phase
    # is whichever of the outer two has the lower fugacity.
    liquid, vapour = min(candidates), max(candidates)
    return liquid if _ln_fugacity_coefficient(liquid, a_dim, b_dim) <= _ln_fugacity_coefficient(vapour, a_dim, b_dim) else vapour


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
