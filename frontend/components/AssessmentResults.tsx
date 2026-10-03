"use client";

import { CapacityChart } from "./charts/CapacityChart";
import { DepthTemperatureChart } from "./charts/DepthTemperatureChart";
import { num } from "@/lib/format";
import {
  SCENARIO_LABELS,
  STATUS_LABELS,
  downloadText,
  label,
  type AssessmentResult,
  type EvaluationResponse,
  type OutcomeCategory,
} from "@/lib/assessment";

const HEADLINE: Record<OutcomeCategory, { text: string; tone: string }> = {
  estimate: { text: "Estimate available", tone: "outcome-estimate" },
  partial_estimate: { text: "Estimate for one scenario only", tone: "outcome-partial" },
  information_needed: { text: "More information needed", tone: "outcome-needed" },
  outside_validated_range: { text: "Outside the model's validated range", tone: "outcome-outside" },
};

/** A DOM id from a user identifier, which may contain spaces or "|". */
export function resultDomId(value: string): string {
  return `result-${value.replace(/[^A-Za-z0-9_-]/g, "-")}`;
}

function scenarioNames(names: string[]): string {
  if (names.length === 2) return "both water-table scenarios";
  return names.map((n) => (SCENARIO_LABELS[n] ?? n).toLowerCase()).join(", ");
}

type Prior = {
  distribution?: string;
  low?: number;
  high?: number;
  unit?: string;
  status?: string;
  provenance?: string;
  citation?: { short?: string; title?: string; reference?: string } | null;
};

