/**
 * The user-data workflow: choose data -> review inputs -> calculate -> read.
 *
 * Responses are real backend output (tests/assessment-fixtures.json, kept in
 * sync by tests/test_frontend_fixtures.py on the Python side), so these tests
 * check that the page renders what the engine returns.
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssessmentWorkspace } from "@/components/AssessmentWorkspace";
import { CapacityChart } from "@/components/charts/CapacityChart";
import { DepthTemperatureChart, observationPoints } from "@/components/charts/DepthTemperatureChart";
import { InputCompleteness } from "@/components/InputCompleteness";
import * as api from "@/lib/api";
import * as assessment from "@/lib/assessment";
import {
  assessmentToDraft,
  completeness,
  draftToAssessment,
  draftsToDocument,
  emptyDraft,
  type AssessmentDocument,
  type EvaluationResponse,
  type ParseResponse,
  type Problem,
} from "@/lib/assessment";
import fixtures from "./assessment-fixtures.json";

const F = fixtures as unknown as {
  examples: AssessmentDocument;
  user_document: AssessmentDocument;
  user_result: EvaluationResponse;
  unavailable_result: EvaluationResponse;
  two_reasons_result: EvaluationResponse;
  md_result: EvaluationResponse;
  example_results: EvaluationResponse;
  invalid_problems: Problem[];
  csv_parse: ParseResponse;
  bad_csv_parse: ParseResponse;
};

type User = ReturnType<typeof userEvent.setup>;

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(assessment, "getExamples").mockResolvedValue(F.examples);
});

/** Fill the form as a user would, with the fixture's values. */
async function fillMySite(user: User) {
  const a = F.user_document.assessments[0] as Record<string, any>;
  await user.clear(screen.getByLabelText(/^assessment id$/i));
  await user.type(screen.getByLabelText(/^assessment id$/i), a.id);
  await user.type(screen.getByLabelText(/^display name/i), a.name);
  await user.type(screen.getByLabelText(/^storage area$/i), String(a.storage_area.value));
  await user.type(screen.getByLabelText(/^top \(z_top\)/i), String(a.storage_interval.top));
  await user.type(screen.getByLabelText(/^base \(z_base\)/i), String(a.storage_interval.base));
  await user.selectOptions(screen.getByLabelText(/^depths measured from$/i), "ground_level");
  await user.selectOptions(screen.getByLabelText(/^depth convention$/i), "TVD");
  await user.type(screen.getByLabelText(/^total depth$/i), String(a.total_depth.value));
  await user.type(screen.getByLabelText(/^ground elevation$/i), String(a.surface_elevation.value));
  const observations = a.temperature_observations as Record<string, any>[];
  for (let i = 0; i < observations.length; i += 1) {
    if (i > 0) await user.click(screen.getByRole("button", { name: /add temperature observation/i }));
    const group = screen.getByRole("group", { name: `Observation ${i + 1}` });
    const o = observations[i];
    await user.type(within(group).getByLabelText(/^temperature$/i), String(o.value));
    await user.type(within(group).getByLabelText(/measured at depth/i), String(o.depth));
    await user.selectOptions(within(group).getByLabelText(/^depth from$/i), o.depth_datum);
    await user.selectOptions(within(group).getByLabelText(/^convention$/i), o.depth_convention);
    await user.selectOptions(within(group).getByLabelText(/^method$/i), o.method);
    await user.type(within(group).getByLabelText(/source/i), o.source);
  }
}

const results = () => screen.findByRole("region", { name: /^results$/i });

