import { num, kelvinToCelsius } from "@/lib/format";
import { Notice } from "./Notice";
import type { RequiredInputs, WellDetail as WellDetailType } from "@/lib/types";

function Value({ children }: { children: React.ReactNode }) {
  if (children === null || children === undefined || children === "")
    return <span className="unavailable">Not available</span>;
  return <>{children}</>;
}

/** Source information for the selected well. Missing fields say so. */
export function WellDetail({
  detail,
  inputs,
}: {
  detail: WellDetailType;
  inputs: RequiredInputs | null;
}) {
  const fields = detail.fields ?? {};
  const depth = fields.depth_m;
  const temperature = fields.temperature_k;
  const gross = fields.gross_thickness_m;

  const tempK = typeof temperature?.value === "number" ? temperature.value : null;

  return (
    <section className="panel" aria-labelledby="well-detail-heading">
      <h2 id="well-detail-heading">Source data</h2>
      <dl className="kv">
        <dt>Well ID</dt>
        <dd>{detail.canonical_id}</dd>

        {detail.dataset?.synthetic ? (
          <>
            <dt>Dataset</dt>
            <dd>
              <span className="tag tag-synthetic">SYNTHETIC</span> fictional demo well
            </dd>
          </>
        ) : null}

        <dt>Also known as</dt>
        <dd>
          <Value>{detail.original_names?.join(", ")}</Value>
        </dd>

        <dt>Total depth</dt>
        <dd>
          <Value>{typeof depth?.value === "number" ? `${num(depth.value, 1)} m` : null}</Value>
        </dd>

        <dt>Depth datum</dt>
        <dd>
          <Value>{detail.depth_datum}</Value>
        </dd>

        <dt>Approved-model depth reference</dt>
        <dd>
          <Value>
            {detail.approved_model_depth_reference
              ? detail.approved_model_depth_reference.status +
                (detail.approved_model_depth_reference.diagnostic
                  ? ` (${detail.approved_model_depth_reference.diagnostic})`
                  : "")
              : null}
          </Value>
        </dd>

        <dt>Temperature</dt>
        <dd>
          <Value>
            {tempK === null ? null : `${num(kelvinToCelsius(tempK), 1)} degC (${num(tempK, 2)} K)`}
          </Value>
        </dd>

        <dt>Temperature method</dt>
        <dd>
          <Value>{temperature?.method}</Value>
        </dd>

        <dt>Gross stratigraphic thickness</dt>
        <dd>
          <Value>{typeof gross?.value === "number" ? `${num(gross.value, 1)} m` : null}</Value>
        </dd>

        <dt>Screenable with your inputs</dt>
        <dd>{inputs ? (inputs.can_be_screened_with_user_inputs ? "Yes" : "No") : "-"}</dd>
      </dl>

      {gross?.value !== undefined && gross?.value !== null ? (
        <p className="hint">
          Gross stratigraphic thickness is shown for context only. It is not used
          as net reservoir thickness or as the storage-assessment interval.
        </p>
      ) : null}

      {detail.conflicts?.length ? (
        <div style={{ marginTop: 12 }}>
          <h3 style={{ fontSize: 12, marginBottom: 6 }}>Source conflicts</h3>
          {detail.conflicts.map((conflict) => (
            <Notice key={conflict} tone="plain">
              <p>{conflict}</p>
            </Notice>
          ))}
        </div>
      ) : null}

      {inputs && !inputs.can_be_screened_with_user_inputs ? (
        <div style={{ marginTop: 12 }}>
          {inputs.blocked_by_missing_source_data.map((b) => (
            <Notice key={b.field} tone="stop" title={`Blocked: ${b.field}`}>
              <p>{b.reason}</p>
            </Notice>
          ))}
        </div>
      ) : null}
    </section>
  );
}
