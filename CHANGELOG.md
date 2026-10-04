# Changelog

## 0.2.0 - release candidate

Status reviewed 2026-10-04. This records implemented work, not a published tag
or an available hosted service. The Python distribution remains `ccs-screen`.

- PoreLedger CCS identity, MIT license for code and project documentation.
- Manual and CSV/JSON assessment inputs, editable review, unit normalization,
  depth-reference checks and eligible corrected-temperature selection.
- Partial/conflicting CSV imports block evaluation; editing their preview
  cannot clear the import block. Correct the source or start a fresh assessment.
- Synthetic examples with persistent provenance, scenario outcomes, accessible
  charts, JSON results and CSV summaries. Edited inputs invalidate old exports.
- Dataset-independent readiness, optional per-client POST limits and evaluation
  concurrency caps for a single-process API.
- Static website export, explicit HTTPS API configuration, manual GitHub Pages
  workflow and container/public-demo configuration.
- Separate portfolio page prepared in Lovable preview, with live URLs unset.

### Scientific scope and remaining work

The approved model, fixed priors and density envelope are not broadened by this
release. Measurements are used as declared; Monte Carlo samples model priors,
not uncertainty in every measurement. The software selects supplied corrected
temperatures; it does not correct raw measurements or convert MD to TVD.

Local verification on 2026-10-03: 1,626 Python tests, 186 strict reference
checks and 209 frontend tests passed. Counts are a dated snapshot. Public CI,
container execution and live cross-origin calculation/download verification
are not established by these results. The iframe shrink behaviour and service
status recovery identified in review still need correction/verification before
accepting the public demo. See [publication guide](docs/public-release.md).
