import { InputCard } from "./InputCard";
import { Tag } from "./Tag";
import { BUCKET_DESCRIPTIONS, BUCKET_TITLES, num } from "@/lib/format";
import type { ApprovedScreenResult, InputLabel, LegacyScreenResult } from "@/lib/types";

/**
 * The four provenance buckets, rendered exactly as the API partitions them.
 *
 * They are never merged into a generic "inputs" section: the whole point of
 * this product is that a reader can see, without effort, how much of the
 * number came from measurement and how much from an assumption they supplied.
 * The four-bucket partition belongs to the NOT_VALIDATED legacy paths.
 */
const BUCKETS: { key: keyof LegacyScreenResult; label: InputLabel }[] = [
  { key: "source_derived_inputs", label: "source" },
  { key: "modelled_inputs", label: "MODELLED" },
  { key: "assumed_inputs", label: "ASSUMED" },
  { key: "user_supplied_inputs", label: "USER" },
];

export function ProvenancePanel({ result }: { result: LegacyScreenResult }) {
  return (
    <section className="panel" aria-labelledby="provenance-heading">
      <h2 id="provenance-heading">Provenance of every screening input</h2>
      <p className="bucket-desc">
        Each input belongs to exactly one category. Nothing below is a
        site-specific measurement unless it is marked Source-derived.
      </p>

      {BUCKETS.map(({ key, label }) => {
        const names = (result[key] as string[]) ?? [];
        const title = BUCKET_TITLES[key as string];
        return (
          <div className="bucket" key={key as string}>
            <div className="bucket-head">
              <h3>{title}</h3>
              <Tag label={label} />
              <span className="card-name">
                {names.length} {names.length === 1 ? "input" : "inputs"}
              </span>
            </div>
            <p className="bucket-desc">{BUCKET_DESCRIPTIONS[key as string]}</p>
            {names.length === 0 ? (
              <p className="unavailable">None in this run.</p>
            ) : (
              <div className="cards">
                {names.map((name) => {
                  const input = result.screening_inputs[name];
                  if (!input) return null;
                  return <InputCard key={name} name={name} input={input} />;
                })}
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}

const SAMPLED_NAME: Record<string, string> = {
  porosity: "Porosity",
  brine_density_kg_m3: "Brine density",
  storage_efficiency: "Storage efficiency",
};

/**
 * The approved model's sampled priors, as the API states them. Area and the
 * storage interval are the caller's inputs; temperature and water level are
 * deterministic and reported with each named scenario.
 */
export function ApprovedInputsPanel({ result }: { result: ApprovedScreenResult }) {
  const sampled = result.sampled_inputs ?? {};
  const user = result.user_inputs ?? {};
  return (
    <section className="panel" aria-labelledby="approved-inputs-heading">
      <h2 id="approved-inputs-heading">Approved model inputs</h2>

      <h3 style={{ fontSize: 13 }}>Your inputs</h3>
      <dl className="kv">
        {Object.entries(user).map(([name, entry]) => (
          <div key={name} style={{ display: "contents" }}>
            <dt>{name}</dt>
            <dd>
              {num(entry.value)} {entry.unit}
            </dd>
          </div>
        ))}
      </dl>

      <h3 style={{ fontSize: 13, marginTop: 12 }}>Sampled priors</h3>
      <div className="cards">
        {Object.entries(sampled).map(([name, prior]) => (
          <article className="card" key={name} aria-labelledby={`prior-${name}`}>
            <div className="card-name" id={`prior-${name}`}>
              {SAMPLED_NAME[name] ?? name}
            </div>
            <div className="card-value">
              {num(prior.low, 4)} - {num(prior.high, 4)}
              <span className="unit">{prior.unit}</span>
            </div>
            <dl>
              <dt>Distribution</dt>
              <dd>{prior.distribution}</dd>
              <dt>Status</dt>
              <dd>{prior.status}</dd>
            </dl>
            <p className="note">{prior.provenance}</p>
            {prior.statement ? <p className="note">{prior.statement}</p> : null}
            {prior.citation ? (
              <cite>
                {prior.citation.source} ({prior.citation.year})
              </cite>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
