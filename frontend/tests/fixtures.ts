/**
 * Response fixtures shaped like the real backend.
 *
 * Values are copied from actual `/wells/SALUZZO|1/screen` responses so the
 * tests fail if the frontend drifts from the contract, rather than agreeing
 * with a shape nobody ships.
 *
 * Phase 14: two paths. The approved model (`literature-screening-v1`) takes
 * area_m2, z_top, z_base and returns both named water-level scenarios with
 * their statuses; a legacy placeholder scenario takes area_m2, thickness_m
 * and returns a NOT_VALIDATED result.
 */

import type {
  ApprovedScreenResult,
  Interpretation,
  LegacyScreenResult,
  RequiredInputs,
  ScenarioSummary,
  TemperatureComparison,
  WaterLevelScenarioResult,
  WellDetail,
  WellSummary,
} from "@/lib/types";

/** Legacy (NOT_VALIDATED) interpretation block. */
export const interpretation: Interpretation = {
  type: "scenario_based_capacity",
  site_specific: false,
  certified: false,
  proven_resource: false,
  basis: "literature-constrained screening under explicit engineering assumptions",
  statement:
    "Scenario-based screening capacity. This is not a certified storage capacity, not a proven storage resource, and not a site-specific estimate.",
  area_policy:
    "Area is not inferred from administrative licence boundaries. area_m2 is explicit scenario or user input.",
  net_thickness_policy:
    "Net storage thickness is not derived from gross stratigraphic thickness. thickness_m is explicit scenario or user input.",
  warnings: [
    {
      code: "not_validated_legacy_path",
      severity: "not_validated",
      message:
        "NOT_VALIDATED: this result comes from a legacy path outside the approved Model Contract.",
      detail: "NOT_VALIDATED: this path predates the approved Model Contract.",
      affects: ["scenario_based_capacity_mt"],
      invalidates_result: false,
      correction_applied: false,
    },
    {
      code: "scale_mismatch_basin_vs_closure",
      severity: "advisory",
      message:
        "Literature-constrained porosity and storage-efficiency ranges are not site-specific closure-scale calibrations.",
      detail:
        "Storage efficiency (CSLF-T-2008-04) is calibrated at basin/aquifer scale.",
      affects: ["porosity", "storage_efficiency"],
      invalidates_result: false,
      correction_applied: false,
      reference: "docs/scenario-literature-review.md sections 8 and 10",
    },
  ],
};

/** Approved-model interpretation block. */
export const approvedInterpretation: Interpretation = {
  type: "scenario_based_capacity",
  site_specific: false,
  certified: false,
  proven_resource: false,
  basis: "approved Model Contract (docs/phase13-owner-decision-record.md)",
  statement:
    "Scenario-based screening capacity under the approved Model Contract. This is not a certified storage capacity, not a proven storage resource, and not a site-specific estimate.",
  area_policy:
    "Area is not inferred from administrative licence boundaries. area_m2 is explicit scenario or user input.",
  storage_interval_policy:
    "The storage-assessment interval (z_top, z_base) is explicit user input in the same depth coordinate and datum as depth_m. It is not inferred from total depth or from stratigraphic units. h_g = z_base - z_top is derived; there is no independent thickness input.",
  percentile_interpretation:
    "P10/P50/P90 represent statistical/model uncertainty conditional on the declared model. They are not total accuracy and not bounds on systematic bias.",
  joint_scenario_methodology:
    "Single joint scenario evaluation (F1). No multiplied correction factor is computed.",
  warnings: [
    {
      code: "scale_mismatch_basin_vs_closure",
      severity: "advisory",
      message:
        "Literature-constrained porosity and storage-efficiency ranges are not site-specific closure-scale calibrations.",
      affects: ["porosity", "storage_efficiency"],
      invalidates_result: false,
      correction_applied: false,
    },
  ],
};

const unknownReference = {
  depth_datum: "unknown",
  status: "UNAVAILABLE" as const,
  diagnostic: "DEPTH_REFERENCE_NOT_ESTABLISHED",
  message: "The depth reference is not formally established (datum 'unknown').",
};

