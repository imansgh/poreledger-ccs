/**
 * Response fixtures shaped like the real backend.
 *
 * Values are copied from an actual `/wells/SALUZZO|1/screen` response so the
 * tests fail if the frontend drifts from the contract, rather than agreeing
 * with a shape nobody ships.
 */

import type {
  Interpretation,
  RequiredInputs,
  ScenarioSummary,
  ScreenResult,
  TemperatureComparison,
  WellDetail,
  WellSummary,
} from "@/lib/types";

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
  required_user_inputs: ["area_m2", "thickness_m"],
  interpretation,
};

export const requiredInputs: RequiredInputs = {
  well_id: "SALUZZO|1",
  scenario: { name: "literature-screening-v1", version: "1" },
  required: [
    {
      field: "area_m2",
      unit: "m2",
      label: "Storage area",
      description: "Structural closure area of the storage complex.",
      policy: "Area is not inferred from administrative licence boundaries.",
      not_inferred_from: ["licence boundaries", "well spacing"],
      minimum_exclusive: 0,
      needed: true,
    },
    {
      field: "thickness_m",
      unit: "m",
      label: "Net storage thickness",
      description: "Net reservoir thickness inside the closure.",
      policy: "Net storage thickness is not derived from gross stratigraphic thickness.",
      not_inferred_from: ["gross stratigraphic thickness"],
      minimum_exclusive: 0,
      needed: true,
    },
  ],
  blocked_by_missing_source_data: [],
  can_be_screened_with_user_inputs: true,
  interpretation,
};

export const scenarios: ScenarioSummary[] = [
  {
    name: "literature-screening-v1",
    aliases: ["literature", "literature-screening-v1"],
    version: "1",
    date: "2026-09-19",
    description: "Literature-constrained screening scenario.",
    assumed_parameters: ["storage_efficiency", "porosity"],
    evidence_classes: ["generic", "regional"],
    literature_derived: true,
    supplies_user_inputs: [],
  },
];

export const screened: ScreenResult = {
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

export const blocked: ScreenResult = {
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
