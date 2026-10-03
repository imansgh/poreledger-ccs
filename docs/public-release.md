# Public release and live demo

How PoreLedger CCS is published and how its live demo is reached from
`https://imansgh.me`. Status: **prepared, not published**. Nothing has been
pushed, made public or deployed; each step below that changes something
outside this working copy is the owner's action, after authorization.

## 1. What is published

**Included** (the files Git tracks plus the untracked files not excluded by
`.gitignore`; review with `git ls-files --cached --others --exclude-standard`):

- the Python package `src/ccs_screen` (engine, user assessments, FastAPI app,
  optional ingestion) with its synthetic examples and templates;
- the website `frontend/` (Next.js) and all tests (`tests/`, `frontend/tests/`);
- `demo/` (fictional demo wells), `deploy/` (Dockerfiles, public-demo
  backend environment, the imansgh.me route), `scripts/`, `.github/`
  (CI, the manual GitHub Pages workflow, issue templates);
- documentation in `docs/`, `README.md`, `CONTRIBUTING.md`, `LICENSE` (MIT).

**Excluded**, and kept in the local workspace (`.gitignore`):

| Excluded | Why |
| --- | --- |
| `data/` (about 11 GB: workbook, registry CSVs, well-report PDFs, KML) | real sources; redistribution not established |
| `REVIEW*.md`, `USA-DATA-ASSESSMENT*.md` | local review notes |
| `docs/well-data-readiness*`, `docs/depth-reference-resolution.md`, `docs/storage-interval-evidence.md`, `docs/depth-and-interval-decision-matrix.csv` | transcriptions from the real document corpus |
| `docs/niche-*.md`, `docs/*comparable-tools*.md` | unpublished positioning research |
| `.env`, `.env.local`, `frontend/.env.local` | local configuration |
| `.agents/`, `skills-lock.json`, `.claude/`, `.cursor/` | local agent tooling |
| caches and build output (`__pycache__`, `.pytest_cache`, `.next/`, `out/`, `node_modules/`, `build/`, `dist/`) | generated |

No credentials, tokens or private keys were found in the publishable files
or anywhere in the repository history (pattern scan of every blob: GitHub,
cloud and AI-provider token formats, private keys, password assignments).
Owner decisions about published content are listed in
[release-decisions.md](release-decisions.md) ("Real-data redistribution").

**License scope.** The MIT license covers this repository's code and
documentation. It grants no rights to external datasets, well reports or
publications, including the Italian well records the audit documents cite.

## 2. Repository and history (recommendation)

The current remote, `imansgh/ccs_UI`, is **private**. Its history contains
files the release deliberately excludes (deleted evidence transcriptions
`docs/finding-3.1-*` and `docs/finding-4.2-*`, a deleted personal note) and
commits under two personal e-mail addresses. Making that repository public
or renaming it would publish all of that.

Recommended: create a **new public repository `imansgh/poreledger-ccs`**
whose first commit is the reviewed tree, and keep `ccs_UI` private as the
research history. After authorization (Git Bash, from this directory):

```bash
REL=../poreledger-ccs-release
mkdir "$REL"
git ls-files -z --cached --others --exclude-standard | xargs -0 cp --parents -t "$REL"
cd "$REL"
git init -b main
git config user.name "Iman Saghafifar"
git config user.email "<your GitHub noreply address>"   # avoids publishing a personal address
git add -A
git commit -m "PoreLedger CCS 0.2.0: initial public release"
gh repo create imansgh/poreledger-ccs --public --source . --push \
  --description "PoreLedger CCS: CO2 storage screening & uncertainty analysis (research software)" \
  --homepage "https://imansgh.me/poreledger-ccs"
```

The CI workflow then runs on the first push (Python 3.10-3.12, strict
CoolProp reference checks, frontend tests, type check and build).

## 3. Live-demo architecture

```
visitor ── https://imansgh.me/poreledger-ccs            (Lovable site: page with an iframe)
             └─ iframe https://imansgh.github.io/poreledger-ccs/   (GitHub Pages: static website)
                   └─ fetch https://<backend-host>/assessments/*   (FastAPI container, HTTPS)
```

Why this shape (checked against the live site on 2026-10-02):

- `imansgh.me` is a Lovable project (TanStack Start, server-rendered, on
  Cloudflare). It cannot run the Python backend, and serving the Next.js
  export from inside it is fragile: unknown paths are a real 404 (no static
  directory index), and `/poreledger-ccs/` is redirected to `/poreledger-ccs`.
  A normal page route at `/poreledger-ccs` that embeds the demo works with the
  site as built, and keeps the two deployments independent.
- The static website is built with base path `/poreledger-ccs`, which is
  exactly the GitHub Pages project path for a repository named
  `poreledger-ccs`. GitHub Pages is free for public repositories.
- The backend must be a separately reachable HTTPS service.
- **CORS origin:** the API calls come from the iframe's own origin,
  `https://imansgh.github.io`, not from `imansgh.me`. That is the value of
  `CCS_CORS_ORIGINS`. It changes only if the website moves to a custom domain.
