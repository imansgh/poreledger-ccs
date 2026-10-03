/**
 * Contract behaviour of the screening UI.
 *
 * These do not re-test the backend. They test the things a frontend can break
 * on its own: showing a number without its provenance, merging the four
 * buckets, hiding a warning, inventing a default, rendering a capacity for a
 * blocked well, computing a scientific value, or presenting a NOT_VALIDATED
 * legacy result as validated.
 *
 * Phase 14: the default scenario runs the approved model (inputs area_m2,
 * z_top, z_base; both named water-level scenarios with their statuses). The
 * original legacy-path tests run against a NOT_VALIDATED placeholder scenario
 * with its unchanged inputs (area_m2, thickness_m).
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectIntro } from "@/components/AboutSections";
import { ScreeningWorkspace } from "@/components/ScreeningWorkspace";
import * as api from "@/lib/api";
import { ApiClientError } from "@/lib/api";
import {
  approvedBlocked,
  approvedMixed,
  approvedUnavailable,
  approvedValidated,
  blocked,
  demoDataset,
  demoHealth,
  realHealth,
  legacyRequiredInputs,
  legacyScenario,
  requiredInputs,
  scenarios,
  screened,
  temperatureComparison,
  wellDetail,
  wells,
} from "./fixtures";

type User = ReturnType<typeof userEvent.setup>;

/** Approved model: the default scenario. */
function stubHappyPath() {
  vi.spyOn(api, "listWells").mockResolvedValue(wells);
  vi.spyOn(api, "listScenarios").mockResolvedValue(scenarios);
  vi.spyOn(api, "getWell").mockResolvedValue(wellDetail);
  vi.spyOn(api, "getRequiredInputs").mockResolvedValue(requiredInputs);
}

/** A NOT_VALIDATED legacy scenario is the only one offered, so it is selected. */
function stubLegacyPath() {
  vi.spyOn(api, "listWells").mockResolvedValue(wells);
  vi.spyOn(api, "listScenarios").mockResolvedValue([legacyScenario]);
  vi.spyOn(api, "getWell").mockResolvedValue(wellDetail);
  vi.spyOn(api, "getRequiredInputs").mockResolvedValue(legacyRequiredInputs);
}

async function selectSaluzzo(user: User) {
  const button = await screen.findByRole("button", { name: /SALUZZO\|1/ });
  await user.click(button);
  await screen.findByRole("heading", { name: /source data/i });
}

/** Legacy inputs. */
async function fillInputs(user: User, areaKm2 = "80", thickness = "35") {
  await user.type(screen.getByLabelText(/storage area/i), areaKm2);
  await user.type(screen.getByLabelText(/net reservoir thickness/i), thickness);
}

/** Approved-model inputs. */
async function fillApproved(user: User, areaKm2 = "80", top = "1400", base = "1527") {
  await user.type(screen.getByLabelText(/storage area/i), areaKm2);
  await user.type(screen.getByLabelText(/z_top/i), top);
  await user.type(screen.getByLabelText(/z_base/i), base);
}

async function runApproved(result = approvedValidated) {
  stubHappyPath();
  const spy = vi.spyOn(api, "screenWell").mockResolvedValue(result);
  const user = userEvent.setup();
  render(<ScreeningWorkspace />);
  await selectSaluzzo(user);
  await fillApproved(user);
  await user.click(screen.getByRole("button", { name: /run screening/i }));
  await screen.findByRole("heading", { name: /^result$/i });
  return { user, spy };
}