export const wells: WellSummary[] = [
  {
    well_id: "SALUZZO|1",
    original_names: ["SALUZZO 001", "SALUZZO 1"],
    depth_m: 1527.5,
    has_temperature: true,
    has_gross_thickness: true,
    operator: "AGIP",
    outcome: "STERILE",
    screenable_without_user_inputs: false,
  },
  {
    well_id: "CRESCENTINO|1",
    original_names: ["CRESCENTINO 1"],
    depth_m: 900,
    has_temperature: false,
    has_gross_thickness: false,
    operator: "AGIP",
    outcome: "STERILE",
    screenable_without_user_inputs: false,
  },
];

export const wellDetail: WellDetail = {
  canonical_id: "SALUZZO|1",
  original_names: ["SALUZZO 001", "SALUZZO 1"],
  sources: ["Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx"],
  depth_datum: "unknown",
  fields: {
    depth_m: { value: 1527.5, unit: "m", provenance: "extracted", confidence: "high" },
    temperature_k: {
      value: 318.15,
      unit: "K",
      provenance: "derived",
      confidence: "medium",
      method: "extrapolated_squarci_taffi",
    },
    gross_thickness_m: {
      value: 1104.7,
      unit: "m",
      provenance: "derived",
      confidence: "medium",
    },
    porosity: { value: null, unit: "", provenance: "missing", confidence: "none" },
  },
  n_intervals: 3,
  n_temperature_observations: 4,
  conflicts: [
    "depth_m: chose 1527.5, also saw 1531.0 (pozzi-storici.csv) -- sources disagree on total depth",
  ],
  required_user_inputs: ["area_m2", "z_top", "z_base"],
  approved_model_depth_reference: unknownReference,
  interpretation: approvedInterpretation,
};

const areaSpec = {
  field: "area_m2",
  unit: "m2",
  label: "Storage area",
  description: "Structural closure area of the storage complex.",
  policy: "Area is not inferred from administrative licence boundaries.",
  not_inferred_from: ["licence boundaries", "well spacing"],
  minimum_exclusive: 0,
  needed: true,
};

/** Approved model: area and the storage interval; the datum blocks (C2). */
export const requiredInputs: RequiredInputs = {
  well_id: "SALUZZO|1",
  scenario: { name: "literature-screening-v1", version: "1" },
  model_path: "APPROVED_MODEL",
  required: [
    areaSpec,
    {
      field: "z_top",
      unit: "m",
      label: "Storage interval top (z_top)",
      description: "Top of the designated storage-assessment interval.",
      policy: "The storage-assessment interval (z_top, z_base) is explicit user input.",
      not_inferred_from: ["total well depth", "stratigraphic units"],
      minimum_inclusive: 0,
      model_path: "APPROVED_MODEL",
      needed: true,
    },
    {
      field: "z_base",
      unit: "m",
      label: "Storage interval base (z_base)",
      description: "Base of the designated storage-assessment interval.",
      policy: "The storage-assessment interval (z_top, z_base) is explicit user input.",
      not_inferred_from: ["total well depth", "stratigraphic units"],
      minimum_exclusive: 0,
      must_exceed: "z_top",
      model_path: "APPROVED_MODEL",
      needed: true,
    },
  ],
  blocked_by_missing_source_data: [
    {
      field: "depth_datum",
      reason: "DEPTH_REFERENCE_NOT_ESTABLISHED: The depth reference is not formally established.",
    },
  ],
  can_be_screened_with_user_inputs: false,
  depth_reference: unknownReference,
  interpretation: approvedInterpretation,
};

/** A NOT_VALIDATED legacy scenario: area and net thickness, as before. */
export const legacyRequiredInputs: RequiredInputs = {
  well_id: "SALUZZO|1",
  scenario: { name: "sensitivity-placeholder", version: "0-placeholder" },
  model_path: "LEGACY_NOT_VALIDATED",
  validation_status: "NOT_VALIDATED",
  required: [
    areaSpec,
    {
      field: "thickness_m",
      unit: "m",
      label: "Net storage thickness",
      description: "Net reservoir thickness inside the closure.",
      policy: "Net storage thickness is not derived from gross stratigraphic thickness.",
      not_inferred_from: ["gross stratigraphic thickness"],
      minimum_exclusive: 0,
      model_path: "LEGACY_NOT_VALIDATED",
      needed: true,
    },
  ],
  blocked_by_missing_source_data: [],
  can_be_screened_with_user_inputs: true,
  interpretation,
};

