import { num, kelvinToCelsius } from "@/lib/format";
import { Notice } from "./Notice";
import type {
  ApprovedScreenResult,
  Diagnostic,
  LegacyScreenResult,
  ScreenResult,
  WaterLevelScenarioResult,
} from "@/lib/types";
import { isApproved } from "@/lib/types";

/**
 * The screening result, framed by what it is not.
 *
 * The approved model always reports both named water-level scenarios, each
 * with its own status and diagnostics. A legacy scenario's result keeps its
 * original layout and is badged NOT_VALIDATED. The interpretation block
 * returned by the API is authoritative for the caveat wording; this component
 * displays what the API sends and computes nothing.
 */
export function ResultPanel({ result }: { result: ScreenResult }) {
  if (isApproved(result)) return <ApprovedResultPanel result={result} />;
  return <LegacyResultPanel result={result} />;
}

// -- legacy (NOT_VALIDATED) -----------------------------------------------------

function NotValidatedNotice() {
  return (
    <Notice tone="advisory" title="NOT_VALIDATED">
      <p>
        This result comes from a legacy scenario outside the approved Model
        Contract. It is not a validated scientific screening result.
      </p>
    </Notice>
  );
}

export function LegacyResultPanel({ result }: { result: LegacyScreenResult }) {
  if (result.status === "blocked" || !result.scenario_based_capacity_mt) {
    return <BlockedPanel result={result} />;
  }

  const c = result.scenario_based_capacity_mt;
  const userSupplied = result.user_supplied_inputs ?? [];
  return (
    <section className="panel" aria-labelledby="result-heading">
      <h2 id="result-heading">Result</h2>
      <NotValidatedNotice />
      <div className="result-head">
        <div className="result-label">Scenario-based storage capacity (P50)</div>
        <div className="result-value">
          {num(c.p50, 1)}
          <span className="unit">Mt CO2</span>
        </div>

        {/*
          Sits between the number and everything else, in normal flow, with no
          disclosure control. A reader who takes only the headline still takes
          this with it.
        */}
        <div className="result-qualifier">
          <p>
            Scenario-based screening estimate - not a site-specific or certified
            storage capacity.
          </p>
          <p className="qualifier-inputs">
            {userSupplied.length > 0
              ? "Area and net reservoir thickness are user-supplied inputs."
              : "Screening inputs are listed with their provenance below."}
          </p>
        </div>
      </div>

      <dl className="percentiles">
        <div>
          <dt>P10</dt>
          <dd>{num(c.p10, 1)}</dd>
        </div>
        <div>
          <dt>P50</dt>
          <dd>{num(c.p50, 1)}</dd>
        </div>
        <div>
          <dt>P90</dt>
          <dd>{num(c.p90, 1)}</dd>
        </div>
        <div>
          <dt>Mean</dt>
          <dd>{num(c.mean, 1)}</dd>
        </div>
        <div>
          <dt>Samples</dt>
          <dd>{num(c.n_samples, 0)}</dd>
        </div>
      </dl>

      <p className="hint" style={{ marginTop: 12 }}>
        P10 is the 10th percentile (low case). Values in Mt CO2.
        {c.deterministic
          ? " Every prior is a point value, so P10 = P50 = P90."
          : ""}
      </p>

      <div style={{ marginTop: 12 }}>
        <Notice tone="plain" title="How to read this">
          <p>{result.interpretation.statement}</p>
        </Notice>
      </div>
    </section>
  );
}

/** A well that cannot be screened on a legacy path. Never renders a zero. */
export function BlockedPanel({ result }: { result: LegacyScreenResult }) {
  const reasons = result.missing_reasons ?? {};
  const missing = result.missing_fields ?? [];
  return (
    <section className="panel" aria-labelledby="result-heading">
      <h2 id="result-heading">Result</h2>
      <NotValidatedNotice />
      <div className="result-head">
        <div className="result-label">Screening unavailable</div>
        <p className="result-caveat" style={{ marginTop: 6 }}>
          This well cannot be screened. No capacity value is produced, and none
          is estimated in its place.
        </p>
      </div>

      {result.error ? (
        <Notice tone="stop" title="Request rejected">
          <p>{result.error}</p>
        </Notice>
      ) : null}

      {missing.map((field) => (
        <Notice key={field} tone="stop" title={`Missing: ${field}`}>
          <p>{reasons[field] ?? "Required input is unavailable for this well."}</p>
        </Notice>
      ))}

      {missing.includes("temperature_k") ? (
        <Notice tone="plain" title="Why this is not filled in">
          <p>
            Temperature is intentionally non-assumable in this toolkit. It is
            the one required input the source data can supply, so a scenario is
            never allowed to substitute a generic value for it.
          </p>
        </Notice>
      ) : null}
    </section>
  );
}