describe("workflow first", () => {
  it("shows the input form immediately, with the three ways in and no existing-data calls", () => {
    const wells = vi.spyOn(api, "listWells");
    const health = vi.spyOn(api, "getHealth");
    render(<AssessmentWorkspace />);
    expect(screen.getByLabelText(/^storage area$/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Calculate" })).toBeInTheDocument();
    for (const name of ["Enter my data", "Upload a data file", "Explore a synthetic example"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    expect(screen.getByText(/results appear here after you calculate/i)).toBeInTheDocument();
    expect(wells).not.toHaveBeenCalled();
    expect(health).not.toHaveBeenCalled();
  });

  it("keeps units beside their values", () => {
    render(<AssessmentWorkspace />);
    expect(screen.getByLabelText("Area unit")).toHaveValue("km2");
    expect(screen.getByLabelText("Temperature unit")).toHaveValue("degC");
    expect(screen.getByRole("option", { name: "km²" })).toBeInTheDocument();
  });
});

describe("manual entry and results", () => {
  it("sends exactly the schema document typed and summarises a valid result", async () => {
    const spy = vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.user_result });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0]).toEqual(F.user_document);
    const region = await results();
    expect(region.querySelector(".outcome-status")).toHaveTextContent("Estimate available");
    expect(region).toHaveTextContent(/not a certified or site-specific capacity/i);
    const p50 = F.user_result.assessments[0].result.water_level_scenarios[0].capacity_mt!.p50;
    expect(region).toHaveTextContent(`P50 ${p50.toFixed(2)}`);
    expect(region).not.toHaveTextContent(/SYNTHETIC/);
    // Primary text is readable labels, not codes.
    expect(within(region).getAllByText("Water table at ground level (reference)").length).toBeGreaterThan(0);
  });

  it("moves focus to the result summary and offers a link to it", async () => {
    vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.user_result });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Results", level: 2 })).toHaveFocus());
    expect(screen.getByRole("link", { name: /view result summary/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /result is up to date/i })).toBeDisabled();
  });

  it("marks a result outdated as soon as an input changes and disables its exports", async () => {
    vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.user_result });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    await results();
    await user.type(screen.getByLabelText(/^storage area$/i), "5");
    expect(screen.getByText(/outdated: the inputs changed/i)).toBeInTheDocument();
    expect(screen.getAllByText("OUTDATED").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /download results/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Calculate" })).toBeEnabled();
  });

  it("drops a response that arrives after the inputs changed", async () => {
    let release!: (v: Awaited<ReturnType<typeof assessment.evaluate>>) => void;
    vi.spyOn(assessment, "evaluate").mockReturnValue(new Promise((r) => (release = r)));
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    fireEvent.change(screen.getByLabelText(/^base \(z_base\)/i), { target: { value: "1560" } });
    release({ ok: true, data: F.user_result });
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByRole("region", { name: /^results$/i })).not.toBeInTheDocument();
  });

  it("shows field errors beside the fields and keeps every entry", async () => {
    vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: false, problems: F.invalid_problems });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    expect(await screen.findByText(/area must be > 0/i)).toBeInTheDocument();
    expect(screen.getByText(/top must be shallower than base/i)).toBeInTheDocument();
    expect(screen.getByText(/2 input problem\(s\) to fix/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^base \(z_base\)/i)).toHaveValue("1550");
  });

  it("states one blocking reason once, with the affected scenarios and what to do", async () => {
    vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.unavailable_result });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    const region = await results();
    expect(within(region).getByText("More information needed")).toBeInTheDocument();
    expect(within(region).getAllByText(/^Depth datum not established/)).toHaveLength(1);
    expect(region).toHaveTextContent(/\(both water-table scenarios\)/);
    expect(within(region).getAllByText(/what to do:/i)).toHaveLength(1);
    // Not an error screen: no alert role, no service-problem notice.
    expect(screen.queryByText(/service problem/i)).not.toBeInTheDocument();
    expect(region.querySelectorAll(".range-bar")).toHaveLength(0);
  });

  it("keeps distinct reasons separate and names their scenarios", async () => {
    vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.two_reasons_result });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    const region = await results();
    const reasons = region.querySelectorAll(".reasons > li");
    expect(reasons).toHaveLength(2);
    expect(reasons[0]).toHaveTextContent(/total depth missing \(both water-table scenarios\)/i);
    expect(reasons[1]).toHaveTextContent(/ground elevation above sea level missing \(water table at sea level/i);
  });

  it("shows a service failure differently from an unavailable result", async () => {
    vi.spyOn(assessment, "evaluate").mockRejectedValue(new api.ApiClientError("Cannot reach", 0, "network"));
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await fillMySite(user);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    expect(await screen.findByText("Service problem")).toBeInTheDocument();
    expect(screen.getByLabelText(/^assessment id$/i)).toHaveValue("MY-SITE-1");
  });
});

describe("synthetic examples", () => {
  it("loads and calculates an example in one action", async () => {
    const spy = vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.example_results });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.click(screen.getByRole("button", { name: "Explore a synthetic example" }));
    await user.click(await screen.findByRole("button", { name: "Load and calculate example SYNTH ALPHA|1" }));
    expect(spy).toHaveBeenCalledTimes(1);
    expect((spy.mock.calls[0][0].assessments[0] as Record<string, any>).synthetic).toBe(true);
    const region = await results();
    expect(within(region).getAllByText("SYNTHETIC EXAMPLE").length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: /synthetic example data/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/^top \(z_top\)/i)).toHaveValue("1450");
  });

  it("keeps the synthetic origin after editing", async () => {
    const spy = vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.example_results });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.click(screen.getByRole("button", { name: "Explore a synthetic example" }));
    await user.click(await screen.findByRole("button", { name: "Load example SYNTH ALPHA|1" }));
    await user.clear(screen.getByLabelText(/^storage area$/i));
    await user.type(screen.getByLabelText(/^storage area$/i), "35");
    expect(screen.getByRole("region", { name: /synthetic example data/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    const sent = spy.mock.calls[0][0].assessments[0] as Record<string, any>;
    expect(sent.synthetic).toBe(true);
    expect(sent.storage_area.value).toBe(35);
  });

  it("asks before 'Start my own assessment' replaces edited inputs, then clears the origin", async () => {
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.click(screen.getByRole("button", { name: "Explore a synthetic example" }));
    await user.click(await screen.findByRole("button", { name: "Load example SYNTH ALPHA|1" }));
    await user.type(screen.getByLabelText(/^storage area$/i), "1");
    await user.click(screen.getByRole("button", { name: "Start my own assessment" }));
    expect(screen.getByText(/replace the inputs you edited/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep my inputs" }));
    expect(screen.getByLabelText(/^storage area$/i)).toHaveValue("201");
    await user.click(screen.getByRole("button", { name: "Start my own assessment" }));
    await user.click(screen.getByRole("button", { name: "Replace my inputs" }));
    expect(screen.queryByRole("region", { name: /synthetic example data/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^top \(z_top\)/i)).toHaveValue("");
  });

  it("reports outside-envelope honestly: no estimate plotted, diagnostic values labelled", async () => {
    vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.example_results });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.click(screen.getByRole("button", { name: "Explore a synthetic example" }));
    await user.click(await screen.findByRole("button", { name: "Load and calculate example SYNTH ALPHA|1" }));
    const region = await results();
    const gamma = within(region).getByRole("article", { name: /outside the validated envelope/i });
    expect(within(gamma).getByText("Outside the model's validated range")).toBeInTheDocument();
    expect(gamma.querySelectorAll(".range-bar")).toHaveLength(0);
    expect(within(gamma).getByText(/diagnostic values \(not estimates\)/i)).toBeInTheDocument();
    const alpha = within(region).getByRole("article", { name: /complete inputs/i });
    expect(alpha.querySelectorAll(".range-bar")).toHaveLength(2);
  });
});

