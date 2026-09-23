import { num } from "@/lib/format";
import { Notice } from "./Notice";
import type { ScreenResult } from "@/lib/types";

/**
 * The headline number, framed by what it is not.
 *
 * The term is always "Scenario-based storage capacity". The interpretation
 * block returned by the API is authoritative for the caveat wording.
 */
export function ResultPanel({ result }: { result: ScreenResult }) {
  if (result.status === "blocked" || !result.scenario_based_capacity_mt) {
    return <BlockedPanel result={result} />;
  }

  const c = result.scenario_based_capacity_mt;
  const userSupplied = result.user_supplied_inputs ?? [];
  return (
    <section className="panel" aria-labelledby="result-heading">
      <h2 id="result-heading">Result</h2>
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

/** A well that cannot be screened. Never renders a zero. */
export function BlockedPanel({ result }: { result: ScreenResult }) {
  const reasons = result.missing_reasons ?? {};
  const missing = result.missing_fields ?? [];
  return (
    <section className="panel" aria-labelledby="result-heading">
      <h2 id="result-heading">Result</h2>
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
