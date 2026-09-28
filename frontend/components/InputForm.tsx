"use client";

import { useState } from "react";
import { Notice } from "./Notice";
import { km2ToM2 } from "@/lib/format";
import type { RequiredInputSpec, ScenarioSummary, UserInputValues } from "@/lib/types";

/** Reader-facing label and hint per input. The API spec supplies the policy. */
const FIELD_TEXT: Record<string, { label: string; hint: string; required: string }> = {
  area_m2: {
    label: "Storage area (km²)",
    hint:
      "Structural closure area. Not inferred from licence boundaries, concession " +
      "polygons, well spacing or a radius around the well. Sent to the API in m².",
    required: "Storage area is required.",
  },
  z_top: {
    label: "Storage interval top, z_top (m below ground level)",
    hint:
      "Top of the designated storage-assessment interval, in the same depth " +
      "coordinate and datum as the well's total depth. Not inferred from total " +
      "depth or stratigraphic units.",
    required: "Storage interval top (z_top) is required.",
  },
  z_base: {
    label: "Storage interval base, z_base (m below ground level)",
    hint:
      "Base of the designated storage-assessment interval. The API derives the " +
      "gross thickness and state-point depth from the interval; this form does not.",
    required: "Storage interval base (z_base) is required.",
  },
  thickness_m: {
    label: "Net reservoir thickness (m)",
    hint:
      "Legacy NOT_VALIDATED scenarios only. This is not inferred from gross " +
      "stratigraphic thickness.",
    required: "Net reservoir thickness is required.",
  },
};

type Values = Record<string, string>;
type Errors = Record<string, string>;

/**
 * The inputs the backend refuses to invent, as the selected scenario requires
 * them (the API's required-inputs list decides which fields appear).
 *
 * Every field starts empty. A default here would be a hidden geological
 * assumption wearing the clothes of a result, which is exactly what the
 * backend contract exists to prevent. The form checks only that each value is
 * a usable number; it computes nothing from them.
 *
 * Area is entered in km2 because that is the scale an engineer thinks in, and
 * converted to m2 explicitly before the request.
 */
export function InputForm({
  scenarios,
  scenario,
  required,
  onScenarioChange,
  onSubmit,
  onCompareTemperature,
  busy,
  disabled,
}: {
  scenarios: ScenarioSummary[];
  scenario: string;
  required: RequiredInputSpec[] | null;
  onScenarioChange: (name: string) => void;
  onSubmit: (values: UserInputValues) => void;
  /** Only offered on NOT_VALIDATED legacy scenarios. */
  onCompareTemperature: ((values: UserInputValues) => void) | null;
  busy: boolean;
  disabled: boolean;
}) {
  const [values, setValues] = useState<Values>({});
  const [errors, setErrors] = useState<Errors>({});

  const fields = (required ?? []).map((spec) => spec.field);

  function validate(): UserInputValues | null {
    const next: Errors = {};
    const parsed: Record<string, number> = {};
    for (const field of fields) {
      const raw = (values[field] ?? "").trim();
      const number = Number(raw);
      if (raw === "") next[field] = FIELD_TEXT[field]?.required ?? `${field} is required.`;
      else if (!Number.isFinite(number)) next[field] = "Enter a finite number.";
      else if (field === "z_top" && number < 0) next[field] = "Must be 0 or greater.";
      else if (field !== "z_top" && number <= 0) next[field] = "Must be greater than 0.";
      else parsed[field] = number;
    }
    if (
      parsed.z_top !== undefined &&
      parsed.z_base !== undefined &&
      !(parsed.z_base > parsed.z_top)
    ) {
      next.z_base = "Must be deeper than z_top.";
    }
    setErrors(next);
    if (fields.length === 0 || Object.keys(next).length > 0) return null;

    const out: UserInputValues = { area_m2: km2ToM2(parsed.area_m2) };
    if (fields.includes("z_top")) out.z_top = parsed.z_top;
    if (fields.includes("z_base")) out.z_base = parsed.z_base;
    if (fields.includes("thickness_m")) out.thickness_m = parsed.thickness_m;
    return out;
  }

  const active = scenarios.find((s) => s.name === scenario || s.aliases.includes(scenario));
  const notValidated = active?.validation_status === "NOT_VALIDATED";

  return (
    <section className="panel" aria-labelledby="inputs-heading">
      <h2 id="inputs-heading">Scenario and your inputs</h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const parsed = validate();
          if (parsed) onSubmit(parsed);
        }}
        noValidate
      >
        <div className="field">
          <label htmlFor="scenario">Screening scenario</label>
          <select
            id="scenario"
            value={scenario}
            onChange={(e) => onScenarioChange(e.target.value)}
          >
            {scenarios.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name} (v{s.version})
                {s.validation_status === "NOT_VALIDATED" ? " - NOT_VALIDATED" : ""}
              </option>
            ))}
          </select>
          {active ? (
            <p className="hint">
              {active.description} Literature-constrained values are published
              ranges, not measurements from this well.
            </p>
          ) : null}
          {notValidated ? (
            <Notice tone="advisory" title="NOT_VALIDATED legacy scenario">
              <p>Its results do not come from the approved Model Contract.</p>
            </Notice>
          ) : null}
        </div>

        {required === null ? (
          <p className="unavailable" role="status">
            Loading the inputs this scenario requires...
          </p>
        ) : null}

        {fields.map((field) => {
          const text = FIELD_TEXT[field] ?? { label: field, hint: "", required: "" };
          return (
            <div className="field" key={field}>
              <label htmlFor={`input-${field}`}>{text.label}</label>
              <input
                id={`input-${field}`}
                type="number"
                inputMode="decimal"
                step="any"
                min="0"
                value={values[field] ?? ""}
                aria-invalid={Boolean(errors[field])}
                aria-describedby={`${field}-hint ${field}-error`}
                onChange={(e) => setValues((prev) => ({ ...prev, [field]: e.target.value }))}
              />
              <p className="hint" id={`${field}-hint`}>
                {text.hint}
              </p>
              {errors[field] ? (
                <p className="field-error" id={`${field}-error`} role="alert">
                  {errors[field]}
                </p>
              ) : null}
            </div>
          );
        })}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="submit" disabled={busy || disabled || required === null}>
            {busy ? "Running..." : "Run screening"}
          </button>
          {onCompareTemperature ? (
            <button
              type="button"
              className="secondary"
              disabled={busy || disabled || required === null}
              onClick={() => {
                const parsed = validate();
                if (parsed) onCompareTemperature(parsed);
              }}
            >
              Compare temperature methods (NOT_VALIDATED)
            </button>
          ) : null}
        </div>
        {!onCompareTemperature && required !== null ? (
          <p className="hint">
            Under the approved model, temperature is selected by the contract rule
            and shown with the result. The temperature-method comparison is a
            NOT_VALIDATED legacy diagnostic, offered on legacy scenarios only.
          </p>
        ) : null}
      </form>
    </section>
  );
}
