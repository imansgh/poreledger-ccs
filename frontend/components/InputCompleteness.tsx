"use client";

import { completeness, type AssessmentDraft, type CompletenessStatus } from "@/lib/assessment";

const MARK: Record<CompletenessStatus, { symbol: string; text: string }> = {
  present: { symbol: "✓", text: "Ready" },
  missing: { symbol: "○", text: "Missing" },
  invalid: { symbol: "!", text: "Check value" },
  unsupported: { symbol: "✕", text: "Not supported" },
  not_established: { symbol: "?", text: "Not established" },
};

/**
 * Which inputs are filled in and use supported values, with a link to each
 * field. Input completeness only: it says nothing about accuracy or
 * scientific confidence, and the backend repeats every check on calculation.
 */
export function InputCompleteness({ draft, index }: { draft: AssessmentDraft; index: number }) {
  const items = completeness(draft, index);
  const required = items.filter((i) => !i.optional);
  const ready = required.filter((i) => i.status === "present").length;

  function go(fieldId: string) {
    const el = document.getElementById(fieldId);
    if (el) {
      el.focus();
      el.scrollIntoView?.({ block: "center" });
    }
  }

  return (
    <details className="completeness">
      <summary>
        <h3 id={`completeness-${index}`}>
          Input completeness: {ready} of {required.length} required inputs ready
        </h3>
      </summary>
      <p className="hint">Not an accuracy or confidence score. Every check is repeated when you calculate.</p>
      <ul>
        {items.map((item) => (
          <li key={item.key} className={`status-${item.status}`}>
            <span className="mark" aria-hidden="true">{MARK[item.status].symbol}</span>
            <span className="what">
              {item.label}
              {item.optional ? " (optional)" : ""}: <strong>{MARK[item.status].text}</strong>
              {item.note ? <span className="note"> {item.note}</span> : null}
            </span>
            {item.status !== "present" ? (
              <a href={`#${item.fieldId}`} aria-label={`Go to ${item.label}`} onClick={(e) => { e.preventDefault(); go(item.fieldId); }}>
                Go to field
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}
