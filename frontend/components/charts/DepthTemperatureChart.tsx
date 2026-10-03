"use client";

import { num } from "@/lib/format";
import { label, type AssessmentResult } from "@/lib/assessment";
import { niceTicks, useWidth } from "./useWidth";

export type ObservationStatus = "selected" | "eligible" | "excluded" | "withheld" | "not_assessed";

export interface ObservationPoint {
  index: number;
  depth_m: number;
  temperature_k: number;
  method: string;
  depth_datum: string;
  depth_convention: string;
  status: ObservationStatus;
  reasons: string[];
  plotted: boolean;
}

interface InputObservation {
  index: number;
  depth_m: number;
  temperature_k: number;
  method: string;
  depth_datum: string;
  depth_convention: string;
  passed_to_engine: boolean;
}

interface EngineObservation {
  depth_m: number;
  temperature_k: number;
  method: string;
  depth_datum?: string | null;
  /** Index of the submitted observation, as reported by the API. */
  input_index?: number | null;
  reasons?: string[];
}

/**
 * The engine observation is this submitted one. Identity comes from the API's
 * ``input_index``; readings with equal depth, temperature and method but a
 * different datum or source are different observations.
 */
const same = (a: EngineObservation, b: InputObservation) =>
  typeof a.input_index === "number"
    ? a.input_index === b.index
    : a.depth_m === b.depth_m && a.temperature_k === b.temperature_k && a.method === b.method
      && (a.depth_datum ?? null) === (b.depth_datum ?? null);

/** Readable explanations of the engine's exclusion codes. */
const REASON_LABELS: Record<string, string> = {
  METHOD_NOT_ELIGIBLE: "method not eligible",
  OUTSIDE_STORAGE_INTERVAL: "outside the interval",
  BELOW_RECORDED_TOTAL_DEPTH: "below total depth",
  TOTAL_DEPTH_NOT_RECORDED: "total depth missing",
  DEPTH_REFERENCE_NOT_ESTABLISHED: "depth datum not established",
  UNSUPPORTED_DEPTH_DATUM: "depth not from ground level",
};

/**
 * Classify every submitted observation from the API's own selection lists.
 * Nothing is recomputed: the status is whatever the engine reported.
 */
export function observationPoints(item: AssessmentResult): {
  points: ObservationPoint[];
  datum: string;
  convention: string;
  comparable: boolean;
} {
  const inputs = item.inputs as {
    depth_reference: { datum: string; convention: string };
    temperature_observations: InputObservation[];
  };
  const selection = item.result.temperature_selection as
    | {
        evaluated?: boolean;
        selected_observation?: EngineObservation | null;
        eligible_observations?: EngineObservation[];
        excluded_observations?: EngineObservation[];
      }
    | undefined;
  const { datum, convention } = inputs.depth_reference;
  const comparable = datum !== "unknown" && convention !== "unknown";
  let selectedUsed = false;
  const points = inputs.temperature_observations.map((o): ObservationPoint => {
    let status: ObservationStatus = "not_assessed";
    let reasons: string[] = [];
    if (!o.passed_to_engine) {
      status = "withheld";
      reasons = ["not TVD: withheld from the model"];
    } else if (selection && selection.evaluated !== false) {
      const excluded = selection.excluded_observations?.find((e) => same(e, o));
      if (!selectedUsed && selection.selected_observation && same(selection.selected_observation, o)) {
        status = "selected";
        selectedUsed = true;
      } else if (excluded) {
        status = "excluded";
        reasons = (excluded.reasons ?? []).map((r) => REASON_LABELS[r] ?? r);
      } else if (selection.eligible_observations?.some((e) => same(e, o))) {
        status = "eligible";
      }
    } else {
      reasons = ["not assessed: the depth reference is not usable"];
    }
    return {
      index: o.index,
      depth_m: o.depth_m,
      temperature_k: o.temperature_k,
      method: o.method,
      depth_datum: o.depth_datum,
      depth_convention: o.depth_convention,
      status,
      reasons,
      // Overlay only where the observation's depth reference is the interval's.
      plotted: comparable && o.depth_datum === datum && o.depth_convention === convention,
    };
  });
  return { points, datum, convention, comparable };
}

const STATUS_TEXT: Record<ObservationStatus, string> = {
  selected: "Selected",
  eligible: "Eligible",
  excluded: "Excluded",
  withheld: "Withheld",
  not_assessed: "Not assessed",
};

function Symbol({ status, x, y }: { status: ObservationStatus; x: number; y: number }) {
  if (status === "selected") {
    return <path d={`M${x} ${y - 8} L${x + 8} ${y} L${x} ${y + 8} L${x - 8} ${y} Z`} className="sym-selected" />;
  }
  if (status === "eligible") return <circle cx={x} cy={y} r={5} className="sym-eligible" />;
  return (
    <path d={`M${x - 5} ${y - 5} L${x + 5} ${y + 5} M${x + 5} ${y - 5} L${x - 5} ${y + 5}`} className="sym-excluded" />
  );
}

function LegendSymbol({ status }: { status: ObservationStatus }) {
  return (
    <svg width={18} height={18} aria-hidden="true">
      <Symbol status={status} x={9} y={9} />
    </svg>
  );
}

const celsius = (k: number) => k - 273.15;

/**
 * Storage interval and submitted temperatures against depth. Points only; no
 * line joins them, because the model does not interpolate. Observations whose
 * depth reference differs from the interval's are listed, not overlaid.
 */
