# CCS screening starter

Screening-grade tools for **geologic CO2 storage**: Peng-Robinson density, CSLF volumetric capacity, Theis aquifer pressurization, Monte Carlo P10/P50/P90, and a linear surrogate.

This is not a full-physics reservoir simulator. It is a portfolio piece: physics-based Python a hiring manager can run in one command.

```bash
pip install -r requirements.txt
python scripts/run_demo.py
python -m pytest tests -q
```

## What it computes

| Piece | Use | Limit |
| --- | --- | --- |
| `co2_density_kg_m3` | Dense-phase ρ(P,T) | Pure CO2, Peng-Robinson |
| `volumetric_storage_mass_kg` | M = A h φ ρ E | Efficiency E is an input, not predicted |
| `theis_injection_delta_p_pa` | Far-field pressure bound | Single-phase brine analog |
| `run_capacity_mc` | Uncertainty | Independent uniform priors in the demo |
| `fit_linear_surrogate` | Fast ranking of samples | Linear in standardized features |

## Next (on purpose left out)

Two-phase plume, residual/solubility trapping, caprock geomechanics, well integrity. Those are the follow-on if this repo stays the CCS public project.
