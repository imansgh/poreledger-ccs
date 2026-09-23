"use client";

import { useState } from "react";
import { km2ToM2 } from "@/lib/format";
import type { ScenarioSummary, UserInputValues } from "@/lib/types";

/**
 * The two inputs the backend refuses to invent.
 *
 * Both fields start empty. A default here would be a hidden geological
 * assumption wearing the clothes of a result, which is exactly what the
 * backend contract exists to prevent.
 *
 * Area is entered in km2 because that is the scale an engineer thinks in, and
 * converted to m2 explicitly before the request.
 */
export function InputForm({
  scenarios,
  scenario,
  onScenarioChange,
  onSubmit,
  onCompareTemperature,
  busy,
  disabled,
}: {
  scenarios: ScenarioSummary[];
  scenario: string;
  onScenarioChange: (name: string) => void;
  onSubmit: (values: UserInputValues) => void;
  onCompareTemperature: (values: UserInputValues) => void;
  busy: boolean;
  disabled: boolean;
}) {
  const [areaKm2, setAreaKm2] = useState("");
  const [thickness, setThickness] = useState("");
  const [errors, setErrors] = useState<{ area?: string; thickness?: string }>({});

  function validate(): UserInputValues | null {
    const next: { area?: string; thickness?: string } = {};
    const area = Number(areaKm2);
    const net = Number(thickness);

    if (areaKm2.trim() === "") next.area = "Storage area is required.";
    else if (!Number.isFinite(area)) next.area = "Enter a finite number.";
    else if (area <= 0) next.area = "Must be greater than 0.";

    if (thickness.trim() === "") next.thickness = "Net reservoir thickness is required.";
    else if (!Number.isFinite(net)) next.thickness = "Enter a finite number.";
    else if (net <= 0) next.thickness = "Must be greater than 0.";

    setErrors(next);
    if (Object.keys(next).length > 0) return null;
    return { area_m2: km2ToM2(area), thickness_m: net };
  }

  const active = scenarios.find((s) => s.name === scenario || s.aliases.includes(scenario));

  return (
    <section className="panel" aria-labelledby="inputs-heading">
      <h2 id="inputs-heading">Scenario and your inputs</h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const values = validate();
          if (values) onSubmit(values);
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
              </option>
            ))}
          </select>
          {active ? (
            <p className="hint">
              {active.description} Literature-constrained values are published
              ranges, not measurements from this well.
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="area">Storage area (km&sup2;)</label>
          <input
            id="area"
            type="number"
            inputMode="decimal"
            step="any"
            min="0"
            value={areaKm2}
            aria-invalid={Boolean(errors.area)}
            aria-describedby="area-hint area-error"
            onChange={(e) => setAreaKm2(e.target.value)}
          />
          <p className="hint" id="area-hint">
            Structural closure area. Not inferred from licence boundaries,
            concession polygons, well spacing or a radius around the well. Sent
            to the API in m&sup2;.
          </p>
          {errors.area ? (
            <p className="field-error" id="area-error" role="alert">
              {errors.area}
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="thickness">Net reservoir thickness (m)</label>
          <input
            id="thickness"
            type="number"
            inputMode="decimal"
            step="any"
            min="0"
            value={thickness}
            aria-invalid={Boolean(errors.thickness)}
            aria-describedby="thickness-hint thickness-error"
            onChange={(e) => setThickness(e.target.value)}
          />
          <p className="hint" id="thickness-hint">
            This is not inferred from gross stratigraphic thickness.
          </p>
          {errors.thickness ? (
            <p className="field-error" id="thickness-error" role="alert">
              {errors.thickness}
            </p>
          ) : null}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="submit" disabled={busy || disabled}>
            {busy ? "Running..." : "Run screening"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy || disabled}
            onClick={() => {
              const values = validate();
              if (values) onCompareTemperature(values);
            }}
          >
            Compare temperature methods
          </button>
        </div>
      </form>
    </section>
  );
}
