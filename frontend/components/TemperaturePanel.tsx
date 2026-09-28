import { num } from "@/lib/format";
import { Notice } from "./Notice";
import type { TemperatureComparison } from "@/lib/types";

function NotValidatedDiagnostic({ note }: { note?: string }) {
  return (
    <Notice tone="advisory" title="NOT_VALIDATED legacy diagnostic">
      <p>
        {note ??
          "The comparison runs the legacy resolver and temperature selection, not the approved model."}
      </p>
    </Notice>
  );
}

/**
 * Sensitivity of capacity to the choice of temperature method.
 *
 * A NOT_VALIDATED legacy diagnostic: it uses the legacy resolver, not the
 * approved model's temperature rule. The selected method is marked, but no
 * method is presented as correct: the point is to show how much the answer
 * moves on a methodological choice.
 */
export function TemperaturePanel({ comparison }: { comparison: TemperatureComparison }) {
  if (!comparison.variants?.length) {
    return (
      <section className="panel" aria-labelledby="temp-heading">
        <h2 id="temp-heading">Temperature methodology sensitivity</h2>
        <NotValidatedDiagnostic note={comparison.validation_note} />
        <p className="unavailable">
          This well has no alternative temperature records to compare.
        </p>
      </section>
    );
  }

  return (
    <section className="panel" aria-labelledby="temp-heading">
      <h2 id="temp-heading">Temperature methodology sensitivity</h2>
      <NotValidatedDiagnostic note={comparison.validation_note} />
      <p className="bucket-desc">
        Each row re-runs the same scenario with only the temperature changed. No
        method is authoritative.
      </p>

      <div className="table-wrap">
        <table>
          <caption className="sr-only">
            Capacity P50 by temperature acquisition method
          </caption>
          <thead>
            <tr>
              <th scope="col">Method</th>
              <th scope="col">Temperature</th>
              <th scope="col">Depth</th>
              <th scope="col">P50 (Mt)</th>
              <th scope="col">Selected</th>
            </tr>
          </thead>
          <tbody>
            {comparison.variants.map((v, i) => {
              const selected = v.method === comparison.selected_method;
              return (
                <tr key={`${v.method}-${v.depth_m}-${i}`} data-selected={selected}>
                  <td>{v.method}</td>
                  <td>{num(v.temperature_degc, 1)} degC</td>
                  <td>{num(v.depth_m, 0)} m</td>
                  <td>{v.p50_mt === null ? "n/a" : num(v.p50_mt, 2)}</td>
                  <td>{selected ? "used" : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {comparison.p50_spread_percent !== null ? (
        <div style={{ marginTop: 12 }}>
          <Notice tone="advisory" title="Methodology sensitivity">
            <p>
              Capacity P50 varies by {num(comparison.p50_spread_percent, 1)}%
              across the available temperature methods for this well
              {comparison.p50_spread_mt !== null
                ? ` (${num(comparison.p50_spread_mt, 2)} Mt)`
                : ""}
              .
            </p>
          </Notice>
        </div>
      ) : null}
    </section>
  );
}
