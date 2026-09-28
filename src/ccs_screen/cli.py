"""Command-line screening run: capacity distribution, sensitivity, injectivity.

    ccs-screen --samples 2000 --porosity 0.10 0.20 --json

Every output of this command is NOT_VALIDATED demo output. Under owner decision
O1 of the Phase 13 Model Contract (``docs/phase13-owner-decision-record.md``)
the CLI capacity path -- the synthetic ``DEPLETED_GAS_ANALOG`` priors, a flat
pressure prior, independent P/T sampling and a demo E range -- is outside the
approved model, and supplying flags or ``--config`` does not bring it under the
contract. Its injectivity outputs are outside the approved model under the
contract's rule B. The approved model is served by ``ccs_screen.api``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from typing import Any

from ccs_screen.config import UNSET_BY_DEFAULT_FIELDS, ScreeningConfig
from ccs_screen.monte_carlo import DEPLETED_GAS_ANALOG, McResult, UniformPriors, run_capacity_mc
from ccs_screen.pressure import (
    allowable_delta_p_pa,
    fracture_pressure_pa,
    max_injection_rate_m3_s,
    theis_injection_delta_p_pa,
)
from ccs_screen.surrogate import evaluate, fit_linear_surrogate, sensitivity

SECONDS_PER_YEAR = 365.25 * 24 * 3600

NOT_VALIDATED = "NOT_VALIDATED"
UNAVAILABLE = "UNAVAILABLE"

#: O1: the scope statement carried by every run.
DEMO_SCOPE_STATEMENT = (
    "NOT_VALIDATED demo output (owner decision O1). The ccs-screen capacity path "
    "(synthetic DEPLETED_GAS_ANALOG priors, flat pressure prior, independent P/T "
    "sampling, demo storage-efficiency range) is outside the approved Model Contract; "
    "supplying flags or --config does not bring it under the contract. Capacity, "
    "surrogate and sensitivity outputs are not validated scientific screening results."
)

#: Rule B: the scope statement of the injectivity block.
INJECTIVITY_SCOPE_STATEMENT = (
    "Outside the approved scientific model (Model Contract D1, Final Gap Closure rule B). "
    "The Theis infinite-acting outputs are NOT_VALIDATED. No fracture-gradient criterion, "
    "safety factor, evaluation radius or bounded-aquifer solution is approved, and none "
    "has a default: fracture-dependent outputs are UNAVAILABLE unless the caller supplies "
    "them, and are then NOT_VALIDATED."
)

#: Why each fracture-dependent output is unavailable, by missing input.
_MISSING_INPUT_REASON = {
    "fracture_gradient_pa_m": "no fracture gradient supplied (--fracture-gradient-pa-m has no default)",
    "safety_factor": "no safety factor supplied (--safety-factor has no default)",
}

PRIOR_HELP = {
    "area_m2": "closure area (m2)",
    "thickness_m": "net storage thickness (m)",
    "porosity": "porosity (-)",
    "pressure_pa": "reservoir pressure (Pa)",
    "temperature_k": "reservoir temperature (K)",
    "storage_efficiency": "storage efficiency factor (-)",
}


#: Scalar injectivity / run-control defaults, shared by the parser and the
#: config layer so the two can never drift apart.
SCALAR_DEFAULTS: dict[str, float] = {
    "depth_m": 2000.0,
    "permeability_m2": 8e-14,
    "aquifer_thickness_m": 40.0,
    "viscosity_pa_s": 4.5e-4,
    "radius_m": 500.0,
    "years": 10.0,
    "aquifer_porosity": 0.18,
    "compressibility_1_pa": 1.2e-9,
    "rate_m3_s": 0.08,
}

#: Injectivity scalars with no default (see ``config.UNSET_BY_DEFAULT_FIELDS``).
UNSET_SCALARS: tuple[str, ...] = UNSET_BY_DEFAULT_FIELDS

SCALAR_HELP = {
    "depth_m": "reservoir depth (m)",
    "permeability_m2": "aquifer permeability (m2)",
    "aquifer_thickness_m": "aquifer thickness used by Theis (m)",
    "viscosity_pa_s": "brine viscosity (Pa.s)",
    "radius_m": "radius at which dP is evaluated (m)",
    "years": "injection duration (yr)",
    "aquifer_porosity": "aquifer porosity (-)",
    "compressibility_1_pa": "total compressibility (1/Pa)",
    "rate_m3_s": "planned injection rate (m3/s)",
    "fracture_gradient_pa_m": (
        "fracture gradient (Pa/m); no default -- if omitted, fracture-dependent "
        "outputs are UNAVAILABLE; if supplied, they are NOT_VALIDATED"
    ),
    "safety_factor": (
        "fraction of fracture pressure allowed (-); no default -- if omitted, "
        "headroom-dependent outputs are UNAVAILABLE; if supplied, they are NOT_VALIDATED"
    ),
}


def build_parser(*, defaults: bool = True) -> argparse.ArgumentParser:
    """Build the CLI parser.

    With ``defaults=False`` every option defaults to ``argparse.SUPPRESS``, so
    the parsed namespace contains *only* what the user actually typed. That is
    how ``--config`` precedence is resolved without changing the behaviour of
    the normal parser.
    """

    def default_for(value: Any) -> Any:
        return value if defaults else argparse.SUPPRESS

    parser = argparse.ArgumentParser(
        prog="ccs-screen",
        description=(
            "Screening-grade CO2 storage capacity, sensitivity and injectivity "
            "(NOT_VALIDATED demo; outside the approved Model Contract)."
        ),
        epilog=(
            "Defaults describe a synthetic depleted-gas analog, not a real site. Every "
            "output is NOT_VALIDATED (owner decision O1); fracture-dependent outputs are "
            "UNAVAILABLE unless a fracture gradient and safety factor are supplied."
        ),
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=default_for(None),
        help="JSON screening config; CLI flags override individual fields",
    )
    parser.add_argument(
        "--samples", type=int, default=default_for(2000), help="Monte Carlo realisations (default: 2000)"
    )
    parser.add_argument("--seed", type=int, default=default_for(42), help="RNG seed (default: 42)")
    parser.add_argument(
        "--json", action="store_true", default=default_for(False), help="emit machine-readable JSON"
    )

    priors = parser.add_argument_group("priors", "uniform LOW HIGH ranges")
    for field in fields(UniformPriors):
        low, high = getattr(DEPLETED_GAS_ANALOG, field.name)
        priors.add_argument(
            f"--{field.name.replace('_', '-')}",
            dest=field.name,
            type=float,
            nargs=2,
            metavar=("LOW", "HIGH"),
            default=default_for([low, high]),
            help=f"{PRIOR_HELP[field.name]} (default: {low:g} {high:g})",
        )

    aquifer = parser.add_argument_group("injectivity", "Theis brine-analog aquifer (NOT_VALIDATED)")
    for name, value in SCALAR_DEFAULTS.items():
        aquifer.add_argument(
            f"--{name.replace('_', '-')}",
            dest=name,
            type=float,
            default=default_for(value),
            help=f"{SCALAR_HELP[name]} (default: {value:g})",
        )
    for name in UNSET_SCALARS:
        aquifer.add_argument(
            f"--{name.replace('_', '-')}",
            dest=name,
            type=float,
            default=default_for(None),
            help=SCALAR_HELP[name],
        )
    return parser


def _merge_config(args: argparse.Namespace, argv: list[str] | None) -> argparse.Namespace:
    """Apply ``--config`` under CLI overrides.

    Precedence is engine defaults -> config file -> CLI flags. The merged result
    is revalidated through :class:`ScreeningConfig`, so an override cannot slip
    a physically impossible value past the schema.
    """
    if getattr(args, "config", None) is None:
        return args

    config = ScreeningConfig.from_json_file(args.config)

    merged: dict[str, Any] = {name: list(value) for name, value in config.prior_ranges().items()}
    for name in (*SCALAR_DEFAULTS, *UNSET_SCALARS):
        merged[name] = getattr(config, name)
    merged["samples"] = config.samples
    merged["seed"] = config.seed

    # Only the flags the user actually typed override the file.
    provided = vars(build_parser(defaults=False).parse_args(argv))
    for name, value in provided.items():
        if name in ("config", "json"):
            continue
        merged[name] = value

    revalidated = ScreeningConfig.from_mapping({**merged, "well_id": config.well_id})

    resolved = argparse.Namespace(**vars(args))
    for name, value in revalidated.prior_ranges().items():
        setattr(resolved, name, list(value))
    for name in (*SCALAR_DEFAULTS, *UNSET_SCALARS):
        setattr(resolved, name, getattr(revalidated, name))
    resolved.samples = revalidated.samples
    resolved.seed = revalidated.seed
    resolved.well_id = revalidated.well_id
    return resolved


def _check_supplied_criteria(args: argparse.Namespace) -> None:
    """Reject an impossible caller-supplied criterion even when its partner is absent."""
    gradient = getattr(args, "fracture_gradient_pa_m", None)
    factor = getattr(args, "safety_factor", None)
    if gradient is not None and gradient <= 0:
        raise ValueError("fracture_gradient_pa_m must be positive")
    if factor is not None and not 0 < factor <= 1:
        raise ValueError("safety_factor must be in (0, 1]")


def _injectivity(args: argparse.Namespace, priors: UniformPriors,
                 aquifer: dict[str, float]) -> dict[str, Any]:
    """Rule B: Theis outputs NOT_VALIDATED; fracture-dependent outputs UNAVAILABLE
    unless the caller supplies the criterion, then NOT_VALIDATED."""
    gradient = getattr(args, "fracture_gradient_pa_m", None)
    factor = getattr(args, "safety_factor", None)
    # Mid-prior reservoir pressure, the demo's starting point for the headroom
    # check (Finding 5.2); it has no approved injectivity role.
    initial_pressure_pa = sum(priors.pressure_pa) / 2
    planned_dp = theis_injection_delta_p_pa(rate_m3_s=args.rate_m3_s, **aquifer)

    values: dict[str, Any] = {
        "initial_pressure_pa": initial_pressure_pa,
        "fracture_pressure_pa": None,
        "allowable_delta_p_pa": None,
        "planned_rate_m3_s": args.rate_m3_s,
        "planned_delta_p_pa": planned_dp,
        "max_rate_m3_s": None,
        "within_limit": None,
    }
    status = {name: NOT_VALIDATED for name in values}
    reasons: dict[str, str] = {}

    if gradient is not None:
        values["fracture_pressure_pa"] = fracture_pressure_pa(args.depth_m, gradient)
    else:
        status["fracture_pressure_pa"] = UNAVAILABLE
        reasons["fracture_pressure_pa"] = _MISSING_INPUT_REASON["fracture_gradient_pa_m"]

    if gradient is not None and factor is not None:
        headroom = allowable_delta_p_pa(
            initial_pressure_pa=initial_pressure_pa,
            depth_m=args.depth_m,
            fracture_gradient_pa_m=gradient,
            safety_factor=factor,
        )
        values["allowable_delta_p_pa"] = headroom
        values["max_rate_m3_s"] = (max_injection_rate_m3_s(allowable_delta_p_pa=headroom, **aquifer)
                                   if headroom > 0 else 0.0)
        values["within_limit"] = bool(planned_dp <= headroom)
    else:
        reason = "; ".join(_MISSING_INPUT_REASON[name] for name in UNSET_SCALARS
                           if getattr(args, name, None) is None)
        for name in ("allowable_delta_p_pa", "max_rate_m3_s", "within_limit"):
            status[name] = UNAVAILABLE
            reasons[name] = reason

    return {
        **values,
        "validation_status": NOT_VALIDATED,
        "output_status": status,
        "unavailable_reasons": reasons,
        "caller_supplied_criteria": {"fracture_gradient_pa_m": gradient, "safety_factor": factor},
        "scope": INJECTIVITY_SCOPE_STATEMENT,
    }


def _screen(args: argparse.Namespace) -> dict[str, Any]:
    if args.samples <= 0:
        raise ValueError("--samples must be a positive integer")
    _check_supplied_criteria(args)
    priors_map = {field.name: tuple(getattr(args, field.name)) for field in fields(UniformPriors)}
    priors = UniformPriors(**priors_map)
    samples = priors.sample(args.samples, seed=args.seed)
    result: McResult = run_capacity_mc(samples)
    model = fit_linear_surrogate(samples, result.masses_mt)
    metrics = evaluate(model, samples, result.masses_mt)

    aquifer = dict(
        permeability_m2=args.permeability_m2,
        thickness_m=args.aquifer_thickness_m,
        viscosity_pa_s=args.viscosity_pa_s,
        time_s=args.years * SECONDS_PER_YEAR,
        radius_m=args.radius_m,
        porosity=args.aquifer_porosity,
        compressibility_1_pa=args.compressibility_1_pa,
    )

    return {
        "validation_status": NOT_VALIDATED,
        "scope": DEMO_SCOPE_STATEMENT,
        "well_id": getattr(args, "well_id", None),
        "n_samples": result.n,
        "seed": args.seed,
        "deterministic": all(low == high for low, high in priors_map.values()),
        "capacity_mt": {
            "p10": result.p10_mt,
            "p50": result.p50_mt,
            "p90": result.p90_mt,
            "mean": result.mean_mt,
            "validation_status": NOT_VALIDATED,
        },
        "surrogate": {"r2": metrics.r2, "rmse_mt": metrics.rmse_mt, "mae_mt": metrics.mae_mt,
                      "validation_status": NOT_VALIDATED},
        "sensitivity_mt_per_sigma": dict(sensitivity(model)),
        "sensitivity_validation_status": NOT_VALIDATED,
        "injectivity": _injectivity(args, priors, aquifer),
    }


def _pa_to_mpa(value: float | None, digits: int) -> str:
    return UNAVAILABLE if value is None else f"{value / 1e6:.{digits}f} MPa"


def _render(report: dict[str, Any]) -> str:
    cap = report["capacity_mt"]
    sur = report["surrogate"]
    inj = report["injectivity"]
    header = report.get("well_id") or "synthetic depleted-gas analog - not a site model"
    lines = [
        f"CCS screening run ({header})",
        "  status                     : NOT_VALIDATED demo output (owner decision O1);",
        "                               outside the approved Model Contract",
        f"  realisations               : {report['n_samples']} (seed {report['seed']})",
    ]
    if report.get("deterministic"):
        lines.append("  NOTE: all priors are point values - P10 = P50 = P90, no uncertainty")
    lines += [
        "",
        "Capacity (NOT_VALIDATED)",
        f"  P10 / P50 / P90            : {cap['p10']:.1f} / {cap['p50']:.1f} / {cap['p90']:.1f} Mt"
        "  (low / median / high case)",
        "  P10-P90 band               : sampled uncertainty only; excludes systematic/model bias",
        f"  mean                       : {cap['mean']:.1f} Mt",
        "",
        "Linear surrogate (NOT_VALIDATED)",
        f"  R2 / RMSE                  : {sur['r2']:.3f} / {sur['rmse_mt']:.2f} Mt",
        "  sensitivity (Mt per sigma) :",
    ]
    lines += [
        f"      {name:<20} {value:+8.2f}" for name, value in report["sensitivity_mt_per_sigma"].items()
    ]
    if inj["within_limit"] is None:
        verdict = UNAVAILABLE
    else:
        verdict = ("WITHIN LIMIT" if inj["within_limit"] else "EXCEEDS LIMIT") + " (NOT_VALIDATED)"
    max_rate = inj["max_rate_m3_s"]
    lines += [
        "",
        "Injectivity (Theis brine analog; NOT_VALIDATED, outside the approved model)",
        f"  fracture pressure          : {_pa_to_mpa(inj['fracture_pressure_pa'], 1)}",
        f"  allowable dP headroom      : {_pa_to_mpa(inj['allowable_delta_p_pa'], 2)}",
        f"  planned rate dP            : {inj['planned_delta_p_pa']/1e6:.2f} MPa at {inj['planned_rate_m3_s']:.3f} m3/s",
        f"  max sustainable rate       : {UNAVAILABLE if max_rate is None else f'{max_rate:.3f} m3/s'}",
        f"  verdict                    : {verdict}",
    ]
    missing = [_MISSING_INPUT_REASON[name] for name in UNSET_SCALARS
               if inj["caller_supplied_criteria"].get(name) is None]
    if missing:
        lines.append(f"  UNAVAILABLE because        : {missing[0]}")
        lines += [f"                               {reason}" for reason in missing[1:]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = _screen(_merge_config(args, argv))
    except ValueError as exc:
        print(f"ccs-screen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else _render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