// -- approved model ---------------------------------------------------------------

const STATUS_TONE: Record<string, "plain" | "advisory" | "stop"> = {
  VALIDATED: "plain",
  OUTSIDE_VALIDATED_ENVELOPE: "advisory",
  UNAVAILABLE: "stop",
};

function Diagnostics({ items }: { items: Diagnostic[] }) {
  if (!items.length) return null;
  return (
    <ul className="hint" style={{ margin: "6px 0 0", paddingLeft: 18 }}>
      {items.map((d, i) => (
        <li key={`${d.code}-${i}`}>
          <strong>{d.code}</strong>: {d.message}
        </li>
      ))}
    </ul>
  );
}

function mpa(pa: number): string {
  return num(pa / 1e6, 2);
}

function ScenarioCard({ scenario }: { scenario: WaterLevelScenarioResult }) {
  const capacity =
    scenario.validated_percentiles === "REPORTED" ? scenario.capacity_mt : null;
  const envelope = scenario.envelope;
  return (
    <article className="card" aria-labelledby={`scenario-${scenario.name}`}>
      <div className="card-name" id={`scenario-${scenario.name}`}>
        {scenario.name} ({scenario.role})
      </div>
      <div className="card-name">{scenario.label}</div>
      <p>
        <span className="tag">{scenario.validation_status}</span>
      </p>

      <dl>
        <dt>Water level</dt>
        <dd>
          {scenario.z_wl_m === null ? (
            <span className="unavailable">Not available</span>
          ) : (
            `${num(scenario.z_wl_m, 1)} m below ground (${scenario.z_wl_definition})`
          )}
        </dd>
        <dt>P_EOS</dt>
        <dd>
          {scenario.pressure_eos_pa ? (
            `${mpa(scenario.pressure_eos_pa.low)} - ${mpa(scenario.pressure_eos_pa.high)} MPa (absolute)`
          ) : (
            <span className="unavailable">Not available</span>
          )}
        </dd>
        <dt>Temperature</dt>
        <dd>
          {scenario.temperature_k === null ? (
            <span className="unavailable">Not available</span>
          ) : (
            `${num(scenario.temperature_k, 2)} K (${num(kelvinToCelsius(scenario.temperature_k), 1)} degC)`
          )}
        </dd>
      </dl>

      {capacity ? (
        <dl className="percentiles">
          <div>
            <dt>P10</dt>
            <dd>{num(capacity.p10, 1)}</dd>
          </div>
          <div>
            <dt>P50</dt>
            <dd>{num(capacity.p50, 1)}</dd>
          </div>
          <div>
            <dt>P90</dt>
            <dd>{num(capacity.p90, 1)}</dd>
          </div>
          <div>
            <dt>Mean</dt>
            <dd>{num(capacity.mean, 1)}</dd>
          </div>
          <div>
            <dt>Samples</dt>
            <dd>{num(capacity.n_samples, 0)}</dd>
          </div>
        </dl>
      ) : scenario.validated_percentiles === "BLOCKED" ? (
        <p className="note">
          Validated percentiles blocked:{" "}
          {envelope
            ? `${num(envelope.n_outside, 0)} of ${num(envelope.n_realisations, 0)} realisations`
            : "realisations"}{" "}
          lie outside the validated EOS envelope. No realisation was discarded.
        </p>
      ) : (
        <p className="note">No capacity is produced for this scenario.</p>
      )}

      <Diagnostics items={scenario.diagnostics} />
    </article>
  );
}

