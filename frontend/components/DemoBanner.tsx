import type { DatasetInfo } from "@/lib/types";

/**
 * Shown above everything while the backend serves the synthetic demo dataset.
 *
 * Not dismissible and not a tooltip: every well, value and result on the page
 * is fictional while it is visible, so it must stay in view.
 */
export function DemoBanner({ dataset }: { dataset: DatasetInfo | null }) {
  return (
    <section className="demo-banner" role="region" aria-labelledby="demo-banner-heading">
      <h2 id="demo-banner-heading">Synthetic demonstration data</h2>
      <p>
        Every well on this page (ids starting with <code>SYNTH</code>) and every
        depth, datum, elevation and temperature is <strong>fictional</strong>.
        Results show how the software behaves; they are not capacity estimates for
        any real site, and a VALIDATED status here means only that fictional inputs
        fell inside the model&apos;s validated envelope.
      </p>
      {dataset?.statement ? <p className="detail">{dataset.statement}</p> : null}
    </section>
  );
}

/** In-flow label directly above a result computed from synthetic data. */
export function SyntheticResultNotice() {
  return (
    <p className="synthetic-result" role="note">
      <span className="tag tag-synthetic">SYNTHETIC</span> Computed from fictional demo
      inputs. Not a measurement-based or site-specific result.
    </p>
  );
}
