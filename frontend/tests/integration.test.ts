/**
 * Integration test against a REAL FastAPI backend.
 *
 * Every other frontend test stubs the API client, so all of them would still
 * pass if the backend contract changed underneath us. This one exercises the
 * actual HTTP path: the real client, a real uvicorn process, the real
 * SALUZZO|1 record, and the real Monte Carlo result.
 *
 * It starts and stops the backend itself. Run it with:
 *
 *     npm run test:integration
 *
 * Requirements: the repository's Python environment with `.[dev,web]`
 * installed, and the `data/` directory present.
 *
 * Skipping policy: if `data/` is absent the suite skips, so a contributor
 * without the dataset is not blocked. If `data/` IS present but the backend
 * will not start, that is a hard failure -- a silently skipped integration
 * test is worse than none, because it reports green while verifying nothing.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it, type TaskContext } from "vitest";

const REPO_ROOT = dirname(process.cwd());
const DATA_DIR = join(REPO_ROOT, "data");
const PORT = Number(process.env.CCS_TEST_PORT ?? 8787);
const BASE = `http://127.0.0.1:${PORT}`;
const WELL = "SALUZZO|1";

let backend: ChildProcess | null = null;
let available = false;
let startupError = "";

const haveData = existsSync(DATA_DIR);

/** Runtime gate. `it.runIf` is evaluated at collection time, before
 * `beforeAll` has run, so it would always see the initial `false`. */
function requireBackend(ctx: TaskContext): boolean {
  if (!haveData) {
    ctx.skip();
    return false;
  }
  if (!available) {
    throw new Error(
      `data/ exists but the backend never became healthy at ${BASE}. ${startupError}`,
    );
  }
  return true;
}

