"""Phase 9 audit regression tests for provenance and literature.

Phase 9 obtained both primary sources and read them in full, so these tests pin
what the sources actually say -- the adopted ranges, the verbatim quote, the
evidence classes -- against drift in either direction.

Two of them encode results the audit had to go to the primary source to settle:
the CSLF storage-efficiency factor contains a net-to-gross term (confirming
Finding 3.1 and re-bounding it to 1.33x-4x), and it also contains an
interconnected-porosity term (resolving Finding 3.2 in the implementation's
favour).

See ``docs/scientific-validation-audit.md``, Phase 9.
"""

from __future__ import annotations

import pytest

from ccs_screen.ingest.assumptions import AssumptionError, Citation, EvidenceClass
from ccs_screen.ingest.scenario import (
    AREA_POLICY_STATEMENT,
    CSLF_2008,
    DONDA_2011,
    LITERATURE_SCREENING_V1,
)

#: CSLF-T-2008-04, the components varied to produce the 1-4% range for E.
#: Read from the primary source in Phase 9.
CSLF_EFFICIENCY_COMPONENTS = {
    "aquifer suitable for storage": (0.2, 0.8),
    "unit with required porosity and permeability": (0.25, 0.75),
    "interconnected porosity": (0.6, 0.95),
    "areal displacement": (0.5, 0.8),
    "vertical displacement": (0.6, 0.9),
    "net thickness contacted by buoyancy": (0.2, 0.6),
    "pore-scale displacement": (0.5, 0.8),
}

#: Donda et al. (2011) Table 2, porosity column, all 14 published rows.
DONDA_TABLE_2_POROSITY_PERCENT = [25, 25, 30, 30, 10, 35, 25, 25, 20, 20, 35, 25, 30, 30]

#: Donda et al. (2011) Table 2 totals, in Mt, at Seff = 1% and Seff = 4%.
DONDA_TABLE_2_TOTALS_MT = (2_950, 11_800)


def assumption_for(parameter):
    for assumption in LITERATURE_SCREENING_V1.assumptions.assumptions:
        if assumption.parameter == parameter:
            return assumption
    raise AssertionError(f"{parameter} is not assumed by literature-screening-v1")


# -- the adopted ranges match the sources ------------------------------------


def test_storage_efficiency_range_matches_cslf():
    assert assumption_for("storage_efficiency").value == (0.01, 0.04)


def test_porosity_range_matches_all_fourteen_donda_rows():
    """The locator says 13 rows; the published table has 14.

    The range is unaffected, which is why Finding 9.6 is LOW: the minimum is
    still Lombardia 1 at 10% and the maximum still Marche 1 / Sicilia 1 at 35%.
    """
    assert len(DONDA_TABLE_2_POROSITY_PERCENT) == 14
    low, high = assumption_for("porosity").value
    assert low * 100 == min(DONDA_TABLE_2_POROSITY_PERCENT)
    assert high * 100 == max(DONDA_TABLE_2_POROSITY_PERCENT)


def test_donda_table_totals_prove_the_four_percent_reading():
    """Finding 9.5: the paper says '1% or 4%' then '(Seff = 1% or 5%)'.

    Its own table settles it -- the totals are in a ratio of exactly 4.00, so
    the table was computed at 4% and the text sentence is the typo. The project
    adopted the table-consistent value.
    """
    at_one_percent, at_four_percent = DONDA_TABLE_2_TOTALS_MT
    assert at_four_percent / at_one_percent == pytest.approx(4.0, abs=0.01)
    assert at_one_percent * 5 != at_four_percent
    assert assumption_for("storage_efficiency").value[1] == 0.04


# -- Finding 9.1: E contains a net-to-gross term -----------------------------


def test_cslf_efficiency_contains_a_net_to_gross_term():
    """Finding 9.1, from the primary source.

    E is calibrated to absorb the gross-to-net reduction, so supplying net
    thickness and then multiplying by E applies it twice.
    """
    assert "unit with required porosity and permeability" in CSLF_EFFICIENCY_COMPONENTS
    low, high = CSLF_EFFICIENCY_COMPONENTS["unit with required porosity and permeability"]
    assert (low, high) == (0.25, 0.75)


