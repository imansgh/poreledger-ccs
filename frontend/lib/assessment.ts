/**
 * User-supplied assessments: schema ccs-assessment/1.
 *
 * The browser only collects values and maps them to the documented JSON
 * schema. Every validation that matters, every unit conversion and every
 * calculation happens in the backend's approved engine; nothing scientific is
 * computed here. Form values are kept as the text the user typed, so a
 * correctable error never discards input.
 */

import { API_BASE_URL, ApiClientError } from "./api";
import type { Interpretation } from "./types";

export const SCHEMA_VERSION = "ccs-assessment/1";

export const AREA_UNITS = ["km2", "m2", "ha", "acre"] as const;
export const LENGTH_UNITS = ["m", "ft"] as const;
export const TEMPERATURE_UNITS = ["degC", "K", "degF"] as const;
export const DATUMS = ["ground_level", "rotary_table", "kelly_bushing", "msl", "unknown"] as const;
export const CONVENTIONS = ["TVD", "MD", "unknown"] as const;
export const ELEVATION_REFERENCES = ["msl", "unknown"] as const;
export const ELIGIBLE_METHODS = [
  "horner_corrected",
  "extrapolated_fertl_wichmann",
  "extrapolated_squarci_taffi",
] as const;
export const METHODS = [
  ...ELIGIBLE_METHODS,
  "non_stabilized",
  "raw",
  "surface_air_mean",
  "unknown",
] as const;

/** Plain-language labels; the technical value is always shown beside them. */
export const LABELS: Record<string, string> = {
  km2: "km²",
  m2: "m²",
  ha: "ha",
  acre: "acres",
  m: "m",
  ft: "ft",
  degC: "°C",
  K: "K",
  degF: "°F",
  ground_level: "Ground level",
  rotary_table: "Rotary table",
  kelly_bushing: "Kelly bushing",
  msl: "Mean sea level",
  unknown: "Unknown",
  TVD: "TVD (true vertical)",
  MD: "MD (measured along hole)",
  horner_corrected: "Horner-corrected",
  extrapolated_fertl_wichmann: "Fertl-Wichmann",
  extrapolated_squarci_taffi: "Squarci-Taffi",
  non_stabilized: "Non-stabilized reading",
  raw: "Raw reading",
  surface_air_mean: "Surface air mean",
};

/** Readable label for a code; the code itself is kept in exports and details. */
export function label(value: string): string {
  return LABELS[value] ?? value;
}

/** Readable status labels for the validation statuses. */
export const STATUS_LABELS: Record<string, string> = {
  VALIDATED: "Estimate available",
  OUTSIDE_VALIDATED_ENVELOPE: "Outside validated range",
  UNAVAILABLE: "Not available",
  NOT_VALIDATED: "Not validated (legacy)",
};

export const SCENARIO_LABELS: Record<string, string> = {
  GROUND_REFERENCE: "Water table at ground level (reference)",
  SEA_LEVEL_SENSITIVITY: "Water table at sea level (sensitivity)",
};

// -- form state: everything is the text the user typed ------------------------

type Obj = Record<string, unknown>;

export interface ObservationFields {
  value: string;
  unit: string;
  depth: string;
  depth_unit: string;
  depth_datum: string;
  depth_convention: string;
  method: string;
  source: string;
}

/**
 * Where an imported value came from. ``raw`` is exactly what the file held
 * (any JSON value, including a wrong type, a missing unit or an unknown
 * field); ``form`` is the text the form showed for it at import. A field the
 * user has not changed is sent back as ``raw``, so the backend judges the
 * file's own input and an import is never silently repaired.
 */
export interface ImportOrigin<F> {
  raw: unknown;
  form: F;
}

export interface ObservationDraft extends ObservationFields {
  origin?: ImportOrigin<ObservationFields>;
}

export interface DraftFields {
  id: string;
  name: string;
  area: string;
  area_unit: string;
  area_source: string;
  top: string;
  base: string;
  depth_unit: string;
  interval_source: string;
  datum: string;
  convention: string;
  reference_source: string;
  total_depth: string;
  /** Independent of the interval's unit: a file may give total depth in another unit. */
  total_depth_unit: string;
  total_depth_source: string;
  elevation: string;
  elevation_unit: string;
  elevation_reference: string;
  elevation_source: string;
  notes: string;
}

