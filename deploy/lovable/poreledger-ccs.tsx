// Route for the imansgh.me website (Lovable, TanStack Start): /poreledger-ccs
// Copy to src/routes/poreledger-ccs.tsx in the Lovable project. Reference only;
// it is not part of this repository's build. See docs/public-release.md.
//
// It embeds the separately hosted PoreLedger CCS website in an iframe. The
// embedded site reports its height (postMessage, only to https://imansgh.me),
// so the frame grows with the content instead of scrolling inside the page.
// Calculations are made by the iframe's own origin, so the backend's CORS
// origin is the demo host's origin, not imansgh.me.
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowUpRight, Github } from "lucide-react";
import { SectionHeader } from "@/lib/portfolio-ui";

const DEMO_URL = "https://imansgh.github.io/poreledger-ccs/";
const DEMO_ORIGIN = "https://imansgh.github.io";
const REPO_URL = "https://github.com/imansgh/poreledger-ccs";
const HEIGHT_MESSAGE = "poreledger-ccs:height";

export const Route = createFileRoute("/poreledger-ccs")({
  head: () => ({
    meta: [
      { title: "PoreLedger CCS: CO₂ Storage Screening & Uncertainty Analysis | Iman Saghafifar" },
      {
        name: "description",
        content:
          "Interactive research demo: conditional CO₂ storage screening with user-declared inputs, fixed priors, Monte Carlo uncertainty and reproducible exports.",
      },
      { property: "og:title", content: "PoreLedger CCS: live demo" },
      { property: "og:image", content: "https://imansgh.me/og-image.png" },
    ],
    links: [{ rel: "canonical", href: "https://imansgh.me/poreledger-ccs" }],
  }),
  component: PoreLedgerPage,
});

function PoreLedgerPage() {
  const [height, setHeight] = useState(1400);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== DEMO_ORIGIN) return;
      const data = event.data as { type?: unknown; height?: unknown } | null;
      if (!data || data.type !== HEIGHT_MESSAGE || typeof data.height !== "number") return;
      setHeight(Math.min(Math.max(Math.ceil(data.height), 600), 20000));
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <section className="py-12 sm:py-16">
      <Link
        to="/projects"
        className="inline-flex items-center gap-2.5 rounded-full border border-border/70 bg-secondary/40 px-4 py-2.5 text-sm font-medium text-foreground/80 transition hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to Projects
      </Link>

      <div className="mt-8">
        <SectionHeader
          as="h1"
          kicker="Python · FastAPI · Next.js · CCS — Author & Developer · 2026"
          title="PoreLedger CCS"
          lead="CO₂ Storage Screening & Uncertainty Analysis. Enter or upload your own well or site data, or load a synthetic example, and get a conditional screening estimate with its uncertainty — or the exact reason none can be given. Not a certified storage estimate."
        />
        <div className="flex flex-wrap gap-3">
          <a
            href={DEMO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background transition hover:opacity-90"
          >
            Open the demo full screen <ArrowUpRight className="size-4" />
          </a>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/40 px-5 py-2.5 text-sm font-medium text-foreground/85 transition hover:border-foreground/25"
          >
            <Github className="size-4" /> Source code (MIT) <ArrowUpRight className="size-4" />
          </a>
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-[1.7] text-muted-foreground">
          The calculation service runs on free hosting and may take up to a minute to wake up.
          Do not enter confidential data in the public demo; the software can be run locally instead.
        </p>
      </div>

      <div className="mt-10 overflow-hidden rounded-2xl border border-border/60 bg-white">
        <iframe
          src={DEMO_URL}
          title="PoreLedger CCS interactive demo"
          style={{ height, width: "100%", border: 0, display: "block" }}
          loading="lazy"
          referrerPolicy="no-referrer"
          sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
        />
      </div>
    </section>
  );
}
