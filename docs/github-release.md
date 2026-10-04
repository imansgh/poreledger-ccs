# GitHub presentation for version 0.2.0

Status: release candidate, reviewed 2026-10-04. The current accessible source
repository is private `imansgh/ccs_UI`, on `phase15a/software-hardening`.
The intended public name `imansgh/poreledger-ccs` is not yet a verified public
release. Do not change visibility of the research-history repository as part
of a README update.

## Repository About fields

Suggested description:

> PoreLedger CCS: conditional CO2 storage screening with explicit inputs, fixed-prior Monte Carlo uncertainty, and reproducible exports. Research software, MIT.

Website for now: `https://imansgh.me` (author portfolio).
Use `https://imansgh.me/poreledger-ccs` only after publishing and verifying that
page. Do not label it a live demo until calculations and exports work online.

Suggested topics: `carbon-storage`, `ccs`, `geoenergy`, `scientific-computing`,
`python`, `fastapi`, `nextjs`, `monte-carlo`, `uncertainty-quantification`.

These are prepared metadata values, not confirmation that GitHub settings were
changed. The new public repository should use a reviewed fresh tree, preserving
the private history separately; see [public-release.md](public-release.md).

## Release description

Use [CHANGELOG.md](../CHANGELOG.md) as the version summary. Mark an initial
release candidate as a prerelease. Do not invent a publication date, DOI,
download count or scientific-accuracy badge. A green CI badge must point to
the actual repository/branch and an observed workflow run.

Before a public release, verify packaged install, CI, external data exclusions,
real HTTPS endpoints, container readiness and cross-origin calculations and
actual JSON/CSV downloads. Keep the research limitations prominent.
