/**
 * Types mirroring the FastAPI screening contract.
 *
 * These are a description of what the backend returns, not a second source of
 * truth. Nothing here invents a field the API does not send, and nothing
 * collapses the four provenance buckets into a generic "inputs" shape.
 */

/** Label the backend assigns to every screening input. Never merged. */
export type InputLabel = "source" | "MODELLED" | "ASSUMED" | "USER";

/** How close a value's evidence is to the well it is applied to. */
export type EvidenceClass =
  | "site_specific"
  | "regional"
  | "generic"
  | "user_input"
  | "unsupported"
  | "placeholder";

export interface Citation {
  source: string;
  title: string;
  year: number;
  text: string;
  evidence_class: EvidenceClass;
  locator: string | null;
  quote: string | null;
  url: string | null;
}

/** One resolved screening input, with its full lineage. */
export interface ScreeningInput {
  value: number | number[];
  unit: string;
  provenance: string;
  assumed: boolean;
  from_source: boolean;
  label: InputLabel;
  evidence_class: EvidenceClass;
  assumption_ignored_source_won: boolean;
  detail?: string;
  method?: string;
  derivation?: string;
  rationale?: string;
  author?: string;
  citation: Citation | string | null;
}

export interface InterpretationWarning {
  code: string;
  severity: string;
  message: string;
  detail?: string;
  affects?: string[];
  invalidates_result: boolean;
  correction_applied: boolean;
  reference?: string;
}

export interface Interpretation {
  type: "scenario_based_capacity";
  site_specific: false;
  certified: false;
  proven_resource: false;
  basis: string;
  statement: string;
  area_policy: string;
  net_thickness_policy: string;
  warnings: InterpretationWarning[];
}

export interface Capacity {
  p10: number;
  p50: number;
  p90: number;
  mean: number;
  n_samples: number;
  deterministic: boolean;
}

export interface WellSummary {
  well_id: string;
  original_names: string[];
  depth_m: number | null;
  has_temperature: boolean;
  has_gross_thickness: boolean;
  operator: string | null;
  outcome: string | null;
  screenable_without_user_inputs: boolean;
}

export interface FieldValue {
  value: number | string | null;
  unit: string;
  provenance: string;
  confidence: string;
  source?: string;
  method?: string;
  derivation?: string;
  notes?: string[];
  conflicts?: string[];
}

export interface WellDetail {
  canonical_id: string;
  original_names: string[];
  sources: string[];
  depth_datum: string;
  fields: Record<string, FieldValue>;
  n_intervals: number;
  n_temperature_observations: number;
  conflicts: string[];
  required_user_inputs: string[];
  interpretation: Interpretation;
}

export interface RequiredInputSpec {
  field: string;
  unit: string;
  label: string;
  description: string;
  policy: string;
  not_inferred_from: string[];
  minimum_exclusive: number;
  needed?: boolean;
}

export interface RequiredInputs {
  well_id: string;
  scenario: { name: string; version: string };
  required: RequiredInputSpec[];
  blocked_by_missing_source_data: { field: string; reason: string }[];
  can_be_screened_with_user_inputs: boolean;
  interpretation: Interpretation;
}

export interface TemperatureDetail {
  value_k: number | null;
  value_degc: number | null;
  method: string | null;
  provenance: string;
  derivation: string | null;
  alternatives: { value_k: number; source: string }[];
}

export interface ScreenResult {
  status: "screened" | "blocked";
  well_id: string;
  scenario: { name: string; version: string; date?: string; applied_as?: string };
  interpretation: Interpretation;
  scenario_based_capacity_mt: Capacity | null;
  source_derived_inputs: string[];
  modelled_inputs: string[];
  assumed_inputs: string[];
  user_supplied_inputs: string[];
  screening_inputs: Record<string, ScreeningInput>;
  label_legend: Record<string, string>;
  user_inputs: Record<string, { value: number; unit: string }>;
  temperature: TemperatureDetail | null;
  conflicts: string[];
  depth_m: number | null;
  reason?: string | null;
  error?: string | null;
  missing_fields?: string[] | null;
  missing_reasons?: Record<string, string> | null;
}

export interface ScenarioSummary {
  name: string;
  aliases: string[];
  version: string;
  date: string;
  description: string;
  assumed_parameters: string[];
  evidence_classes: EvidenceClass[];
  literature_derived: boolean;
  supplies_user_inputs: string[];
}

export interface TemperatureVariant {
  method: string;
  temperature_k: number;
  temperature_degc: number;
  depth_m: number;
  p50_mt: number | null;
}

export interface TemperatureComparison {
  status: string;
  well_id: string | null;
  selected_method: string | null;
  variants: TemperatureVariant[];
  p50_spread_mt: number | null;
  p50_spread_percent: number | null;
  interpretation: Interpretation;
  note?: string;
}

export interface UserInputValues {
  area_m2: number;
  thickness_m: number;
}
