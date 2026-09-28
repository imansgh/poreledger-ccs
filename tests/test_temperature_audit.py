"""Phase 6 audit regression tests for temperature method selection.

No correction equation exists in this repository -- the corrections were applied
by the data publisher and this project only records which one produced each
value. So these tests pin the *selection rule* and its rank ordering, plus the
two places where that rule leaks: the 0.85 depth filter lets a geothermal
gradient masquerade as method disagreement, and an unstabilised reading is used
uncorrected.

Several tests are marked CHARACTERISATION: they assert today's behaviour and
name the finding, because Phase 6 found questionable choices it was not
authorised to change.

Phase 14. The rank table, the 0.85 filter and the ingestion-time selection
pinned below now belong to the NOT_VALIDATED legacy paths only (owner decision
O2); they are kept and unchanged. The approved model replaces them with the
M3 + R1 + C3 rule (no ranking, no 0.85 filter, in-interval nearest observation,
uncorrected BHT excluded, below-TD observations excluded), tested in
``tests/test_approved_model.py`` and, as counterparts of the Phase 6 findings,
in the last section of this module.

See ``docs/scientific-validation-audit.md``, Phase 6.
"""

from __future__ import annotations

import pytest

from ccs_screen.ingest.normalize import RESERVOIR_DEPTH_FRACTION
from ccs_screen.ingest.provenance import (
    TEMPERATURE_METHOD_CONFIDENCE,
    TEMPERATURE_METHOD_RANK,
    Confidence,
    TemperatureMethod,
)
from ccs_screen.ingest.sources import _METHOD_MAP, classify_temperature_method
from ccs_screen.properties import co2_density_kg_m3

#: The documented TRECATE|9|ST observations, from docs/ingestion.md.
TRECATE = [
    (TemperatureMethod.FERTL_WICHMANN, 452.15, 6247.9),
    (TemperatureMethod.SQUARCI_TAFFI, 440.15, 6000.0),
    (TemperatureMethod.NON_STABILIZED, 399.15, 5510.0),
]

#: Generic continental gradient, used only to split depth from method effects.
GRADIENT_K_PER_KM = 30.0

#: Hydrostatic pressure at TRECATE TD, for density sensitivity.
TRECATE_PRESSURE_PA = 6247.9 * 1050.0 * 9.80665


def select(observations, fraction=RESERVOIR_DEPTH_FRACTION):
    """Reimplementation of _derive_temperature's choice, for testing the rule."""
    reservoir = [o for o in observations if TEMPERATURE_METHOD_RANK[o[0]] < 99]
    if not reservoir:
        return None
    deepest = max(depth for _, _, depth in reservoir)
    near_td = [o for o in reservoir if o[2] >= fraction * deepest]
    return min(near_td, key=lambda o: (TEMPERATURE_METHOD_RANK[o[0]], -o[2]))


# -- no correction is implemented --------------------------------------------


def test_no_correction_arithmetic_exists_for_any_named_method():
    """Finding 6.1: this project selects, it does not correct.

    If a correction is ever implemented it must be audited as an equation, so
    this guard fails first.
    """
    import ccs_screen.ingest.normalize as normalize_module
    import ccs_screen.ingest.sources as sources_module

    for module in (normalize_module, sources_module):
        names = [n.lower() for n in dir(module)]
        for banned in ("horner", "squarci", "fertl", "wichmann", "taffi"):
            assert not any(banned in n for n in names), (
                f"{banned} arithmetic appeared in {module.__name__}; audit it as an equation"
            )


# -- rank ordering -----------------------------------------------------------


def test_rank_ordering_is_the_audited_one():
    expected = [
        (TemperatureMethod.HORNER, 0),
        (TemperatureMethod.FERTL_WICHMANN, 1),
        (TemperatureMethod.SQUARCI_TAFFI, 2),
        (TemperatureMethod.NON_STABILIZED, 3),
        (TemperatureMethod.RAW, 4),
        (TemperatureMethod.UNKNOWN, 5),
        (TemperatureMethod.SURFACE_AIR, 99),
    ]
    assert sorted(TEMPERATURE_METHOD_RANK.items(), key=lambda kv: kv[1]) == expected


