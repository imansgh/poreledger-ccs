# Documentation index

Current target: **0.2.0 release candidate**. The portfolio page is prepared
in Lovable preview; the hosted calculation demo is not active.

## Start here

| Document | What it is for |
| --- | --- |
| [../CHANGELOG.md](../CHANGELOG.md) | Version 0.2.0 changes and known release limitations |
| [github-release.md](github-release.md) | Accurate GitHub description, topics and release checklist |
| [../README.md](../README.md) | Purpose, what is computed and not assessed, quick start, the user-data workflow |
| [assessment-input-schema.md](assessment-input-schema.md) | **Input contract** for your own data: JSON and CSV formats, units, conventions, limits, templates |
| [validation-evidence.md](validation-evidence.md) | What the calculations are checked against, measured density errors, and the limits of that evidence |
| [scientific-notes.md](scientific-notes.md) | Interpretations made to apply the contract to user data (awaiting owner confirmation), formula audit |
| [data-handling.md](data-handling.md) | What happens to submitted data: not stored, not logged, parsed as data only |
| [../demo/README.md](../demo/README.md) | The fictional demo wells for the optional existing-data section |
| [deployment.md](deployment.md) | Running the API and website; build-time settings, CORS, `/health` vs `/ready`, data storage, containers |
| [data-contribution.md](data-contribution.md) | How to contribute real well data to the project (optional existing-data workflow) |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Development setup, checks, workflow, rules for scientific changes |
| [public-release.md](public-release.md) | Publication contents, the live-demo architecture and how it is linked from imansgh.me |
| [release-decisions.md](release-decisions.md) | Owner decisions (license, identity) and what is still open (hosting, accounts, data rights) |

## Reference

| Document | What it is for |
| --- | --- |
| [phase13-owner-decision-record.md](phase13-owner-decision-record.md) | **The approved Model Contract**: equations, inputs, priors, temperature rule, depth-reference and envelope guards. Authoritative. |
| [http-api.md](http-api.md) | HTTP endpoints, request and response contracts, status codes, readiness |
| [ingestion.md](ingestion.md) | How structured sources become provenance-carrying well records |
| [cli.md](cli.md) | The `ccs-screen` command-line demo path (all output `NOT_VALIDATED`), config files, density accuracy |
| [scenario-literature-review.md](scenario-literature-review.md) | Literature basis of the `literature-screening-v1` priors |

## Historical audit and design records

Kept for traceability of how the current model was reached. They describe
earlier states, proposals and evidence reviews; where they disagree with the
Model Contract or the code, **the contract and the code win**.

| Document | Topic |
| --- | --- |
| [scientific-validation-audit.md](scientific-validation-audit.md) | Phase-by-phase scientific validation audit |
| [phase14-change-map.md](phase14-change-map.md) | Implementation plan for the approved model (Phase 14) |
| [finding-3.1-literature-review.md](finding-3.1-literature-review.md) | Net-to-gross and effective thickness in the capacity equation |
| [bprime-control-experiment.md](bprime-control-experiment.md) | Control experiment on removing net-to-gross from E |
| [ev3-semantics.md](ev3-semantics.md) | Semantics of the `E_V3` buoyancy term |
| [net-to-gross-semantics.md](net-to-gross-semantics.md) | Specification of the `net_to_gross` disclosure field |
| [ntg-elicitation-design.md](ntg-elicitation-design.md) | Design note on making implicit net-to-gross explicit |
| [phase1-ntg-disclosure-draft.md](phase1-ntg-disclosure-draft.md) | Draft proposal for net-to-gross disclosure |
| [piemonte-ntg-evidence.md](piemonte-ntg-evidence.md) | Evidence review for a Piemonte net-to-gross value |