export interface AssessmentDraft extends DraftFields {
  synthetic: boolean;
  example: { key: string; demonstrates?: string } | null;
  observations: ObservationDraft[];
  /** JSON-only context carried through unchanged. */
  stratigraphy: unknown[] | null;
  origin?: ImportOrigin<DraftFields> & { observations: ObservationFields[] };
}

/** Schema location of each form field. */
const DRAFT_PATHS: Record<keyof DraftFields, readonly string[]> = {
  id: ["id"],
  name: ["name"],
  area: ["storage_area", "value"],
  area_unit: ["storage_area", "unit"],
  area_source: ["storage_area", "source"],
  top: ["storage_interval", "top"],
  base: ["storage_interval", "base"],
  depth_unit: ["storage_interval", "unit"],
  interval_source: ["storage_interval", "source"],
  datum: ["depth_reference", "datum"],
  convention: ["depth_reference", "convention"],
  reference_source: ["depth_reference", "source"],
  total_depth: ["total_depth", "value"],
  total_depth_unit: ["total_depth", "unit"],
  total_depth_source: ["total_depth", "source"],
  elevation: ["surface_elevation", "value"],
  elevation_unit: ["surface_elevation", "unit"],
  elevation_reference: ["surface_elevation", "reference"],
  elevation_source: ["surface_elevation", "source"],
  notes: ["notes"],
};

const OBSERVATION_PATHS: Record<keyof ObservationFields, readonly string[]> = {
  value: ["value"],
  unit: ["unit"],
  depth: ["depth"],
  depth_unit: ["depth_unit"],
  depth_datum: ["depth_datum"],
  depth_convention: ["depth_convention"],
  method: ["method"],
  source: ["source"],
};

/** New-entry defaults. Imported values never fall back to these. */
export function emptyObservation(): ObservationDraft {
  return {
    value: "",
    unit: "degC",
    depth: "",
    depth_unit: "m",
    depth_datum: "",
    depth_convention: "",
    method: "",
    source: "",
  };
}

/** A new, manually entered assessment. Imported values never fall back to these. */
export function emptyDraft(id = "MY-SITE-1"): AssessmentDraft {
  return {
    id,
    name: "",
    synthetic: false,
    example: null,
    area: "",
    area_unit: "km2",
    area_source: "",
    top: "",
    base: "",
    depth_unit: "m",
    interval_source: "",
    datum: "",
    convention: "",
    reference_source: "",
    total_depth: "",
    total_depth_unit: "m",
    total_depth_source: "",
    elevation: "",
    elevation_unit: "m",
    elevation_reference: "msl",
    elevation_source: "",
    observations: [emptyObservation()],
    notes: "",
    stratigraphy: null,
  };
}

/** A typed number stays as typed when it is not a number; the backend names it. */
function numberOrText(text: string): number | string | null {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : trimmed;
}

function withSource<T extends Record<string, unknown>>(obj: T, source: string): T {
  return source.trim() ? { ...obj, source: source.trim() } : obj;
}

function blankObservation(o: ObservationFields): boolean {
  return [o.value, o.depth, o.depth_datum, o.depth_convention, o.method, o.source].every(
    (v) => v.trim() === "",
  );
}

const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const clone = <T,>(v: T): T => (v === undefined ? v : (JSON.parse(JSON.stringify(v)) as T));

function pick<F>(source: F, keys: readonly (keyof F)[]): F {
  return Object.fromEntries(keys.map((k) => [k, source[k]])) as F;
}

const DRAFT_KEYS = Object.keys(DRAFT_PATHS) as (keyof DraftFields)[];
const OBSERVATION_KEYS = Object.keys(OBSERVATION_PATHS) as (keyof ObservationFields)[];

/** The schema form of one observation, from the form text alone. */
function formObservation(o: ObservationFields): Obj {
  return withSource(
    {
      value: numberOrText(o.value),
      unit: o.unit || null,
      depth: numberOrText(o.depth),
      depth_unit: o.depth_unit || null,
      depth_datum: o.depth_datum || null,
      depth_convention: o.depth_convention || null,
      method: o.method || null,
    },
    o.source,
  );
}