export const approvedScenario: ScenarioSummary = {
  name: "literature-screening-v1",
  aliases: ["literature", "literature-screening-v1"],
  version: "1",
  date: "2026-09-19",
  description: "Literature-constrained parameter set of the approved Model Contract.",
  assumed_parameters: ["storage_efficiency", "porosity"],
  evidence_classes: ["generic", "regional"],
  literature_derived: true,
  supplies_user_inputs: [],
  validation_status: "APPROVED_MODEL",
  model_path: "APPROVED_MODEL",
  required_user_inputs: ["area_m2", "z_top", "z_base"],
};

export const legacyScenario: ScenarioSummary = {
  name: "sensitivity-placeholder",
  aliases: ["sensitivity"],
  version: "0-placeholder",
  date: "2026-09-19",
  description: "NOT_VALIDATED legacy placeholder scenario.",
  assumed_parameters: ["area_m2", "thickness_m", "porosity", "pressure_pa", "storage_efficiency"],
  evidence_classes: ["placeholder"],
  literature_derived: false,
  supplies_user_inputs: ["area_m2", "thickness_m"],
  validation_status: "NOT_VALIDATED",
  model_path: "LEGACY_NOT_VALIDATED",
  required_user_inputs: ["area_m2", "thickness_m"],
};

export const scenarios: ScenarioSummary[] = [approvedScenario, legacyScenario];

/** A NOT_VALIDATED legacy result (the pre-contract response shape, labelled). */
export const screened: LegacyScreenResult = {
  model_path: "LEGACY_NOT_VALIDATED",
  validation_status: "NOT_VALIDATED",
  status: "screened",
  well_id: "SALUZZO|1",
  scenario: { name: "literature-screening-v1", version: "1", date: "2026-09-19" },
  interpretation,
  scenario_based_capacity_mt: {
    p10: 5.24,
    p50: 10.64,
    p90: 20.26,
    mean: 11.84,
    n_samples: 2000,
    deterministic: false,
  },
  source_derived_inputs: ["temperature_k"],
  modelled_inputs: ["pressure_pa"],
  assumed_inputs: ["porosity", "storage_efficiency"],
  user_supplied_inputs: ["area_m2", "thickness_m"],
  screening_inputs: {
    temperature_k: {
      value: 318.15,
      unit: "K",
      provenance: "derived",
      assumed: false,
      from_source: true,
      label: "source",
      evidence_class: "site_specific",
      assumption_ignored_source_won: false,
      method: "extrapolated_squarci_taffi",
      derivation: "45.0 degC at 1522.6 m converted to K",
      citation: null,
    },
    pressure_pa: {
      value: [15279251.03, 16477623.66],
      unit: "Pa",
      provenance: "derived",
      assumed: false,
      from_source: true,
      label: "MODELLED",
      evidence_class: "generic",
      assumption_ignored_source_won: false,
      method: "hydrostatic_from_depth",
      derivation:
        "P = rho*g*z with rho = (1020.0, 1100.0) kg/m3, g = 9.80665 m/s2, z = 1527.5 m",
      rationale: "Normally-pressured hydrostatic assumption.",
      citation: null,
    },
    porosity: {
      value: [0.1, 0.35],
      unit: "-",
      provenance: "assumed",
      assumed: true,
      from_source: false,
      label: "ASSUMED",
      evidence_class: "regional",
      assumption_ignored_source_won: false,
      method: "engineering_assumption",
      rationale: "Full porosity range across 13 Italian potential reservoirs.",
      author: "Iman (geoenergy engineer)",
      citation: {
        source: "Donda, Volpi, Persoglia & Parushev (OGS, Trieste)",
        title: "CO2 storage potential of deep saline aquifers: The case of Italy",
        year: 2011,
        text: "Donda, F. et al. (2011). IJGGC 5(2), 327-335.",
        evidence_class: "regional",
        locator: "Table 2",
        quote: null,
        url: "https://doi.org/10.1016/j.ijggc.2010.08.009",
      },
    },
    storage_efficiency: {
      value: [0.01, 0.04],
      unit: "-",
      provenance: "assumed",
      assumed: true,
      from_source: false,
      label: "ASSUMED",
      evidence_class: "generic",
      assumption_ignored_source_won: false,
      method: "engineering_assumption",
      rationale: "CSLF/USDOE P15-P85 storage efficiency for deep saline aquifers.",
      author: "Iman (geoenergy engineer)",
      citation: {
        source: "CSLF Task Force",
        title: "Phase III Report",
        year: 2008,
        text: "Bachu, S. (2008). CSLF-T-2008-04.",
        evidence_class: "generic",
        locator: "Executive Summary",
        quote: "between 1% and 4% for deep saline aquifers",
        url: null,
      },
    },
    area_m2: {
      value: 80000000,
      unit: "m2",
      provenance: "assumed",
      assumed: true,
      from_source: false,
      label: "USER",
      evidence_class: "user_input",
      assumption_ignored_source_won: false,
      method: "engineering_assumption",
      rationale: "Structural closure area, supplied by the caller.",
      author: "caller (user input)",
      citation: {
        source: "caller",
        title: "User-supplied screening input",
        year: 2026,
        text: "USER INPUT supplied at request time. No literature range exists.",
        evidence_class: "user_input",
        locator: null,
        quote: null,
        url: null,
      },
    },
    thickness_m: {
      value: 35,
      unit: "m",
      provenance: "assumed",
      assumed: true,
      from_source: false,
      label: "USER",
      evidence_class: "user_input",
      assumption_ignored_source_won: false,
      method: "engineering_assumption",
      rationale: "Net reservoir thickness, supplied by the caller.",
      author: "caller (user input)",
      citation: null,
    },
  },
  label_legend: {
    source: "extracted from, or derived from, this well's own data",
    MODELLED: "computed from source data under a declared generic model",
    ASSUMED: "supplied by the scenario",
    USER: "supplied by the caller for this request",
  },
  user_inputs: {
    area_m2: { value: 80000000, unit: "m2" },
    thickness_m: { value: 35, unit: "m" },
  },
  temperature: {
    value_k: 318.15,
    value_degc: 45,
    method: "extrapolated_squarci_taffi",
    provenance: "derived",
    derivation: "45.0 degC at 1522.6 m",
    alternatives: [{ value_k: 312.15, source: "non_stabilized @ 1522.6 m" }],
  },
  conflicts: ["depth_m: chose 1527.5, also saw 1531.0"],
  depth_m: 1527.5,
};