def test_double_counting_understatement_is_between_one_third_and_four_times():
    """Re-bounds Phase 3's 1.4x-10x estimate to 1.33x-4x from the source."""
    low, high = CSLF_EFFICIENCY_COMPONENTS["unit with required porosity and permeability"]
    assert 1 / high == pytest.approx(1.33, abs=0.01)
    assert 1 / low == pytest.approx(4.00, abs=0.01)


def test_the_api_still_requires_net_thickness():
    """CHARACTERISATION, Finding 9.1.

    The double-count exists because the contract asks for net thickness. If the
    contract ever changes to gross, Finding 9.1 is resolved and this test must
    be replaced.
    """
    from ccs_screen.api import USER_INPUT_SPEC

    assert USER_INPUT_SPEC["thickness_m"]["label"] == "Net storage thickness"
    assert "gross stratigraphic thickness" in USER_INPUT_SPEC["thickness_m"]["not_inferred_from"]


def test_efficiency_components_multiply_into_the_adopted_range():
    """Sanity check on the component list: the product must land near 1-4%."""
    lows = 1.0
    highs = 1.0
    for low, high in CSLF_EFFICIENCY_COMPONENTS.values():
        lows *= low
        highs *= high
    assert lows < 0.01, "the low corner should fall below the adopted 1%"
    assert highs > 0.04, "the high corner should exceed the adopted 4%"


# -- Finding 9.2: porosity is total, and the pairing is correct --------------


def test_cslf_efficiency_contains_the_interconnected_porosity_term():
    """Finding 9.2 resolved: E expects TOTAL porosity.

    Because the connected fraction is inside E, supplying effective porosity
    would double-count it. Donda's range is sonic-log derived, i.e. total, so
    the pairing is right.
    """
    assert CSLF_EFFICIENCY_COMPONENTS["interconnected porosity"] == (0.6, 0.95)


def test_porosity_citation_records_the_derivation_method():
    """The sonic-log derivation is what makes the range total porosity."""
    quote = (DONDA_2011.quote or "").lower()
    assert "sonic" in quote
    assert DONDA_2011.locator is not None and "table 2" in DONDA_2011.locator.lower()


# -- citation integrity ------------------------------------------------------


def test_cslf_quote_is_the_verbatim_sentence():
    quote = CSLF_2008.quote
    for fragment in (
        "USDOE Subgroup obtained a range of values",
        "15% and 85% confidence intervals",
        "between 1% and 4% for deep saline aquifers",
    ):
        assert fragment in quote
    assert "..." in quote, "elisions must be marked"


def test_both_citations_carry_a_resolvable_source_url():
    for citation in (CSLF_2008, DONDA_2011):
        assert citation.url and citation.url.startswith("https://")


def test_citation_years_and_authors_are_recorded():
    assert CSLF_2008.year == 2008
    assert DONDA_2011.year == 2011
    assert "Bachu" in CSLF_2008.text
    assert "Donda" in DONDA_2011.text
    assert "10.1016/j.ijggc.2010.08.009" in DONDA_2011.text


def test_evidence_classes_match_what_the_sources_say():
    """CSLF is North American Monte Carlo; Donda is 14 Italian reservoirs."""
    assert CSLF_2008.evidence_class is EvidenceClass.GENERIC
    assert DONDA_2011.evidence_class is EvidenceClass.REGIONAL
    assert assumption_for("storage_efficiency").citation is CSLF_2008
    assert assumption_for("porosity").citation is DONDA_2011


@pytest.mark.parametrize("field", ["source", "title", "text"])
def test_a_citation_cannot_be_constructed_empty(field):
    kwargs = dict(source="s", title="t", year=2008, text="x")
    kwargs[field] = "   "
    with pytest.raises(AssumptionError):
        Citation(**kwargs)