describe("file import", () => {
  function upload(name: string, content: string, type: string) {
    const input = screen.getByLabelText(/data file \(json or csv\)/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File([content], name, { type })] } });
  }

  it("loads a CSV into an editable preview before any calculation", async () => {
    const parse = vi.spyOn(assessment, "parseFile").mockResolvedValue(F.csv_parse);
    const run = vi.spyOn(assessment, "evaluate");
    render(<AssessmentWorkspace />);
    upload("examples.csv", "x", "text/csv");
    expect(await screen.findByText(/4 assessments from examples\.csv/i)).toBeInTheDocument();
    expect(parse.mock.calls[0][0]).toBe("csv");
    expect(run).not.toHaveBeenCalled();
    await userEvent.setup().click(screen.getByRole("button", { name: /SYNTH GAMMA\|1/ }));
    expect(screen.getByLabelText(/^top \(z_top\)/i)).toHaveValue("3450");
  });

  it("shows import problems beside the field with row numbers", async () => {
    vi.spyOn(assessment, "parseFile").mockResolvedValue(F.bad_csv_parse);
    render(<AssessmentWorkspace />);
    upload("bad.csv", "x", "text/csv");
    await userEvent.setup().click(await screen.findByRole("button", { name: /SYNTH BETA\|1/ }));
    expect(screen.getByText(/Row 7: top must be shallower than base/i)).toBeInTheDocument();
  });

  it("rejects an oversized file without sending it", async () => {
    const parse = vi.spyOn(assessment, "parseFile");
    render(<AssessmentWorkspace />);
    upload("big.json", "x".repeat(200_001), "application/json");
    expect(await screen.findByText(/the limit is 200000 bytes/i)).toBeInTheDocument();
    expect(parse).not.toHaveBeenCalled();
  });
});

describe("exports", () => {
  it("downloads the JSON results and CSV summary exactly as returned", async () => {
    vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.example_results });
    const download = vi.spyOn(assessment, "downloadText").mockImplementation(() => {});
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.click(screen.getByRole("button", { name: "Explore a synthetic example" }));
    await user.click(await screen.findByRole("button", { name: "Load and calculate example SYNTH ALPHA|1" }));
    await user.click(await screen.findByRole("button", { name: /download results \(json\)/i }));
    await user.click(screen.getByRole("button", { name: /download summary \(csv\)/i }));
    const [jsonCall, csvCall] = download.mock.calls;
    expect(jsonCall[0]).toBe("ccs-assessment-SYNTHETIC-results.json");
    expect(JSON.parse(jsonCall[1])).toEqual(F.example_results);
    expect(csvCall[1]).toBe(F.example_results.summary_csv);
  });
});

describe("capacity chart", () => {
  it("plots each VALIDATED scenario as a P10-P90 range with a P50 mark, with a table", () => {
    const scenarios = F.user_result.assessments[0].result.water_level_scenarios;
    const { container } = render(<CapacityChart scenarios={scenarios} samples={200} />);
    expect(container.querySelectorAll(".range-bar")).toHaveLength(2);
    expect(container.querySelectorAll(".p50-mark")).toHaveLength(2);
    expect(screen.getByRole("img")).toHaveAccessibleName(/P10 .* P50 .* P90/);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(screen.getByText(/P10 is the low case/)).toBeInTheDocument();
  });

  it("never draws an unavailable scenario as zero", () => {
    const scenarios = F.two_reasons_result.assessments[0].result.water_level_scenarios;
    const { container } = render(<CapacityChart scenarios={scenarios} samples={200} />);
    expect(container.innerHTML).toBe("");
    const mixed = [F.user_result.assessments[0].result.water_level_scenarios[0],
                   F.two_reasons_result.assessments[0].result.water_level_scenarios[1]];
    const r = render(<CapacityChart scenarios={mixed} samples={200} />);
    expect(r.container.querySelectorAll(".range-bar")).toHaveLength(1);
    expect(r.container).toHaveTextContent(/Not plotted: Not available, no estimate/);
    expect(within(r.container).getByRole("table")).toHaveTextContent("no estimate");
  });
});

