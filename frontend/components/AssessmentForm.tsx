"use client";

import type { ReactNode } from "react";
import {
  AREA_UNITS,
  CONVENTIONS,
  DATUMS,
  ELEVATION_REFERENCES,
  ELIGIBLE_METHODS,
  LENGTH_UNITS,
  METHODS,
  TEMPERATURE_UNITS,
  emptyObservation,
  label,
  type AssessmentDraft,
  type ObservationDraft,
  type Problem,
} from "@/lib/assessment";

type Errors = Map<string, Problem[]>;

const NOT_ELIGIBLE = METHODS.filter((m) => !(ELIGIBLE_METHODS as readonly string[]).includes(m));

function FieldErrors({ id, problems }: { id: string; problems?: Problem[] }) {
  if (!problems?.length) return null;
  return (
    <div id={id}>
      {problems.map((p, i) => (
        <p key={i} className={p.severity === "error" ? "field-error" : "field-notice"}>
          {p.row ? `Row ${p.row}: ` : ""}
          {p.message}
        </p>
      ))}
    </div>
  );
}

/**
 * The choices for a select. ``value`` is the current value: an imported value
 * that is empty or not supported is shown as it is, never as the first option,
 * so nothing appears chosen that the file did not say.
 */
function Options({ options, value, placeholder }: {
  options: readonly string[];
  value?: string;
  placeholder?: string;
}) {
  return (
    <>
      {placeholder !== undefined || value === "" ? (
        <option value="">{placeholder ?? "Choose..."}</option>
      ) : null}
      {value && !options.includes(value) ? (
        <option value={value}>{value} (not supported)</option>
      ) : null}
      {options.map((o) => (
        <option key={o} value={o}>
          {label(o)}
        </option>
      ))}
    </>
  );
}

function Field({
  id,
  text,
  hint,
  errors,
  children,
}: {
  id: string;
  text: string;
  hint?: ReactNode;
  errors?: Problem[];
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{text}</label>
      {children}
      {hint ? <p className="hint">{hint}</p> : null}
      <FieldErrors id={`${id}-errors`} problems={errors} />
    </div>
  );
}

/** A number with its unit selector beside it, so the unit is never out of sight. */
function NumberWithUnit({
  id,
  value,
  onValue,
  unit,
  units,
  onUnit,
  unitLabel,
  invalid,
}: {
  id: string;
  value: string;
  onValue: (v: string) => void;
  unit: string;
  units: readonly string[];
  onUnit: (u: string) => void;
  unitLabel: string;
  invalid?: boolean;
}) {
  return (
    <div className="with-unit">
      <input id={id} type="text" inputMode="decimal" value={value} autoComplete="off"
             aria-invalid={invalid || undefined} aria-describedby={`${id}-errors`}
             onChange={(e) => onValue(e.target.value)} />
      <select aria-label={unitLabel} value={unit} onChange={(e) => onUnit(e.target.value)}>
        <Options options={units} value={unit} />
      </select>
    </div>
  );
}

/**
 * One assessment. Values are kept exactly as typed. A new assessment starts
 * with unit selectors set; an imported one shows exactly what the file gave,
 * and an empty unit must be chosen.
 */