def test_placeholder_scenarios_are_marked_as_such():
    """The guard that stops an uncited value passing for a cited one."""
    from ccs_screen.ingest.scenario import BUILTIN_SCENARIOS

    for name, scenario in BUILTIN_SCENARIOS.items():
        for assumption in scenario.assumptions.assumptions:
            citation = assumption.citation
            if citation is None:
                continue
            if citation.evidence_class is EvidenceClass.PLACEHOLDER:
                assert "PLACEHOLDER" in citation.text


# -- Finding 9.3: scale mismatch --------------------------------------------


def test_scale_mismatch_warning_names_both_parameters_and_applies_no_correction():
    """Finding 9.3: every clause of this warning is confirmed by the sources."""
    from ccs_screen.api import SCALE_MISMATCH_WARNING

    assert set(SCALE_MISMATCH_WARNING["affects"]) == {"porosity", "storage_efficiency"}
    assert SCALE_MISMATCH_WARNING["correction_applied"] is False
    assert SCALE_MISMATCH_WARNING["invalidates_result"] is False
    detail = SCALE_MISMATCH_WARNING["detail"].lower()
    assert "basin" in detail and "closure" in detail


def test_area_policy_refuses_administrative_boundaries():
    """Donda's A is basin area obtained from seismic interpretation.

    Neither that nor a licence polygon may stand in for a closure area.
    """
    assert "not inferred from administrative licence boundaries" in AREA_POLICY_STATEMENT.lower()


# -- Finding 9.8: the provenance inventory -----------------------------------


def test_only_the_two_literature_parameters_carry_a_citation():
    """CHARACTERISATION, Finding 9.8.

    Everything else scientific in src/ is either definitional or uncited. This
    pins the count so that adding provenance elsewhere is a deliberate, visible
    change.
    """
    cited = {
        a.parameter
        for a in LITERATURE_SCREENING_V1.assumptions.assumptions
        if a.citation is not None and a.citation.evidence_class is not EvidenceClass.PLACEHOLDER
    }
    assert cited == {"storage_efficiency", "porosity"}


@pytest.mark.parametrize(
    "module_name,constant",
    [
        ("ccs_screen.pressure", "DEFAULT_FRACTURE_GRADIENT_PA_M"),
        ("ccs_screen.pressure", "DEFAULT_SAFETY_FACTOR"),
        ("ccs_screen.ingest.normalize", "RESERVOIR_DEPTH_FRACTION"),
        ("ccs_screen.ingest.normalize", "DEPTH_CONFLICT_TOLERANCE_M"),
    ],
)
def test_engineering_constants_exist_but_carry_no_citation_object(module_name, constant):
    """CHARACTERISATION, Finding 9.8.

    These are scientific choices with no recorded provenance. The sharpest is
    DEFAULT_SAFETY_FACTOR, which names no regulator while multiplying the
    injection-rate ceiling directly.
    """
    import importlib

    module = importlib.import_module(module_name)
    assert isinstance(getattr(module, constant), float)
    assert not hasattr(module, f"{constant}_CITATION")


def test_co2_critical_constants_have_no_citation_object():
    """CHARACTERISATION, Finding 9.8. Phase 1 verified them numerically only."""
    import ccs_screen.properties as properties

    for name in ("CO2_TC_K", "CO2_PC_PA", "CO2_OMEGA", "CO2_MW_KG_MOL", "CO2_Z_RA"):
        assert isinstance(getattr(properties, name), float)
    assert not any("citation" in n.lower() for n in dir(properties))


# -- Finding 9.9: the source's own ambiguity ---------------------------------


def test_efficiency_is_documented_as_a_fraction_of_pore_volume():
    """Finding 9.9: CSLF equation (15) says pore volume, its prose says bulk.

    The implementation follows the equation and Donda, which is the defensible
    reading.
    """
    from pathlib import Path

    review = Path("docs/scenario-literature-review.md").read_text(encoding="utf-8").lower()
    assert "fraction of pore volume" in review