describe("depth and temperature view", () => {
  it("classifies observations from the API: selected, excluded, eligible", () => {
    const { points, comparable } = observationPoints(F.user_result.assessments[0]);
    expect(comparable).toBe(true);
    expect(points.map((p) => p.status)).toEqual(["excluded", "excluded", "selected"]);
    expect(points[1].reasons).toContain("method not eligible");
    expect(points.every((p) => p.plotted)).toBe(true);
  });

  it("does not overlay observations when the depth reference is not established", () => {
    const item = F.unavailable_result.assessments[0];
    const { points, comparable } = observationPoints(item);
    expect(comparable).toBe(false);
    expect(points.every((p) => !p.plotted && p.status === "not_assessed")).toBe(true);
    render(<DepthTemperatureChart item={item} />);
    expect(screen.getByText(/observations are listed but not overlaid/i)).toBeInTheDocument();
    expect(screen.getAllByText(/not plotted: depth reference not established/i).length).toBe(3);
  });

  it("does not compare TVD observations with an MD interval", () => {
    const { points } = observationPoints(F.md_result.assessments[0]);
    expect(points.every((p) => !p.plotted)).toBe(true);
  });

  it("labels symbols in a legend and provides a table", () => {
    const { container } = render(<DepthTemperatureChart item={F.user_result.assessments[0]} />);
    expect(container.querySelectorAll(".sym-selected").length).toBeGreaterThan(1); // point + legend
    const legend = container.querySelector(".legend")!;
    expect(legend).toHaveTextContent(/Selected.*Eligible.*Excluded/);
    expect(screen.getByRole("table")).toHaveTextContent(/Squarci-Taffi/);
    expect(screen.getByText(/Depth in metres below ground level \(TVD\)/)).toBeInTheDocument();
  });
});

describe("input completeness", () => {
  it("is labelled as completeness, not accuracy, and links to each missing field", async () => {
    render(<InputCompleteness draft={emptyDraft()} index={0} />);
    expect(screen.getByRole("heading", { name: /input completeness: 0 of 6 required inputs ready/i })).toBeInTheDocument();
    expect(screen.getByText(/not an accuracy or confidence score/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Storage area" })).toHaveAttribute("href", "#a0-area");
  });

  it("flags unsupported and unestablished references", () => {
    const items = completeness({ ...emptyDraft(), datum: "rotary_table", convention: "unknown" }, 0);
    expect(items.find((i) => i.key === "datum")?.status).toBe("unsupported");
    expect(items.find((i) => i.key === "convention")?.status).toBe("not_established");
  });

  it("moves focus to the field from the link", async () => {
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.click(screen.getByRole("link", { name: "Go to Total depth" }));
    expect(screen.getByLabelText(/^total depth$/i)).toHaveFocus();
  });
});

describe("draft <-> schema mapping", () => {
  it("round-trips every example without loss", () => {
    for (const a of F.examples.assessments) {
      expect(draftToAssessment(assessmentToDraft(a as Record<string, unknown>))).toEqual(a);
    }
  });

  it("omits empty optional sections and never fills a value", () => {
    const a = draftsToDocument([emptyDraft()]).assessments[0];
    expect(a).not.toHaveProperty("total_depth");
    expect(a).not.toHaveProperty("surface_elevation");
    expect(a.temperature_observations).toEqual([]);
    expect(a.depth_reference).toEqual({ datum: null, convention: null });
  });
});

// -- review 2026-10-02: imports are never silently repaired -------------------------

/** ALPHA alone, with total depth in feet while the interval stays in metres. */
function mixedUnitAlpha(): AssessmentDocument {
  const alpha = JSON.parse(JSON.stringify(F.examples.assessments[0])) as Record<string, any>;
  expect(alpha.example.key).toBe("validated");
  alpha.total_depth = { value: 3000, unit: "ft" };
  return { schema_version: F.examples.schema_version, assessments: [alpha] };
}

const roundTrip = (doc: AssessmentDocument) =>
  draftsToDocument(assessment.documentToDrafts(doc), doc as unknown as Record<string, unknown>);

function uploadParsed(name: string) {
  const input = screen.getByLabelText(/data file \(json or csv\)/i) as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["{}"], name, { type: "application/json" })] } });
}

describe("R1: total depth keeps its own unit", () => {
  it("imports, shows and sends total depth in the file's unit", () => {
    const doc = mixedUnitAlpha();
    const [draft] = assessment.documentToDrafts(doc);
    expect(draft.depth_unit).toBe("m");
    expect(draft.total_depth).toBe("3000");
    expect(draft.total_depth_unit).toBe("ft");
    expect(roundTrip(doc)).toEqual(doc);
  });

  it("keeps the unit when the user edits the total-depth value", () => {
    const [draft] = assessment.documentToDrafts(mixedUnitAlpha());
    const sent = draftToAssessment({ ...draft, total_depth: "3100" }) as Record<string, any>;
    expect(sent.total_depth).toEqual({ value: 3100, unit: "ft" });
    expect(sent.storage_interval.unit).toBe("m");
  });

  it("shows the total-depth unit beside the value in the form", async () => {
    vi.spyOn(assessment, "parseFile").mockResolvedValue({
      format: "json", import_blocked: false, preview_document: null, document: mixedUnitAlpha(), problems: [], valid: true });
    render(<AssessmentWorkspace />);
    uploadParsed("mixed.json");
    await waitFor(() => expect(screen.getByLabelText(/^total depth$/i)).toHaveValue("3000"));
    expect(screen.getByLabelText(/^total depth unit$/i)).toHaveValue("ft");
    expect(screen.getByLabelText(/^depth unit$/i)).toHaveValue("m");
  });

  it("a new manual draft states its total-depth unit explicitly", () => {
    const sent = draftToAssessment({ ...emptyDraft(), depth_unit: "ft", total_depth: "5000",
                                     total_depth_unit: "m" }) as Record<string, any>;
    expect(sent.total_depth).toEqual({ value: 5000, unit: "m" });
    expect(sent.storage_interval.unit).toBe("ft");
  });
});

