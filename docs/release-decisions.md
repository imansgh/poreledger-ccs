# Release decisions

Owner decisions for the public release, and what is still open. Documentation and GitHub updates for this version were requested on
2026-10-04. This does not by itself change repository visibility or deploy
the live service.
How the release is assembled: [public-release.md](public-release.md).

## Confirmed

| Decision | Date | Decision |
| --- | --- | --- |
| Project identity | 2026-10-02 | Display name **PoreLedger CCS**; subtitle **CO2 Storage Screening & Uncertainty Analysis**; repository slug `poreledger-ccs`. Python distribution and import names (`ccs-screen`, `ccs_screen`) are unchanged. |
| Software license | 2026-10-02 | **MIT** ([LICENSE](../LICENSE)), copyright Iman Saghafifar. It covers this repository's code and documentation only; it grants no rights to external datasets, well reports or publications. |
| Personal website | 2026-10-02 | `https://imansgh.me` (built and hosted with Lovable). The demo is to be reachable from it, preferably at `/poreledger-ccs`. |
| Goals | 2026-10-02 | A credible scientific portfolio piece and a useful free research tool. The proposed niche is not implemented in this release. |
| Public demo data | 2026-10-02 | User assessments and the shipped synthetic examples only; **no** existing-well dataset on the public backend. |

## Open

| Decision | Status | Notes |
| --- | --- | --- |
| **Public release / production deployment** | Pending | Private development is on GitHub; public release and live-demo deployment are separate, unfinished steps. |
| **Repository and history** | Pending; recommendation in [public-release.md](public-release.md) | The current remote `imansgh/ccs_UI` is private. Its history contains files the release excludes (deleted evidence transcriptions, a deleted personal note) and two author e-mail addresses. Recommended: a new public repository `poreledger-ccs` with one initial commit of the reviewed tree; keep `ccs_UI` private. |
| **Backend host** | Pending | No backend hosting account is configured. The website host (GitHub Pages) needs no new account. A no-cost container host is recommended in [public-release.md](public-release.md); creating it is the owner's action. |
| **Website change on imansgh.me** | Prepared in Lovable preview, 2026-10-03; production publication pending | The `/poreledger-ccs` page, project card and sitemap entry exist in preview. Demo/repository URLs are unset until verified. Activation instructions: [public-release.md](public-release.md). The existing page `/projects/co2-storage-screening-dashboard` describes a different tool (`imansgh/CO-Storage-Screening-Dashboard`); it was preserved. |
| **Real-data redistribution** | Not established | The real structured sources and the document corpus are not in the release and must not be added until their terms are confirmed. The published audit and design records (e.g. `scientific-validation-audit.md`, `piemonte-ntg-evidence.md`) and some tests quote individual values from public Italian well records (ViDEPI / UNMIG registries) with attribution. Confirm this is acceptable before publishing, or remove those records from the public tree. |
| **Accounts and access** | Pending | Who holds the hosting and GitHub accounts and who may merge data submissions. |
| **Depth convention (TVD only) for user data** | Owner confirmation pending | Interpretation N1 in [scientific-notes.md](scientific-notes.md): MD and unknown conventions give UNAVAILABLE. |
| **User-declared datum counts as established** | Owner confirmation pending | Interpretation N2 in [scientific-notes.md](scientific-notes.md); results label the declaration as unverified. |
| **Existing-well depth-convention gate** | Open | User assessments are gated to TVD; the existing-well path does not apply the same gate. Resolve before claiming equivalent validation across both paths. |
| **Scientific scope** | Unchanged | The approved Model Contract is unchanged by release preparation. |

Record each decision here (date, decision, who) when it is made.
