"""Canonical well identity.

Naive matching linked 3 of 46 pilot wells to the national registry; canonical
matching linked 40. The cases below are the real spellings that caused that gap.
"""

from __future__ import annotations

import pytest

from ccs_screen.ingest.identity import canonical_well_id, normalize_name, same_well


@pytest.mark.parametrize(
    "name,canonical",
    [
        ("SALUZZO 1", "SALUZZO|1"),
        ("SALUZZO 001", "SALUZZO|1"),
        ("saluzzo_001", "SALUZZO|1"),
        ("TRECATE 5D", "TRECATE|5|D"),
        ("TRECATE 9ST", "TRECATE|9|ST"),
        ("NOVI LIGURE 2 BIS DIR", "NOVI LIGURE|2|BIS DIR"),
        ("MALOSSA 15", "MALOSSA|15"),
        ("VILLA FORTUNA 3", "VILLA FORTUNA|3"),
        ("CASALE COCCHI 001 DIR", "CASALE COCCHI|1|DIR"),
    ],
)
def test_canonical_forms(name, canonical):
    assert canonical_well_id(name).canonical == canonical


@pytest.mark.parametrize(
    "a,b",
    [
        ("SALUZZO 1", "SALUZZO 001"),
        ("saluzzo_001", "SALUZZO 1"),
        ("S.BENIGNO CANAVESE 1", "SAN BENIGNO CANAVESE 1"),
        ("S.GERMANO VERCELLESE 1", "SAN GERMANO VERCELLESE 1"),
        ("S. BENIGNO 1", "SANTO BENIGNO 1"),
        ("NOVI LIGURE 002", "NOVI LIGURE 2"),
    ],
)
def test_spelling_variants_match(a, b):
    assert same_well(a, b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("ASTI 1", "ASTI 2"),
        ("TRECATE 5D", "TRECATE 5"),          # a sidetrack is not the parent well
        ("BALZOLA 1", "BALZOLA 3"),
        ("NOVI LIGURE 2", "NOVI LIGURE 2 BIS DIR"),
        ("DESANA 1", "MORETTA 1"),
    ],
)
def test_genuinely_different_wells_do_not_match(a, b):
    assert not same_well(a, b)


def test_original_spelling_is_preserved():
    identity = canonical_well_id("  saluzzo_001  ")
    assert identity.original == "saluzzo_001"
    assert identity.canonical == "SALUZZO|1"


def test_components_are_exposed():
    identity = canonical_well_id("NOVI LIGURE 2 BIS DIR")
    assert identity.base == "NOVI LIGURE"
    assert identity.number == 2
    assert identity.suffix == "BIS DIR"


def test_accents_are_folded():
    assert normalize_name("CAVAGLIÈTTO 1") == "CAVAGLIETTO 1"


def test_name_without_a_number_keeps_number_none():
    """A nameless-number well is not silently promoted to well 1."""
    identity = canonical_well_id("TRECATE A")
    assert identity.number is None
    assert identity.canonical == "TRECATE A|"


def test_empty_name_is_rejected():
    with pytest.raises(ValueError):
        canonical_well_id("   ")


def test_same_well_is_false_for_unparseable_input():
    assert not same_well("", "SALUZZO 1")
