/**
 * Static checks over the stylesheet.
 *
 * No browser is available in this environment, so layout cannot be observed.
 * What *can* be verified is arithmetic and structure: contrast ratios computed
 * from the declared tokens, that every token used is defined in both themes,
 * and that the rules known to cause horizontal overflow are present.
 *
 * These do not replace looking at the page. They catch the class of mistake
 * that is invisible in code review and obvious on a phone.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// vitest runs with the project root as cwd; import.meta.url is not a file URL
// under the jsdom environment.
const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");

/** Pull `--name: value;` pairs out of one block of the stylesheet. */
function tokensIn(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const match of block.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    out[match[1]] = match[2].trim();
  }
  return out;
}

function blockAfter(marker: string): string {
  const start = css.indexOf(marker);
  if (start === -1) throw new Error(`marker not found: ${marker}`);
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}") {
      depth -= 1;
      if (depth === 0) return css.slice(open, i);
    }
  }
  throw new Error(`unbalanced block after ${marker}`);
}

const light = tokensIn(blockAfter(":root {"));
const dark = tokensIn(blockAfter(':root[data-theme="dark"]'));

function srgbToLinear(channel: number): number {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const clean = hex.trim().replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((c) => c + c)
          .join("")
      : clean;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

/** Foreground/background pairs the UI actually renders. */
const PAIRS: [string, string, number][] = [
  // [foreground token, background token, minimum ratio]
  ["ink", "bg", 4.5],
  ["ink", "panel", 4.5],
  ["ink", "panel-alt", 4.5],
  ["ink-soft", "panel", 4.5],
  ["ink-faint", "panel", 3.0], // hints and secondary metadata: large/AA-large
  ["source", "source-bg", 4.5],
  ["modelled", "modelled-bg", 4.5],
  ["assumed", "assumed-bg", 4.5],
  ["user", "user-bg", 4.5],
  ["warn", "warn-bg", 4.5],
  ["stop", "stop-bg", 4.5],
];

describe("colour tokens", () => {
  it("defines every token in both themes", () => {
    const missing = Object.keys(light)
      .filter((name) => !name.startsWith("mono") && !name.startsWith("sans") && name !== "radius")
      .filter((name) => !(name in dark));
    expect(missing).toEqual([]);
  });

  it("uses no token that is never defined", () => {
    const used = new Set(
      [...css.matchAll(/var\(--([\w-]+)\)/g)].map((m) => m[1]),
    );
    const defined = new Set(Object.keys(light));
    expect([...used].filter((name) => !defined.has(name))).toEqual([]);
  });

  describe.each([
    ["light", light],
    ["dark", dark],
  ])("%s theme contrast", (_name, theme) => {
    it.each(PAIRS)("%s on %s meets %s:1", (fg, bg, minimum) => {
      const ratio = contrast(theme[fg], theme[bg]);
      expect(
        ratio,
        `${fg} (${theme[fg]}) on ${bg} (${theme[bg]}) = ${ratio.toFixed(2)}:1`,
      ).toBeGreaterThanOrEqual(minimum);
    });
  });

  it("has a dark block for the system preference as well as the explicit toggle", () => {
    expect(css).toContain("prefers-color-scheme: dark");
    expect(css).toContain(':root[data-theme="dark"]');
  });

  it("paints the body background explicitly", () => {
    // A transparent body borrows the host's colour and breaks in dark mode.
    expect(css).toMatch(/body\s*\{[^}]*background:\s*var\(--bg\)/);
  });
});

describe("narrow-width safety", () => {
  it("never lets a grid track have automatic minimum width", () => {
    // `1fr` alone has min-width:auto, which is the usual cause of a grid
    // stretching past the viewport when a child holds a long unbroken string.
    const gridRules = [...css.matchAll(/grid-template-columns:\s*([^;]+);/g)].map(
      (m) => m[1],
    );
    expect(gridRules.length).toBeGreaterThan(0);
    for (const rule of gridRules) {
      if (rule.includes("auto-fill")) {
        expect(rule).toContain("min(");
      } else {
        expect(rule).toMatch(/minmax\(\s*0|minmax\(\s*\d+px/);
      }
    }
  });

  it("allows long monospace strings to wrap", () => {
    for (const selector of [".kv dd", ".card dd", ".well-row .id"]) {
      const block = blockAfter(selector);
      expect(block, `${selector} must wrap long values`).toContain("overflow-wrap");
    }
  });

  it("scales the headline number down on narrow screens", () => {
    expect(blockAfter(".result-value {")).toContain("clamp(");
  });

  it("keeps tables in their own scroll container", () => {
    expect(blockAfter(".table-wrap")).toContain("overflow-x: auto");
  });

  it("gives the shell a side gutter at every width", () => {
    expect(blockAfter(".shell")).toMatch(/padding-inline:\s*\d+px/);
  });

  it("raises input font size on small screens to avoid iOS zoom", () => {
    const smallScreen = css.slice(css.indexOf("@media (max-width: 520px)"));
    expect(smallScreen).toMatch(/font-size:\s*16px/);
  });

  it("stacks to a single column below the desktop breakpoint", () => {
    expect(css).toMatch(/@media \(max-width: 900px\)[\s\S]{0,120}grid-template-columns/);
  });
});

describe("motion", () => {
  it("uses no keyframe animation", () => {
    // Strip comments: prose about animation is not animation.
    const rules = css.replace(/\/\*[\s\S]*?\*\//g, "");
    expect(rules).not.toContain("@keyframes");
    expect(rules).not.toMatch(/animation:/);
  });

  it("limits transitions to a short state change", () => {
    const rules = css.replace(/\/\*[\s\S]*?\*\//g, "");
    for (const match of rules.matchAll(/transition:[^;]*?(\d+)ms/g)) {
      expect(Number(match[1])).toBeLessThanOrEqual(200);
    }
  });
});