export const blocked: LegacyScreenResult = {
  ...screened,
  status: "blocked",
  well_id: "CRESCENTINO|1",
  scenario_based_capacity_mt: null,
  missing_fields: ["temperature_k"],
  missing_reasons: {
    temperature_k:
      "no source value, and temperature_k may not be supplied by a scenario",
  },
  source_derived_inputs: [],
  modelled_inputs: [],
  assumed_inputs: [],
  user_supplied_inputs: [],
  screening_inputs: {},
  temperature: null,
};

export const temperatureComparison: TemperatureComparison = {
  status: "compared",
  validation_status: "NOT_VALIDATED",
  validation_note:
    "NOT_VALIDATED legacy diagnostic (owner decision O2). The comparison runs the legacy scenario resolver.",
  well_id: "SALUZZO|1",
  selected_method: "extrapolated_squarci_taffi",
  variants: [
    {
      method: "extrapolated_squarci_taffi",
      temperature_k: 318.15,
      temperature_degc: 45,
      depth_m: 1522.6,
      p50_mt: 10.64,
    },
    {
      method: "non_stabilized",
      temperature_k: 312.15,
      temperature_degc: 39,
      depth_m: 1522.6,
      p50_mt: 11.4,
    },
  ],
  p50_spread_mt: 0.76,
  p50_spread_percent: 7.1,
  interpretation,
};

// -- approved model ------------------------------------------------------------

const envelopeInside = {
  pressure_pa: [1e6, 35e6] as [number, number],
  temperature_k: [280, 400] as [number, number],
  n_realisations: 2000,
  n_outside: 0,
  n_pressure_below_envelope: 0,
  n_pressure_above_envelope: 0,
  temperature_inside: true,
  all_inside: true,
  realisations_discarded: 0,
};

export const groundValidated: WaterLevelScenarioResult = {
  name: "GROUND_REFERENCE",
  role: "baseline",
  label: "PROJECT REFERENCE SCENARIO -- not a measured formation head",
  description: "Formation-head reference at ground elevation.",
  z_wl_definition: "z_wl = 0 (ground level)",
  validation_status: "VALIDATED",
  validated_percentiles: "REPORTED",
  z_wl_m: 0,
  z_state_m: 1463.5,
  pressure_eos_pa: { low: 14741000, high: 15888000, unit: "Pa" },
  temperature_k: 318.15,
  envelope: envelopeInside,
  capacity_mt: {
    p10: 7.31,
    p50: 14.62,
    p90: 27.48,
    mean: 16.07,
    n_samples: 2000,
    validation_status: "VALIDATED",
    interpretation: "P10/P50/P90 are conditional on the declared model.",
  },
  diagnostic_capacity_mt: null,
  diagnostics: [],
};