describe("R2: invalid imports are sent back as imported", () => {
  function alpha(): Record<string, any> {
    return JSON.parse(JSON.stringify(F.examples.assessments[0]));
  }

  it("keeps an unsupported schema version", () => {
    const doc = { schema_version: "ccs-assessment/999", assessments: [alpha()] };
    expect(roundTrip(doc)).toEqual(doc);
  });

  it("keeps a missing schema version missing", () => {
    const doc = { assessments: [alpha()] } as unknown as AssessmentDocument;
    expect(roundTrip(doc)).not.toHaveProperty("schema_version");
    expect(assessment.missingSchemaVersion(doc as unknown as Record<string, unknown>)).toBe(true);
  });

  it("never fills in a missing unit or reference", () => {
    const a = alpha();
    delete a.storage_area.unit;
    delete a.temperature_observations[2].unit;
    delete a.temperature_observations[2].depth_unit;
    delete a.surface_elevation.reference;
    delete a.storage_interval.unit;
    const doc = { schema_version: "ccs-assessment/1", assessments: [a] };
    const [draft] = assessment.documentToDrafts(doc);
    expect(draft.area_unit).toBe("");
    expect(draft.depth_unit).toBe("");
    expect(draft.elevation_reference).toBe("");
    expect(draft.observations[2].unit).toBe("");
    expect(roundTrip(doc)).toEqual(doc);
    // Editing another field still does not invent the unit.
    const sent = draftToAssessment({ ...draft, area: "25" }) as Record<string, any>;
    expect(sent.storage_area).toEqual({ value: 25, source: "fictional" });
    expect(sent.temperature_observations[2]).not.toHaveProperty("unit");
  });

  it("shows a missing unit as a choice to make, not a default", async () => {
    const a = alpha();
    delete a.storage_area.unit;
    vi.spyOn(assessment, "parseFile").mockResolvedValue({ format: "json", import_blocked: false, preview_document: null, valid: false, problems: [],
      document: { schema_version: "ccs-assessment/1", assessments: [a] } });
    render(<AssessmentWorkspace />);
    uploadParsed("no-unit.json");
    await waitFor(() => expect(screen.getByLabelText(/^storage area$/i)).toHaveValue("20"));
    expect(screen.getByLabelText(/^area unit$/i)).toHaveValue("");
  });

  it("shows an unsupported imported value as it is, not as the first option", async () => {
    const a = alpha();
    a.storage_interval.unit = "yd";
    vi.spyOn(assessment, "parseFile").mockResolvedValue({ format: "json", import_blocked: false, preview_document: null, valid: false, problems: [],
      document: { schema_version: "ccs-assessment/1", assessments: [a] } });
    render(<AssessmentWorkspace />);
    uploadParsed("yards.json");
    await waitFor(() => expect(screen.getByLabelText(/^depth unit$/i)).toHaveValue("yd"));
    expect(screen.getByRole("option", { name: /yd \(not supported\)/i })).toBeInTheDocument();
  });

  it("keeps unknown fields at every level", () => {
    const a = alpha();
    a.colour = "blue";
    a.storage_area.porosity = 0.3;
    a.temperature_observations[0].quality = "good";
    const doc = { schema_version: "ccs-assessment/1", extra: true, assessments: [a] } as unknown as AssessmentDocument;
    expect(roundTrip(doc)).toEqual(doc);
    const [draft] = assessment.documentToDrafts(doc);
    const sent = draftToAssessment({ ...draft, area: "25" }) as Record<string, any>;
    expect(sent.colour).toBe("blue");
    expect(sent.storage_area.porosity).toBe(0.3);
  });

  it("removes unknown fields only on the user's explicit request, keeping edits", () => {
    const a = alpha();
    a.colour = "blue";
    a.storage_area.porosity = 0.3;
    a.temperature_observations[0].quality = "good";
    const base = { schema_version: "ccs-assessment/1", extra: true, assessments: [a] };
    const drafts = assessment.documentToDrafts(base as unknown as AssessmentDocument);
    drafts[0] = { ...drafts[0], area: "25" };
    const fixed = assessment.withoutUnknownFields(base, drafts);
    const doc = draftsToDocument(fixed.drafts, fixed.base) as unknown as Record<string, any>;
    expect(doc).not.toHaveProperty("extra");
    expect(doc.assessments[0]).not.toHaveProperty("colour");
    expect(doc.assessments[0].storage_area).toEqual({ value: 25, unit: "km2", source: "fictional" });
    expect(doc.assessments[0].temperature_observations[0]).not.toHaveProperty("quality");
  });

  it("offers the unknown-field removal as a button and applies it only when pressed", async () => {
    const a = alpha();
    a.colour = "blue";
    const doc = { schema_version: "ccs-assessment/1", assessments: [a] };
    const problems: Problem[] = [{ path: "assessments[0]", row: null, code: "UNKNOWN_FIELD",
      message: "unknown field(s): colour", severity: "error" }];
    vi.spyOn(assessment, "parseFile").mockResolvedValue({ format: "json", import_blocked: false, preview_document: null, document: doc, problems, valid: false });
    const run = vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: false, problems });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    uploadParsed("colour.json");
    const remove = await screen.findByRole("button", { name: /remove unrecognised fields/i });
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    expect((run.mock.calls[0][0].assessments[0] as Record<string, unknown>).colour).toBe("blue");
    await user.click(remove);
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    expect(run.mock.calls[1][0].assessments[0]).not.toHaveProperty("colour");
  });

  it("keeps wrong types as imported", () => {
    const a = alpha();
    a.storage_area.value = "twenty";
    a.total_depth.value = true;
    a.storage_interval = "1450-1550";
    const doc = { schema_version: "ccs-assessment/1", assessments: [a] };
    expect(roundTrip(doc)).toEqual(doc);
  });

  it("handles a null observation and a null assessment without throwing", () => {
    const a = alpha();
    a.temperature_observations.push(null);
    const doc = { schema_version: "ccs-assessment/1", assessments: [a, null] } as unknown as AssessmentDocument;
    const drafts = assessment.documentToDrafts(doc);
    expect(drafts).toHaveLength(2);
    expect(drafts[0].observations).toHaveLength(4);
    expect(roundTrip(doc)).toEqual(doc);
    // Filling the null observation in turns it into a real one.
    const edited = { ...drafts[0], observations: drafts[0].observations.map((o, i) =>
      i === 3 ? { ...o, value: "60", unit: "degC" } : o) };
    const sent = draftToAssessment(edited) as Record<string, any>;
    expect(sent.temperature_observations[3]).toEqual({ value: 60, unit: "degC" });
  });

  it("renders an import with a null observation as an editable preview", async () => {
    const a = alpha();
    a.temperature_observations.push(null);
    vi.spyOn(assessment, "parseFile").mockResolvedValue({ format: "json", import_blocked: false, preview_document: null, valid: false, problems: [],
      document: { schema_version: "ccs-assessment/1", assessments: [a] } });
    render(<AssessmentWorkspace />);
    uploadParsed("null-obs.json");
    expect(await screen.findByRole("group", { name: "Observation 4" })).toBeInTheDocument();
  });

  it("keeps a non-list observations field until the user adds an observation", () => {
    const a = alpha();
    a.temperature_observations = { value: 58 };
    const doc = { schema_version: "ccs-assessment/1", assessments: [a] };
    expect(roundTrip(doc)).toEqual(doc);
  });

  it("removing an imported observation removes only that observation", () => {
    const doc = { schema_version: "ccs-assessment/1", assessments: [alpha()] };
    const [draft] = assessment.documentToDrafts(doc);
    const sent = draftToAssessment({ ...draft, observations: draft.observations.slice(1) }) as Record<string, any>;
    expect(sent.temperature_observations).toEqual(alpha().temperature_observations.slice(1));
  });

  it("Calculate sends the imported document, so its problems stay in force", async () => {
    const doc = { schema_version: "ccs-assessment/999", assessments: [alpha()] };
    const problems: Problem[] = [{ path: "schema_version", row: null, code: "UNSUPPORTED_SCHEMA_VERSION",
      message: "unsupported schema_version 'ccs-assessment/999'; supported: ccs-assessment/1", severity: "error" }];
    vi.spyOn(assessment, "parseFile").mockResolvedValue({ format: "json", import_blocked: false, preview_document: null, document: doc, problems, valid: false });
    const run = vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: false, problems });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    uploadParsed("v999.json");
    expect(await screen.findByText(/unsupported schema_version/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    expect(run.mock.calls[0][0]).toEqual(doc);
    expect(screen.getByText(/unsupported schema_version/i)).toBeInTheDocument();
  });

  it("a file that cannot be opened for editing leaves the current inputs alone", async () => {
    vi.spyOn(assessment, "parseFile").mockResolvedValue({ format: "json", import_blocked: false, preview_document: null, document: null, valid: false,
      problems: [{ path: "", row: null, code: "INVALID_JSON", message: "not valid JSON", severity: "error" }] });
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.type(screen.getByLabelText(/^storage area$/i), "42");
    uploadParsed("broken.json");
    expect(await screen.findByText(/not valid JSON/i)).toBeInTheDocument();
    expect(screen.getByText(/broken\.json was not loaded/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^storage area$/i)).toHaveValue("42");
  });
});