/** The schema form of one assessment, from the form text alone. */
function formAssessment(d: AssessmentDraft): Obj {
  const out: Obj = {
    id: d.id.trim(),
    storage_area: withSource({ value: numberOrText(d.area), unit: d.area_unit || null }, d.area_source),
    storage_interval: withSource(
      { top: numberOrText(d.top), base: numberOrText(d.base), unit: d.depth_unit || null },
      d.interval_source,
    ),
    depth_reference: withSource(
      { datum: d.datum || null, convention: d.convention || null },
      d.reference_source,
    ),
    temperature_observations: d.observations
      .filter((o) => o.origin || !blankObservation(o))
      .map(formObservation),
  };
  if (d.name.trim()) out.name = d.name.trim();
  if (d.synthetic) out.synthetic = true;
  if (d.synthetic && d.example) out.example = d.example;
  if (d.total_depth.trim()) {
    out.total_depth = withSource(
      { value: numberOrText(d.total_depth), unit: d.total_depth_unit || null },
      d.total_depth_source,
    );
  }
  if (d.elevation.trim()) {
    out.surface_elevation = withSource(
      {
        value: numberOrText(d.elevation),
        unit: d.elevation_unit || null,
        reference: d.elevation_reference || null,
      },
      d.elevation_source,
    );
  }
  if (d.notes.trim()) out.notes = d.notes.trim();
  if (d.stratigraphy && d.stratigraphy.length) out.stratigraphy = d.stratigraphy;
  return out;
}

/**
 * Apply only the fields the user changed onto the imported value. Unchanged
 * fields, unknown fields and anything the form cannot represent stay exactly
 * as imported.
 */
function overlay<F>(
  raw: unknown,
  changed: (keyof F)[],
  paths: Record<keyof F, readonly string[]>,
  fresh: Obj,
): Obj {
  const out: Obj = isObj(raw) ? clone(raw) : {};
  for (const key of changed) {
    const path = paths[key];
    if (path.length === 1) {
      const value = fresh[path[0]];
      if (value === undefined) delete out[path[0]];
      else out[path[0]] = clone(value);
      continue;
    }
    const [section, field] = path;
    const freshSection = fresh[section];
    if (!isObj(freshSection)) {
      delete out[section]; // the user cleared an optional section
      continue;
    }
    const target: Obj = isObj(out[section]) ? { ...(out[section] as Obj) } : {};
    if (freshSection[field] === undefined) delete target[field];
    else target[field] = freshSection[field];
    out[section] = target;
  }
  return out;
}

function changedKeys<F>(now: F, then: F, keys: readonly (keyof F)[]): (keyof F)[] {
  return keys.filter((k) => now[k] !== then[k]);
}

function sameObservations(now: ObservationDraft[], then: ObservationFields[]): boolean {
  return (
    now.length === then.length &&
    now.every((o, i) => changedKeys<ObservationFields>(o, then[i], OBSERVATION_KEYS).length === 0)
  );
}

function observationToSchema(o: ObservationDraft): unknown {
  if (!o.origin) return formObservation(o);
  const changed = changedKeys<ObservationFields>(o, o.origin.form, OBSERVATION_KEYS);
  if (!changed.length) return clone(o.origin.raw);
  return overlay(o.origin.raw, changed, OBSERVATION_PATHS, formObservation(o));
}

/**
 * Map one draft to the schema. Empty optional sections are omitted, never
 * invented. For an imported draft, only what the user changed is replaced.
 */
export function draftToAssessment(d: AssessmentDraft): Record<string, unknown> {
  if (!d.origin) return formAssessment(d);
  const changed = changedKeys<DraftFields>(d, d.origin.form, DRAFT_KEYS);
  const observationsChanged = !sameObservations(d.observations, d.origin.observations);
  if (!changed.length && !observationsChanged) return clone(d.origin.raw) as Record<string, unknown>;
  const fresh = formAssessment(d);
  const out = overlay(d.origin.raw, changed, DRAFT_PATHS, fresh);
  if (observationsChanged) {
    out.temperature_observations = d.observations
      .filter((o) => o.origin || !blankObservation(o))
      .map(observationToSchema);
  }
  return out;
}

/**
 * The document for a set of drafts. ``base`` is the imported document: its
 * schema_version (supported or not, present or not) and any other top-level
 * field are kept, so the backend sees what the file declared.
 */
export function draftsToDocument(drafts: AssessmentDraft[], base?: Obj | null): AssessmentDocument {
  const assessments = drafts.map(draftToAssessment);
  if (!base) return { schema_version: SCHEMA_VERSION, assessments };
  const { assessments: _ignored, ...rest } = base;
  return { ...clone(rest), assessments } as unknown as AssessmentDocument;
}

