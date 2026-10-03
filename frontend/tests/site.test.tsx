/**
 * The public site's explanatory content.
 *
 * Pins what the page must say in plain language: readiness is not validation,
 * results are conditional and not certified, all four statuses are explained,
 * and how to contribute data. A repository link appears only when a deployment
 * configures one; none is invented.
 */

import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  ContributeData,
  ProjectIntro,
  SiteFooter,
  StatusGuide,
  repositoryUrl,
} from "@/components/AboutSections";

const ORIGINAL = process.env.NEXT_PUBLIC_CCS_REPO_URL;

afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.NEXT_PUBLIC_CCS_REPO_URL;
  else process.env.NEXT_PUBLIC_CCS_REPO_URL = ORIGINAL;
});

describe("project introduction", () => {
  it("separates software readiness from scientific validation", () => {
    render(<ProjectIntro />);
    const intro = screen.getByRole("region", { name: /what this is/i });
    expect(intro).toHaveTextContent(/software readiness is not scientific validation/i);
    expect(intro).toHaveTextContent(/conditional estimates/i);
    expect(intro).toHaveTextContent(/never certified or site-specific/i);
    expect(within(intro).getAllByRole("listitem")).toHaveLength(3);
  });
});

describe("status guide", () => {
  it("explains all four statuses in plain language", () => {
    render(<StatusGuide />);
    const guide = screen.getByRole("region", { name: /how to read a result/i });
    for (const status of [
      "VALIDATED",
      "OUTSIDE_VALIDATED_ENVELOPE",
      "UNAVAILABLE",
      "NOT_VALIDATED",
    ]) {
      expect(within(guide).getByText(status, { selector: "code" })).toBeInTheDocument();
    }
    expect(guide).toHaveTextContent(/not a certified capacity/i);
    expect(guide).toHaveTextContent(/expected outcome for every current real well/i);
  });
});

describe("data contribution", () => {
  it("lists what a submission must document and that it may stay unavailable", () => {
    render(<ContributeData />);
    const section = screen.getByRole("region", { name: /contribute real data/i });
    for (const topic of [/depth datum/i, /MD versus TVD/i, /measurement method/i,
                         /storage-assessment interval/i, /redistribute/i, /missing/i]) {
      expect(section).toHaveTextContent(topic);
    }
    expect(section).toHaveTextContent(/may still leave a well\s+scientifically UNAVAILABLE/i);
    expect(section).toHaveTextContent("docs/data-contribution.md");
  });
});

describe("repository link", () => {
  it("is absent unless a deployment configures one", () => {
    delete process.env.NEXT_PUBLIC_CCS_REPO_URL;
    expect(repositoryUrl()).toBeNull();
    render(
      <>
        <ContributeData />
        <SiteFooter />
      </>,
    );
    expect(screen.queryByRole("link", { name: /source code/i })).not.toBeInTheDocument();
  });

  it("is rendered from NEXT_PUBLIC_CCS_REPO_URL when set", () => {
    process.env.NEXT_PUBLIC_CCS_REPO_URL = "https://example.org/owner/repo";
    render(<SiteFooter />);
    expect(screen.getByRole("link", { name: /source code/i })).toHaveAttribute(
      "href",
      "https://example.org/owner/repo",
    );
  });

  it("ignores a value that is not an https URL", () => {
    process.env.NEXT_PUBLIC_CCS_REPO_URL = "javascript:alert(1)";
    expect(repositoryUrl()).toBeNull();
  });
});
