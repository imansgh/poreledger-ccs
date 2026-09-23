/** Number and unit formatting. Display units differ from API units. */

const M2_PER_KM2 = 1_000_000;

export function km2ToM2(km2: number): number {
  return km2 * M2_PER_KM2;
}

export function m2ToKm2(m2: number): number {
  return m2 / M2_PER_KM2;
}

/** Significant-figure formatting that keeps small values readable. */
export function num(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "Not available";
  const abs = Math.abs(value);
  if (abs !== 0 && (abs < 0.01 || abs >= 1e6)) return value.toExponential(digits);
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

/**
 * Render an input's value in units a reader expects, without changing what was
 * sent to the API. Ranges stay ranges: a prior is not a point estimate.
 */
export function displayValue(
  value: number | number[],
  unit: string,
): { text: string; unit: string } {
  const convert = (v: number): number => {
    if (unit === "m2") return m2ToKm2(v);
    if (unit === "Pa") return v / 1e6;
    if (unit === "-") return v * 100;
    return v;
  };
  const display = (): string => {
    if (unit === "m2") return "km2";
    if (unit === "Pa") return "MPa";
    if (unit === "-") return "%";
    if (unit === "K") return "K";
    return unit;
  };

  if (Array.isArray(value)) {
    const [low, high] = value;
    if (low === high) return { text: num(convert(low)), unit: display() };
    return { text: `${num(convert(low))} - ${num(convert(high))}`, unit: display() };
  }
  return { text: num(convert(value)), unit: display() };
}

export function kelvinToCelsius(k: number): number {
  return k - 273.15;
}

/** Human wording for an evidence class. Never softened into marketing terms. */
export const EVIDENCE_LABEL: Record<string, string> = {
  site_specific: "Site-specific",
  regional: "Regional",
  generic: "Generic",
  user_input: "User-supplied",
  unsupported: "Unsupported",
  placeholder: "Placeholder",
};

/** Heading for each provenance bucket. These are never merged or renamed. */
export const BUCKET_TITLES: Record<string, string> = {
  source_derived_inputs: "Source-derived",
  modelled_inputs: "Modelled",
  assumed_inputs: "Literature-constrained",
  user_supplied_inputs: "User input",
};

export const BUCKET_DESCRIPTIONS: Record<string, string> = {
  source_derived_inputs: "Extracted from, or derived from, this well's own data.",
  modelled_inputs: "Computed from source data under a declared generic model.",
  assumed_inputs:
    "Supplied by the scenario from published literature. Not a site-specific measurement.",
  user_supplied_inputs: "Supplied by you for this screening run.",
};