export function AssessmentForm({
  draft,
  onChange,
  errors,
  index,
}: {
  draft: AssessmentDraft;
  onChange: (next: AssessmentDraft) => void;
  errors: Errors;
  index: number;
}) {
  const p = `a${index}`;
  const set = (patch: Partial<AssessmentDraft>) => onChange({ ...draft, ...patch });
  const setObs = (i: number, patch: Partial<ObservationDraft>) =>
    set({ observations: draft.observations.map((o, j) => (j === i ? { ...o, ...patch } : o)) });
  const err = (key: string) => errors.get(key);
  const under = (prefix: string) =>
    [...errors.entries()]
      .filter(([k]) => k === prefix || k.startsWith(`${prefix}.`))
      .flatMap(([, v]) => v);
  const invalid = (key: string) => Boolean(under(key).some((x) => x.severity === "error"));

  return (
    <div className="assessment-form">
      <fieldset>
        <legend>Site</legend>
        <div className="row-2">
          <Field id={`${p}-id`} text="Assessment ID" errors={err("id")} hint="Your label, e.g. a well name.">
            <input id={`${p}-id`} type="text" value={draft.id} autoComplete="off"
                   aria-invalid={invalid("id") || undefined}
                   onChange={(e) => set({ id: e.target.value })} />
          </Field>
          <Field id={`${p}-name`} text="Display name (optional)" errors={err("name")}>
            <input id={`${p}-name`} type="text" value={draft.name} autoComplete="off"
                   onChange={(e) => set({ name: e.target.value })} />
          </Field>
        </div>
        <Field id={`${p}-area`} text="Storage area" errors={under("storage_area")}
               hint="Closure area of the storage unit.">
          <NumberWithUnit id={`${p}-area`} value={draft.area} onValue={(v) => set({ area: v })}
                          unit={draft.area_unit} units={AREA_UNITS} unitLabel="Area unit"
                          onUnit={(u) => set({ area_unit: u })} invalid={invalid("storage_area")} />
        </Field>
      </fieldset>

      <fieldset>
        <legend>Storage interval</legend>
        <div className="row-3">
          <Field id={`${p}-top`} text="Top (z_top)" errors={err("storage_interval.top")}>
            <input id={`${p}-top`} type="text" inputMode="decimal" value={draft.top} autoComplete="off"
                   aria-invalid={invalid("storage_interval.top") || undefined}
                   onChange={(e) => set({ top: e.target.value })} />
          </Field>
          <Field id={`${p}-base`} text="Base (z_base)" errors={err("storage_interval.base")}>
            <input id={`${p}-base`} type="text" inputMode="decimal" value={draft.base} autoComplete="off"
                   aria-invalid={invalid("storage_interval.base") || undefined}
                   onChange={(e) => set({ base: e.target.value })} />
          </Field>
          <Field id={`${p}-depth-unit`} text="Depth unit" hint="Unit of top and base.">
            <select id={`${p}-depth-unit`} value={draft.depth_unit}
                    aria-invalid={invalid("storage_interval.unit") || undefined}
                    onChange={(e) => set({ depth_unit: e.target.value })}>
              <Options options={LENGTH_UNITS} value={draft.depth_unit} />
            </select>
          </Field>
        </div>
        <FieldErrors id={`${p}-interval-errors`}
                     problems={[...(err("storage_interval") ?? []), ...(err("storage_interval.unit") ?? [])]} />
        <div className="row-2">
          <Field id={`${p}-datum`} text="Depths measured from" errors={err("depth_reference.datum")}
                 hint="Only ground level can be used.">
            <select id={`${p}-datum`} value={draft.datum} aria-invalid={invalid("depth_reference.datum") || undefined}
                    onChange={(e) => set({ datum: e.target.value })}>
              <Options options={DATUMS} value={draft.datum} placeholder="Choose..." />
            </select>
          </Field>
          <Field id={`${p}-convention`} text="Depth convention" errors={err("depth_reference.convention")}
                 hint="Only TVD can be used; MD is never converted.">
            <select id={`${p}-convention`} value={draft.convention}
                    aria-invalid={invalid("depth_reference.convention") || undefined}
                    onChange={(e) => set({ convention: e.target.value })}>
              <Options options={CONVENTIONS} value={draft.convention} placeholder="Choose..." />
            </select>
          </Field>
        </div>
        <FieldErrors id={`${p}-reference-errors`} problems={err("depth_reference")} />
      </fieldset>

      <fieldset>
        <legend>Well</legend>
        <div className="row-2">
          <Field id={`${p}-td`} text="Total depth" errors={under("total_depth")}
                 hint="Needed to accept a temperature. Has its own unit.">
            <NumberWithUnit id={`${p}-td`} value={draft.total_depth} onValue={(v) => set({ total_depth: v })}
                            unit={draft.total_depth_unit} units={LENGTH_UNITS} unitLabel="Total depth unit"
                            onUnit={(u) => set({ total_depth_unit: u })} invalid={invalid("total_depth")} />
          </Field>
          <Field id={`${p}-elev`} text="Ground elevation" errors={under("surface_elevation")}
                 hint="Optional: only the sea-level scenario needs it.">
            <NumberWithUnit id={`${p}-elev`} value={draft.elevation} onValue={(v) => set({ elevation: v })}
                            unit={draft.elevation_unit} units={LENGTH_UNITS} unitLabel="Elevation unit"
                            onUnit={(u) => set({ elevation_unit: u })} invalid={invalid("surface_elevation")} />
          </Field>
        </div>
        <Field id={`${p}-elev-ref`} text="Elevation measured above">
          <select id={`${p}-elev-ref`} value={draft.elevation_reference}
                  onChange={(e) => set({ elevation_reference: e.target.value })}>
            <Options options={ELEVATION_REFERENCES} value={draft.elevation_reference} />
          </select>
        </Field>
      </fieldset>

      <fieldset>
        <legend>Temperature observations</legend>
        <p className="hint">
          Only Horner-corrected, Fertl-Wichmann and Squarci-Taffi values inside the interval can be
          selected. Other readings are kept and shown.
        </p>
        <FieldErrors id={`${p}-obs-errors`} problems={err("temperature_observations")} />
        {draft.observations.map((o, i) => {
          const q = `temperature_observations[${i}]`;
          const oid = `${p}-obs${i}`;
          return (
            <div className="observation" key={i} role="group" aria-label={`Observation ${i + 1}`}>
              <div className="observation-head">
                <strong>Observation {i + 1}</strong>
                <button type="button" className="secondary small"
                        onClick={() => set({ observations: draft.observations.filter((_, j) => j !== i) })}
                        aria-label={`Remove observation ${i + 1}`}>
                  Remove
                </button>
              </div>
              <div className="row-2">
                <Field id={`${oid}-value`} text="Temperature" errors={under(`${q}.value`).concat(err(`${q}.unit`) ?? [])}>
                  <NumberWithUnit id={`${oid}-value`} value={o.value} onValue={(v) => setObs(i, { value: v })}
                                  unit={o.unit} units={TEMPERATURE_UNITS} unitLabel="Temperature unit"
                                  onUnit={(u) => setObs(i, { unit: u })} invalid={invalid(`${q}.value`)} />
                </Field>
                <Field id={`${oid}-depth`} text="Measured at depth" errors={under(`${q}.depth`)}>
                  <NumberWithUnit id={`${oid}-depth`} value={o.depth} onValue={(v) => setObs(i, { depth: v })}
                                  unit={o.depth_unit} units={LENGTH_UNITS} unitLabel="Observation depth unit"
                                  onUnit={(u) => setObs(i, { depth_unit: u })} invalid={invalid(`${q}.depth`)} />
                </Field>
              </div>
              <div className="row-3">
                <Field id={`${oid}-datum`} text="Depth from" errors={err(`${q}.depth_datum`)}>
                  <select id={`${oid}-datum`} value={o.depth_datum}
                          aria-invalid={invalid(`${q}.depth_datum`) || undefined}
                          onChange={(e) => setObs(i, { depth_datum: e.target.value })}>
                    <Options options={DATUMS} value={o.depth_datum} placeholder="Choose..." />
                  </select>
                </Field>
                <Field id={`${oid}-conv`} text="Convention" errors={err(`${q}.depth_convention`)}>
                  <select id={`${oid}-conv`} value={o.depth_convention}
                          aria-invalid={invalid(`${q}.depth_convention`) || undefined}
                          onChange={(e) => setObs(i, { depth_convention: e.target.value })}>
                    <Options options={CONVENTIONS} value={o.depth_convention} placeholder="Choose..." />
                  </select>
                </Field>
                <Field id={`${oid}-method`} text="Method" errors={err(`${q}.method`)}>
                  <select id={`${oid}-method`} value={o.method} aria-invalid={invalid(`${q}.method`) || undefined}
                          onChange={(e) => setObs(i, { method: e.target.value })}>
                    <option value="">Choose...</option>
                    {o.method && !(METHODS as readonly string[]).includes(o.method) ? (
                      <option value={o.method}>{o.method} (not supported)</option>
                    ) : null}
                    <optgroup label="Eligible (corrected)">
                      <Options options={ELIGIBLE_METHODS} />
                    </optgroup>
                    <optgroup label="Not eligible">
                      <Options options={NOT_ELIGIBLE} />
                    </optgroup>
                  </select>
                </Field>
              </div>
              <Field id={`${oid}-source`} text="Source (optional)" errors={err(`${q}.source`)}>
                <input id={`${oid}-source`} type="text" value={o.source} autoComplete="off"
                       onChange={(e) => setObs(i, { source: e.target.value })} />
              </Field>
              <FieldErrors id={`${oid}-errors`} problems={err(q)} />
            </div>
          );
        })}
        <button type="button" className="secondary"
                onClick={() => set({ observations: [...draft.observations, emptyObservation()] })}>
          Add temperature observation
        </button>
      </fieldset>

      <details className="disclosure">
        <summary>Source notes (optional)</summary>
        <div className="row-2">
          <Field id={`${p}-area-src`} text="Source of the area">
            <input id={`${p}-area-src`} type="text" value={draft.area_source}
                   onChange={(e) => set({ area_source: e.target.value })} />
          </Field>
          <Field id={`${p}-int-src`} text="Source of the interval">
            <input id={`${p}-int-src`} type="text" value={draft.interval_source}
                   onChange={(e) => set({ interval_source: e.target.value })} />
          </Field>
          <Field id={`${p}-ref-src`} text="Source of the depth reference">
            <input id={`${p}-ref-src`} type="text" value={draft.reference_source}
                   onChange={(e) => set({ reference_source: e.target.value })} />
          </Field>
          <Field id={`${p}-td-src`} text="Source of the total depth">
            <input id={`${p}-td-src`} type="text" value={draft.total_depth_source}
                   onChange={(e) => set({ total_depth_source: e.target.value })} />
          </Field>
        </div>
        <Field id={`${p}-notes`} text="Notes" errors={err("notes")}>
          <textarea id={`${p}-notes`} rows={3} value={draft.notes}
                    onChange={(e) => set({ notes: e.target.value })} />
        </Field>
      </details>

      <p className="model-controlled">
        <strong>Set by the approved model, not editable:</strong> porosity, storage efficiency and
        brine-density ranges, the CO2 density model and the two water-table scenarios. Their values
        are listed with each result.
      </p>
      <FieldErrors id={`${p}-general-errors`} problems={err("")} />
    </div>
  );
}
