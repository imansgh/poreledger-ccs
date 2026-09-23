import { Tag } from "./Tag";
import { EVIDENCE_LABEL, displayValue, kelvinToCelsius, num } from "@/lib/format";
import type { Citation, ScreeningInput } from "@/lib/types";

const CARD_CLASS: Record<string, string> = {
  source: "card card-source",
  MODELLED: "card card-modelled",
  ASSUMED: "card card-assumed",
  USER: "card card-user",
};

/** Field name -> reader-facing name. Scientific wording is never softened. */
const DISPLAY_NAME: Record<string, string> = {
  area_m2: "Storage area",
  thickness_m: "Net reservoir thickness",
  porosity: "Porosity",
  pressure_pa: "Pressure",
  temperature_k: "Temperature",
  storage_efficiency: "Storage efficiency",
};

function citationOf(citation: Citation | string | null): Citation | null {
  if (!citation || typeof citation === "string") return null;
  return citation;
}

/**
 * One screening input with its full lineage.
 *
 * Every card shows value, unit and provenance label. Rationale, citation and
 * derivation appear when the API supplies them; nothing is invented to fill a
 * gap, and nothing available is hidden.
 */
export function InputCard({ name, input }: { name: string; input: ScreeningInput }) {
  const shown = displayValue(input.value, input.unit);
  const citation = citationOf(input.citation);
  const title = DISPLAY_NAME[name] ?? name;

  // Temperature is stored in kelvin; engineers read celsius.
  const celsius =
    input.unit === "K" && typeof input.value === "number"
      ? `${num(kelvinToCelsius(input.value), 1)} degC`
      : null;

  return (
    <article className={CARD_CLASS[input.label] ?? "card"} aria-labelledby={`card-${name}`}>
      <div className="card-name" id={`card-${name}`}>
        {title}
        <span className="sr-only"> ({name})</span>
      </div>
      <div className="card-value">
        {shown.text}
        <span className="unit">{shown.unit}</span>
      </div>
      {celsius ? <div className="card-name">{celsius}</div> : null}

      <Tag label={input.label} />

      <dl>
        <dt>Evidence</dt>
        <dd>{EVIDENCE_LABEL[input.evidence_class] ?? input.evidence_class}</dd>
        {input.method ? (
          <>
            <dt>Method</dt>
            <dd>{input.method}</dd>
          </>
        ) : null}
        {input.assumption_ignored_source_won ? (
          <>
            <dt>Note</dt>
            <dd>Scenario value ignored; source data won</dd>
          </>
        ) : null}
      </dl>

      {input.derivation ? <p className="note">{input.derivation}</p> : null}
      {input.rationale ? <p className="note">{input.rationale}</p> : null}

      {citation ? (
        <cite>
          {citation.source} ({citation.year})
          {citation.url ? (
            <>
              {" "}
              <a href={citation.url} target="_blank" rel="noreferrer">
                link
              </a>
            </>
          ) : null}
        </cite>
      ) : null}
    </article>
  );
}