def test_horner_outranks_every_other_method():
    horner = TEMPERATURE_METHOD_RANK[TemperatureMethod.HORNER]
    others = [r for m, r in TEMPERATURE_METHOD_RANK.items() if m is not TemperatureMethod.HORNER]
    assert all(horner < r for r in others)


def test_generic_method_outranks_the_regional_one():
    """CHARACTERISATION, Finding 6.3.

    Fertl-Wichmann (generic, Gulf Coast) is preferred over Squarci-Taffi
    (Italian, the GEOTHOPICA lineage) for Italian wells, with no stated reason.
    This inverts the regional-over-generic preference the project applies in
    EvidenceClass and in its porosity citation.

    If the ordering is ever reversed, this test must be replaced and Finding 6.3
    marked resolved -- it changes the selected temperature for every well where
    both methods appear.
    """
    assert (
        TEMPERATURE_METHOD_RANK[TemperatureMethod.FERTL_WICHMANN]
        < TEMPERATURE_METHOD_RANK[TemperatureMethod.SQUARCI_TAFFI]
    )
    # Both carry the same confidence, so rank alone decides.
    assert (
        TEMPERATURE_METHOD_CONFIDENCE[TemperatureMethod.FERTL_WICHMANN]
        == TEMPERATURE_METHOD_CONFIDENCE[TemperatureMethod.SQUARCI_TAFFI]
        == Confidence.MEDIUM
    )


def test_surface_air_is_never_selectable_and_carries_no_confidence():
    assert TEMPERATURE_METHOD_RANK[TemperatureMethod.SURFACE_AIR] == 99
    assert TEMPERATURE_METHOD_CONFIDENCE[TemperatureMethod.SURFACE_AIR] is Confidence.NONE


def test_confidence_never_improves_as_rank_worsens():
    order = [Confidence.NONE, Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]
    ranked = sorted(TEMPERATURE_METHOD_RANK.items(), key=lambda kv: kv[1])
    confidences = [order.index(TEMPERATURE_METHOD_CONFIDENCE[m]) for m, _ in ranked]
    assert confidences == sorted(confidences, reverse=True)


# -- selection rule ----------------------------------------------------------


def test_surface_air_only_well_selects_nothing():
    assert select([(TemperatureMethod.SURFACE_AIR, 285.0, 0.0)]) is None


def test_surface_air_is_dropped_before_the_depth_filter():
    """A surface reading must not become 'deepest' and shift the 0.85 window."""
    chosen = select(
        [
            (TemperatureMethod.SURFACE_AIR, 285.0, 0.0),
            (TemperatureMethod.NON_STABILIZED, 380.0, 2000.0),
        ]
    )
    assert chosen[0] is TemperatureMethod.NON_STABILIZED


def test_better_method_beats_greater_depth_inside_the_window():
    """Method quality dominates; depth is only the tie-break."""
    chosen = select(
        [
            (TemperatureMethod.FERTL_WICHMANN, 440.0, 1700.0),
            (TemperatureMethod.NON_STABILIZED, 450.0, 2000.0),
        ]
    )
    assert chosen[0] is TemperatureMethod.FERTL_WICHMANN


def test_depth_breaks_ties_within_one_method():
    chosen = select(
        [
            (TemperatureMethod.SQUARCI_TAFFI, 430.0, 1800.0),
            (TemperatureMethod.SQUARCI_TAFFI, 445.0, 2000.0),
        ]
    )
    assert chosen[2] == 2000.0


def test_shallow_modelled_grid_points_cannot_win():
    """The filter's stated purpose: exclude the 300/500/1000 m modelled points."""
    chosen = select(
        [
            (TemperatureMethod.FERTL_WICHMANN, 300.0, 300.0),
            (TemperatureMethod.FERTL_WICHMANN, 310.0, 500.0),
            (TemperatureMethod.FERTL_WICHMANN, 330.0, 1000.0),
            (TemperatureMethod.NON_STABILIZED, 420.0, 3000.0),
        ]
    )
    assert chosen[2] == 3000.0, "a shallow better-ranked point outranked a deep reading"


# -- Finding 6.4: the depth filter -------------------------------------------

