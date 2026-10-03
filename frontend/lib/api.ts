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
  HealthInfo,
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
// Each use reads process.env.NEXT_PUBLIC_CCS_API_URL directly so the build
// inlines it and folds these expressions: when the URL is set, the fallback
// and its warning are removed from the bundle entirely (the published bundle
// must not mention a loopback URL; scripts/build-static.mjs checks this).
export const API_BASE_URL = process.env.NEXT_PUBLIC_CCS_API_URL || "http://127.0.0.1:8000";

/** True when a production build is running on the development fallback. */
export const USING_DEV_FALLBACK_URL =
  !process.env.NEXT_PUBLIC_CCS_API_URL && process.env.NODE_ENV === "production";

if (!process.env.NEXT_PUBLIC_CCS_API_URL && process.env.NODE_ENV === "production" &&
    typeof console !== "undefined") {
  console.error(
    "NEXT_PUBLIC_CCS_API_URL was not set at build time; falling back to " +
      `${API_BASE_URL}, which will not work for remote visitors.`,
  );
}

export type ApiErrorKind =
  | "bad_request"
  | "not_found"
  | "too_large"
  | "validation"
  | "data_not_ready"
  | "server"
  | "network"
  /** 429: the public deployment's per-client request limit. */
  | "rate_limited"
  /** 503 ServerBusy: all calculation slots of the public deployment are taken. */
  | "busy";

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
  if (status === 503) return "data_not_ready";
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
      `Cannot reach the calculation service at ${API_BASE_URL}. It may be starting up or temporarily offline; try again in a minute.`,
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

  if (kind === "data_not_ready") {
    // A controlled 503: a required data source on the backend is missing or
    // unreadable. Its envelope names the sources; it never carries a trace.
    const envelope = body as { type?: string; error?: string } | null;
    const message =
      envelope?.type === "DatasetNotReadyError" && typeof envelope.error === "string"
        ? `The screening backend's dataset is not ready: ${envelope.error}`
        : "The screening backend is temporarily unavailable.";
    throw new ApiClientError(message, status, kind);
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

/** Liveness and the dataset in use (synthetic demo or real sources). */
export function getHealth(): Promise<HealthInfo> {
  return request<HealthInfo>("/health");
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