/** Form text for an imported value. Never a default: missing stays empty. */
const text = (v: unknown): string =>
  v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
const obj = (v: unknown): Obj => (isObj(v) ? v : {});

function observationToDraft(raw: unknown): ObservationDraft {
  const o = obj(raw);
  const fields: ObservationFields = {
    value: text(o.value),
    unit: text(o.unit),
    depth: text(o.depth),
    depth_unit: text(o.depth_unit),
    depth_datum: text(o.depth_datum),
    depth_convention: text(o.depth_convention),
    method: text(o.method),
    source: text(o.source),
  };
  return { ...fields, origin: { raw: clone(raw), form: { ...fields } } };
}

/**
 * Map a parsed or example assessment into an editable draft. Nothing is
 * guessed: a missing unit or reference stays empty and must be chosen, and
 * the imported value is kept so unchanged fields go back exactly as given.
 */
export function assessmentToDraft(raw: unknown): AssessmentDraft {
  const a = obj(raw);
  const area = obj(a.storage_area);
  const interval = obj(a.storage_interval);
  const reference = obj(a.depth_reference);
  const total = obj(a.total_depth);
  const elevation = obj(a.surface_elevation);
  const imported = Array.isArray(a.temperature_observations)
    ? (a.temperature_observations as unknown[]).map(observationToDraft)
    : [];
  const observations = imported.length ? imported : [emptyObservation()];
  const example = isObj(a.example) ? (a.example as { key: string; demonstrates?: string }) : null;
  const fields: DraftFields = {
    id: text(a.id),
    name: text(a.name),
    area: text(area.value),
    area_unit: text(area.unit),
    area_source: text(area.source),
    top: text(interval.top),
    base: text(interval.base),
    depth_unit: text(interval.unit),
    interval_source: text(interval.source),
    datum: text(reference.datum),
    convention: text(reference.convention),
    reference_source: text(reference.source),
    total_depth: text(total.value),
    total_depth_unit: text(total.unit),
    total_depth_source: text(total.source),
    elevation: text(elevation.value),
    elevation_unit: text(elevation.unit),
    elevation_reference: text(elevation.reference),
    elevation_source: text(elevation.source),
    notes: text(a.notes),
  };
  return {
    ...fields,
    synthetic: a.synthetic === true,
    example,
    observations,
    stratigraphy: Array.isArray(a.stratigraphy) ? (a.stratigraphy as unknown[]) : null,
    origin: {
      raw: clone(raw),
      form: pick(fields, DRAFT_KEYS),
      observations: observations.map((o) => pick<ObservationFields>(o, OBSERVATION_KEYS)),
    },
  };
}

/** Editable drafts, or ``null`` when the document has no list of assessments to edit. */
export function documentToDrafts(doc: AssessmentDocument): AssessmentDraft[] {
  const list = (doc as unknown as Obj).assessments;
  return Array.isArray(list) ? list.map(assessmentToDraft) : [];
}

// -- explicit corrections for an imported file ------------------------------------

const KNOWN_KEYS = {
  // The blocked-import marker is never "unrecognised": removing it must not unblock a preview.
  document: ["schema_version", "assessments", "blocked_import"],
  assessment: [
    "id", "name", "synthetic", "example", "storage_area", "storage_interval",
    "depth_reference", "surface_elevation", "total_depth", "temperature_observations",
    "stratigraphy", "notes",
  ],
  example: ["key", "demonstrates"],
  storage_area: ["value", "unit", "source"],
  storage_interval: ["top", "base", "unit", "source"],
  depth_reference: ["datum", "convention", "source"],
  surface_elevation: ["value", "unit", "reference", "source"],
  total_depth: ["value", "unit", "source"],
  observation: ["value", "unit", "depth", "depth_unit", "depth_datum", "depth_convention", "method", "source"],
  stratigraphy: ["top", "base", "unit", "description"],
} as const;

function only(value: unknown, keys: readonly string[]): unknown {
  if (!isObj(value)) return value;
  return Object.fromEntries(Object.entries(value).filter(([k]) => keys.includes(k)));
}

