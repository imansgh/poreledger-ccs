"use client";

import { useState } from "react";
import { ScreeningWorkspace } from "./ScreeningWorkspace";

/**
 * The optional existing-data workflow (wells already loaded on the server).
 * Collapsed by default and mounted only when opened, so the main workflow
 * never depends on that dataset being present or ready.
 */
export function ExistingDataSection() {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="panel existing-data"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>
        <h2>Existing well data (optional)</h2>
        <span className="hint">
          Screen wells already loaded on this server, if any. Not needed for your own data.
        </span>
      </summary>
      {open ? <ScreeningWorkspace /> : null}
    </details>
  );
}