function Inputs({ item }: { item: AssessmentResult }) {
  const inputs = item.inputs as Record<string, any>;
  const priors = (item.result.sampled_inputs ?? {}) as Record<string, Prior>;
  const rows: [string, string][] = [
    ["Storage area", `${inputs.storage_area.original.value} ${label(inputs.storage_area.original.unit)} (${num(inputs.storage_area.value_m2, 4)} m²)`],
    ["Storage interval", `${inputs.storage_interval.original.top}-${inputs.storage_interval.original.base} ${inputs.storage_interval.original.unit}`],
    ["Depth reference", `${label(inputs.depth_reference.datum)}, ${label(inputs.depth_reference.convention)} (declared, not verified)`],
    ["Total depth", inputs.total_depth ? `${inputs.total_depth.original.value} ${inputs.total_depth.original.unit}` : "not given"],
    ["Ground elevation", inputs.surface_elevation ? `${inputs.surface_elevation.original.value} ${inputs.surface_elevation.original.unit} above ${label(inputs.surface_elevation.reference)}` : "not given"],
    ["Temperature observations", String(inputs.temperature_observations.length)],
  ];
  return (
    <>
      <h4>Your inputs{item.synthetic ? " (synthetic example)" : ""}</h4>
      <table className="kv-table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th scope="row">{k}</th>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>Set by the approved model</h4>
      <table className="kv-table">
        <tbody>
          {Object.entries(priors).map(([k, v]) => (
            <tr key={k}>
              <th scope="row">{k.replace(/_/g, " ")}</th>
              <td>
                {v.distribution} {v.low}-{v.high} {v.unit !== "-" ? v.unit : ""}; {v.status}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Steps({ item }: { item: AssessmentResult }) {
  const r = item.result as Record<string, any>;
  const interval = r.storage_interval;
  const selection = r.temperature_selection;
  return (
    <>
      <p>
        <code>{item.model.capacity_equation}</code>
      </p>
      <ol className="steps-list">
        {interval?.h_g_m != null ? (
          <li>
            Gross thickness h_g = z_base - z_top = {num(interval.h_g_m, 1)} m; state point z_state =
            midpoint = {num(interval.z_state_m, 1)} m (project convention).
          </li>
        ) : (
          <li>Interval geometry not used: the depth reference is not usable.</li>
        )}
        <li>
          Temperature:{" "}
          {selection?.temperature_k != null
            ? `${num(selection.temperature_k, 2)} K, ${label(selection.selected_observation?.method ?? "")} at ${num(selection.selected_observation?.depth_m ?? 0, 1)} m, selected by the approved rule`
            : "not available; never assumed"}
          .
        </li>
        {r.water_level_scenarios.map((s: any) => (
          <li key={s.name}>
            {SCENARIO_LABELS[s.name] ?? s.name}: z_wl = {s.z_wl_m != null ? `${num(s.z_wl_m, 1)} m` : "n/a"};
            pressure P_EOS = 101325 Pa + rho_brine x g x (z_state - z_wl)
            {s.pressure_eos_pa ? ` = ${num(s.pressure_eos_pa.low / 1e6, 2)}-${num(s.pressure_eos_pa.high / 1e6, 2)} MPa` : ""}
            ; status {STATUS_LABELS[s.validation_status] ?? s.validation_status}.
          </li>
        ))}
        <li>
          CO2 density: Peng-Robinson with Peneloux shift; capacity from {num(item.run.samples, 0)} Monte
          Carlo realisations, seed {item.run.seed}.
        </li>
      </ol>
    </>
  );
}

function References({ item }: { item: AssessmentResult }) {
  const priors = (item.result.sampled_inputs ?? {}) as Record<string, Prior>;
  return (
    <ul>
      {Object.entries(priors).map(([k, v]) => (
        <li key={k}>
          <strong>{k.replace(/_/g, " ")}</strong>: {v.provenance}
          {v.citation ? ` (${v.citation.short ?? v.citation.reference ?? v.citation.title ?? ""})` : ""}
        </li>
      ))}
    </ul>
  );
}

function OneResult({ item, multiple, outdated }: { item: AssessmentResult; multiple: boolean; outdated: boolean }) {
  const headingId = resultDomId(item.assessment_id);
  const outcome = item.outcome;
  const headline = HEADLINE[outcome.category] ?? HEADLINE.information_needed;
  const scenarios = item.result.water_level_scenarios;
  const diagnosticValues = scenarios.filter((s) => s.diagnostic_capacity_mt);
  const warnings = item.interpretation.warnings ?? [];
  return (
    <article className="panel result-card" aria-labelledby={`${headingId}-title`} id={headingId}>
      <header className="result-card-head">
        <h3 id={`${headingId}-title`}>
          {item.name || item.assessment_id}
          {item.name ? <span className="tech nowrap"> {item.assessment_id}</span> : null}
        </h3>
        {item.synthetic ? <span className="tag tag-synthetic">SYNTHETIC EXAMPLE</span> : null}
        {outdated ? <span className="tag tag-outdated">OUTDATED</span> : null}
      </header>

      {item.synthetic ? (
        <p className="synthetic-result" role="note">
          Fictional inputs: shows how the model behaves, not an estimate for any real site.
        </p>
      ) : null}

      <div className={`outcome ${headline.tone}`}>
        <p className="outcome-status">{headline.text}</p>
        <p className="outcome-restriction">
          Conditional screening result from inputs as declared. Not a certified or site-specific
          capacity.
        </p>
        {outcome.blocking_reasons.length ? (
          <ul className="reasons">
            {outcome.blocking_reasons.map((r) => (
              <li key={r.code} className={r.kind === "outside_validated_range" ? "reason-outside" : "reason-input"}>
                <p className="reason-title">
                  {r.title} <span className="reason-scope">({scenarioNames(r.scenarios)})</span>
                </p>
                <p>{r.explanation}</p>
                {r.action ? (
                  <p>
                    <strong>What to do:</strong> {r.action}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <ul className="scenario-status">
        {scenarios.map((s) => (
          <li key={s.name}>
            <span>{SCENARIO_LABELS[s.name] ?? s.name}</span>
            <span className={`status-pill status-${s.validation_status}`}>
              {STATUS_LABELS[s.validation_status] ?? s.validation_status}
            </span>
          </li>
        ))}
      </ul>

      {scenarios.some((s) => s.capacity_mt) ? (
        <CapacityChart scenarios={scenarios} samples={item.run.samples} />
      ) : (
        <p className="chart-note">No capacity range is shown: no scenario has a reportable estimate.</p>
      )}
      <DepthTemperatureChart item={item} />

      <div className="details-group">
        <details className="disclosure">
          <summary>
            Inputs and provenance
            <span className="summary-hint"> your values, and the {Object.keys(item.result.sampled_inputs ?? {}).length || "approved"} model-controlled priors</span>
          </summary>
          <Inputs item={item} />
        </details>
        <details className="disclosure">
          <summary>
            Calculation steps and formulas
            <span className="summary-hint"> thickness, state point, pressure, temperature, density</span>
          </summary>
          <Steps item={item} />
        </details>
        <details className="disclosure">
          <summary>
            Prior distributions and references
            <span className="summary-hint"> where the model-controlled ranges come from</span>
          </summary>
          <References item={item} />
        </details>
        {diagnosticValues.length ? (
          <details className="disclosure">
            <summary>
              Diagnostic values (not estimates)
              <span className="summary-hint"> computed outside the validated range</span>
            </summary>
            <p className="field-notice">For diagnosis only. Do not report or use these as capacity estimates.</p>
            <ul>
              {diagnosticValues.map((s) => (
                <li key={s.name}>
                  {SCENARIO_LABELS[s.name] ?? s.name}: diagnostic P50 {num(s.diagnostic_capacity_mt!.p50, 2)} Mt
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        <details className="disclosure">
          <summary>
            Assumptions and limitations
            <span className="summary-hint"> {warnings.length + item.limitations.length} items</span>
          </summary>
          <ul>
            {warnings.map((w) => (
              <li key={w.code}>{w.message}</li>
            ))}
            {item.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
        <details className="disclosure">
          <summary>
            Technical diagnostics
            <span className="summary-hint"> exact codes and engine messages</span>
          </summary>
          <ul className="code-list">
            {scenarios.map((s) => (
              <li key={s.name}>
                <code>{s.name}</code>: <code>{s.validation_status}</code>
                <ul>
                  {s.diagnostics.map((d, i) => (
                    <li key={i}>
                      <code>{d.code}</code> {d.message}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
          <pre className="json">{JSON.stringify(item.result, null, 2)}</pre>
        </details>
      </div>
      {multiple ? (
        <p>
          <a href="#results-heading">Back to all results</a>
        </p>
      ) : null}
    </article>
  );
}

/** Every assessment's result, summary first, with exports that keep statuses and labels. */
export function AssessmentResults({
  response,
  outdated = false,
}: {
  response: EvaluationResponse;
  outdated?: boolean;
}) {
  const synthetic = response.assessments.some((a) => a.synthetic);
  const stem = synthetic ? "ccs-assessment-SYNTHETIC" : "ccs-assessment";
  const multiple = response.assessments.length > 1;
  return (
    <section aria-labelledby="results-heading" className={`stack results${outdated ? " outdated" : ""}`}>
      <div className="panel results-head">
        <h2 id="results-heading" tabIndex={-1}>
          Results
        </h2>
        {outdated ? (
          <p className="outdated-note" role="status">
            Outdated: the inputs changed after this calculation. Calculate again to update.
          </p>
        ) : null}
        <div className="actions">
          <button type="button" className="secondary" disabled={outdated}
                  onClick={() => downloadText(`${stem}-results.json`, JSON.stringify(response, null, 2), "application/json")}>
            Download results (JSON)
          </button>
          <button type="button" className="secondary" disabled={outdated}
                  onClick={() => downloadText(`${stem}-summary.csv`, response.summary_csv, "text/csv")}>
            Download summary (CSV)
          </button>
        </div>
        {multiple ? (
          <table className="overview">
            <caption className="sr-only">Outcome of each assessment</caption>
            <tbody>
              {response.assessments.map((a) => (
                <tr key={a.assessment_id}>
                  <th scope="row">
                    <a href={`#${resultDomId(a.assessment_id)}`} className="nowrap">{a.assessment_id}</a>
                  </th>
                  <td>{(HEADLINE[a.outcome.category] ?? HEADLINE.information_needed).text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
      <div className="result-cards">
        {response.assessments.map((item) => (
          <OneResult key={item.assessment_id} item={item} multiple={multiple} outdated={outdated} />
        ))}
      </div>
    </section>
  );
}
