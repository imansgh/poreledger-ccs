/**
 * The public demo against a REAL FastAPI backend.
 *
 * Starts uvicorn on the bundled synthetic dataset (`demo/data`) and drives the
 * same HTTP calls the website makes, with the documented example requests in
 * `demo/requests`. The demo ships with the repository, so this suite never
 * skips: a backend that will not start or a demo that is not ready is a
 * failure.
 *
 *     npm run test:demo
 *
 * Requirements: the repository's Python environment with `.[dev,web]`
 * installed. CCS_PYTHON overrides the interpreter.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const REPO_ROOT = dirname(process.cwd());
const DEMO_DIR = join(REPO_ROOT, "demo", "data");
const REQUESTS = join(REPO_ROOT, "demo", "requests");
const PORT = Number(process.env.CCS_DEMO_TEST_PORT ?? 8788);
const BASE = `http://127.0.0.1:${PORT}`;

let backend: ChildProcess | null = null;

function request(name: string): unknown {
  return JSON.parse(readFileSync(join(REQUESTS, name), "utf8"));
}

async function screen(well: string, body: unknown) {
  const response = await fetch(`${BASE}/wells/${encodeURIComponent(well)}/screen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  expect(response.status).toBe(200);
  return response.json();
}

function statuses(result: { water_level_scenarios: { validation_status: string }[] }) {
  return result.water_level_scenarios.map((s) => s.validation_status);
}

beforeAll(async () => {
  const python = process.env.CCS_PYTHON ?? (process.platform === "win32" ? "python" : "python3");
  backend = spawn(
    python,
    ["-m", "uvicorn", "ccs_screen.web.app:app", "--port", String(PORT), "--log-level", "warning"],
    {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        PYTHONPATH: join(REPO_ROOT, "src"),
        CCS_DATA_DIR: DEMO_DIR,
        CCS_CORS_ORIGINS: "http://localhost:3000",
      },
      stdio: "ignore",
    },
  );
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${BASE}/ready/existing-data`)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`the demo backend never became ready at ${BASE}`);
}, 60_000);

afterAll(() => {
  backend?.kill();
});

describe("public demo against a real backend", () => {
  it("reports the synthetic demo dataset on /health and /ready/existing-data", async () => {
    const health = await (await fetch(`${BASE}/health`)).json();
    expect(health.status).toBe("ok");
    expect(health.data_ready).toBe(true);
    expect(health.dataset.kind).toBe("synthetic_demo");
    expect(health.dataset.synthetic).toBe(true);
    const ready = await (await fetch(`${BASE}/ready/existing-data`)).json();
    expect(ready.dataset.synthetic).toBe(true);
  });

  it("lists only fictional, flagged wells", async () => {
    const wells = (await (await fetch(`${BASE}/wells`)).json()) as {
      well_id: string;
      synthetic: boolean;
    }[];
    expect(wells.map((w) => w.well_id)).toEqual([
      "SYNTH ALPHA|1",
      "SYNTH BETA|1",
      "SYNTH DELTA|1",
      "SYNTH GAMMA|1",
    ]);
    expect(wells.every((w) => w.synthetic)).toBe(true);
  });

  it("evaluates the approved model to VALIDATED on established synthetic inputs", async () => {
    const result = await screen("SYNTH ALPHA|1", request("approved-validated.json"));
    expect(result.model_path).toBe("APPROVED_MODEL");
    expect(statuses(result)).toEqual(["VALIDATED", "VALIDATED"]);
    expect(result.dataset.synthetic).toBe(true);
    expect(result.interpretation.warnings[0].code).toBe("synthetic_demo_dataset");
  });

  it("returns UNAVAILABLE when the depth reference is not established", async () => {
    const result = await screen("SYNTH BETA|1", request("approved-unavailable.json"));
    expect(statuses(result)).toEqual(["UNAVAILABLE", "UNAVAILABLE"]);
    expect(result.water_level_scenarios[0].diagnostics[0].code).toBe(
      "DEPTH_REFERENCE_NOT_ESTABLISHED",
    );
  });

  it("returns OUTSIDE_VALIDATED_ENVELOPE for the deep, hot well", async () => {
    const result = await screen("SYNTH GAMMA|1", request("approved-outside-envelope.json"));
    expect(statuses(result)).toEqual([
      "OUTSIDE_VALIDATED_ENVELOPE",
      "OUTSIDE_VALIDATED_ENVELOPE",
    ]);
  });

  it("labels the legacy path NOT_VALIDATED", async () => {
    const result = await screen("SYNTH ALPHA|1", request("legacy-not-validated.json"));
    expect(result.validation_status).toBe("NOT_VALIDATED");
    expect(result.dataset.synthetic).toBe(true);
  });
});
