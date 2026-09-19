"""Command-line screening run: capacity distribution, sensitivity, injectivity.

    ccs-screen --samples 2000 --porosity 0.10 0.20 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from typing import Any

from ccs_screen.config import ScreeningConfig
from ccs_screen.monte_carlo import DEPLETED_GAS_ANALOG, McResult, UniformPriors, run_capacity_mc
from ccs_screen.pressure import (
    DEFAULT_FRACTURE_GRADIENT_PA_M,
    DEFAULT_SAFETY_FACTOR,
    allowable_delta_p_pa,
    fracture_pressure_pa,
    max_injection_rate_m3_s,
    theis_injection_delta_p_pa,
)
from ccs_screen.surrogate import evaluate, fit_linear_surrogate, sensitivity

SECONDS_PER_YEAR = 365.25 * 24 * 3600

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
    "fracture_gradient_pa_m": DEFAULT_FRACTURE_GRADIENT_PA_M,
    "safety_factor": DEFAULT_SAFETY_FACTOR,
}

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
    "fracture_gradient_pa_m": "fracture gradient (Pa/m)",
    "safety_factor": "fraction of fracture pressure allowed (-)",
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
        description="Screening-grade CO2 storage capacity, sensitivity and injectivity.",
        epilog="Defaults describe a synthetic depleted-gas analog, not a real site.",
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

    aquifer = parser.add_argument_group("injectivity", "Theis brine-analog aquifer")
    for name, value in SCALAR_DEFAULTS.items():
        aquifer.add_argument(
            f"--{name.replace('_', '-')}",
            dest=name,
            type=float,
            default=default_for(value),
            help=f"{SCALAR_HELP[name]} (default: {value:g})",
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
    for name in SCALAR_DEFAULTS:
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
    for name in SCALAR_DEFAULTS:
        setattr(resolved, name, getattr(revalidated, name))
    resolved.samples = revalidated.samples
    resolved.seed = revalidated.seed
    resolved.well_id = revalidated.well_id
    return resolved


def _screen(args: argparse.Namespace) -> dict[str, Any]:
    if args.samples <= 0:
        raise ValueError("--samples must be a positive integer")
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
    # Mid-prior reservoir pressure sets the starting point for the headroom check.
    initial_pressure_pa = sum(priors.pressure_pa) / 2
    headroom = allowable_delta_p_pa(
        initial_pressure_pa=initial_pressure_pa,
        depth_m=args.depth_m,
        fracture_gradient_pa_m=args.fracture_gradient_pa_m,
        safety_factor=args.safety_factor,
    )
    planned_dp = theis_injection_delta_p_pa(rate_m3_s=args.rate_m3_s, **aquifer)
    max_rate = max_injection_rate_m3_s(allowable_delta_p_pa=headroom, **aquifer) if headroom > 0 else 0.0

    return {
        "well_id": getattr(args, "well_id", None),
        "n_samples": result.n,
        "seed": args.seed,
        "deterministic": all(low == high for low, high in priors_map.values()),
        "capacity_mt": {
            "p10": result.p10_mt,
            "p50": result.p50_mt,
            "p90": result.p90_mt,
            "mean": result.mean_mt,
        },
        "surrogate": {"r2": metrics.r2, "rmse_mt": metrics.rmse_mt, "mae_mt": metrics.mae_mt},
        "sensitivity_mt_per_sigma": dict(sensitivity(model)),
        "injectivity": {
            "initial_pressure_pa": initial_pressure_pa,
            "fracture_pressure_pa": fracture_pressure_pa(args.depth_m, args.fracture_gradient_pa_m),
            "allowable_delta_p_pa": headroom,
            "planned_rate_m3_s": args.rate_m3_s,
            "planned_delta_p_pa": planned_dp,
            "max_rate_m3_s": max_rate,
            "within_limit": bool(planned_dp <= headroom),
        },
    }


def _render(report: dict[str, Any]) -> str:
    cap = report["capacity_mt"]
    sur = report["surrogate"]
    inj = report["injectivity"]
    header = report.get("well_id") or "synthetic depleted-gas analog - not a site model"
    lines = [
        f"CCS screening run ({header})",
        f"  realisations               : {report['n_samples']} (seed {report['seed']})",
    ]
    if report.get("deterministic"):
        lines.append("  NOTE: all priors are point values - P10 = P50 = P90, no uncertainty")
    lines += [
        "",
        "Capacity",
        f"  P10 / P50 / P90            : {cap['p10']:.1f} / {cap['p50']:.1f} / {cap['p90']:.1f} Mt",
        f"  mean                       : {cap['mean']:.1f} Mt",
        "",
        "Linear surrogate",
        f"  R2 / RMSE                  : {sur['r2']:.3f} / {sur['rmse_mt']:.2f} Mt",
        "  sensitivity (Mt per sigma) :",
    ]
    lines += [
        f"      {name:<20} {value:+8.2f}" for name, value in report["sensitivity_mt_per_sigma"].items()
    ]
    verdict = "WITHIN LIMIT" if inj["within_limit"] else "EXCEEDS LIMIT"
    lines += [
        "",
        "Injectivity (Theis brine analog, screening only)",
        f"  fracture pressure          : {inj['fracture_pressure_pa']/1e6:.1f} MPa",
        f"  allowable dP headroom      : {inj['allowable_delta_p_pa']/1e6:.2f} MPa",
        f"  planned rate dP            : {inj['planned_delta_p_pa']/1e6:.2f} MPa at {inj['planned_rate_m3_s']:.3f} m3/s",
        f"  max sustainable rate       : {inj['max_rate_m3_s']:.3f} m3/s",
        f"  verdict                    : {verdict}",
    ]
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
