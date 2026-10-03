"""Shared test helpers."""

from __future__ import annotations

import os

import pytest

#: Set in the CI reference-checks job: an optional reference dependency that
#: is missing is then a failure, not a skip, so the checks behind the public
#: validation claims cannot pass by not running.
REQUIRE_REFERENCES = os.environ.get("CCS_REQUIRE_REFERENCE_TESTS") == "1"


def coolprop_propssi():
    """CoolProp's PropsSI (Span & Wagner 1996 for CO2 via HEOS), or skip.

    Under CCS_REQUIRE_REFERENCE_TESTS=1 a missing CoolProp fails the test.
    """
    if REQUIRE_REFERENCES:
        from CoolProp.CoolProp import PropsSI  # ImportError fails the test

        return PropsSI
    return pytest.importorskip("CoolProp.CoolProp").PropsSI