function knownAssessment(raw: unknown): unknown {
  const a = only(raw, KNOWN_KEYS.assessment);
  if (!isObj(a)) return a;
  const out: Obj = { ...a };
  for (const section of ["example", "storage_area", "storage_interval", "depth_reference",
                         "surface_elevation", "total_depth"] as const) {
    if (section in out) out[section] = only(out[section], KNOWN_KEYS[section]);
  }
  if (Array.isArray(out.temperature_observations)) {
    out.temperature_observations = out.temperature_observations.map((o) => only(o, KNOWN_KEYS.observation));
  }
  if (Array.isArray(out.stratigraphy)) {
    out.stratigraphy = out.stratigraphy.map((s) => only(s, KNOWN_KEYS.stratigraphy));
  }
  return out;
}

/**
 * Drop fields the schema does not define, at the user's explicit request.
 * Only the imported values change; everything typed in the form is kept.
 */
export function withoutUnknownFields(
  base: Obj | null,
  drafts: AssessmentDraft[],
): { base: Obj | null; drafts: AssessmentDraft[] } {
  return {
    base: base ? (only(base, KNOWN_KEYS.document) as Obj) : base,
    drafts: drafts.map((d) => ({
      ...d,
      stratigraphy: d.stratigraphy?.map((s) => only(s, KNOWN_KEYS.stratigraphy)) ?? null,
      origin: d.origin ? { ...d.origin, raw: knownAssessment(d.origin.raw) } : d.origin,
      observations: d.observations.map((o) =>
        o.origin ? { ...o, origin: { ...o.origin, raw: only(o.origin.raw, KNOWN_KEYS.observation) } } : o,
      ),
    })),
  };
}

/** True when the imported document has no schema_version at all (not an unsupported one). */
/** Key of the backend's marker on a partial import preview (see ParseResponse.preview_document). */
export const BLOCKED_IMPORT_KEY = "blocked_import";

/**
 * True for a parser-produced partial preview. The marker travels with the
 * imported document through every edit, and the backend rejects any
 * document carrying it (IMPORT_BLOCKED).
 */
export function isBlockedPreview(base: Obj | null): boolean {
  return base !== null && BLOCKED_IMPORT_KEY in base;
}

export function missingSchemaVersion(base: Obj | null): boolean {
  return base !== null && (base.schema_version === undefined || base.schema_version === null
    || base.schema_version === "");
}

// -- API types -----------------------------------------------------------------

export interface AssessmentDocument {
  schema_version: string;
  assessments: Record<string, unknown>[];
}

export interface Problem {
  path: string;
  row: number | null;
  code: string;
  message: string;
  severity: "error" | "notice";
}

export interface ScenarioCapacity {
  p10: number;
  p50: number;
  p90: number;
  mean: number;
  n_samples: number;
  validation_status?: string;
  label?: string;
}

export interface ScenarioResult {
  name: string;
  label?: string;
  description?: string;
  validation_status: string;
  z_wl_m: number | null;
  z_state_m: number | null;
  temperature_k: number | null;
  pressure_eos_pa: { low: number; high: number } | null;
  capacity_mt: ScenarioCapacity | null;
  diagnostic_capacity_mt: ScenarioCapacity | null;
  diagnostics: { code: string; message: string }[];
}

export interface BlockingReason {
  code: string;
  title: string;
  explanation: string;
  action: string | null;
  technical_message: string;
  scenarios: string[];
  kind: "input" | "outside_validated_range";
}

export type OutcomeCategory =
  | "estimate"
  | "partial_estimate"
  | "information_needed"
  | "outside_validated_range";

export interface AssessmentOutcome {
  overall_status: string;
  category: OutcomeCategory;
  blocking_reasons: BlockingReason[];
  scenarios: {
    name: string;
    label?: string;
    validation_status: string;
    reportable_estimate: boolean;
    diagnostic_value_only: boolean;
  }[];
  main_reason: { code: string; message: string } | null;
  next_action: string | null;
  meaning: string;
}

export interface AssessmentResult {
  assessment_id: string;
  name: string | null;
  synthetic: boolean;
  data_origin: "synthetic_example" | "user_supplied";
  example: { key: string; demonstrates?: string } | null;
  schema_version: string;
  model: {
    model_path: string;
    parameter_set: { name: string; version: string };
    contract: string;
    capacity_equation: string;
    engine: string;
    evaluated: boolean;
  };
  run: { samples: number; seed: number };
  outcome: AssessmentOutcome;
  inputs: Record<string, unknown>;
  provenance: Record<string, unknown>;
  result: {
    status: string;
    water_level_scenarios: ScenarioResult[];
    temperature_selection?: Record<string, unknown>;
    sampled_inputs?: Record<string, unknown>;
    model_constants?: Record<string, unknown>;
  };
  interpretation: Interpretation;
  limitations: string[];
}