export const seaValidated: WaterLevelScenarioResult = {
  ...groundValidated,
  name: "SEA_LEVEL_SENSITIVITY",
  role: "sensitivity",
  label: "SENSITIVITY SCENARIO -- not a measured formation head",
  description: "Formation-head reference at sea level.",
  z_wl_definition: "z_wl = quota (ground elevation above mean sea level)",
  z_wl_m: 310,
  pressure_eos_pa: { low: 11640000, high: 12540000, unit: "Pa" },
  capacity_mt: {
    p10: 6.02,
    p50: 12.18,
    p90: 22.95,
    mean: 13.4,
    n_samples: 2000,
    validation_status: "VALIDATED",
  },
};

/** Outside the envelope: percentiles blocked; the diagnostic numbers must never show. */
export const groundOutside: WaterLevelScenarioResult = {
  ...groundValidated,
  validation_status: "OUTSIDE_VALIDATED_ENVELOPE",
  validated_percentiles: "BLOCKED",
  temperature_k: 410,
  envelope: { ...envelopeInside, n_outside: 2000, temperature_inside: false, all_inside: false },
  capacity_mt: null,
  diagnostic_capacity_mt: {
    p10: 88.8,
    p50: 99.9,
    p90: 111.1,
    mean: 100.5,
    n_samples: 2000,
    validation_status: "NOT_VALIDATED",
    label: "DIAGNOSTIC ONLY -- NOT VALIDATED.",
  },
  diagnostics: [
    {
      code: "OUTSIDE_VALIDATED_ENVELOPE",
      message: "At least one Monte Carlo realisation lies outside the validated EOS envelope.",
      n_outside: 2000,
      n_realisations: 2000,
    },
  ],
};

export const seaUnavailable: WaterLevelScenarioResult = {
  ...seaValidated,
  validation_status: "UNAVAILABLE",
  validated_percentiles: "UNAVAILABLE",
  z_wl_m: null,
  pressure_eos_pa: null,
  envelope: null,
  capacity_mt: null,
  diagnostics: [
    {
      code: "SURFACE_ELEVATION_UNAVAILABLE",
      message: "SEA_LEVEL_SENSITIVITY needs the ground elevation above sea level (quota).",
    },
  ],
};

const approvedBase = {
  model_path: "APPROVED_MODEL" as const,
  status: "evaluated" as const,
  well_id: "SALUZZO|1",
  scenario: {
    name: "literature-screening-v1",
    version: "1",
    date: "2026-09-19",
    applied_as: "approved-model",
  },
  interpretation: approvedInterpretation,
  user_inputs: {
    area_m2: { value: 80000000, unit: "m2" },
    z_top: { value: 1400, unit: "m" },
    z_base: { value: 1527, unit: "m" },
  },
  depth_reference: { depth_datum: "ground_level", status: "AVAILABLE" as const, diagnostics: [] },
  storage_interval: {
    status: "AVAILABLE" as const,
    z_top_m: 1400,
    z_base_m: 1527,
    h_g_m: 127,
    z_state_m: 1463.5,
    state_point_convention: "PROJECT MODEL CONVENTION (S1): z_state = (z_top + z_base) / 2.",
    diagnostics: [],
  },
  temperature_selection: {
    status: "AVAILABLE" as const,
    evaluated: true,
    temperature_k: 318.15,
    selected_observation: {
      depth_m: 1522.6,
      temperature_k: 318.15,
      method: "extrapolated_squarci_taffi",
    },
    diagnostics: [],
  },
  sampled_inputs: {
    porosity: {
      distribution: "uniform",
      low: 0.1,
      high: 0.35,
      unit: "-",
      status: "PROVISIONAL",
      provenance: "Donda et al. (2011), Table 2 (13 Italian potential reservoirs)",
      citation: {
        source: "Donda, Volpi, Persoglia & Parushev (OGS, Trieste)",
        title: "CO2 storage potential of deep saline aquifers: The case of Italy",
        year: 2011,
        text: "Donda, F. et al. (2011). IJGGC 5(2), 327-335.",
        evidence_class: "regional" as const,
        locator: "Table 2",
        quote: null,
        url: null,
      },
    },
    storage_efficiency: {
      distribution: "uniform",
      low: 0.01,
      high: 0.04,
      unit: "-",
      status: "DECIDED (A6)",
      provenance: "CSLF-T-2008-04 / DOE-derived P15-P85 bounds",
      statement:
        "The Uniform distribution is a project-defined prior over the DOE-derived P15\u2013P85 bounds. It is not claimed to reproduce the DOE probability distribution.",
      citation: {
        source: "CSLF Task Force",
        title: "Phase III Report",
        year: 2008,
        text: "Bachu, S. (2008). CSLF-T-2008-04.",
        evidence_class: "generic" as const,
        locator: "Executive Summary",
        quote: null,
        url: null,
      },
    },
  },
  n_samples: 2000,
};

