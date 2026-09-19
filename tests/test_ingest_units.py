"""Number parsing, unit conversion and depth-datum handling.

These are the silent-error surfaces identified in reconnaissance: Italian
decimal commas beside decimal points, feet beside metres, and depths measured
from the rotary table rather than sea level.
"""

from __future__ import annotations

import pytest

from ccs_screen.ingest.provenance import Unit
from ccs_screen.ingest.units import (
    AmbiguousValueError,
    DepthDatum,
    DepthMeasurement,
    UnitError,
    parse_number,
    to_kelvin,
    to_metres,
)


# -- decimal separators ----------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("313.20", 313.20),     # decimal point (SALUZZO 1 rotary table)
        ("120,00", 120.00),     # decimal comma (MALOSSA 15 rotary table)
        ("238.7", 238.7),
        ("2.299,4", 2299.4),    # Italian: dot thousands, comma decimal
        ("1,234.5", 1234.5),    # Anglo: comma thousands, dot decimal
        ("1.384.543", 1384543.0),   # repeated dots -> thousands
        ("4.947.203", 4947203.0),
        ("5497", 5497.0),
        ("-12,5", -12.5),
        ("0,18", 0.18),
    ],
)
def test_decimal_separators_are_resolved_deterministically(text, expected):
    assert parse_number(text).value == pytest.approx(expected)


@pytest.mark.parametrize("text", ["1.384", "5,500", "12.000", "3,141"])
def test_three_trailing_digits_is_refused_as_ambiguous(text):
    """`1.384` is either 1384 or 1.384 and the source does not say which."""
    with pytest.raises(AmbiguousValueError) as excinfo:
        parse_number(text, field_name="depth_m")
    assert "ambiguous" in str(excinfo.value)
    assert "depth_m" in str(excinfo.value)


def test_approximation_markers_are_flagged_not_discarded():
    parsed = parse_number("5497~")
    assert parsed.value == pytest.approx(5497.0)
    assert parsed.approximate is True
    assert parsed.original == "5497~"


def test_numeric_input_passes_through():
    assert parse_number(1527.5).value == pytest.approx(1527.5)
    assert parse_number(42).value == pytest.approx(42.0)


@pytest.mark.parametrize("text", ["", "   ", "abc", "5500 v.5497~", "n/d", "-"])
def test_non_numeric_text_is_rejected(text):
    with pytest.raises(ValueError):
        parse_number(text)


def test_booleans_are_not_silently_numeric():
    with pytest.raises(ValueError):
        parse_number(True)


# -- units -----------------------------------------------------------------


def test_feet_convert_only_when_explicitly_labelled():
    assert to_metres(1000.0, Unit.FOOT) == pytest.approx(304.8)
    assert to_metres(1000.0, Unit.METRE) == pytest.approx(1000.0)


def test_unlabelled_unit_cannot_be_converted():
    """Magnitude alone never implies a unit: 3000 could be m or ft."""
    with pytest.raises(UnitError):
        to_metres(3000.0, Unit.DIMENSIONLESS)


def test_celsius_to_kelvin():
    assert to_kelvin(0.0, Unit.CELSIUS) == pytest.approx(273.15)
    assert to_kelvin(45.0, Unit.CELSIUS) == pytest.approx(318.15)
    assert to_kelvin(318.15, Unit.KELVIN) == pytest.approx(318.15)


def test_pressure_unit_is_not_a_length():
    with pytest.raises(UnitError):
        to_metres(100.0, Unit.PASCAL)


# -- depth datum -----------------------------------------------------------


def test_rotary_table_depth_corrects_to_msl():
    """MALOSSA 15: 5500 m from a rotary table standing 120.00 m above MSL."""
    d = DepthMeasurement(5500.0, DepthDatum.ROTARY_TABLE, datum_elevation_m=120.0)
    assert d.can_convert_to_msl
    assert d.to_msl().value_m == pytest.approx(5380.0)
    assert d.to_msl().datum is DepthDatum.MEAN_SEA_LEVEL


def test_cavaglietto_rotary_correction_is_material():
    """238.7 m of correction on a 900 m well is 27% of total depth."""
    d = DepthMeasurement(900.0, DepthDatum.ROTARY_TABLE, datum_elevation_m=238.7)
    assert d.to_msl().value_m == pytest.approx(661.3)


def test_unknown_datum_refuses_correction():
    d = DepthMeasurement(900.0, DepthDatum.UNKNOWN)
    assert not d.can_convert_to_msl
    with pytest.raises(UnitError) as excinfo:
        d.to_msl()
    assert "unknown" in str(excinfo.value)


def test_known_datum_without_elevation_refuses_correction():
    d = DepthMeasurement(900.0, DepthDatum.ROTARY_TABLE, datum_elevation_m=None)
    assert not d.can_convert_to_msl
    with pytest.raises(UnitError):
        d.to_msl()


def test_msl_depth_is_already_corrected():
    d = DepthMeasurement(1000.0, DepthDatum.MEAN_SEA_LEVEL)
    assert d.to_msl() is d


def test_describe_states_the_datum():
    assert "rotary_table" in DepthMeasurement(900.0, DepthDatum.ROTARY_TABLE, 238.7).describe()
    assert "MSL" in DepthMeasurement(661.3, DepthDatum.MEAN_SEA_LEVEL).describe()