describe("R4: a delayed file import never overwrites newer work", () => {
  function docWithArea(id: string, area: number): AssessmentDocument {
    const a = JSON.parse(JSON.stringify(F.examples.assessments[0])) as Record<string, any>;
    a.id = id;
    a.storage_area.value = area;
    return { schema_version: "ccs-assessment/1", assessments: [a] };
  }
  const parsed = (doc: AssessmentDocument): ParseResponse => ({ format: "json", import_blocked: false, preview_document: null, document: doc, problems: [], valid: true });

  it("drops a parse that finishes after the user edited", async () => {
    let release!: (v: ParseResponse) => void;
    vi.spyOn(assessment, "parseFile").mockReturnValue(new Promise((r) => (release = r)));
    render(<AssessmentWorkspace />);
    uploadParsed("slow.json");
    await waitFor(() => expect(assessment.parseFile).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText(/^storage area$/i), { target: { value: "7" } });
    release(parsed(docWithArea("SLOW", 99)));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.getByLabelText(/^storage area$/i)).toHaveValue("7");
    expect(screen.getByLabelText(/^assessment id$/i)).toHaveValue("MY-SITE-1");
  });

  it("keeps the newer file when two parses finish out of order", async () => {
    const releases: ((v: ParseResponse) => void)[] = [];
    vi.spyOn(assessment, "parseFile").mockImplementation(() => new Promise((r) => releases.push(r)));
    render(<AssessmentWorkspace />);
    uploadParsed("first.json");
    await waitFor(() => expect(releases).toHaveLength(1));
    uploadParsed("second.json");
    await waitFor(() => expect(releases).toHaveLength(2));
    releases[1](parsed(docWithArea("SECOND", 2)));
    await waitFor(() => expect(screen.getByLabelText(/^assessment id$/i)).toHaveValue("SECOND"));
    releases[0](parsed(docWithArea("FIRST", 1)));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.getByLabelText(/^assessment id$/i)).toHaveValue("SECOND");
    expect(screen.getByLabelText(/^storage area$/i)).toHaveValue("2");
  });

  it("drops a parse that finishes after an example was loaded", async () => {
    let release!: (v: ParseResponse) => void;
    vi.spyOn(assessment, "parseFile").mockReturnValue(new Promise((r) => (release = r)));
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    uploadParsed("slow.json");
    await waitFor(() => expect(assessment.parseFile).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /explore a synthetic example/i }));
    await user.click(await screen.findByRole("button", { name: /^load example SYNTH BETA\|1$/i }));
    release(parsed(docWithArea("SLOW", 99)));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.getByLabelText(/^assessment id$/i)).toHaveValue("SYNTH BETA|1");
  });
});

