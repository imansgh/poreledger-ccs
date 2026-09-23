/**
 * Client for the CCS screening backend.
 *
 * Every failure becomes an `ApiClientError` carrying a status and a message
 * safe to render. Backend error envelopes look like
 * `{error, type, detail}`; FastAPI validation failures look like
 * `{detail: [{loc, msg, type}]}`. Both are parsed into readable text. A stack
 * trace is never surfaced: if a 500 body arrives, the message is replaced
 * rather than echoed.
 */

import type {
  RequiredInputs,
  ScenarioSummary,
  ScreenResult,
  TemperatureComparison,
  UserInputValues,
  WellDetail,
  WellSummary,
} from "./types";

/**
 * Backend base URL.
 *
 * `NEXT_PUBLIC_*` values are inlined at BUILD time, not read at runtime, so a
 * production image built without this variable would ship a localhost URL that
 * fails for every visitor with no obvious cause. The fallback is kept for
 * development convenience, but a production build that relies on it is flagged
 * so the UI can say so rather than appearing merely broken.
 */
const CONFIGURED_API_URL = process.env.NEXT_PUBLIC_CCS_API_URL;
const DEV_FALLBACK_URL = "http://127.0.0.1:8000";

export const API_BASE_URL = CONFIGURED_API_URL ?? DEV_FALLBACK_URL;

/** True when a production build is running on the development fallback. */
export const USING_DEV_FALLBACK_URL =
  !CONFIGURED_API_URL && process.env.NODE_ENV === "production";

if (USING_DEV_FALLBACK_URL && typeof console !== "undefined") {
  console.error(
    "NEXT_PUBLIC_CCS_API_URL was not set at build time; falling back to " +
      `${DEV_FALLBACK_URL}, which will not work for remote visitors.`,
  );
}

export type ApiErrorKind =
  | "bad_request"
  | "not_found"
  | "too_large"
  | "validation"
  | "server"
  | "network";

export class ApiClientError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  /** Field-level problems from a 422, for form display. */
  readonly fieldErrors: { field: string; message: string }[];

  constructor(
    message: string,
    status: number,
    kind: ApiErrorKind,
    fieldErrors: { field: string; message: string }[] = [],
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.kind = kind;
    this.fieldErrors = fieldErrors;
  }
}

function kindFor(status: number): ApiErrorKind {
  if (status === 400) return "bad_request";
  if (status === 404) return "not_found";
  if (status === 413) return "too_large";
  if (status === 422) return "validation";
  return "server";
}

/** Turn a FastAPI 422 body into readable field errors. */
function parseValidationErrors(
  body: unknown,
): { field: string; message: string }[] {
  if (!body || typeof body !== "object") return [];
  const detail = (body as { detail?: unknown }).detail;
  if (!Array.isArray(detail)) return [];
  return detail.map((item) => {
    const entry = item as { loc?: unknown[]; msg?: string };
    const loc = Array.isArray(entry.loc)
      ? entry.loc.filter((p) => p !== "body").join(".")
      : "";
    return { field: String(loc || "request"), message: String(entry.msg ?? "invalid value") };
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiClientError(
      `Cannot reach the screening backend at ${API_BASE_URL}. Check that it is running.`,
      0,
      "network",
    );
  }

  if (response.ok) {
    return (await response.json()) as T;
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  const status = response.status;
  const kind = kindFor(status);

  if (kind === "validation") {
    const fieldErrors = parseValidationErrors(body);
    const summary =
      fieldErrors.length > 0
        ? fieldErrors.map((e) => `${e.field}: ${e.message}`).join("; ")
        : "The request was rejected by validation.";
    throw new ApiClientError(summary, status, kind, fieldErrors);
  }

  if (kind === "server") {
    // Never echo a server body: it may contain a trace.
    throw new ApiClientError(
      "The screening backend reported an internal error.",
      status,
      kind,
    );
  }

  const envelope = body as { error?: string; detail?: string } | null;
  const message =
    (typeof envelope?.error === "string" && envelope.error) ||
    (typeof envelope?.detail === "string" && envelope.detail) ||
    `Request failed with status ${status}.`;
  throw new ApiClientError(message, status, kind);
}

export function listWells(): Promise<WellSummary[]> {
  return request<WellSummary[]>("/wells");
}

export function getWell(wellId: string): Promise<WellDetail> {
  return request<WellDetail>(`/wells/${encodeURIComponent(wellId)}`);
}

export function getRequiredInputs(
  wellId: string,
  scenario?: string,
): Promise<RequiredInputs> {
  const query = scenario ? `?scenario=${encodeURIComponent(scenario)}` : "";
  return request<RequiredInputs>(
    `/wells/${encodeURIComponent(wellId)}/inputs${query}`,
  );
}

export function listScenarios(): Promise<ScenarioSummary[]> {
  return request<ScenarioSummary[]>("/scenarios");
}

export function screenWell(
  wellId: string,
  userInputs: UserInputValues,
  scenario: string,
  samples = 2000,
): Promise<ScreenResult> {
  return request<ScreenResult>(`/wells/${encodeURIComponent(wellId)}/screen`, {
    method: "POST",
    body: JSON.stringify({ user_inputs: userInputs, scenario, samples }),
  });
}

export function compareTemperatureMethods(
  wellId: string,
  userInputs: UserInputValues,
  scenario: string,
  samples = 500,
): Promise<TemperatureComparison> {
  return request<TemperatureComparison>(
    `/wells/${encodeURIComponent(wellId)}/temperature`,
    {
      method: "POST",
      body: JSON.stringify({ user_inputs: userInputs, scenario, samples }),
    },
  );
}