export interface EvaluationResponse {
  schema_version: string;
  run: { samples: number; seed: number };
  notices: Problem[];
  assessments: AssessmentResult[];
  summary_csv: string;
}

export interface ParseResponse {
  format: "json" | "csv";
  /** An evaluatable document; null when the file could not be parsed faithfully. */
  document: AssessmentDocument | null;
  /**
   * When ``import_blocked``: the partial data, for display only. It carries the
   * ``blocked_import`` marker, so the backend rejects it (IMPORT_BLOCKED).
   */
  preview_document: AssessmentDocument | null;
  problems: Problem[];
  valid: boolean;
  /** The parser itself reported an error (e.g. conflicting CSV rows, a skipped row). */
  import_blocked: boolean;
}

// -- API calls -------------------------------------------------------------------

async function call(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiClientError(
      `Cannot reach the calculation service at ${API_BASE_URL}. It may be starting up or temporarily offline; try again in a minute.`,
      0,
      "network",
    );
  }
}

async function failure(response: Response): Promise<never> {
  let body: { error?: string; type?: string } | null = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  // Deployment limits: the server's own message says what to do and when.
  if (response.status === 429) {
    const retry = Number(response.headers.get("Retry-After"));
    const wait = Number.isFinite(retry) && retry > 0 ? ` Try again in ${retry} s.` : "";
    throw new ApiClientError(
      `${body?.error ?? "Too many requests; wait a minute and try again."}.${wait}`, 429, "rate_limited");
  }
  if (response.status === 503 && body?.type === "ServerBusy") {
    throw new ApiClientError(body.error ?? "The server is busy; try again shortly.", 503, "busy");
  }
  if (response.status >= 500) {
    throw new ApiClientError("The screening backend reported an internal error.", response.status, "server");
  }
  const kind = response.status === 413 ? "too_large" : "bad_request";
  throw new ApiClientError(body?.error ?? `Request failed with status ${response.status}.`, response.status, kind);
}

export async function getExamples(): Promise<AssessmentDocument> {
  const response = await call("/assessments/examples");
  if (!response.ok) return failure(response);
  return response.json();
}

export async function parseFile(format: "json" | "csv", content: string): Promise<ParseResponse> {
  const response = await call("/assessments/parse", {
    method: "POST",
    body: JSON.stringify({ format, content }),
  });
  if (!response.ok) return failure(response);
  return response.json();
}

/** Either results, or every input problem (a 422 is an outcome here, not an exception). */
export async function evaluate(
  document: AssessmentDocument,
  samples = 2000,
  seed = 42,
): Promise<{ ok: true; data: EvaluationResponse } | { ok: false; problems: Problem[] }> {
  const response = await call("/assessments/evaluate", {
    method: "POST",
    body: JSON.stringify({ document, samples, seed }),
  });
  if (response.status === 422) {
    const body = (await response.json()) as { type?: string; detail?: unknown };
    if (body.type === "AssessmentValidationError" && Array.isArray(body.detail)) {
      return { ok: false, problems: body.detail as Problem[] };
    }
    const fields = Array.isArray(body.detail)
      ? (body.detail as { loc?: unknown[]; msg?: string }[]).map((d) => ({
          path: (d.loc ?? []).filter((p) => p !== "body").join("."),
          row: null,
          code: "REQUEST_INVALID",
          message: d.msg ?? "invalid",
          severity: "error" as const,
        }))
      : [];
    return { ok: false, problems: fields };
  }
  if (!response.ok) return failure(response);
  return { ok: true, data: await response.json() };
}

export function fileUrl(name: string): string {
  return `${API_BASE_URL}/assessments/files/${encodeURIComponent(name)}`;
}

/** Problems for one draft, keyed by field path relative to the assessment. */
export function problemsFor(problems: Problem[], index: number): Map<string, Problem[]> {
  const prefix = `assessments[${index}]`;
  const map = new Map<string, Problem[]>();
  for (const p of problems) {
    if (!p.path.startsWith(prefix)) continue;
    const key = p.path.slice(prefix.length).replace(/^\./, "");
    map.set(key, [...(map.get(key) ?? []), p]);
  }
  return map;
}

