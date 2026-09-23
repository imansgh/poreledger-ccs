"use client";

import { useMemo, useState } from "react";
import type { WellSummary } from "@/lib/types";
import { num } from "@/lib/format";

/** Well picker with a text filter. Shows only metadata the API returns. */
export function WellSelector({
  wells,
  selectedId,
  onSelect,
}: {
  wells: WellSummary[];
  selectedId: string | null;
  onSelect: (wellId: string) => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return wells;
    return wells.filter(
      (w) =>
        w.well_id.toLowerCase().includes(q) ||
        w.original_names.some((n) => n.toLowerCase().includes(q)),
    );
  }, [wells, query]);

  return (
    <section className="panel" aria-labelledby="wells-heading">
      <h2 id="wells-heading">Well</h2>
      <div className="field">
        <label htmlFor="well-search">Filter by well ID</label>
        <input
          id="well-search"
          type="search"
          value={query}
          placeholder="e.g. SALUZZO"
          onChange={(e) => setQuery(e.target.value)}
        />
        <p className="hint">
          {filtered.length} of {wells.length} wells
        </p>
      </div>

      {filtered.length === 0 ? (
        <p className="unavailable">No well matches that filter.</p>
      ) : (
        <ul className="well-list">
          {filtered.map((well) => (
            <li key={well.well_id}>
              <button
                type="button"
                className="well-row"
                aria-current={well.well_id === selectedId}
                onClick={() => onSelect(well.well_id)}
              >
                <span className="id">{well.well_id}</span>
                <span className="meta">
                  {well.depth_m === null ? "depth n/a" : `${num(well.depth_m, 0)} m`}
                  {well.has_temperature ? "" : " - no temp"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
