/**
 * The user-data workflow against a REAL backend that has NO well dataset.
 *
 * Starts uvicorn with CCS_DATA_DIR pointing at a directory that does not
 * exist, then drives the same client functions the website uses: examples,
 * file parsing, evaluation, and exports. Proves the primary workflow needs
 * neither the owner's data nor the bundled demo wells, and that the browser's
 * form mapping and the backend agree.
 *
 *     npm run test:assessment
 *
 * Never skips: everything it needs ships with the repository. CCS_PYTHON
 * overrides the interpreter.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const REPO_ROOT = dirname(process.cwd());
const PORT = Number(process.env.CCS_ASSESSMENT_TEST_PORT ?? 8789);
const BASE = `http://127.0.0.1:${PORT}`;

// The client reads its base URL at import time.
vi.stubEnv("NEXT_PUBLIC_CCS_API_URL", BASE);

let backend: ChildProcess | null = null;

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
        CCS_DATA_DIR: join(REPO_ROOT, "no-such-data-directory"),
        CCS_CORS_ORIGINS: "http://localhost:3000",
      },
      stdio: "ignore",
    },
  );
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${BASE}/ready`)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`the backend never became ready at ${BASE}`);
}, 60_000);

afterAll(() => {
  backend?.kill();
});

async function client() {
  return import("@/lib/assessment");
}

describe("user assessments with no well dataset", () => {
  it("is engine-ready while the optional existing data is not", async () => {
    const ready = await (await fetch(`${BASE}/ready`)).json();
    expect(ready.status).toBe("ready");
    expect(ready.existing_data.ready).toBe(false);
    expect((await fetch(`${BASE}/ready/existing-data`)).status).toBe(503);
    const wells = await fetch(`${BASE}/wells`);
    expect(wells.status).toBe(400);
    expect((await wells.json()).type).toBe("ApiError");
  });

  it("evaluates the examples through the form mapping exactly as sent directly", async () => {
    const { getExamples, documentToDrafts, draftsToDocument, evaluate } = await client();
    const examples = await getExamples();
    const viaForm = draftsToDocument(documentToDrafts(examples));
    expect(viaForm).toEqual(examples);
    const result = await evaluate(viaForm, 500, 42);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const statuses = result.data.assessments.map((a) => a.outcome.overall_status);
    expect(statuses).toEqual([
      "VALIDATED",
      "UNAVAILABLE",
      "OUTSIDE_VALIDATED_ENVELOPE",
      "UNAVAILABLE",
    ]);
    expect(result.data.assessments.every((a) => a.synthetic)).toBe(true);
    expect(result.data.summary_csv.split("\n")[1]).toContain("SYNTHETIC EXAMPLE");
  });

  it("evaluates a user's own assessment entered in feet and Fahrenheit", async () => {
    const { emptyDraft, draftsToDocument, evaluate } = await client();
    const draft = {
      ...emptyDraft("MY-WELL-7"),
      area: "4942.1",
      area_unit: "acre",
      top: "4757.2",
      base: "5085.3",
      depth_unit: "ft",
      datum: "ground_level",
      convention: "TVD",
      total_depth: "5413.4",
      total_depth_unit: "ft",
      elevation: "787.4",
      elevation_unit: "ft",
      observations: [
        {
          value: "136.4",
          unit: "degF",
          depth: "4921.3",
          depth_unit: "ft",
          depth_datum: "ground_level",
          depth_convention: "TVD",
          method: "horner_corrected",
          source: "test",
        },
      ],
    };
    const result = await evaluate(draftsToDocument([draft]), 500, 1);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const item = result.data.assessments[0];
    expect(item.synthetic).toBe(false);
    expect(item.outcome.overall_status).toBe("VALIDATED");
    const inputs = item.inputs as { storage_interval: { z_top_m: number } };
    expect(inputs.storage_interval.z_top_m).toBeCloseTo(4757.2 * 0.3048, 9);
  });

  it("returns every input problem as data, not as an exception", async () => {
    const { emptyDraft, draftsToDocument, evaluate } = await client();
    const result = await evaluate(draftsToDocument([emptyDraft()]));
    expect(result.ok).toBe(false);
    if (result.ok) return;
    const paths = result.problems.map((p) => p.path);
    expect(paths).toContain("assessments[0].storage_area.value");
    expect(paths).toContain("assessments[0].depth_reference.datum");
  });

  it("parses the shipped CSV examples and reports row numbers for bad rows", async () => {
    const { parseFile } = await client();
    const csv = readFileSync(
      join(REPO_ROOT, "src", "ccs_screen", "assessment_data", "synthetic-examples.csv"),
      "utf8",
    );
    const good = await parseFile("csv", csv);
    expect(good.valid).toBe(true);
    expect(good.document?.assessments).toHaveLength(4);
    const bad = await parseFile("csv", csv.replace("SYNTH BETA|1,20,km2,1400", "SYNTH BETA|1,20,km2,1600"));
    expect(bad.valid).toBe(false);
    expect(bad.problems.find((p) => p.code === "INTERVAL_ORDER")?.row).toBe(7);
  });

  it("serves the templates as downloads", async () => {
    const { fileUrl } = await client();
    const response = await fetch(fileUrl("assessment-template.csv"));
    expect(response.status).toBe(200);
    expect(response.headers.get("content-disposition")).toContain("attachment");
    expect(await response.text()).toContain("schema_version,assessment_id");
  });

  it("R1: a mixed-unit import keeps its total-depth unit through the form to the engine", async () => {
    const { getExamples, parseFile, documentToDrafts, draftsToDocument, evaluate } = await client();
    const examples = await getExamples();
    const alpha = JSON.parse(JSON.stringify(examples.assessments[0])) as Record<string, any>;
    expect(alpha.example.key).toBe("validated");
    alpha.total_depth = { value: 3000, unit: "ft" }; // 914.4 m, above the 1500 m reading
    const file = JSON.stringify({ schema_version: examples.schema_version, assessments: [alpha] });

    // Directly: the engine rejects the temperature as below total depth.
    const direct = await evaluate(JSON.parse(file), 500, 42);
    expect(direct.ok).toBe(true);
    if (!direct.ok) return;
    expect(direct.data.assessments[0].outcome.overall_status).toBe("UNAVAILABLE");

    // Through the website: upload -> editable draft -> submission.
    const parsed = await parseFile("json", file);
    expect(parsed.valid).toBe(true);
    const drafts = documentToDrafts(parsed.document!);
    expect(drafts[0].total_depth_unit).toBe("ft");
    const sent = draftsToDocument(drafts, parsed.document as unknown as Record<string, unknown>);
    expect(sent).toEqual(JSON.parse(file));
    const viaForm = await evaluate(sent, 500, 42);
    expect(viaForm.ok).toBe(true);
    if (!viaForm.ok) return;
    const item = viaForm.data.assessments[0];
    expect(item.outcome.overall_status).toBe("UNAVAILABLE");
    expect(item.result.water_level_scenarios.every((s) => s.capacity_mt === null)).toBe(true);
    const reasons = item.outcome.blocking_reasons.map((r) => r.code).join(" ");
    expect(reasons).toMatch(/TOTAL_DEPTH|TEMPERATURE/);
  });

  it("R2: an imported unsupported version or missing unit is still rejected after the form", async () => {
    const { getExamples, parseFile, documentToDrafts, draftsToDocument, evaluate } = await client();
    const examples = await getExamples();
    const alpha = JSON.parse(JSON.stringify(examples.assessments[0])) as Record<string, any>;
    for (const [doc, code] of [
      [{ schema_version: "ccs-assessment/999", assessments: [alpha] }, "UNSUPPORTED_SCHEMA_VERSION"],
      [{ schema_version: "ccs-assessment/1",
         assessments: [{ ...alpha, storage_area: { value: 20 } }] }, "MISSING_VALUE"],
    ] as const) {
      const parsed = await parseFile("json", JSON.stringify(doc));
      expect(parsed.problems.map((p) => p.code)).toContain(code);
      const sent = draftsToDocument(documentToDrafts(parsed.document!),
                                    parsed.document as unknown as Record<string, unknown>);
      expect(sent).toEqual(doc);
      const result = await evaluate(sent, 500, 42);
      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.problems.map((p) => p.code)).toContain(code);
    }
  });

  it("R3: the engine names which submitted observation it selected", async () => {
    const { getExamples, evaluate } = await client();
    const alpha = JSON.parse(JSON.stringify((await getExamples()).assessments[0])) as Record<string, any>;
    const reading = { value: 331.15, unit: "K", depth: 1500, depth_unit: "m", depth_datum: "ground_level",
                      depth_convention: "TVD", method: "extrapolated_squarci_taffi" };
    alpha.temperature_observations = [reading, { ...reading, depth_datum: "msl" }];
    const result = await evaluate({ schema_version: "ccs-assessment/1", assessments: [alpha] }, 500, 42);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const { observationPoints } = await import("@/components/charts/DepthTemperatureChart");
    const { points } = observationPoints(result.data.assessments[0]);
    expect(points.map((p) => p.status)).toEqual(["selected", "excluded"]);
  });

  it("R2 (CSV): conflicting rows block calculation in the website until a corrected re-upload", async () => {
    const { parseFile, evaluate, documentToDrafts, draftsToDocument } = await client();
    const { AssessmentWorkspace } = await import("@/components/AssessmentWorkspace");
    const csv = readFileSync(
      join(REPO_ROOT, "src", "ccs_screen", "assessment_data", "synthetic-examples.csv"), "utf8");
    const lines = csv.split("\n");
    const alpha = lines.map((l, i) => [l, i] as const).filter(([l]) => l.startsWith("1,SYNTH ALPHA|1,20,"));
    expect(alpha).toHaveLength(3);
    lines[alpha[1][1]] = alpha[1][0].replace("1,SYNTH ALPHA|1,20,", "1,SYNTH ALPHA|1,999,");
    const conflicting = lines.join("\n");

    // The backend gives no evaluatable document, only a marked preview, and rejects the
    // preview however it is resubmitted: directly, or mapped and edited through the form's
    // own draft functions.
    const parsed = await parseFile("csv", conflicting);
    expect(parsed.import_blocked).toBe(true);
    expect(parsed.document).toBeNull();
    expect(parsed.problems.map((p) => p.code)).toEqual(["CONFLICTING_VALUE"]);
    const preview = parsed.preview_document!;
    const drafts = documentToDrafts(preview);
    drafts[0] = { ...drafts[0], area: "999" };
    for (const doc of [preview, draftsToDocument(drafts, preview as unknown as Record<string, unknown>)]) {
      const evaluated = await evaluate(doc, 200, 42);
      expect(evaluated.ok).toBe(false);
      if (evaluated.ok) return;
      expect(evaluated.problems.map((p) => p.code)).toEqual(["IMPORT_BLOCKED"]);
      const validated = await (await fetch(`${BASE}/assessments/validate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document: doc }) })).json();
      expect(validated.valid).toBe(false);
      expect(validated.assessments).toEqual([]);
    }

    render(createElement(AssessmentWorkspace));
    const upload = (text: string, name: string) => {
      const input = screen.getByLabelText(/data file \(json or csv\)/i) as HTMLInputElement;
      fireEvent.change(input, { target: { files: [new File([text], name, { type: "text/csv" })] } });
    };
    upload(conflicting, "conflict.csv");
    await screen.findByText(/calculation is blocked/i, undefined, { timeout: 10_000 });
    const button = () => screen.getByRole("button", { name: /^calculate/i });
    expect(button()).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^storage area$/i), { target: { value: "21" } });
    fireEvent.submit(button().closest("form")!);
    await new Promise((r) => setTimeout(r, 1500));
    expect(screen.queryByRole("region", { name: /^results$/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Row \d+: .*area_value is '999' here/i)).toBeInTheDocument();

    upload(csv, "fixed.csv");
    await waitFor(() => expect(screen.queryByText(/calculation is blocked/i)).not.toBeInTheDocument(),
                  { timeout: 10_000 });
    expect(button()).toBeEnabled();
    fireEvent.click(button());
    expect(await screen.findByRole("region", { name: /^results$/i }, { timeout: 25_000 })).toBeInTheDocument();

    // Blocked again, then replaced by a loaded synthetic example: calculation works.
    upload(conflicting, "conflict.csv");
    await screen.findByText(/calculation is blocked/i, undefined, { timeout: 10_000 });
    fireEvent.click(screen.getByRole("button", { name: /explore a synthetic example/i }));
    fireEvent.click(await screen.findByRole("button", { name: /^load and calculate example SYNTH ALPHA\|1$/i },
                                            { timeout: 10_000 }));
    await waitFor(() => expect(screen.queryByText(/calculation is blocked/i)).not.toBeInTheDocument());
    expect(await screen.findByText("Estimate available", { selector: ".outcome-status" }, { timeout: 25_000 }))
      .toBeInTheDocument();
    cleanup();
  });
});