/** Both named scenarios VALIDATED (a ground-level reference; test data). */
export const approvedValidated: ApprovedScreenResult = {
  ...approvedBase,
  water_level_scenarios: [groundValidated, seaValidated],
  systematic_effect: {
    methodology: "Single joint scenario evaluation (F1).",
    baseline: "GROUND_REFERENCE",
    individual_effects: [
      {
        effect: "water_level",
        contrast: "SEA_LEVEL_SENSITIVITY vs GROUND_REFERENCE",
        status: "AVAILABLE",
        p50_difference_mt: -2.44,
        reason: null,
        is_correction: false,
      },
    ],
    multiplied_correction_factor: null,
  },
};

/** One scenario outside the envelope, the other unavailable. */
export const approvedMixed: ApprovedScreenResult = {
  ...approvedBase,
  water_level_scenarios: [groundOutside, seaUnavailable],
  systematic_effect: {
    ...approvedValidated.systematic_effect!,
    individual_effects: [
      {
        effect: "water_level",
        contrast: "SEA_LEVEL_SENSITIVITY vs GROUND_REFERENCE",
        status: "UNAVAILABLE",
        p50_difference_mt: null,
        reason: "Reported only when both named scenarios are VALIDATED.",
        is_correction: false,
      },
    ],
  },
};

const depthDiagnostic = {
  code: "DEPTH_REFERENCE_NOT_ESTABLISHED",
  message: "The depth reference is not formally established (datum 'unknown').",
  depth_datum: "unknown",
};

/** What every ingested well returns today: the depth reference is not established. */
export const approvedUnavailable: ApprovedScreenResult = {
  ...approvedBase,
  depth_reference: { depth_datum: "unknown", status: "UNAVAILABLE", diagnostics: [depthDiagnostic] },
  storage_interval: {
    ...approvedBase.storage_interval,
    status: "UNAVAILABLE",
    h_g_m: null,
    z_state_m: null,
    diagnostics: [depthDiagnostic],
  },
  temperature_selection: {
    status: "UNAVAILABLE",
    evaluated: false,
    temperature_k: null,
    selected_observation: null,
    diagnostics: [depthDiagnostic],
  },
  water_level_scenarios: [
    {
      ...groundValidated,
      validation_status: "UNAVAILABLE",
      validated_percentiles: "UNAVAILABLE",
      z_wl_m: null,
      z_state_m: null,
      pressure_eos_pa: null,
      temperature_k: null,
      envelope: null,
      capacity_mt: null,
      diagnostics: [depthDiagnostic],
    },
    {
      ...seaValidated,
      validation_status: "UNAVAILABLE",
      validated_percentiles: "UNAVAILABLE",
      z_wl_m: null,
      z_state_m: null,
      pressure_eos_pa: null,
      temperature_k: null,
      envelope: null,
      capacity_mt: null,
      diagnostics: [depthDiagnostic],
    },
  ],
};

/** The approved path refusing a request (missing or invalid inputs). */
export const approvedBlocked: ApprovedScreenResult = {
  model_path: "APPROVED_MODEL",
  status: "blocked",
  well_id: "SALUZZO|1",
  scenario: { name: "literature-screening-v1", version: "1" },
  interpretation: approvedInterpretation,
  water_level_scenarios: [],
  reason: "missing_or_invalid_user_inputs",
  error:
    "thickness_m is not an input of the approved model: its thickness term is h_g = z_base - z_top.",
};