@pytest.mark.parametrize(
    "total_depth_m,expected_window_m", [(1000, 150), (2000, 300), (4000, 600)]
)
def test_depth_window_grows_with_depth(total_depth_m, expected_window_m):
    assert total_depth_m * (1 - RESERVOIR_DEPTH_FRACTION) == pytest.approx(
        expected_window_m, abs=0.5
    )


def test_all_three_trecate_observations_pass_the_filter():
    deepest = max(d for _, _, d in TRECATE)
    assert all(d >= RESERVOIR_DEPTH_FRACTION * deepest for _, _, d in TRECATE)
    assert select(TRECATE)[0] is TemperatureMethod.FERTL_WICHMANN


def test_most_of_the_trecate_method_spread_is_actually_depth():
    """CHARACTERISATION, Finding 6.4.

    docs/ingestion.md reports 'P50 spread 30.5% from temperature method alone'.
    At 30 K/km, 62% of the Squarci-Taffi spread and 42% of the non-stabilised
    spread is the geothermal gradient between 5510 m and 6248 m, not method.
    """
    selected_t, selected_depth = 452.15, 6247.9
    shares = {}
    for method, temperature_k, depth_m in TRECATE[1:]:
        total = selected_t - temperature_k
        depth_component = (selected_depth - depth_m) / 1000 * GRADIENT_K_PER_KM
        shares[method] = depth_component / total
    assert shares[TemperatureMethod.SQUARCI_TAFFI] == pytest.approx(0.620, abs=0.01)
    assert shares[TemperatureMethod.NON_STABILIZED] == pytest.approx(0.418, abs=0.01)


# -- Finding 6.6: capacity sensitivity ---------------------------------------


@pytest.mark.parametrize(
    "temperature_error_k,expected_bias", [(1, 0.0031), (10, 0.0317), (20, 0.0650)]
)
def test_a_low_bht_overstates_capacity(temperature_error_k, expected_bias):
    """Mud cooling makes an uncorrected BHT read low; low T means denser CO2.

    Capacity is linear in density, so the bias passes straight through.
    """
    base = co2_density_kg_m3(TRECATE_PRESSURE_PA, 452.15)
    biased = co2_density_kg_m3(TRECATE_PRESSURE_PA, 452.15 - temperature_error_k)
    assert biased > base, "lower temperature must give higher density here"
    assert (biased - base) / base == pytest.approx(expected_bias, abs=0.002)


def test_method_choice_alone_moves_capacity_by_up_to_nineteen_percent():
    """Finding 6.6: what the rank ordering is worth, in capacity terms."""
    densities = {
        method: co2_density_kg_m3(TRECATE_PRESSURE_PA, temperature_k)
        for method, temperature_k, _ in TRECATE
    }
    selected = densities[TemperatureMethod.FERTL_WICHMANN]
    squarci = (densities[TemperatureMethod.SQUARCI_TAFFI] - selected) / selected
    unstabilised = (densities[TemperatureMethod.NON_STABILIZED] - selected) / selected
    assert squarci == pytest.approx(0.0382, abs=0.002)
    assert unstabilised == pytest.approx(0.1860, abs=0.002)


# -- Finding 6.2 and 6.7: the classifier -------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("estrap.metodo squarci-taffi", TemperatureMethod.SQUARCI_TAFFI),
        ("Estrap.metodo Squarci-Taffi", TemperatureMethod.SQUARCI_TAFFI),
        ("ESTRAP.METODO FERTL-WICHMANN", TemperatureMethod.FERTL_WICHMANN),
        ("  estrap.metodo   fertl-wichmann  ", TemperatureMethod.FERTL_WICHMANN),
        ("non stabilizzata", TemperatureMethod.NON_STABILIZED),
        ("Non Stabilizzata", TemperatureMethod.NON_STABILIZED),
        ("temp.atmosferica media annuale", TemperatureMethod.SURFACE_AIR),
    ],
)
def test_classifier_recognises_the_source_strings(raw, expected):
    assert classify_temperature_method(raw) is expected