beforeEach(() => {
  vi.restoreAllMocks();
  // Never reach for a real backend: the dataset is the real-sources one
  // unless a test says otherwise.
  vi.spyOn(api, "getHealth").mockResolvedValue(realHealth);
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

  it("shows the approved-model depth reference status as the API reports it", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(
      screen.getByText("UNAVAILABLE (DEPTH_REFERENCE_NOT_ESTABLISHED)"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Blocked: depth_datum/)).toBeInTheDocument();
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

describe("required user inputs -- approved model", () => {
  it("asks for area and the storage interval, never a thickness", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getByLabelText(/storage area/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/z_top/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/z_base/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/net reservoir thickness/i)).not.toBeInTheDocument();
  });

  it("has no default area or interval", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getByLabelText(/storage area/i)).toHaveValue(null);
    expect(screen.getByLabelText(/z_top/i)).toHaveValue(null);
    expect(screen.getByLabelText(/z_base/i)).toHaveValue(null);
  });

  it("requires area before screening", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(approvedValidated);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await user.type(screen.getByLabelText(/z_top/i), "1400");
    await user.type(screen.getByLabelText(/z_base/i), "1527");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText(/storage area is required/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("requires both interval bounds before screening", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(approvedValidated);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await user.type(screen.getByLabelText(/storage area/i), "80");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText(/z_top\) is required/i)).toBeInTheDocument();
    expect(screen.getByText(/z_base\) is required/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("rejects a negative top and a base that is not deeper than the top", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(approvedValidated);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillApproved(user, "80", "-5", "1527");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText(/must be 0 or greater/i)).toBeInTheDocument();
    await user.clear(screen.getByLabelText(/z_top/i));
    await user.type(screen.getByLabelText(/z_top/i), "1600");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText(/must be deeper than z_top/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("sends exactly area (converted to m2), z_top and z_base -- nothing derived", async () => {
    const { spy } = await runApproved();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][1]).toEqual({ area_m2: 80_000_000, z_top: 1400, z_base: 1527 });
    expect(spy.mock.calls[0][2]).toBe("literature-screening-v1");
  });

  it("states that the interval is not inferred from total depth", async () => {
    stubHappyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(
      screen.getByText(/not inferred from total depth or stratigraphic units/i),
    ).toBeInTheDocument();
  });
});

describe("required user inputs -- legacy scenario (NOT_VALIDATED)", () => {
  it("has no default area or thickness", async () => {
    stubLegacyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getByLabelText(/storage area/i)).toHaveValue(null);
    expect(screen.getByLabelText(/net reservoir thickness/i)).toHaveValue(null);
    expect(screen.queryByLabelText(/z_top/i)).not.toBeInTheDocument();
  });

  it("marks the scenario NOT_VALIDATED at the point of entry", async () => {
    stubLegacyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getByText("NOT_VALIDATED legacy scenario")).toBeInTheDocument();
  });

  it("requires net reservoir thickness before screening", async () => {
    stubLegacyPath();
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
    stubLegacyPath();
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
    stubLegacyPath();
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(
      screen.getByText(/not inferred from gross stratigraphic thickness/i),
    ).toBeInTheDocument();
  });

  it("converts area from km2 to m2 and sends thickness_m unchanged", async () => {
    stubLegacyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user, "80", "35");
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][1]).toEqual({ area_m2: 80_000_000, thickness_m: 35 });
    expect(spy.mock.calls[0][2]).toBe("sensitivity-placeholder");
  });
});