/** Trigger a download of text the page already holds; nothing is uploaded. */
export function downloadText(filename: string, text: string, type: string): void {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// -- input completeness: presence and supported values only ---------------------

export type CompletenessStatus = "present" | "missing" | "invalid" | "unsupported" | "not_established";

export interface CompletenessItem {
  key: string;
  label: string;
  status: CompletenessStatus;
  note: string;
  /** id of the form control to move to. */
  fieldId: string;
  /** Needed only for the sea-level scenario. */
  optional?: boolean;
}

const positive = (text: string): boolean => {
  const n = Number(text.trim());
  return text.trim() !== "" && Number.isFinite(n) && n > 0;
};
const number = (text: string): boolean => text.trim() !== "" && Number.isFinite(Number(text.trim()));

/**
 * Which inputs are filled in and use values the approved model accepts.
 * Presence and enumerated values only: it is not an accuracy or confidence
 * score, and the backend still makes every check when you calculate.
 */
export function completeness(d: AssessmentDraft, index: number): CompletenessItem[] {
  const p = `a${index}`;
  const items: CompletenessItem[] = [];
  items.push({
    key: "area",
    label: "Storage area",
    fieldId: `${p}-area`,
    ...(d.area.trim() === ""
      ? { status: "missing", note: "Enter the area." }
      : positive(d.area)
        ? { status: "present", note: "" }
        : { status: "invalid", note: "Must be a positive number." }),
  } as CompletenessItem);
  const interval: Pick<CompletenessItem, "status" | "note"> =
    d.top.trim() === "" || d.base.trim() === ""
      ? { status: "missing", note: "Enter top and base." }
      : !number(d.top) || !number(d.base) || Number(d.top) >= Number(d.base)
        ? { status: "invalid", note: "Top must be shallower than base." }
        : { status: "present", note: "" };
  items.push({ key: "interval", label: "Storage interval", fieldId: `${p}-top`, ...interval });
  items.push({
    key: "datum",
    label: "Depth datum",
    fieldId: `${p}-datum`,
    ...(d.datum === ""
      ? { status: "missing", note: "Choose what depths are measured from." }
      : d.datum === "ground_level"
        ? { status: "present", note: "" }
        : d.datum === "unknown"
          ? { status: "not_established", note: "Unknown datum: no result can be produced." }
          : { status: "unsupported", note: "Only ground level is supported." }),
  } as CompletenessItem);
  items.push({
    key: "convention",
    label: "Depth convention",
    fieldId: `${p}-convention`,
    ...(d.convention === ""
      ? { status: "missing", note: "Choose TVD or MD." }
      : d.convention === "TVD"
        ? { status: "present", note: "" }
        : d.convention === "unknown"
          ? { status: "not_established", note: "Unknown convention: no result can be produced." }
          : { status: "unsupported", note: "Only TVD is supported." }),
  } as CompletenessItem);
  items.push({
    key: "total_depth",
    label: "Total depth",
    fieldId: `${p}-td`,
    ...(positive(d.total_depth)
      ? { status: "present", note: "" }
      : { status: d.total_depth.trim() ? "invalid" : "missing", note: "Needed to accept a temperature." }),
  } as CompletenessItem);
  const usable = d.observations.some(
    (o) =>
      number(o.value) &&
      number(o.depth) &&
      (ELIGIBLE_METHODS as readonly string[]).includes(o.method) &&
      o.depth_datum === "ground_level" &&
      o.depth_convention === "TVD",
  );
  items.push({
    key: "temperature",
    label: "Corrected temperature",
    fieldId: `${p}-obs0-value`,
    status: usable ? "present" : "missing",
    note: usable
      ? "Interval and total-depth checks run when you calculate."
      : "Needs a Horner, Fertl-Wichmann or Squarci-Taffi value at ground level, TVD.",
  });
  items.push({
    key: "elevation",
    label: "Ground elevation",
    fieldId: `${p}-elev`,
    optional: true,
    ...(number(d.elevation) && d.elevation_reference === "msl"
      ? { status: "present", note: "" }
      : { status: "missing", note: "Only the sea-level scenario needs it." }),
  } as CompletenessItem);
  return items;
}