async function waitForHealth(timeoutMs = 45_000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${BASE}/health`);
      if (response.ok) return true;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

beforeAll(async () => {
  if (!haveData) return;

  const python = process.platform === "win32" ? "python" : "python3";
  backend = spawn(
    python,
    ["-m", "uvicorn", "ccs_screen.web.app:app", "--port", String(PORT), "--log-level", "warning"],
    {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        PYTHONPATH: join(REPO_ROOT, "src"),
        CCS_DATA_DIR: "data",
        CCS_CORS_ORIGINS: "http://localhost:3000",
      },
      stdio: "ignore",
    },
  );
  backend.on("error", (err) => {
    available = false;
    startupError = `spawn failed: ${err.message}`;
  });

  available = await waitForHealth();
  if (!available) startupError ||= "health check timed out";
}, 60_000);

afterAll(() => {
  backend?.kill();
});

describe("frontend against a real backend", () => {
  it("starts a real backend", (ctx) => {
    if (!requireBackend(ctx)) return;
    expect(available).toBe(true);
  });

  it("serves the well list", async (ctx) => {
    if (!requireBackend(ctx)) return;
    const response = await fetch(`${BASE}/wells`);
    const wells = (await response.json()) as { well_id: string }[];
    expect(wells.length).toBeGreaterThan(0);
    expect(wells.some((w) => w.well_id === WELL)).toBe(true);
  });

  it(
    "runs the approved workflow: area and interval in, both named scenarios out",
    async (ctx) => {
      if (!requireBackend(ctx)) return;
      // 1. Well selection -> the record the UI would display.
      const detail = await (await fetch(`${BASE}/wells/${encodeURIComponent(WELL)}`)).json();
      expect(detail.canonical_id).toBe(WELL);
      expect(detail.fields.temperature_k.provenance).toBe("derived");
      expect(detail.approved_model_depth_reference.status).toBe("UNAVAILABLE");

      // 2. What the UI must ask the user for on the approved model.
      const inputs = await (
        await fetch(`${BASE}/wells/${encodeURIComponent(WELL)}/inputs`)
      ).json();
      expect(inputs.model_path).toBe("APPROVED_MODEL");
      expect(inputs.required.map((r: { field: string }) => r.field).sort()).toEqual([
        "area_m2",
        "z_base",
        "z_top",
      ]);

      // 3. User enters 80 km2 and an interval; the form converts area to m2.
      const body = {
        user_inputs: { area_m2: 80_000_000, z_top: 1400, z_base: 1527 },
        scenario: "literature-screening-v1",
        samples: 2000,
      };
      const response = await fetch(`${BASE}/wells/${encodeURIComponent(WELL)}/screen`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      expect(response.status).toBe(200);
      const result = await response.json();

      // 4. Both named scenarios, each with a status. No ingested depth reference
      //    is established (C2), so on real data both are UNAVAILABLE.
      expect(result.status).toBe("evaluated");
      expect(result.model_path).toBe("APPROVED_MODEL");
      const names = result.water_level_scenarios.map((s: { name: string }) => s.name);
      expect(names).toEqual(["GROUND_REFERENCE", "SEA_LEVEL_SENSITIVITY"]);
      for (const scenario of result.water_level_scenarios) {
        expect(scenario.validation_status).toBe("UNAVAILABLE");
        expect(scenario.capacity_mt).toBeNull();
        expect(scenario.diagnostics[0].code).toBe("DEPTH_REFERENCE_NOT_ESTABLISHED");
      }

      // 5. The interpretation block the qualifier depends on.
      expect(result.interpretation.type).toBe("scenario_based_capacity");
      expect(result.interpretation.site_specific).toBe(false);
      expect(result.interpretation.certified).toBe(false);
      expect(
        result.interpretation.warnings.map((w: { code: string }) => w.code),
      ).toContain("scale_mismatch_basin_vs_closure");
    },
    30_000,
  );

  it(
    "runs the legacy workflow: NOT_VALIDATED, with the provenance partition",
    async (ctx) => {
      if (!requireBackend(ctx)) return;
      const inputs = await (
        await fetch(`${BASE}/wells/${encodeURIComponent(WELL)}/inputs?scenario=sensitivity`)
      ).json();
      expect(inputs.required.map((r: { field: string }) => r.field).sort()).toEqual([
        "area_m2",
        "thickness_m",
      ]);

      const response = await fetch(`${BASE}/wells/${encodeURIComponent(WELL)}/screen`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_inputs: { area_m2: 80_000_000, thickness_m: 35 },
          scenario: "sensitivity",
          samples: 2000,
        }),
      });
      expect(response.status).toBe(200);
      const result = await response.json();

      // A real Monte Carlo result, ordered and finite, labelled NOT_VALIDATED.
      expect(result.status).toBe("screened");
      expect(result.validation_status).toBe("NOT_VALIDATED");
      const capacity = result.scenario_based_capacity_mt;
      expect(capacity.p10).toBeLessThan(capacity.p50);
      expect(capacity.p50).toBeLessThan(capacity.p90);
      expect(capacity.n_samples).toBe(2000);
      for (const key of ["p10", "p50", "p90", "mean"]) {
        expect(Number.isFinite(capacity[key])).toBe(true);
        expect(capacity[key]).toBeGreaterThan(0);
      }

      // The provenance contract the UI renders (placeholder scenario: the
      // pressure is a flat assumption, so no MODELLED input).
      expect(result.source_derived_inputs).toEqual(["temperature_k"]);
      expect(result.modelled_inputs).toEqual([]);
      expect(result.user_supplied_inputs.sort()).toEqual(["area_m2", "thickness_m"]);
      const buckets = [
        ...result.source_derived_inputs,
        ...result.modelled_inputs,
        ...result.assumed_inputs,
        ...result.user_supplied_inputs,
      ];
      expect(new Set(buckets).size, "buckets must stay disjoint").toBe(buckets.length);
      expect(buckets.length).toBe(6);
      expect(
        result.interpretation.warnings.map((w: { code: string }) => w.code),
      ).toContain("not_validated_legacy_path");
    },
    30_000,
  );

  it("blocks a well with no reservoir temperature", async (ctx) => {
    if (!requireBackend(ctx)) return;
    const response = await fetch(`${BASE}/wells/${encodeURIComponent("CRESCENTINO|1")}/screen`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_inputs: { area_m2: 80_000_000, thickness_m: 35 },
        scenario: "sensitivity",
        samples: 100,
      }),
    });
    expect(response.status).toBe(200);
    const result = await response.json();
    expect(result.status).toBe("blocked");
    expect(result.scenario_based_capacity_mt).toBeNull();
    expect(result.missing_fields).toContain("temperature_k");
  });

  it("maps errors the way the client expects", async (ctx) => {
    if (!requireBackend(ctx)) return;
    const unknown = await fetch(`${BASE}/wells/${encodeURIComponent("NOPE|9")}`);
    expect(unknown.status).toBe(404);
    expect((await unknown.json()).type).toBe("UnknownWellError");

    const badScenario = await fetch(
      `${BASE}/wells/${encodeURIComponent(WELL)}/inputs?scenario=no-such`,
    );
    expect(badScenario.status).toBe(400);

    const badSamples = await fetch(`${BASE}/wells/${encodeURIComponent(WELL)}/screen`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_inputs: { area_m2: 8e7, z_top: 1400, z_base: 1527 },
        samples: 10_000_000,
      }),
    });
    expect(badSamples.status).toBe(422);
  });

  it("allows the configured CORS origin and no other", async (ctx) => {
    if (!requireBackend(ctx)) return;
    const allowed = await fetch(`${BASE}/wells`, {
      headers: { Origin: "http://localhost:3000" },
    });
    expect(allowed.headers.get("access-control-allow-origin")).toBe("http://localhost:3000");

    const denied = await fetch(`${BASE}/wells`, {
      headers: { Origin: "https://evil.example" },
    });
    expect(denied.headers.get("access-control-allow-origin")).not.toBe("https://evil.example");
    expect(denied.headers.get("access-control-allow-origin")).not.toBe("*");
  });
});