describe("approved model result", () => {
  it("renders both named water-level scenarios together", async () => {
    await runApproved();
    expect(screen.getByText(/GROUND_REFERENCE \(baseline\)/)).toBeInTheDocument();
    expect(screen.getByText(/SEA_LEVEL_SENSITIVITY \(sensitivity\)/)).toBeInTheDocument();
    expect(screen.getByText(/PROJECT REFERENCE SCENARIO/)).toBeInTheDocument();
    expect(screen.getAllByText(/not a measured formation head/).length).toBeGreaterThan(1);
    // Neither is offered as a choice: there is no control to pick one.
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });

  it("shows validated percentiles for each VALIDATED scenario", async () => {
    await runApproved();
    expect(screen.getAllByText("VALIDATED")).toHaveLength(2);
    expect(screen.getByText("14.6")).toBeInTheDocument();
    expect(screen.getByText("12.2")).toBeInTheDocument();
    expect(screen.getAllByText("P50")).toHaveLength(2);
  });

  it("shows the scenario contrast as a contrast, not a correction", async () => {
    await runApproved();
    expect(screen.getByText(/P50 difference -2.44 Mt CO2/)).toBeInTheDocument();
    expect(screen.getByText(/not a correction factor/i)).toBeInTheDocument();
  });

  it("hides percentiles when a scenario is not validated and shows why", async () => {
    await runApproved(approvedMixed);
    expect(screen.getAllByText("OUTSIDE_VALIDATED_ENVELOPE").length).toBeGreaterThan(0);
    expect(screen.getAllByText("UNAVAILABLE").length).toBeGreaterThan(0);
    expect(screen.queryByText("P50")).not.toBeInTheDocument();
    expect(screen.getByText(/validated percentiles blocked/i)).toBeInTheDocument();
    expect(screen.getByText(/no realisation was discarded/i)).toBeInTheDocument();
    expect(screen.getByText(/SURFACE_ELEVATION_UNAVAILABLE/)).toBeInTheDocument();
    expect(screen.getAllByText(/OUTSIDE_VALIDATED_ENVELOPE/).length).toBeGreaterThan(1);
    expect(screen.getByText(/not reported - both scenarios must be VALIDATED/)).toBeInTheDocument();
  });

  it("never displays the NOT_VALIDATED diagnostic capacity numbers", async () => {
    await runApproved(approvedMixed);
    const body = document.body.textContent ?? "";
    for (const value of ["88.8", "99.9", "111.1", "100.5"]) {
      expect(body).not.toContain(value);
    }
  });

  it("shows the depth-reference diagnostic when every scenario is unavailable", async () => {
    await runApproved(approvedUnavailable);
    expect(screen.getAllByText("UNAVAILABLE").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/DEPTH_REFERENCE_NOT_ESTABLISHED/).length).toBeGreaterThan(0);
    expect(screen.queryByText("P50")).not.toBeInTheDocument();
  });

  it("does not calculate h_g or z_state when the API withholds them", async () => {
    await runApproved(approvedUnavailable);
    // z_top 1400 and z_base 1527 are shown, but 127 m and 1463.5 m are not
    // computed here: the API reports them as unavailable.
    expect(screen.getByText("1,400 m / 1,527 m")).toBeInTheDocument();
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("127 m");
    expect(body).not.toContain("1,463.5");
  });

  it("shows derived values only as the API reports them", async () => {
    await runApproved();
    expect(screen.getByText("127 m")).toBeInTheDocument();
    expect(screen.getByText("1,463.5 m")).toBeInTheDocument();
  });

  it("shows the selected temperature observation and the sampled priors with citations", async () => {
    await runApproved();
    expect(screen.getByText(/318.15 K at 1,522.6 m \(extrapolated_squarci_taffi\)/)).toBeInTheDocument();
    const panel = screen.getByRole("region", { name: /approved model inputs/i });
    expect(within(panel).getByText(/Donda, Volpi.*\(2011\)/)).toBeInTheDocument();
    expect(within(panel).getByText(/project-defined prior over the DOE-derived/)).toBeInTheDocument();
    expect(within(panel).getByText(/CSLF Task Force \(2008\)/)).toBeInTheDocument();
  });

  it("does not expose legacy-only controls or panels", async () => {
    await runApproved();
    expect(
      screen.queryByRole("button", { name: /compare temperature methods/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: /provenance of every screening input/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/^NOT_VALIDATED$/)).not.toBeInTheDocument();
  });

  it("shows a rejected approved request without a number", async () => {
    await runApproved(approvedBlocked);
    expect(screen.getByText(/screening unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/not an input of the approved model/i)).toBeInTheDocument();
    expect(screen.queryByText("P50")).not.toBeInTheDocument();
  });

  it("states the result is scenario-based and not certified", async () => {
    await runApproved();
    expect(
      screen.getByText(/not a site-specific or certified storage capacity/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/conditional on the declared model/i)).toBeInTheDocument();
  });
});

