/**
 * Error mapping of the API client for a backend whose dataset is not ready.
 *
 * A required data source that is missing or unreadable makes data endpoints
 * answer a controlled 503 `DatasetNotReadyError`. That must read as a dataset
 * problem, not as "internal error", and a 500 body must still never be echoed.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, listWells } from "@/lib/api";

function respond(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

async function failure(): Promise<ApiClientError> {
  try {
    await listWells();
  } catch (error) {
    if (error instanceof ApiClientError) return error;
    throw error;
  }
  throw new Error("expected listWells to fail");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("dataset-not-ready responses", () => {
  it("reports a 503 DatasetNotReadyError as a dataset problem", async () => {
    respond(503, {
      error: "dataset in data is not ready: required source GEOTHOPICA:Anagrafica unreadable",
      type: "DatasetNotReadyError",
      detail: [{ source: "GEOTHOPICA:Anagrafica", status: "unreadable" }],
    });
    const error = await failure();
    expect(error.status).toBe(503);
    expect(error.kind).toBe("data_not_ready");
    expect(error.message).toMatch(/dataset is not ready/i);
    expect(error.message).toMatch(/GEOTHOPICA:Anagrafica unreadable/);
  });

  it("does not echo an unrecognised 503 body", async () => {
    respond(503, { error: "Traceback (most recent call last): ...", type: "Other" });
    const error = await failure();
    expect(error.kind).toBe("data_not_ready");
    expect(error.message).toBe("The screening backend is temporarily unavailable.");
  });

  it("still never echoes a 500 body", async () => {
    respond(500, { error: "Traceback (most recent call last): ...", type: "InternalServerError" });
    const error = await failure();
    expect(error.kind).toBe("server");
    expect(error.message).toBe("The screening backend reported an internal error.");
  });
});
