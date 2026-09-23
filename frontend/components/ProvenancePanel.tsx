import { InputCard } from "./InputCard";
import { Tag } from "./Tag";
import { BUCKET_DESCRIPTIONS, BUCKET_TITLES } from "@/lib/format";
import type { InputLabel, ScreenResult } from "@/lib/types";

/**
 * The four provenance buckets, rendered exactly as the API partitions them.
 *
 * They are never merged into a generic "inputs" section: the whole point of
 * this product is that a reader can see, without effort, how much of the
 * number came from measurement and how much from an assumption they supplied.
 */
const BUCKETS: { key: keyof ScreenResult; label: InputLabel }[] = [
  { key: "source_derived_inputs", label: "source" },
  { key: "modelled_inputs", label: "MODELLED" },
  { key: "assumed_inputs", label: "ASSUMED" },
  { key: "user_supplied_inputs", label: "USER" },
];

export function ProvenancePanel({ result }: { result: ScreenResult }) {
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
