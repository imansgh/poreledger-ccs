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

/**
 * The two screening paths the backend exposes. The approved model implements
 * the owner-approved Model Contract; every legacy path is NOT_VALIDATED.
 */
export type ModelPath = "APPROVED_MODEL" | "LEGACY_NOT_VALIDATED";

/** Per-scenario status on the approved model. Legacy results are NOT_VALIDATED. */
export type ScenarioValidationStatus =
  | "VALIDATED"
  | "OUTSIDE_VALIDATED_ENVELOPE"
  | "UNAVAILABLE";

export interface Interpretation {
  type: "scenario_based_capacity";
  site_specific: false;
  certified: false;
  proven_resource: false;
  basis: string;
  statement: string;
  area_policy: string;
  /** Legacy paths only. */
  net_thickness_policy?: string;
  /** Approved model only. */
  storage_interval_policy?: string;
  percentile_interpretation?: string;
  joint_scenario_methodology?: string;
  warnings: InterpretationWarning[];
}

/** One machine-readable reason attached by the approved model. */
export interface Diagnostic {
  code: string;
  message: string;
  [detail: string]: unknown;
}

export interface DepthReferenceStatus {
  depth_datum: string;
  status: "AVAILABLE" | "UNAVAILABLE";
  diagnostic: string | null;
  message: string | null;
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
  depth_datum?: string;
  approved_model_depth_reference?: DepthReferenceStatus;
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
  approved_model_depth_reference?: DepthReferenceStatus;
  interpretation: Interpretation;
}

export interface RequiredInputSpec {
  field: string;
  unit: string;
  label: string;
  description: string;
  policy: string;
  not_inferred_from: string[];
  minimum_exclusive?: number;
  minimum_inclusive?: number;
  must_exceed?: string;
  model_path?: ModelPath;
  needed?: boolean;
}

export interface RequiredInputs {
  well_id: string;
  scenario: { name: string; version: string };
  model_path?: ModelPath;
  validation_status?: "NOT_VALIDATED";
  required: RequiredInputSpec[];
  blocked_by_missing_source_data: { field: string; reason: string }[];
  can_be_screened_with_user_inputs: boolean;
  depth_reference?: DepthReferenceStatus;
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

/** A NOT_VALIDATED legacy screening result (placeholder scenarios). */
export interface LegacyScreenResult {
  model_path: "LEGACY_NOT_VALIDATED";
  validation_status: "NOT_VALIDATED";
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

/** Validated percentiles of one named scenario; present only when VALIDATED. */
export interface ApprovedCapacity {
  p10: number;
  p50: number;
  p90: number;
  mean: number;
  n_samples: number;
  validation_status: "VALIDATED";
  interpretation?: string;
}

export interface EnvelopeCheck {
  pressure_pa: [number, number];
  temperature_k: [number, number];
  n_realisations: number;
  n_outside: number;
  n_pressure_below_envelope: number;
  n_pressure_above_envelope: number;
  temperature_inside: boolean;
  all_inside: boolean;
  realisations_discarded: number;
}

/** One named water-level scenario of the approved model. */
export interface WaterLevelScenarioResult {
  name: "GROUND_REFERENCE" | "SEA_LEVEL_SENSITIVITY";
  role: "baseline" | "sensitivity";
  label: string;
  description: string;
  z_wl_definition: string;
  validation_status: ScenarioValidationStatus;
  validated_percentiles: "REPORTED" | "BLOCKED" | "UNAVAILABLE";
  z_wl_m: number | null;
  z_state_m: number | null;
  pressure_eos_pa: { low: number; high: number; unit: string } | null;
  temperature_k: number | null;
  envelope: EnvelopeCheck | null;
  capacity_mt: ApprovedCapacity | null;
  /** NOT_VALIDATED diagnostic numbers. The UI never displays them. */
  diagnostic_capacity_mt: Record<string, unknown> | null;
  diagnostics: Diagnostic[];
}

export interface TemperatureSelection {
  status: "AVAILABLE" | "UNAVAILABLE";
  evaluated: boolean;
  temperature_k: number | null;
  selected_observation: {
    depth_m: number;
    temperature_k: number;
    method: string;
  } | null;
  diagnostics: Diagnostic[];
}

export interface StorageIntervalResult {
  status: "AVAILABLE" | "UNAVAILABLE";
  z_top_m: number;
  z_base_m: number;
  h_g_m: number | null;
  z_state_m: number | null;
  state_point_convention: string;
  diagnostics: Diagnostic[];
}

export interface SystematicEffect {
  methodology: string;
  baseline: string;
  individual_effects: {
    effect: string;
    contrast: string;
    status: "AVAILABLE" | "UNAVAILABLE";
    p50_difference_mt: number | null;
    reason: string | null;
    is_correction: false;
  }[];
  multiplied_correction_factor: null;
}

export interface SampledInput {
  distribution: string;
  low: number;
  high: number;
  unit: string;
  status: string;
  provenance: string;
  statement?: string;
  citation: Citation | null;
}

/** The approved-model result: both named water-level scenarios. */
export interface ApprovedScreenResult {
  model_path: "APPROVED_MODEL";
  status: "evaluated" | "blocked";
  well_id: string;
  scenario: { name: string; version: string; date?: string; applied_as?: string };
  interpretation: Interpretation;
  water_level_scenarios: WaterLevelScenarioResult[];
  user_inputs?: Record<string, { value: number; unit: string }>;
  depth_reference?: {
    depth_datum: string;
    status: "AVAILABLE" | "UNAVAILABLE";
    diagnostics: Diagnostic[];
  };
  storage_interval?: StorageIntervalResult;
  temperature_selection?: TemperatureSelection;
  systematic_effect?: SystematicEffect;
  sampled_inputs?: Record<string, SampledInput>;
  n_samples?: number;
  reason?: string;
  error?: string;
  required_user_inputs?: RequiredInputSpec[];
}

export type ScreenResult = ApprovedScreenResult | LegacyScreenResult;

export function isApproved(result: ScreenResult): result is ApprovedScreenResult {
  return result.model_path === "APPROVED_MODEL";
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
  validation_status?: "APPROVED_MODEL" | "NOT_VALIDATED";
  model_path?: ModelPath;
  required_user_inputs?: string[];
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
  validation_status?: "NOT_VALIDATED";
  validation_note?: string;
  note?: string;
}

/**
 * Caller inputs, exactly as sent. Which fields are present depends on the
 * scenario's path: area_m2, z_top, z_base for the approved model; area_m2 and
 * thickness_m for NOT_VALIDATED legacy scenarios. Nothing is derived here.
 */
export interface UserInputValues {
  area_m2: number;
  z_top?: number;
  z_base?: number;
  thickness_m?: number;
}