describe("R3: the chart marks the observation the engine selected", () => {
  it("tells apart readings that differ only in datum", () => {
    const reading = { temperature_k: 331.15, depth_m: 1500, depth_convention: "TVD",
      method: "extrapolated_squarci_taffi", eligible_method: true, passed_to_engine: true };
    const engine = { depth_m: 1500, temperature_k: 331.15, method: "extrapolated_squarci_taffi" };
    const base = F.user_result.assessments[0];
    const item = {
      ...base,
      inputs: { ...base.inputs, depth_reference: { datum: "ground_level", convention: "TVD" },
        temperature_observations: [
          { ...reading, index: 0, depth_datum: "ground_level" },
          { ...reading, index: 1, depth_datum: "msl" },
        ] },
      result: { ...base.result, temperature_selection: {
        evaluated: true,
        selected_observation: { ...engine, depth_datum: "ground_level", input_index: 0 },
        eligible_observations: [{ ...engine, depth_datum: "ground_level", input_index: 0 }],
        excluded_observations: [{ ...engine, depth_datum: "msl", input_index: 1,
                                  reasons: ["UNSUPPORTED_DEPTH_DATUM"] }],
      } },
    } as typeof base;
    const { points } = observationPoints(item);
    expect(points.map((p) => p.status)).toEqual(["selected", "excluded"]);
    expect(points[0].reasons).toEqual([]);
    expect(points[1].reasons).toEqual(["depth not from ground level"]);
  });
});

// -- review 2026-10-02 (verification): CSV parser errors cannot be bypassed --------------

