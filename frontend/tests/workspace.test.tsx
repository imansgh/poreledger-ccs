/**
 * Contract behaviour of the screening UI.
 *
 * These do not re-test the backend. They test the things a frontend can break
 * on its own: showing a number without its provenance, merging the four
 * buckets, hiding a warning, inventing a default, or rendering a capacity for a
 * blocked well.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ScreeningWorkspace } from "@/components/ScreeningWorkspace";
import * as api from "@/lib/api";
import { ApiClientError } from "@/lib/api";
import {
  blocked,
  requiredInputs,
  scenarios,
  screened,
  temperatureComparison,
  wellDetail,
  wells,
} from "./fixtures";

function stubHappyPath() {
  vi.spyOn(api, "listWells").mockResolvedValue(wells);
  vi.spyOn(api, "listScenarios").mockResolvedValue(scenarios);
  vi.spyOn(api, "getWell").mockResolvedValue(wellDetail);
  vi.spyOn(api, "getRequiredInputs").mockResolvedValue(requiredInputs);
}

async function selectSaluzzo(user: ReturnType<typeof userEvent.setup>) {
  const button = await screen.findByRole("button", { name: /SALUZZO\|1/ });
  await user.click(button);
  await screen.findByRole("heading", { name: /source data/i });
}

async function fillInputs(
  user: ReturnType<typeof userEvent.setup>,
  areaKm2 = "80",
  thickness = "35",
) {
  await user.type(screen.getByLabelText(/storage area/i), areaKm2);
  await user.type(screen.getByLabelText(/net reservoir thickness/i), thickness);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("well list and selection", () => {
  it("renders the wells returned by the API", async () => {
    stubHappyPath();
    render(<ScreeningWorkspace />);
    expect(await screen.findByRole("button", { name: /SALUZZO\|1/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /CRESCENTINO\|1/ })).toBeInTheDocument();
  });

  it("filters wells by id", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await screen.findByRole("button", { name: /SALUZZO\|1/ });
    await user.type(screen.getByLabelText(/filter by well id/i), "cresc");
    expect(screen.queryByRole("button", { name: /SALUZZO\|1/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /CRESCENTINO\|1/ })).toBeInTheDocument();
  });

  it("shows source detail for the selected well", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getByText("extrapolated_squarci_taffi")).toBeInTheDocument();
    expect(screen.getByText(/1,527.5 m/)).toBeInTheDocument();
  });

  it("shows Not available rather than inventing a value", async () => {
    stubHappyPath();
    vi.spyOn(api, "getWell").mockResolvedValue({
      ...wellDetail,
      fields: { ...wellDetail.fields, temperature_k: { value: null, unit: "K", provenance: "missing", confidence: "none" } },
    });
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
  });
});

describe("required user inputs", () => {
  it("has no default area or thickness", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getByLabelText(/storage area/i)).toHaveValue(null);
    expect(screen.getByLabelText(/net reservoir thickness/i)).toHaveValue(null);
  });

  it("requires area before screening", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await user.type(screen.getByLabelText(/net reservoir thickness/i), "35");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText(/storage area is required/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("requires net reservoir thickness before screening", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await user.type(screen.getByLabelText(/storage area/i), "80");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(
      await screen.findByText(/net reservoir thickness is required/i),
    ).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("rejects zero and negative values", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user, "0", "35");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText(/must be greater than 0/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("states that net thickness is not inferred from gross thickness", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(
      screen.getByText(/not inferred from gross stratigraphic thickness/i),
    ).toBeInTheDocument();
  });

  it("converts area from km2 to m2 before calling the API", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user, "80", "35");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][1]).toEqual({ area_m2: 80_000_000, thickness_m: 35 });
  });
});

describe("successful screening", () => {
  async function renderScreened() {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByRole("heading", { name: /^result$/i });
    return user;
  }

  it("shows P50 as the headline with the scenario-based wording", async () => {
    await renderScreened();
    const label = screen.getByText(/scenario-based storage capacity \(P50\)/i);
    expect(label).toBeInTheDocument();
    // The headline value sits next to its label; P50 also appears in the
    // percentile row, so scope rather than matching globally.
    const head = label.closest(".result-head") as HTMLElement;
    expect(within(head).getByText("10.6")).toBeInTheDocument();
  });

  it("shows P10, P90, mean and sample count", async () => {
    await renderScreened();
    expect(screen.getByText("P10")).toBeInTheDocument();
    expect(screen.getByText("P90")).toBeInTheDocument();
    expect(screen.getByText("5.2")).toBeInTheDocument();
    expect(screen.getByText("20.3")).toBeInTheDocument();
    expect(screen.getByText("2,000")).toBeInTheDocument();
  });

  it("states that the result is not site-specific or certified", async () => {
    await renderScreened();
    // Wording lives in the prominent qualifier beside the headline number.
    expect(
      screen.getByText(/not a site-specific or certified storage capacity/i),
    ).toBeInTheDocument();
  });

  it("never claims the result is proven or certified", async () => {
    await renderScreened();
    const body = (document.body.textContent ?? "").toLowerCase();
    // These phrases appear legitimately inside denials ("not a site-specific
    // or certified storage capacity"), so assert that any sentence containing
    // one also contains a negation, rather than asserting absence.
    for (const phrase of ["proven storage", "certified storage"]) {
      for (const sentence of body.split(".")) {
        if (sentence.includes(phrase)) {
          expect(sentence.includes("not ")).toBe(true);
        }
      }
    }
    // The headline wording itself is scenario-based only.
    expect(screen.getByText(/scenario-based storage capacity/i)).toBeInTheDocument();
    expect(body).not.toMatch(/certified capacity/);
    expect(body).not.toMatch(/proven resource of/);
  });
});

describe("provenance partition", () => {
  async function renderProvenance() {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    return screen.findByRole("region", { name: /provenance of every screening input/i });
  }

  it("renders all four buckets as separate sections", async () => {
    const panel = await renderProvenance();
    for (const heading of [
      "Source-derived",
      "Modelled",
      "Literature-constrained",
      "User input",
    ]) {
      expect(within(panel).getByRole("heading", { name: heading })).toBeInTheDocument();
    }
  });

  it("labels each input with a text tag, not colour alone", async () => {
    const panel = await renderProvenance();
    expect(within(panel).getAllByText("SOURCE").length).toBeGreaterThan(0);
    expect(within(panel).getAllByText("MODELLED").length).toBeGreaterThan(0);
    expect(within(panel).getAllByText("ASSUMED").length).toBeGreaterThan(0);
    expect(within(panel).getAllByText("USER INPUT").length).toBeGreaterThan(0);
  });

  it("puts each input in exactly one bucket", async () => {
    const panel = await renderProvenance();
    // Six required inputs, each rendered once as a card heading.
    const names = [
      "Temperature",
      "Pressure",
      "Porosity",
      "Storage efficiency",
      "Storage area",
      "Net reservoir thickness",
    ];
    for (const name of names) {
      expect(within(panel).getAllByText(name)).toHaveLength(1);
    }
  });

  it("shows the citation for a literature-constrained input", async () => {
    const panel = await renderProvenance();
    expect(within(panel).getByText(/Donda.*\(2011\)/)).toBeInTheDocument();
    expect(within(panel).getByText(/CSLF Task Force \(2008\)/)).toBeInTheDocument();
  });

  it("shows the derivation for the modelled pressure", async () => {
    const panel = await renderProvenance();
    expect(within(panel).getByText(/P = rho\*g\*z/)).toBeInTheDocument();
  });

  it("marks user input as supplied for this run", async () => {
    const panel = await renderProvenance();
    // Both user inputs carry the same rationale wording.
    expect(within(panel).getAllByText(/supplied by the caller/i)).toHaveLength(2);
  });
});

describe("warnings", () => {
  it("shows the scale mismatch advisory in flow", async () => {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(
      await screen.findByText(
        /Literature-constrained porosity and storage-efficiency ranges are not site-specific closure-scale calibrations/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/scale_mismatch_basin_vs_closure/)).toBeInTheDocument();
    expect(screen.getByText(/does not invalidate the result/i)).toBeInTheDocument();
  });
});

describe("blocked wells", () => {
  it("shows Screening unavailable and no capacity", async () => {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(blocked);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));

    expect(await screen.findByText(/screening unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/scenario-based storage capacity/i)).not.toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("explains that temperature is non-assumable", async () => {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(blocked);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(
      await screen.findByText(/temperature is intentionally non-assumable/i),
    ).toBeInTheDocument();
  });

  it("renders no provenance panel when blocked", async () => {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(blocked);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByText(/screening unavailable/i);
    expect(
      screen.queryByRole("region", { name: /provenance of every screening input/i }),
    ).not.toBeInTheDocument();
  });
});

describe("error handling", () => {
  it("surfaces a 422 validation message without a stack trace", async () => {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockRejectedValue(
      new ApiClientError("user_inputs.area_m2: Input should be greater than 0", 422, "validation"),
    );
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText(/Input should be greater than 0/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Traceback|at Object\./);
  });

  it("surfaces an unknown well as a readable message", async () => {
    stubHappyPath();
    vi.spyOn(api, "getWell").mockRejectedValue(
      new ApiClientError("no well with id 'NOPE|9'", 404, "not_found"),
    );
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    const button = await screen.findByRole("button", { name: /SALUZZO\|1/ });
    await user.click(button);
    expect(await screen.findByText(/no well with id/i)).toBeInTheDocument();
  });

  it("reports a backend that is not running", async () => {
    vi.spyOn(api, "listWells").mockRejectedValue(
      new ApiClientError("Cannot reach the screening backend", 0, "network"),
    );
    vi.spyOn(api, "listScenarios").mockRejectedValue(
      new ApiClientError("Cannot reach the screening backend", 0, "network"),
    );
    render(<ScreeningWorkspace />);
    expect(await screen.findByText(/cannot reach the screening backend/i)).toBeInTheDocument();
  });

  it("ignores a slow response for a well that is no longer selected", async () => {
    stubHappyPath();
    let resolveSlow: (value: typeof wellDetail) => void = () => {};
    const slow = new Promise<typeof wellDetail>((resolve) => {
      resolveSlow = resolve;
    });
    const other = { ...wellDetail, canonical_id: "CRESCENTINO|1" };
    vi.spyOn(api, "getWell").mockImplementation((id: string) =>
      id === "SALUZZO|1" ? slow : Promise.resolve(other),
    );
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await user.click(await screen.findByRole("button", { name: /SALUZZO\|1/ }));
    await user.click(screen.getByRole("button", { name: /CRESCENTINO\|1/ }));
    await screen.findByRole("heading", { name: /source data/i });

    resolveSlow(wellDetail);
    await slow;
    await new Promise((r) => setTimeout(r, 0));
    expect(api.getWell).toHaveBeenCalledWith("SALUZZO|1");
    expect(screen.getByText("CRESCENTINO|1", { selector: "dd" })).toBeInTheDocument();
    expect(screen.queryByText("SALUZZO|1", { selector: "dd" })).not.toBeInTheDocument();
  });

  it("re-fetches required inputs and drops the result when the scenario changes", async () => {
    stubHappyPath();
    const other = {
      ...scenarios[0],
      name: "central-placeholder",
      aliases: ["central"],
      literature_derived: false,
    };
    vi.spyOn(api, "listScenarios").mockResolvedValue([...scenarios, other]);
    vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByText(/scenario-based storage capacity/i);

    await user.selectOptions(screen.getByLabelText(/screening scenario/i), other.name);
    await waitFor(() =>
      expect(api.getRequiredInputs).toHaveBeenLastCalledWith("SALUZZO|1", other.name),
    );
    expect(screen.queryByText(/scenario-based storage capacity/i)).not.toBeInTheDocument();
  });

  it("clears a stale result when another well is selected", async () => {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByText(/scenario-based storage capacity/i);

    await user.click(screen.getByRole("button", { name: /CRESCENTINO\|1/ }));
    await waitFor(() =>
      expect(screen.queryByText(/scenario-based storage capacity/i)).not.toBeInTheDocument(),
    );
  });
});

describe("temperature comparison", () => {
  it("lists each method without declaring one correct", async () => {
    stubHappyPath();
    vi.spyOn(api, "compareTemperatureMethods").mockResolvedValue(temperatureComparison);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /compare temperature methods/i }));

    const table = await screen.findByRole("table");
    expect(within(table).getByText("extrapolated_squarci_taffi")).toBeInTheDocument();
    expect(within(table).getByText("non_stabilized")).toBeInTheDocument();
    expect(screen.getByText(/no method is authoritative/i)).toBeInTheDocument();
  });
});

describe("prominent scientific qualifier", () => {
  async function renderScreened() {
    stubHappyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByRole("heading", { name: /^result$/i });
  }

  it("shows the qualifier next to the headline number", async () => {
    await renderScreened();
    const qualifier = screen.getByText(
      /Scenario-based screening estimate - not a site-specific or certified storage capacity/i,
    );
    expect(qualifier).toBeInTheDocument();
    // It must sit inside the result head, beside the number, not further down.
    const head = qualifier.closest(".result-head");
    expect(head).not.toBeNull();
    expect(within(head as HTMLElement).getByText("10.6")).toBeInTheDocument();
  });

  it("names area and net thickness as user-supplied", async () => {
    await renderScreened();
    expect(
      screen.getByText(/Area and net reservoir thickness are user-supplied inputs/i),
    ).toBeInTheDocument();
  });

  it("needs no disclosure control to be visible", async () => {
    await renderScreened();
    const qualifier = screen.getByText(/Scenario-based screening estimate/i);
    // No <details>/<summary> ancestor, and nothing hidden.
    expect(qualifier.closest("details")).toBeNull();
    expect(qualifier.closest("[hidden]")).toBeNull();
    expect(qualifier).toBeVisible();
  });

  it("keeps the provenance panel as well", async () => {
    await renderScreened();
    expect(
      screen.getByRole("region", { name: /provenance of every screening input/i }),
    ).toBeInTheDocument();
  });
});

describe("loading state", () => {
  function deferredScreen() {
    let resolve!: (value: typeof screened) => void;
    const pending = new Promise<typeof screened>((r) => {
      resolve = r;
    });
    vi.spyOn(api, "screenWell").mockReturnValue(pending as never);
    return resolve;
  }

  it("disables the run button, marks the region busy and hides any stale result", async () => {
    stubHappyPath();
    const firstRun = vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);

    // First run completes so there is a stale result to hide.
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByText(/scenario-based storage capacity/i);
    firstRun.mockRestore();

    const release = deferredScreen();
    await user.click(screen.getByRole("button", { name: /run screening/i }));

    expect(await screen.findByText(/running screening/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /running/i })).toBeDisabled();
    expect(
      document.querySelector('[aria-busy="true"]'),
      "result region must be marked busy",
    ).not.toBeNull();
    expect(
      screen.queryByText(/scenario-based storage capacity/i),
      "a stale number must not sit beside a running request",
    ).not.toBeInTheDocument();

    release(screened);
    await screen.findByText(/scenario-based storage capacity/i);
  });

  it("announces the loading state to assistive technology", async () => {
    stubHappyPath();
    const release = deferredScreen();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByRole("status")).toHaveTextContent(/running screening/i);
    release(screened);
    await screen.findByText(/scenario-based storage capacity/i);
  });
});
