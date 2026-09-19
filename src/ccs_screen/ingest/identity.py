"""Canonical well identity.

Well names are spelled differently in every source. During reconnaissance,
naive string matching linked 3 of 46 Piemonte wells to the national registry;
canonical matching linked 40. Identity is therefore the highest-value piece of
this package, and it is kept deliberately small and testable.

Canonical form is ``BASE|NUMBER|SUFFIX``::

    SALUZZO 1              -> SALUZZO|1|
    SALUZZO 001            -> SALUZZO|1|
    TRECATE 5D             -> TRECATE|5|D
    NOVI LIGURE 2 BIS DIR  -> NOVI LIGURE|2|BIS DIR
    S.BENIGNO CANAVESE 1   -> S BENIGNO CANAVESE|1|
    SAN BENIGNO CANAVESE 1 -> S BENIGNO CANAVESE|1|

The original spelling is always kept alongside the canonical key; nothing in
this module discards it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Saint-prefix variants are collapsed to a single ``S`` token rather than
#: expanded to SAN/SANT'/SANTA. Expanding requires knowing the following word's
#: gender and initial letter, which we cannot do reliably; collapsing is
#: symmetric and therefore safe in both directions.
#: Alternatives are ordered longest-first. Python regex alternation is
#: leftmost-wins, so listing AN before ANTO clips SANTO to SAN and leaves a
#: stray "TO" behind.
_SAINT = re.compile(r"\bS(?:ANTO|ANTA|ANT|AN|\.|')\s*", re.IGNORECASE)

#: Trailing well qualifiers that follow the number (directional, sidetrack...).
_NUMBER_RE = re.compile(r"^(?P<base>.*?)[\s\-_]+0*(?P<num>\d+)(?P<tail>.*)$")


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize_name(name: str) -> str:
    """Upper-case, de-accent and squeeze a raw well name."""
    text = _strip_accents(str(name)).upper()
    text = text.replace("_", " ").replace("-", " ")
    text = _SAINT.sub("S ", text)
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class WellIdentity:
    """A canonical key plus every original spelling that mapped onto it."""

    base: str
    number: int | None
    suffix: str
    original: str

    @property
    def canonical(self) -> str:
        """``BASE|NUMBER``, with ``|SUFFIX`` appended only when one exists."""
        num = "" if self.number is None else str(self.number)
        base = f"{self.base}|{num}"
        return f"{base}|{self.suffix}" if self.suffix else base

    def __str__(self) -> str:
        return self.canonical


def canonical_well_id(name: str) -> WellIdentity:
    """Parse a raw well name into a canonical identity.

    Zero-padding is removed from the number so ``SALUZZO 1`` and
    ``SALUZZO 001`` agree. A name with no number keeps ``number=None`` rather
    than being forced to 1.
    """
    original = str(name).strip()
    text = normalize_name(original)
    if not text:
        raise ValueError("well name is empty")

    match = _NUMBER_RE.match(text)
    if not match:
        return WellIdentity(base=text, number=None, suffix="", original=original)

    base = match.group("base").strip()
    number = int(match.group("num"))
    tail = match.group("tail").strip()

    # "5D" -> number 5, suffix D; "2 BIS DIR" -> number 2, suffix "BIS DIR".
    suffix = " ".join(tail.split())
    if not base:
        # A name that is only a number is not a usable identity.
        return WellIdentity(base=text, number=None, suffix="", original=original)
    return WellIdentity(base=base, number=number, suffix=suffix, original=original)


def same_well(a: str, b: str) -> bool:
    """True when two spellings denote the same well under canonical matching."""
    try:
        return canonical_well_id(a).canonical == canonical_well_id(b).canonical
    except ValueError:
        return False