- The demo reports its content height to `https://imansgh.me` only
  (`NEXT_PUBLIC_CCS_EMBED_ORIGINS`), so the host page sizes the iframe and
  there is no scrollbar inside a scrollbar.

## 4. Backend

Settings: [`deploy/public-demo.env`](../deploy/public-demo.env) with
[`deploy/backend.Dockerfile`](../deploy/backend.Dockerfile). They give: no
well dataset (only user assessments and the shipped synthetic examples), CORS
for exactly `https://imansgh.github.io`, request-body caps, at most 20 POST
requests per client per minute, at most 2 simultaneous Monte Carlo runs, one
process, no application access log, health on `/ready`.

**Host: owner's choice; no account exists yet and none was created.**
Requirements: runs a Dockerfile from the repository, HTTPS URL, environment
variables, health-check path, no cost for a demo. A no-cost option that meets
them is a free Render web service (check its current free-tier terms first):

| Render field | Value |
| --- | --- |
| Source | the `imansgh/poreledger-ccs` repository |
| Runtime | Docker; Dockerfile path `deploy/backend.Dockerfile`; build context `.` |
| Instance type | Free |
| Health check path | `/ready` |
| Environment | every variable in `deploy/public-demo.env` (Render sets `PORT` itself) |

Free instances of such services sleep when idle and need up to about a minute
to wake; the website explains the wait (it probes `/ready` on load). Any host
meeting the requirements works the same way; Hugging Face Spaces (Docker) is
another no-cost option.

After it is up (replace the URL):

```bash
API=https://<backend-host>
curl -s $API/ready                                  # 200, "ready"
curl -s $API/ready/existing-data -o /dev/null -w "%{http_code}\n"   # 503: no dataset, by design
curl -s -X OPTIONS $API/assessments/evaluate -H "Origin: https://imansgh.github.io" \
  -H "Access-Control-Request-Method: POST" -D - -o /dev/null | grep -i access-control-allow-origin
curl -s $API/assessments/contract | grep -o '"deployment_limits":{[^}]*}'
```

## 5. Website (GitHub Pages)

1. Repository *Settings → Pages → Source*: **GitHub Actions**.
2. *Settings → Secrets and variables → Actions → Variables*: add
   `CCS_PUBLIC_API_URL` = the backend's HTTPS URL (no trailing slash).
3. *Actions → "Website (GitHub Pages)" → Run workflow.* It runs the frontend
   tests and type check, then `npm run build:static` (base path
   `/poreledger-ccs`, repository link, embed origin `https://imansgh.me`),
   which fails on a non-HTTPS API URL or any loopback URL in the bundle.
4. Open `https://imansgh.github.io/poreledger-ccs/` and run a synthetic
   example.

The same bundle can be built locally with
`NEXT_PUBLIC_CCS_API_URL=https://<backend-host> npm run build:static`
(output in `frontend/out/`) and uploaded to any static host.

## 6. imansgh.me (Lovable)

The site needs one new page and a link to it. Ready-to-use page:
[`deploy/lovable/poreledger-ccs.tsx`](../deploy/lovable/poreledger-ccs.tsx)
(copy to `src/routes/poreledger-ccs.tsx`; it follows the site's existing
project pages and uses its `SectionHeader`). It shows the title and
disclaimers, "Open the demo full screen" and "Source code (MIT)" buttons,
and the embedded demo, which grows with its content. Its iframe sandbox
allows exactly what the demo needs: scripts and its own origin (API calls),
forms and file upload, downloads (exports), new tabs (repository link) and a
user-initiated top-level link (the footer's link back to imansgh.me).

Alternatively, paste this into the Lovable chat for the website project:

> Add a new page at the route `/poreledger-ccs` (file
> `src/routes/poreledger-ccs.tsx`) using exactly the code I provide
> [paste the file]. Then add a project card for "PoreLedger CCS — CO₂ Storage
> Screening & Uncertainty Analysis" to the Projects page, styled like the
> existing cards, linking to `/poreledger-ccs`, with tags Python, FastAPI,
> Next.js, CCS, Monte Carlo, MIT License, and add `/poreledger-ccs` to the
> sitemap. Do not change any other page.

Decide separately what happens to the existing page
`/projects/co2-storage-screening-dashboard`, which describes a different
tool (`imansgh/CO-Storage-Screening-Dashboard`): keep it, link the two, or
retire it.

## 7. Verified before publication (2026-10-02)

- Python suite, strict CoolProp reference group, frontend unit and
  real-backend integration suites, type check and production build.
- `npm run build:static` with an HTTPS URL: every asset under
  `/poreledger-ccs/_next/...`; no loopback URL anywhere in `out/` (the build
  enforces this).
- A local rehearsal of the architecture: the backend with the public-demo
  limits, the static bundle served under `/poreledger-ccs/` from a separate
  origin, and a host page embedding it with the sandbox above. Synthetic
  calculation, unavailable example, blocked CSV preview and corrected
  re-upload, JSON/CSV exports (also inside the sandboxed iframe), the
  cross-origin height message, the 429 and the API-unavailable messages,
  and a 375 px layout without horizontal overflow.

Not verified here: Docker builds (no Docker available), any real host, the
real GitHub Pages and imansgh.me integration, and a public HTTPS backend.