describe("successful legacy screening", () => {
  async function renderScreened() {
    stubLegacyPath();
    vi.spyOn(api, "screenWell").mockResolvedValue(screened);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillInputs(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByRole("heading", { name: /^result$/i });
    return user;
  }

  it("labels the result NOT_VALIDATED", async () => {
    await renderScreened();
    expect(screen.getByText("NOT_VALIDATED")).toBeInTheDocument();
    expect(screen.getByText(/not a validated scientific screening result/i)).toBeInTheDocument();
    expect(screen.getByText(/not_validated_legacy_path/)).toBeInTheDocument();
  });

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

describe("provenance partition (legacy)", () => {
  async function renderProvenance() {
    stubLegacyPath();
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
    stubLegacyPath();
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
    expect(screen.getAllByText(/does not invalidate the result/i).length).toBeGreaterThan(0);
  });

  it("shows the approved model's standing limitations", async () => {
    await runApproved();
    expect(screen.getByText(/scale_mismatch_basin_vs_closure/)).toBeInTheDocument();
    expect(
      screen.getByText(/storage-assessment interval \(z_top, z_base\) is explicit user input/i),
    ).toBeInTheDocument();
  });
});

describe("blocked wells (legacy)", () => {
  it("shows Screening unavailable and no capacity", async () => {
    stubLegacyPath();
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
    stubLegacyPath();
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
    stubLegacyPath();
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
    await fillApproved(user);
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
    vi.spyOn(api, "screenWell").mockResolvedValue(approvedValidated);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillApproved(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByText(/GROUND_REFERENCE \(baseline\)/);

    vi.spyOn(api, "getRequiredInputs").mockResolvedValue(legacyRequiredInputs);
    await user.selectOptions(screen.getByLabelText(/screening scenario/i), legacyScenario.name);
    await waitFor(() =>
      expect(api.getRequiredInputs).toHaveBeenLastCalledWith("SALUZZO|1", legacyScenario.name),
    );
    expect(screen.queryByText(/GROUND_REFERENCE \(baseline\)/)).not.toBeInTheDocument();
    // The legacy scenario brings its own inputs; the interval is not carried over.
    expect(await screen.findByLabelText(/net reservoir thickness/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/z_top/i)).not.toBeInTheDocument();
  });

  it("clears a stale result when another well is selected", async () => {
    stubLegacyPath();
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

describe("temperature comparison (legacy diagnostic)", () => {
  it("lists each method without declaring one correct, labelled NOT_VALIDATED", async () => {
    stubLegacyPath();
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
    expect(screen.getByText("NOT_VALIDATED legacy diagnostic")).toBeInTheDocument();
  });

  it("is not offered under the approved model", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "compareTemperatureMethods");
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(
      screen.queryByRole("button", { name: /compare temperature methods/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/offered on legacy scenarios only/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("prominent scientific qualifier (legacy)", () => {
  async function renderScreened() {
    stubLegacyPath();
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
    stubLegacyPath();
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
    stubLegacyPath();
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

/** A promise the test resolves by hand, to hold a request in flight. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

describe("per-well state and overlapping requests (REVIEW-2026-10-01 #2, #3)", () => {
  it("does not carry geological inputs from one well to the next", async () => {
    stubHappyPath();
    const spy = vi.spyOn(api, "screenWell").mockResolvedValue(approvedUnavailable);
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    await fillApproved(user, "80", "1400", "1527");
    expect(screen.getByLabelText(/storage area/i)).toHaveValue(80);

    vi.spyOn(api, "getWell").mockResolvedValue({ ...wellDetail, canonical_id: "CRESCENTINO|1" });
    await user.click(screen.getByRole("button", { name: /CRESCENTINO\|1/ }));
    await screen.findByText("CRESCENTINO|1", { selector: "dd" });

    // Every field is empty again: SALUZZO's interval is not CRESCENTINO's.
    expect(screen.getByLabelText(/storage area/i)).toHaveValue(null);
    expect(screen.getByLabelText(/z_top/i)).toHaveValue(null);
    expect(screen.getByLabelText(/z_base/i)).toHaveValue(null);

    // Submitting without re-entering anything sends nothing.
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    expect(await screen.findByText("Storage area is required.")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("loads source data when the scenario changes while the well detail is pending", async () => {
    stubHappyPath();
    const pendingWell = deferred<typeof wellDetail>();
    vi.spyOn(api, "getWell").mockReturnValue(pendingWell.promise);
    vi.spyOn(api, "getRequiredInputs").mockImplementation(async (_id, scenario) =>
      scenario === legacyScenario.name ? legacyRequiredInputs : requiredInputs,
    );
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await user.click(await screen.findByRole("button", { name: /SALUZZO\|1/ }));
    await user.selectOptions(screen.getByLabelText(/screening scenario/i), legacyScenario.name);
    await screen.findByLabelText(/net reservoir thickness/i);

    pendingWell.resolve(wellDetail);
    expect(await screen.findByRole("heading", { name: /source data/i })).toBeInTheDocument();
    expect(screen.getByText("SALUZZO|1", { selector: "dd" })).toBeInTheDocument();
    expect(api.getWell).toHaveBeenCalledTimes(1);
  });

  it("still discards required inputs requested under the previous scenario", async () => {
    stubHappyPath();
    const staleInputs = deferred<typeof requiredInputs>();
    vi.spyOn(api, "getRequiredInputs").mockImplementation((_id, scenario) =>
      scenario === legacyScenario.name
        ? Promise.resolve(legacyRequiredInputs)
        : staleInputs.promise,
    );
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await user.click(await screen.findByRole("button", { name: /SALUZZO\|1/ }));
    await user.selectOptions(screen.getByLabelText(/screening scenario/i), legacyScenario.name);
    await screen.findByLabelText(/net reservoir thickness/i);

    staleInputs.resolve(requiredInputs);
    await staleInputs.promise;
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.getByLabelText(/net reservoir thickness/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/z_top/i)).not.toBeInTheDocument();
  });

  it("discards a slow well detail and inputs for a well no longer selected", async () => {
    stubHappyPath();
    const slowDetail = deferred<typeof wellDetail>();
    const slowInputs = deferred<typeof requiredInputs>();
    vi.spyOn(api, "getWell").mockImplementation((id: string) =>
      id === "SALUZZO|1"
        ? slowDetail.promise
        : Promise.resolve({ ...wellDetail, canonical_id: "CRESCENTINO|1" }),
    );
    vi.spyOn(api, "getRequiredInputs").mockImplementation((id: string) =>
      id === "SALUZZO|1"
        ? slowInputs.promise
        : Promise.resolve({ ...legacyRequiredInputs, well_id: "CRESCENTINO|1" }),
    );
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await user.click(await screen.findByRole("button", { name: /SALUZZO\|1/ }));
    await user.click(screen.getByRole("button", { name: /CRESCENTINO\|1/ }));
    await screen.findByText("CRESCENTINO|1", { selector: "dd" });
    await screen.findByLabelText(/net reservoir thickness/i);

    slowDetail.resolve(wellDetail);
    slowInputs.resolve(requiredInputs);
    await Promise.all([slowDetail.promise, slowInputs.promise]);
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.getByText("CRESCENTINO|1", { selector: "dd" })).toBeInTheDocument();
    expect(screen.queryByText("SALUZZO|1", { selector: "dd" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/z_top/i)).not.toBeInTheDocument();
  });
});

describe("synthetic demo dataset labelling", () => {
  function stubDemo() {
    stubHappyPath();
    vi.spyOn(api, "getHealth").mockResolvedValue(demoHealth);
    vi.spyOn(api, "getWell").mockResolvedValue({ ...wellDetail, dataset: demoDataset });
  }

  it("shows a prominent synthetic-data banner when the demo dataset is served", async () => {
    stubDemo();
    render(<ScreeningWorkspace />);
    const banner = await screen.findByRole("region", { name: /synthetic demonstration data/i });
    expect(banner).toHaveTextContent(/fictional/i);
    expect(banner).toHaveTextContent(/not capacity estimates for\s+any real site/i);
  });

  it("puts the banner before the page introduction, so it is seen first on a phone", async () => {
    stubDemo();
    render(<ScreeningWorkspace intro={<ProjectIntro />} />);
    const banner = await screen.findByRole("region", { name: /synthetic demonstration data/i });
    const intro = screen.getByRole("region", { name: /what this is/i });
    expect(banner.compareDocumentPosition(intro) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows no banner for the real sources", async () => {
    stubHappyPath();
    render(<ScreeningWorkspace />);
    await screen.findByRole("button", { name: /SALUZZO\|1/ });
    expect(
      screen.queryByRole("region", { name: /synthetic demonstration data/i }),
    ).not.toBeInTheDocument();
  });

  it("still labels the demo when /health is unavailable but wells are flagged", async () => {
    stubHappyPath();
    vi.spyOn(api, "getHealth").mockRejectedValue(new ApiClientError("down", 0, "network"));
    vi.spyOn(api, "listWells").mockResolvedValue(wells.map((w) => ({ ...w, synthetic: true })));
    render(<ScreeningWorkspace />);
    expect(
      await screen.findByRole("region", { name: /synthetic demonstration data/i }),
    ).toBeInTheDocument();
  });

  it("labels the well detail and a result as synthetic", async () => {
    stubDemo();
    vi.spyOn(api, "screenWell").mockResolvedValue({ ...approvedValidated, dataset: demoDataset });
    const user = userEvent.setup();
    render(<ScreeningWorkspace />);
    await selectSaluzzo(user);
    expect(screen.getByText(/fictional demo well/i)).toBeInTheDocument();
    await fillApproved(user);
    await user.click(screen.getByRole("button", { name: /run screening/i }));
    await screen.findByRole("heading", { name: /^result$/i });
    expect(screen.getByText(/computed from fictional demo inputs/i)).toBeInTheDocument();
  });

  it("does not label a real-data result as synthetic", async () => {
    await runApproved(approvedValidated);
    expect(screen.queryByText(/computed from fictional demo inputs/i)).not.toBeInTheDocument();
  });
});
