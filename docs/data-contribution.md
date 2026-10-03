# Contributing well data

Most real wells are `UNAVAILABLE` today. Not because the software fails, but
because the sources available so far do not establish what the approved model
needs: a **depth datum** for every depth, **eligible corrected temperatures**
with their measurement depths, and evidence for a **storage-assessment
interval**. Better-documented data is the most valuable contribution this
project can receive.

This guide says what a useful submission contains. Read it before opening a
*Data submission* issue.

## What happens to a submission

1. You open a *Data submission* issue describing the data, its source and its
   redistribution terms. **Do not attach data you are not allowed to share.**
2. A maintainer reviews provenance, rights, units, datums and completeness, and
   may ask questions.
3. Accepted data is mapped into the ingestion layer by a maintainer, keeping
   every value's source reference.
4. The model is applied unchanged. **A well with accepted data can still be
   scientifically `UNAVAILABLE`** -- for example if its datum is not ground
   level, if no temperature uses an eligible method, or if no interval is
   evidenced. That is an honest result, not a rejection of the data.

Submissions never change the Model Contract. A proposal to change how data is
interpreted (for example a datum-conversion rule) is a *Scientific / model
proposal*, reviewed separately.

## Rights and attribution (required)

- **Source**: who published the data, the document or dataset title, edition
  or date, and where it can be obtained (URL, archive reference, page).
- **Redistribution rights**: the license or written permission under which the
  data may be redistributed *in a public repository*. If you do not know, say
  so; the data will not be added until this is settled. Data you may only use
  privately can still inform a discussion, but it cannot be committed.
- **Your relationship to the data** (author, operator, public archive user).

## Well identity

- The well name **exactly as written in the source**, plus any alternate
  spellings or codes you know (registry codes, sidetrack suffixes such as
  `ST`, `BIS`, `DIR`).
- Country, region and, if published, coordinates **with their datum** (for
  example WGS84) and whether they are approximate.
- Sidetracks and re-entries are separate wells; say which one a value belongs to.

## Units

Give every number with its unit as printed (m, ft, °C, °F, bar, psi, ...). Do
not convert. If the source mixes decimal commas and points, or carries markers
such as `~` or `v.`, copy them verbatim; the ingestion layer records the
original text beside the parsed value.

## Depths: datum, MD and TVD

For **every** depth (total depth, interval tops and bases, temperature depths):

- **Depth datum**: the surface the depth is measured from -- ground level,
  rotary table (RT), kelly bushing (KB), mean sea level -- exactly as the
  source states it, with the page or line where it is stated. If the source does
  not state it, write `unknown`. Never assume ground level.
- **Datum elevations**: ground elevation and RT/KB elevation above sea level,
  when printed, with their source.
- **MD or TVD**: whether the depth is measured depth along the hole or true
  vertical depth, and for deviated wells a deviation survey or printed TVD.
  If the source does not say, write `unknown`.

Today the approved model uses only depths with an **established ground-level
reference**. Depths referenced to RT or KB are reported as
`UNSUPPORTED_DEPTH_DATUM`, and no conversion is applied, even when elevations
are known. Submit such depths *as stated*, with their elevations. Whether a
documented conversion should be accepted is an open model decision; converting
values yourself would hide exactly the information that decision needs.

## Temperatures

For each temperature reading:

- value and unit;
- **measurement depth**, with its datum and MD/TVD as above;
- **method** as the source describes it: e.g. bottom-hole temperature after a
  stated circulation time, Horner-corrected, Fertl-Wichmann, Squarci-Taffi,
  non-stabilized log reading, drill-stem test, surface air mean;
- circulation time and time since circulation stopped, when printed;
- the source location (document, page, table).

The approved model only accepts corrected observations (Horner-corrected,
Fertl-Wichmann, Squarci-Taffi) inside the storage interval. Uncorrected
readings are still useful to submit; they are kept and shown, but they do not
become the model temperature.

## Storage-assessment interval

The approved model needs, per well, an interval `z_top`-`z_base` designated as
the storage-assessment interval. It is never inferred from total depth,
stratigraphic units or gross formation thickness. If you have evidence for one,
give:

- the top and base depths with datum and MD/TVD;
- the evidence: reservoir unit identification, log interpretation, test
  intervals, published reservoir description -- with the source;
- who designated it and on what basis.

An interval without documented evidence cannot be used.

## Missing values

Leave unknown values **empty and say they are unknown**. Do not fill gaps with
typical values, regional gradients, neighbouring wells or estimates. A missing
value produces an honest `UNAVAILABLE`; an invented one produces a number that
looks real and is not.

## A minimal submission table

One row per observation is easiest to review. Suggested columns:

| Column | Example (fictional) |
| --- | --- |
| `well_name_as_printed` | `SYNTH EXAMPLE 1` |
| `quantity` | `temperature` / `total_depth` / `interval_top` / `interval_base` / `ground_elevation` |
| `value_as_printed` | `58` |
| `unit_as_printed` | `degC` |
| `depth_value_as_printed` | `1500` |
| `depth_unit` | `m` |
| `depth_datum_as_stated` | `ground level` / `rotary table` / `unknown` |
| `md_or_tvd` | `MD` / `TVD` / `unknown` |
| `method_as_printed` | `Squarci-Taffi extrapolation` |
| `source` | document title, page, table |
| `redistribution` | license or permission reference |
| `notes` | anything that qualifies the value |

The example row is fictional and only shows the format.