export function ApprovedResultPanel({ result }: { result: ApprovedScreenResult }) {
  if (result.status === "blocked") {
    return (
      <section className="panel" aria-labelledby="result-heading">
        <h2 id="result-heading">Result</h2>
        <div className="result-head">
          <div className="result-label">Screening unavailable</div>
          <p className="result-caveat" style={{ marginTop: 6 }}>
            The request was not evaluated. No capacity value is produced, and
            none is estimated in its place.
          </p>
        </div>
        {result.error ? (
          <Notice tone="stop" title="Request rejected">
            <p>{result.error}</p>
          </Notice>
        ) : null}
      </section>
    );
  }

  const interval = result.storage_interval;
  const temperature = result.temperature_selection;
  const effect = result.systematic_effect?.individual_effects?.[0];
  return (
    <section className="panel" aria-labelledby="result-heading">
      <h2 id="result-heading">Result</h2>
      <div className="result-head">
        <div className="result-label">
          Approved model - both named water-level scenarios
        </div>
        <div className="result-qualifier">
          <p>
            Scenario-based screening estimate - not a site-specific or certified
            storage capacity.
          </p>
          <p className="qualifier-inputs">
            Area and the storage-assessment interval are user-supplied inputs.
            The water-level scenarios are named project scenarios, not measured
            formation heads.
          </p>
        </div>
      </div>

      <div className="cards">
        {result.water_level_scenarios.map((scenario) => (
          <ScenarioCard key={scenario.name} scenario={scenario} />
        ))}
      </div>

      {result.water_level_scenarios.map((scenario) =>
        scenario.validation_status === "VALIDATED" ? null : (
          <div key={`notice-${scenario.name}`} style={{ marginTop: 12 }}>
            <Notice
              tone={STATUS_TONE[scenario.validation_status]}
              title={`${scenario.name}: ${scenario.validation_status}`}
            >
              <p>
                {scenario.validation_status === "UNAVAILABLE"
                  ? "No approved capacity is produced for this scenario."
                  : "Validated percentiles are blocked for this scenario."}
              </p>
            </Notice>
          </div>
        ),
      )}

      {effect ? (
        <p className="hint" style={{ marginTop: 12 }}>
          Scenario contrast ({effect.contrast}):{" "}
          {effect.status === "AVAILABLE" && effect.p50_difference_mt !== null
            ? `P50 difference ${num(effect.p50_difference_mt, 2)} Mt CO2. `
            : "not reported - both scenarios must be VALIDATED. "}
          A scenario contrast, not a correction factor.
        </p>
      ) : null}

      <h3 style={{ fontSize: 13, marginTop: 16 }}>Storage interval</h3>
      {interval ? (
        <dl className="kv">
          <dt>z_top / z_base</dt>
          <dd>
            {num(interval.z_top_m, 1)} m / {num(interval.z_base_m, 1)} m
          </dd>
          <dt>h_g (derived by the API)</dt>
          <dd>
            {interval.h_g_m === null ? (
              <span className="unavailable">Not available</span>
            ) : (
              `${num(interval.h_g_m, 1)} m`
            )}
          </dd>
          <dt>z_state (derived by the API)</dt>
          <dd>
            {interval.z_state_m === null ? (
              <span className="unavailable">Not available</span>
            ) : (
              `${num(interval.z_state_m, 1)} m`
            )}
          </dd>
          <dt>Depth reference</dt>
          <dd>
            {result.depth_reference
              ? `${result.depth_reference.depth_datum} - ${result.depth_reference.status}`
              : "-"}
          </dd>
        </dl>
      ) : null}
      {result.depth_reference ? <Diagnostics items={result.depth_reference.diagnostics} /> : null}

      <h3 style={{ fontSize: 13, marginTop: 16 }}>Temperature selection</h3>
      {temperature ? (
        <>
          <dl className="kv">
            <dt>Status</dt>
            <dd>{temperature.status}</dd>
            <dt>Selected observation</dt>
            <dd>
              {temperature.selected_observation ? (
                `${num(temperature.selected_observation.temperature_k, 2)} K at ${num(
                  temperature.selected_observation.depth_m,
                  1,
                )} m (${temperature.selected_observation.method})`
              ) : (
                <span className="unavailable">Not available</span>
              )}
            </dd>
          </dl>
          <Diagnostics items={temperature.diagnostics} />
        </>
      ) : null}

      <div style={{ marginTop: 12 }}>
        <Notice tone="plain" title="How to read this">
          <p>{result.interpretation.statement}</p>
          {result.interpretation.percentile_interpretation ? (
            <p className="detail">{result.interpretation.percentile_interpretation}</p>
          ) : null}
        </Notice>
      </div>
    </section>
  );
}
