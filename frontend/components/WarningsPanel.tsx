import { Notice } from "./Notice";
import type { Interpretation } from "@/lib/types";

/**
 * Interpretation warnings and standing limitations.
 *
 * Rendered in flow, never in a tooltip, and never styled as an error: an
 * advisory says the result needs context, not that it is wrong.
 */
export function WarningsPanel({ interpretation }: { interpretation: Interpretation }) {
  const warnings = interpretation.warnings ?? [];
  return (
    <section className="panel" aria-labelledby="warnings-heading">
      <h2 id="warnings-heading">Warnings and limitations</h2>

      {warnings.length === 0 ? (
        <p className="unavailable">No scenario warnings for this run.</p>
      ) : (
        warnings.map((w) => (
          <Notice
            key={w.code}
            tone={w.invalidates_result ? "stop" : "advisory"}
            title={`Advisory: ${w.code}`}
          >
            <p>{w.message}</p>
            {w.detail ? <p className="detail">{w.detail}</p> : null}
            {w.affects?.length ? (
              <p className="detail">Affects: {w.affects.join(", ")}</p>
            ) : null}
            <p className="detail">
              {w.invalidates_result
                ? "This warning invalidates the result."
                : "This does not invalidate the result."}
              {w.correction_applied
                ? " A correction has been applied."
                : " No correction factor has been applied."}
            </p>
          </Notice>
        ))
      )}

      <Notice tone="plain" title="Standing limitations">
        <p>{interpretation.area_policy}</p>
        {interpretation.storage_interval_policy ? (
          <p className="detail">{interpretation.storage_interval_policy}</p>
        ) : null}
        {interpretation.net_thickness_policy ? (
          <p className="detail">{interpretation.net_thickness_policy}</p>
        ) : null}
        {interpretation.joint_scenario_methodology ? (
          <p className="detail">{interpretation.joint_scenario_methodology}</p>
        ) : null}
        <p className="detail">Basis: {interpretation.basis}</p>
      </Notice>
    </section>
  );
}