describe("R2 (CSV): a file the parser could not read faithfully blocks calculation", () => {
  const blocked = (fixtures as unknown as { blocked_csv_parse: ParseResponse }).blocked_csv_parse;

  function uploadCsv(name: string) {
    const input = screen.getByLabelText(/data file \(json or csv\)/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], name, { type: "text/csv" })] } });
  }

  async function loadBlocked() {
    vi.spyOn(assessment, "parseFile").mockResolvedValue(blocked);
    const run = vi.spyOn(assessment, "evaluate").mockResolvedValue({ ok: true, data: F.example_results });
    render(<AssessmentWorkspace />);
    uploadCsv("conflict.csv");
    await screen.findByText(/calculation is blocked/i);
    return run;
  }

  it("is the real parser's verdict for conflicting rows", () => {
    expect(blocked.import_blocked).toBe(true);
    expect(blocked.problems.map((p) => [p.code, p.row])).toEqual([["CONFLICTING_VALUE", 5]]);
  });

  it("keeps the row problem visible and disables Calculate", async () => {
    await loadBlocked();
    expect(screen.getByText(/Row 5: .*area_value is '999' here but '20'/i)).toBeInTheDocument();
    expect(screen.getByText(/correct the file and upload it again/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^calculate/i })).toBeDisabled();
  });

  it("cannot be bypassed by submitting the form", async () => {
    const run = await loadBlocked();
    fireEvent.submit(screen.getByRole("button", { name: /^calculate/i }).closest("form")!);
    await new Promise((r) => setTimeout(r, 0));
    expect(run).not.toHaveBeenCalled();
  });

  it("stays blocked after an unrelated edit", async () => {
    const run = await loadBlocked();
    fireEvent.change(screen.getByLabelText(/^storage area$/i), { target: { value: "999" } });
    expect(screen.getByRole("button", { name: /^calculate/i })).toBeDisabled();
    expect(screen.getByText(/calculation is blocked/i)).toBeInTheDocument();
    fireEvent.submit(screen.getByRole("button", { name: /^calculate/i }).closest("form")!);
    await new Promise((r) => setTimeout(r, 0));
    expect(run).not.toHaveBeenCalled();
    expect(screen.getByText(/Row 5: /i)).toBeInTheDocument();
  });

  it("a corrected re-upload unblocks calculation", async () => {
    const run = await loadBlocked();
    vi.spyOn(assessment, "parseFile").mockResolvedValue(F.csv_parse);
    uploadCsv("fixed.csv");
    await waitFor(() => expect(screen.queryByText(/calculation is blocked/i)).not.toBeInTheDocument());
    const calc = screen.getByRole("button", { name: /^calculate/i });
    expect(calc).toBeEnabled();
    await userEvent.setup().click(calc);
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("a fresh manual assessment or a loaded example unblocks", async () => {
    await loadBlocked();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /enter my data/i }));
    expect(screen.queryByText(/calculation is blocked/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^calculate/i })).toBeEnabled();

    vi.spyOn(assessment, "parseFile").mockResolvedValue(blocked);
    uploadCsv("conflict.csv");
    await screen.findByText(/calculation is blocked/i);
    await user.click(screen.getByRole("button", { name: /explore a synthetic example/i }));
    await user.click(await screen.findByRole("button", { name: /^load example SYNTH BETA\|1$/i }));
    expect(screen.queryByText(/calculation is blocked/i)).not.toBeInTheDocument();
  });
});

describe("R2 (CSV): the blocked preview carries the backend's marker", () => {
  const blocked = (fixtures as unknown as { blocked_csv_parse: ParseResponse }).blocked_csv_parse;

  it("is returned as a preview, never as an evaluatable document", () => {
    expect(blocked.document).toBeNull();
    const marker = (blocked.preview_document as unknown as Record<string, any>).blocked_import;
    expect(marker.problems.map((p: Problem) => [p.code, p.row])).toEqual([["CONFLICTING_VALUE", 5]]);
  });

  it("keeps the marker through the draft mapping, edits and explicit corrections", () => {
    const preview = blocked.preview_document!;
    const base = preview as unknown as Record<string, unknown>;
    const drafts = assessment.documentToDrafts(preview);
    drafts[0] = { ...drafts[0], area: "999" };
    const sent = draftsToDocument(drafts, base) as unknown as Record<string, unknown>;
    expect(sent.blocked_import).toEqual(base.blocked_import);
    const fixed = assessment.withoutUnknownFields(base, drafts);
    expect(assessment.isBlockedPreview(fixed.base)).toBe(true);
    expect((draftsToDocument(fixed.drafts, fixed.base) as unknown as Record<string, unknown>).blocked_import)
      .toEqual(base.blocked_import);
  });
});

describe("public-deployment limits are explained, not reported as internal errors", () => {
  const respond = (status: number, body: object) =>
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status }));

  it("a 429 says the request limit was reached", async () => {
    respond(429, { error: "too many requests: at most 20 per minute per client", type: "RateLimited" });
    await expect(assessment.evaluate(F.user_document)).rejects.toMatchObject({
      kind: "rate_limited", status: 429, message: expect.stringMatching(/at most 20 per minute/) });
  });

  it("a 503 ServerBusy says the server is busy", async () => {
    respond(503, { error: "the server is busy with other calculations; try again shortly", type: "ServerBusy" });
    await expect(assessment.evaluate(F.user_document)).rejects.toMatchObject({
      kind: "busy", status: 503, message: expect.stringMatching(/busy/) });
  });

  it("other 5xx stay generic and never echo server text", async () => {
    respond(500, { error: "internal server error", type: "InternalServerError" });
    await expect(assessment.evaluate(F.user_document)).rejects.toMatchObject({ kind: "server" });
  });
});

describe("when the calculation service is unreachable", () => {
  it("the examples panel says so and offers a retry instead of loading forever", async () => {
    const get = vi.spyOn(assessment, "getExamples")
      .mockRejectedValueOnce(new api.ApiClientError("Cannot reach the calculation service.", 0, "network"))
      .mockResolvedValueOnce(F.examples);
    const user = userEvent.setup();
    render(<AssessmentWorkspace />);
    await user.click(screen.getByRole("button", { name: /explore a synthetic example/i }));
    expect(await screen.findByText(/examples could not be loaded/i)).toBeInTheDocument();
    expect(screen.queryByText(/loading examples/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("button", { name: /^load example SYNTH ALPHA\|1$/i })).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("the network message tells a visitor what to do", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(assessment.evaluate(F.user_document)).rejects.toMatchObject({
      kind: "network", message: expect.stringMatching(/may be starting up.*try again/i) });
  });
});