@pytest.mark.parametrize(
    "raw",
    ["estrap.metodo", "estrap.metodo sconosciuto", "estrap.metodo squ",
     "stabilizzata", "", None, "   ", 0],
)
def test_classifier_never_guesses(raw):
    """An unrecognised string becomes UNKNOWN rather than a plausible method."""
    assert classify_temperature_method(raw) is TemperatureMethod.UNKNOWN


def test_horner_and_raw_are_unreachable_from_the_data():
    """CHARACTERISATION, Finding 6.2: the top of the ranking is aspirational."""
    reachable = set(_METHOD_MAP.values()) | {TemperatureMethod.UNKNOWN}
    assert TemperatureMethod.HORNER not in reachable
    assert TemperatureMethod.RAW not in reachable
    assert len(reachable) == 5


def test_a_horner_labelled_string_would_rank_below_an_unstabilised_reading():
    """CHARACTERISATION, Finding 6.7. Not reachable with present sources."""
    classified = classify_temperature_method("Horner corrected")
    assert classified is TemperatureMethod.UNKNOWN
    assert (
        TEMPERATURE_METHOD_RANK[classified]
        > TEMPERATURE_METHOD_RANK[TemperatureMethod.NON_STABILIZED]
    )


# -- Phase 14: the approved rule (M3, R1) against the Phase 6 findings --------


def _approved_select(observations, z_top, z_base, depth_m=7000.0):
    from ccs_screen.approved_model import StorageInterval, select_temperature
    from ccs_screen.ingest.identity import canonical_well_id
    from ccs_screen.ingest.provenance import FieldValue, Provenance, Unit
    from ccs_screen.ingest.records import NormalizedWellRecord, TemperatureObservation
    from ccs_screen.ingest.units import DepthDatum

    record = NormalizedWellRecord(identity=canonical_well_id("PHASE6 PROBE 1"))
    record.depth_m = FieldValue(value=depth_m, unit=Unit.METRE, provenance=Provenance.EXTRACTED,
                                confidence=Confidence.HIGH)
    record.depth_datum = DepthDatum.GROUND_LEVEL
    record.temperatures = tuple(
        TemperatureObservation(depth_m=d, temperature_k=k, method=m.value,
                               depth_datum=DepthDatum.GROUND_LEVEL)
        for m, k, d in observations)
    return select_temperature(record, StorageInterval(z_top, z_base))


def test_approved_rule_does_not_rank_fertl_wichmann_over_squarci_taffi():
    """Finding 6.3 / S2: at one depth ST is a convention (R1-3); otherwise the nearest wins."""
    same_depth = _approved_select([(TemperatureMethod.FERTL_WICHMANN, 431.15, 5510.0),
                                   (TemperatureMethod.SQUARCI_TAFFI, 420.15, 5510.0)],
                                  5400.0, 5600.0)
    assert same_depth.selected.method == TemperatureMethod.SQUARCI_TAFFI.value
    nearest = _approved_select([(TemperatureMethod.FERTL_WICHMANN, 431.15, 5510.0),
                                (TemperatureMethod.SQUARCI_TAFFI, 418.15, 5000.0)],
                               5000.0, 5600.0)
    assert nearest.selected.method == TemperatureMethod.FERTL_WICHMANN.value


def test_approved_rule_has_no_depth_fraction_filter():
    """Finding 6.4 / S3: a shallow in-interval observation qualifies; no 0.85 window."""
    selection = _approved_select([(TemperatureMethod.SQUARCI_TAFFI, 312.15, 1000.0)], 900.0, 1100.0)
    assert selection.temperature_k == 312.15


def test_approved_rule_never_uses_an_unstabilised_reading():
    """Finding 6.6 / S5: uncorrected BHT is never substituted."""
    selection = _approved_select([(TemperatureMethod.NON_STABILIZED, 399.15, 5510.0)],
                                 5400.0, 5600.0)
    assert not selection.available


def test_approved_rule_excludes_trecate_observations_below_total_depth():
    """Finding 10.1 / S11: the 6247.9 m FW reading is excluded (recorded TD 6087 m)."""
    selection = _approved_select(TRECATE, 5900.0, 6300.0, depth_m=6087.0)
    assert selection.temperature_k == 440.15
    assert selection.selected.depth_m == 6000.0
