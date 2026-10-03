/**
 * Static explanatory content for the public site: what the tool is, how to
 * read its statuses, and how to contribute data. Plain language on purpose;
 * the authoritative definitions live in the repository documentation.
 */

/** A repository link is rendered only when the deployment configures one. */
export function repositoryUrl(): string | null {
  const url = process.env.NEXT_PUBLIC_CCS_REPO_URL?.trim();
  return url && /^https:\/\/[^\s]+$/.test(url) ? url : null;
}

export function ProjectIntro() {
  return (
    <section className="panel intro" aria-labelledby="intro-heading">
      <h2 id="intro-heading">What this is</h2>
      <p>
        A research and screening toolkit for geological CO2 storage. Describe a well
        or site with your own data (storage area, the storage-assessment interval and
        its depth reference, temperature observations) and the approved screening
        model returns a scenario-based capacity estimate with its uncertainty and
        provenance, or explains exactly why it cannot.
      </p>
      <ol className="steps">
        <li>Enter or upload your data, or load a synthetic example to see how it works.</li>
        <li>
          Correct anything the validation reports. Nothing is defaulted and nothing
          missing is filled in for you.
        </li>
        <li>
          Run the approved model and read both named water-level scenarios with their
          status, uncertainty, provenance and limitations.
        </li>
      </ol>
      <p className="detail">
        <strong>Software readiness is not scientific validation.</strong> &ldquo;Ready&rdquo;
        means the service can run the model. Whether a result is
        scientifically usable is a separate question, answered per result by its
        validation status. Screening results are conditional estimates under stated
        assumptions, never certified or site-specific storage capacities.
      </p>
    </section>
  );
}

const STATUSES: { name: string; meaning: string }[] = [
  {
    name: "VALIDATED",
    meaning:
      "The approved model ran, and every sampled pressure and temperature fell inside the range where its CO2 density model was checked. The number is still a conditional screening estimate, not a certified capacity.",
  },
  {
    name: "OUTSIDE_VALIDATED_ENVELOPE",
    meaning:
      "The approved model ran, but some conditions fall outside that checked range. At most a diagnostic number is shown, and it should not be used as an estimate.",
  },
  {
    name: "UNAVAILABLE",
    meaning:
      "A required input is missing or not established (for example an unknown depth datum, or no eligible temperature), so no number is produced. This is the expected outcome for every current real well in the project's historical dataset; it does not describe all real wells.",
  },
  {
    name: "NOT_VALIDATED",
    meaning:
      "The result comes from a legacy placeholder path outside the approved model. It is kept for comparison and should not be relied on.",
  },
];

export function StatusGuide() {
  return (
    <section className="panel" aria-labelledby="status-guide-heading">
      <h2 id="status-guide-heading">How to read a result</h2>
      <dl className="status-guide">
        {STATUSES.map((status) => (
          <div key={status.name}>
            <dt>
              <code>{status.name}</code>
            </dt>
            <dd>{status.meaning}</dd>
          </div>
        ))}
      </dl>
      <p className="detail">
        Every status comes with machine-readable diagnostics. A status is about the
        model and its inputs; it never certifies a site.
      </p>
    </section>
  );
}

export function ContributeData() {
  const repo = repositoryUrl();
  return (
    <section className="panel" aria-labelledby="contribute-heading">
      <h2 id="contribute-heading">Contribute real data</h2>
      <p>
        Most real wells are UNAVAILABLE today because the sources do not state a
        depth datum or a storage-assessment interval. Better data is the way
        forward, and it has to be documented well enough to check. Useful
        submissions state, for each well:
      </p>
      <ul>
        <li>a stable well identity and the original source, with permission to redistribute it;</li>
        <li>units, the depth datum (ground level, rotary table, sea level), and MD versus TVD;</li>
        <li>each temperature with its measurement method and depth;</li>
        <li>the evidence for any storage-assessment interval;</li>
        <li>which values are missing, rather than estimates filled in.</li>
      </ul>
      <p className="detail">
        Every submission is reviewed. Accepted data may still leave a well
        scientifically UNAVAILABLE if the model&apos;s requirements are not met. See the
        data contribution guide (<code>docs/data-contribution.md</code>)
        {repo ? (
          <>
            {" "}in the <a href={repo}>project repository</a>
          </>
        ) : (
          " in the project repository"
        )}
        .
      </p>
    </section>
  );
}

export function SiteFooter() {
  const repo = repositoryUrl();
  return (
    <footer className="site-footer">
      <p>
        {/* _top: when the demo is embedded on the author's site, leave the frame. */}
        <a href="https://imansgh.me" target="_top">PoreLedger CCS · By Iman</a>.{" "}
        Research and screening software, MIT licensed. Not a certified storage
        estimate, not engineering advice.
        {repo ? (
          <>
            {" "}
            <a href={repo} target="_blank" rel="noopener noreferrer">Source code and documentation</a>.
          </>
        ) : null}
      </p>
    </footer>
  );
}
