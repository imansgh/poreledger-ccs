"use client";

import { num } from "@/lib/format";
import { SCENARIO_LABELS, STATUS_LABELS, type ScenarioResult } from "@/lib/assessment";
import { niceMax, ticks, useWidth } from "./useWidth";

const ROW = 64;
const TOP = 6;
const AXIS = 34;
const PAD_X = 12;

/**
 * Capacity uncertainty: one P10-P90 interval with a P50 marker per VALIDATED
 * water-level scenario, on a shared axis starting at zero. Values are the
 * API's percentiles; nothing is computed here. A scenario without a
 * reportable estimate is named and stated, never drawn as zero.
 */
export function CapacityChart({
  scenarios,
  samples,
}: {
  scenarios: ScenarioResult[];
  samples: number;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const plotted = scenarios.filter((s) => s.capacity_mt);
  if (!plotted.length) return null;

  const max = niceMax(Math.max(...plotted.map((s) => s.capacity_mt!.p90)));
  const left = PAD_X;
  const right = Math.max(width - PAD_X, left + 100);
  const x = (v: number) => left + ((right - left) * v) / max;
  const height = TOP + scenarios.length * ROW + AXIS;
  const summary = plotted
    .map((s) => {
      const c = s.capacity_mt!;
      return `${SCENARIO_LABELS[s.name] ?? s.name}: P10 ${num(c.p10, 2)}, P50 ${num(c.p50, 2)}, P90 ${num(c.p90, 2)} Mt`;
    })
    .join("; ");

  return (
    <figure className="chart" ref={ref}>
      <figcaption className="chart-title">Capacity range by water-table scenario (Mt CO2)</figcaption>
      <svg width={width} height={height} role="img" aria-label={`Capacity ranges. ${summary}.`}>
        {ticks(0, max, 4).map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={TOP} y2={height - AXIS + 4} className="grid-line" />
            <text x={x(t)} y={height - AXIS + 18} textAnchor="middle" className="axis-text">
              {num(t, 2)}
            </text>
          </g>
        ))}
        <text x={right} y={height - 4} textAnchor="end" className="axis-text">
          Mt CO2
        </text>
        {scenarios.map((s, i) => {
          const y = TOP + i * ROW;
          const c = s.capacity_mt;
          return (
            <g key={s.name}>
              <text x={left} y={y + 13} className="row-label">
                {SCENARIO_LABELS[s.name] ?? s.name}
              </text>
              {c ? (
                <>
                  <rect x={x(c.p10)} y={y + 22} width={Math.max(x(c.p90) - x(c.p10), 2)} height={12}
                        className="range-bar" />
                  <line x1={x(c.p50)} x2={x(c.p50)} y1={y + 17} y2={y + 39} className="p50-mark" />
                  <text x={left} y={y + 54} className="row-values">
                    {`P10 ${num(c.p10, 2)}  |  P50 ${num(c.p50, 2)}  |  P90 ${num(c.p90, 2)}`}
                  </text>
                </>
              ) : (
                <text x={left} y={y + 34} className="row-missing">
                  {`Not plotted: ${STATUS_LABELS[s.validation_status] ?? s.validation_status}, no estimate`}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <p className="chart-note">
        Bar: P10 to P90. Mark: P50. Percentiles of {num(samples, 0)} Monte Carlo realisations over
        the approved priors (porosity, storage efficiency, brine density) for your inputs as declared.
        They show that sampled spread only: not input errors, model bias, or the chance that a site
        holds this amount. P10 is the low case.
      </p>
      <details className="disclosure">
        <summary>Show as table</summary>
        <table>
          <caption className="sr-only">Capacity percentiles by scenario</caption>
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              <th scope="col">Status</th>
              <th scope="col">P10 (Mt)</th>
              <th scope="col">P50 (Mt)</th>
              <th scope="col">P90 (Mt)</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s.name}>
                <th scope="row">{SCENARIO_LABELS[s.name] ?? s.name}</th>
                <td>{STATUS_LABELS[s.validation_status] ?? s.validation_status}</td>
                <td>{s.capacity_mt ? num(s.capacity_mt.p10, 2) : "no estimate"}</td>
                <td>{s.capacity_mt ? num(s.capacity_mt.p50, 2) : "no estimate"}</td>
                <td>{s.capacity_mt ? num(s.capacity_mt.p90, 2) : "no estimate"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