export function DepthTemperatureChart({ item }: { item: AssessmentResult }) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const inputs = item.inputs as {
    storage_interval: { z_top_m: number; z_base_m: number };
    total_depth: { value_m: number } | null;
  };
  const { points, datum, convention, comparable } = observationPoints(item);
  const shown = points.filter((p) => p.plotted && p.status !== "withheld");
  const top = inputs.storage_interval.z_top_m;
  const base = inputs.storage_interval.z_base_m;
  const td = inputs.total_depth?.value_m ?? null;

  const depths = [top, base, ...(td !== null ? [td] : []), ...shown.map((p) => p.depth_m)];
  const span = Math.max(...depths) - Math.min(...depths) || 100;
  const dMin = Math.max(0, Math.min(...depths) - span * 0.1);
  const dMax = Math.max(...depths) + span * 0.1;
  const temps = shown.map((p) => celsius(p.temperature_k));
  const tLow = temps.length ? Math.floor((Math.min(...temps) - 5) / 5) * 5 : 0;
  const tHigh = temps.length ? Math.ceil((Math.max(...temps) + 5) / 5) * 5 : 100;

  const left = 56;
  const right = Math.max(width - 14, left + 120);
  const plotTop = 10;
  const height = 320;
  const plotBottom = height - 36;
  const y = (d: number) => plotTop + ((plotBottom - plotTop) * (d - dMin)) / (dMax - dMin);
  const x = (t: number) => left + ((right - left) * (t - tLow)) / (tHigh - tLow || 1);
  const reference = `${label(datum)}, ${label(convention)}`;

  return (
    <figure className="chart" ref={ref}>
      <figcaption className="chart-title">Storage interval and temperature observations</figcaption>
      <p className="chart-note">
        Depth in metres below {datum === "unknown" ? "an unknown reference" : label(datum).toLowerCase()} ({convention}), as declared.
        {comparable ? "" : " The depth reference is not established, so observations are listed but not overlaid on the interval."}
      </p>
      <svg width={width} height={height} role="img"
           aria-label={`Storage interval ${num(top, 0)} to ${num(base, 0)} m${td !== null ? `, total depth ${num(td, 0)} m` : ""}; ${shown.length} of ${points.length} observations plotted. Details in the table below.`}>
        <rect x={left} y={y(top)} width={right - left} height={Math.max(y(base) - y(top), 2)} className="interval-band" />
        <text x={left + 4} y={y(top) - 4} className="axis-text">Storage interval</text>
        <line x1={left} x2={right} y1={y((top + base) / 2)} y2={y((top + base) / 2)} className="state-line" />
        {td !== null ? (
          <>
            <line x1={left} x2={right} y1={y(td)} y2={y(td)} className="td-line" />
            <text x={left + 4} y={y(td) + 13} className="axis-text">Total depth</text>
          </>
        ) : null}
        {niceTicks(dMin, dMax, 5).map((d) => (
          <text key={d} x={left - 6} y={y(d) + 4} textAnchor="end" className="axis-text">
            {num(d, 0)}
          </text>
        ))}
        {temps.length
          ? niceTicks(tLow, tHigh, 4).map((t) => (
              <text key={t} x={x(t)} y={height - 18} textAnchor="middle" className="axis-text">
                {num(t, 0)}
              </text>
            ))
          : null}
        <text x={right} y={height - 2} textAnchor="end" className="axis-text">
          {temps.length ? "temperature (°C)" : "no observation can be plotted"}
        </text>
        {shown.map((p) => (
          <g key={p.index}>
            <Symbol status={p.status} x={x(celsius(p.temperature_k))} y={y(p.depth_m)} />
            {p.status === "selected" ? (
              x(celsius(p.temperature_k)) > right - 70 ? (
                <text x={x(celsius(p.temperature_k)) - 11} y={y(p.depth_m) - 8} textAnchor="end" className="sym-label">
                  selected
                </text>
              ) : (
                <text x={x(celsius(p.temperature_k)) + 11} y={y(p.depth_m) - 8} className="sym-label">
                  selected
                </text>
              )
            ) : null}
          </g>
        ))}
      </svg>
      <ul className="legend">
        {(["selected", "eligible", "excluded"] as const).map((s) => (
          <li key={s}>
            <LegendSymbol status={s} /> {STATUS_TEXT[s]}
          </li>
        ))}
        <li>
          <span className="legend-band" aria-hidden="true" /> Storage interval (dashed: midpoint state point)
        </li>
      </ul>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">Temperature observations ({reference})</caption>
          <thead>
            <tr>
              <th scope="col">Depth (m)</th>
              <th scope="col">Temperature</th>
              <th scope="col">Method</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.index} data-selected={p.status === "selected"}>
                <td>{num(p.depth_m, 1)}</td>
                <td>
                  {num(celsius(p.temperature_k), 1)} °C ({num(p.temperature_k, 2)} K)
                </td>
                <td>{label(p.method)}</td>
                <td>
                  {STATUS_TEXT[p.status]}
                  {p.reasons.length ? `: ${p.reasons.join(", ")}` : ""}
                  {!p.plotted && p.status !== "withheld"
                    ? comparable
                      ? " (not plotted: different depth reference)"
                      : " (not plotted: depth reference not established)"
                    : ""}
                </td>
              </tr>
            ))}
            {points.length === 0 ? (
              <tr>
                <td colSpan={4}>No temperature observations were submitted.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
