"""`ccs-ingest` -- normalize structured sources, report completeness, screen wells.

    ccs-ingest --data-dir data                                  # completeness
    ccs-ingest --data-dir data --well "SALUZZO|1"               # one record
    ccs-ingest --data-dir data --screen --scenario sensitivity  # fleet funnel
    ccs-ingest --data-dir data --screen --scenario central --well "SALUZZO|1"
    ccs-ingest --data-dir data --compare-temperature --well "TRECATE|9|ST"

The interface stays flat on purpose. Screening is a mode of the same pipeline,
not a separate program, and a subcommand tree would add ceremony without adding
capability.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ccs_screen.ingest.assumptions import NO_ASSUMPTIONS, AssumptionError, AssumptionSet
from ccs_screen.ingest.completeness import (
    IncompleteWellError,
    assess,
    build_report,
    build_screening_config,
)
from ccs_screen.ingest.normalize import WellNormalizer
from ccs_screen.ingest.report import (
    build_funnel,
    compare_temperature_methods,
    screen_well,
)
from ccs_screen.ingest.scenario import (
    BUILTIN_SCENARIOS,
    NO_SCENARIO,
    ScreeningScenario,
    load_scenario,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ccs-ingest",
        description="Normalize structured well sources, report completeness, and screen.",
        epilog="Reads only the structured sources; the scanned PDF corpus is never touched.",
    )
    parser.add_argument("--data-dir", default="data", help="directory holding the structured sources")
    parser.add_argument("--well", help="show one canonical well id in full")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    parser.add_argument("--scenario", metavar="NAME|PATH",
                        help=f"engineering assumptions: a built-in "
                             f"({', '.join(sorted(BUILTIN_SCENARIOS))}) or a scenario JSON file")
    parser.add_argument("--assumptions", metavar="PATH",
                        help="a bare assumption-set JSON (wrapped into an ad-hoc scenario)")
    parser.add_argument("--screen", action="store_true",
                        help="run the screening engine and report the funnel")
    parser.add_argument("--compare-temperature", action="store_true",
                        help="show what each temperature method implies for capacity")
    parser.add_argument("--samples", type=int, default=2000, help="Monte Carlo realisations")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")

    parser.add_argument("--list-incomplete", action="store_true",
                        help="list every well that cannot be screened, with reasons")
    parser.add_argument("--emit-configs", metavar="DIR",
                        help="write a ScreeningConfig JSON for each screenable well")
    return parser


def resolve_scenario(args: argparse.Namespace) -> ScreeningScenario:
    """Turn --scenario / --assumptions into one scenario object.

    A bare assumption set is wrapped rather than rejected, so the older
    ``--assumptions`` invocation keeps working through the new model.
    """
    if args.scenario and args.assumptions:
        raise AssumptionError("use either --scenario or --assumptions, not both")
    if args.scenario:
        return load_scenario(args.scenario)
    if args.assumptions:
        assumptions = AssumptionSet.from_json_file(args.assumptions)
        return ScreeningScenario(
            name=assumptions.name or "ad-hoc",
            description=f"ad-hoc scenario wrapped from {args.assumptions}",
            assumptions=assumptions,
            rationale="supplied via --assumptions",
        )
    return NO_SCENARIO


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload: dict[str, Any] = {}
    out_lines: list[str] = []

    try:
        data_dir = Path(args.data_dir)
        if not data_dir.exists():
            raise ValueError(f"data directory not found: {data_dir}")
        if args.samples <= 0:
            raise ValueError("--samples must be a positive integer")

        scenario = resolve_scenario(args)
        normalizer = WellNormalizer(data_dir)
        records = normalizer.run()
        if not records:
            raise ValueError(
                f"no wells normalized from {data_dir}; available sources: "
                f"{normalizer.sources.available}"
            )
        by_id = {r.canonical_id: r for r in records}
        if args.well and args.well not in by_id:
            raise ValueError(f"no well with canonical id {args.well!r}")

        payload["scenario"] = scenario.to_dict()
        payload["raw_records"] = len(normalizer.raw_records)

        if args.compare_temperature:
            targets = [by_id[args.well]] if args.well else records
            comparisons = [
                compare_temperature_methods(r, scenario, samples=min(args.samples, 500), seed=args.seed)
                for r in targets
            ]
            comparisons = [c for c in comparisons if len(c.variants) > 1]
            payload["temperature_comparisons"] = [c.to_dict() for c in comparisons]
            out_lines.append("Temperature-method comparison (same scenario, temperature varied)")
            for c in comparisons:
                out_lines.append(f"\n  {c.canonical_id}  (selected: {c.selected_method})")
                for v in c.variants:
                    p50 = "n/a" if v.p50_mt is None else f"{v.p50_mt:8.2f} Mt"
                    out_lines.append(
                        f"    {v.method:<30} {v.temperature_k:7.2f} K @ {v.depth_m:8.1f} m  P50={p50}"
                    )
                if c.p50_spread_percent is not None:
                    out_lines.append(
                        f"    -> P50 spread {c.p50_spread_mt:.2f} Mt ({c.p50_spread_percent:.1f}%) "
                        f"from temperature method alone"
                    )

        elif args.screen:
            reports = [screen_well(r, scenario, samples=args.samples, seed=args.seed)
                       for r in records]
            funnel = build_funnel(records, scenario, reports)
            payload["funnel"] = funnel.to_dict()
            payload["wells"] = [r.to_dict() for r in reports]
            out_lines.append(funnel.render())
            if args.well:
                match = next(r for r in reports if r.canonical_id == args.well)
                out_lines += ["", "=" * 62, "", match.render()]

        else:
            assumptions = scenario.assumptions if scenario is not NO_SCENARIO else NO_ASSUMPTIONS
            report = build_report(records, assumptions, sources=normalizer.used_sources)
            payload["report"] = report.to_dict()
            out_lines.append(report.render_summary())
            if args.well:
                out_lines += ["", "=" * 62, "", assess(by_id[args.well], assumptions).render()]
            if args.well:
                payload["well"] = by_id[args.well].to_dict()

        if args.list_incomplete:
            out_lines += ["", "Wells that cannot be screened"]
            for rec in records:
                report_obj = screen_well(rec, scenario, samples=1, seed=args.seed)
                if not report_obj.screenable:
                    out_lines.append(
                        f"  {rec.canonical_id:<26} missing: {', '.join(report_obj.missing_fields)}"
                    )

        if args.emit_configs:
            out = Path(args.emit_configs)
            out.mkdir(parents=True, exist_ok=True)
            written, refused = [], []
            for rec in records:
                try:
                    config = build_screening_config(rec, scenario.assumptions)
                except IncompleteWellError as exc:
                    refused.append({"well": rec.canonical_id, "missing": list(exc.missing)})
                    continue
                name = rec.canonical_id.replace("|", "_").replace(" ", "-").strip("_") or "well"
                body: dict[str, Any] = {k: list(v) for k, v in config.prior_ranges().items()}
                body["well_id"] = config.well_id
                body["depth_m"] = config.depth_m
                (out / f"{name}.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
                written.append(str(out / f"{name}.json"))
            payload["emitted_configs"] = written
            payload["refused_wells"] = refused
            out_lines += ["", f"ScreeningConfigs written : {len(written)}",
                          f"Wells refused            : {len(refused)}"]

    except (ValueError, AssumptionError) as exc:
        print(f"ccs-ingest: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0
    print("\n".join(out_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
