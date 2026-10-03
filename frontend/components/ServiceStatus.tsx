"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

type State = "checking" | "slow" | "ready" | "unreachable" | "not_ready";

/** How long a /ready probe may take before the wait is explained. */
const SLOW_AFTER_MS = 3000;

/**
 * Probe the calculation service once on load (``GET /ready``, never rate
 * limited). A hosted demo may be asleep, so a slow answer is explained rather
 * than leaving the first calculation hanging silently. Renders nothing while
 * all is well.
 */
export function ServiceStatus() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let done = false;
    const slow = setTimeout(() => { if (!done) setState("slow"); }, SLOW_AFTER_MS);
    fetch(`${API_BASE_URL}/ready`)
      .then((response) => setState(response.ok ? "ready" : "not_ready"))
      .catch(() => setState("unreachable"))
      .finally(() => { done = true; clearTimeout(slow); });
    return () => { done = true; clearTimeout(slow); };
  }, []);

  if (state === "slow") {
    return (
      <p className="unavailable" role="status">
        The calculation service is starting up; this can take up to a minute. You can enter
        data meanwhile.
      </p>
    );
  }
  if (state === "unreachable" || state === "not_ready") {
    return (
      <p className="field-error" role="alert">
        The calculation service is {state === "unreachable" ? "not reachable" : "not ready"} right
        now. You can still enter data; try calculating again in a minute.
      </p>
    );
  }
  return null;
}
