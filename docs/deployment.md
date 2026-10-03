# Deployment

Two parts: a **FastAPI** backend (`ccs_screen.web.app:app`) and a **Next.js**
website. The browser calls the backend directly, so the backend URL must be
reachable from visitors over HTTPS and must allow the website's origin.

There is **no authentication**. Abuse controls are a request-body cap and
per-request computation bounds (always on), plus an opt-in per-client rate
limit and an evaluation concurrency cap for a public single-process
deployment (see below). Nothing is deployed from this repository
automatically. The public demo plan, with the exact settings, is in
[public-release.md](public-release.md).

## What a deployment needs

The primary workflow -- users entering or uploading their own data -- needs
**no dataset at all**. The engine, the approved priors, the synthetic examples
and the templates ship inside the Python package. A well dataset is optional
and only serves the "Existing well data" section and the `/wells` and
`/funnel` endpoints. No persistent storage is needed.

## Choosing the optional dataset

| Dataset | `CCS_DATA_DIR` | Persistent storage |
| --- | --- | --- |
| None (public demo) | a path that does not exist, e.g. `/app/no-existing-well-dataset` | none |
| Synthetic demo wells (bundled) | `demo/data` (in the image: `/app/demo/data`) | none; read-only, ships with the code |
| Real structured sources | a directory you provide, e.g. `/data` | required: mount it **read-only**; never bake it into an image |

The choice is explicit. A missing, incomplete or unreadable dataset makes
`/ready/existing-data` answer `503` naming the failed sources (the engine
stays ready); it never falls back to the demo. A directory that mixes the demo
manifest with real source files is refused. The real datasets are not
distributed with this repository and their redistribution rights are not
established; never publish them with a deployment.

## Backend

### Environment

The backend reads only the process environment (it does not load a `.env`
file itself). See [`.env.example`](../.env.example) for local use and
[`deploy/public-demo.env`](../deploy/public-demo.env) for the public demo.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CCS_DATA_DIR` | `data` | dataset directory (see above) |
| `CCS_CORS_ORIGINS` | *(empty)* | comma-separated browser **origins** (scheme + host + port, no path) allowed to call the API. Empty means no cross-origin access; there is no wildcard default and `*` must not be used. |
| `CCS_MAX_BODY_BYTES` | `16384` | request-body cap; enforced on bytes actually received (`413` above it) |
| `CCS_MAX_ASSESSMENT_BODY_BYTES` | `262144` | separate cap for `/assessments/*`, which carry uploaded files |
| `CCS_RATE_LIMIT_PER_MINUTE` | `0` (off) | POST requests allowed per client address per rolling minute; over it: `429` with `Retry-After` |
| `CCS_MAX_CONCURRENT_EVALUATIONS` | `0` (no cap) | Monte Carlo runs allowed at once (evaluate, well screening, temperature comparison); over it: `503` `ServerBusy` with `Retry-After`, no queueing |
| `CCS_WARM_CACHE` | `1` | load the dataset at startup |
| `CCS_DOCS` | `1` | set `0` to hide `/docs` and `/redoc` |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | uvicorn: proxy addresses trusted for `X-Forwarded-For` (the client address the rate limit uses) |
| `PORT` | `8000` | container listen port; hosting platforms usually set it |

### Computation bounds

Always enforced, per request: at most 50 assessments, 100 observations each,
`samples <= 50000`, and at most 200 000 Monte Carlo realisations per
`/assessments/evaluate` request. Measured on the development machine, the
largest allowed request takes about 5 s of CPU; a typical website calculation
(2 000 realisations per assessment) takes well under 0.1 s per assessment.

### Rate and concurrency limits are per process

Both opt-in limits keep their state in the process. They are right for a
**single-process** public demo (the container runs one uvicorn process). With
several workers or instances each would count separately, so a scaled
deployment should enforce limits at the reverse proxy or API gateway instead.
Behind a proxy, the client address is taken from `X-Forwarded-For` only for
proxies listed in `FORWARDED_ALLOW_IPS`; `*` is safe only where the container
is reachable exclusively through the platform's proxy. Read-only requests
(`GET`), CORS preflights, `/health` and `/ready` are never rate limited.
`GET /assessments/contract` reports the active limits in `deployment_limits`.

### Health and readiness

| Endpoint | Meaning | Use for |
| --- | --- | --- |
| `GET /health` | **Liveness.** `200` with `status: "ok"` whenever the process is serving. Reports `engine_ready`, `data_ready` and the `dataset` (with `synthetic`). | restart decisions |
| `GET /ready` | **Engine readiness.** `200` when user assessments can be evaluated (a self-check runs the complete synthetic example through the approved engine); independent of any dataset. | routing traffic, deploy gates, platform health checks |
| `GET /ready/existing-data` | **Optional dataset readiness.** `200` when every required source loaded and at least one well was normalized; otherwise `503` with `problems` and per-source status. | monitoring the optional dataset only |

Readiness concerns the software's inputs only. A ready service still returns
`UNAVAILABLE` results wherever the Model Contract requires it.

### Run it

```bash
python -m pip install ".[web]"            # add ",ingest" for real data (openpyxl)
CCS_DATA_DIR=/nonexistent CCS_CORS_ORIGINS=https://www.example.org \
CCS_RATE_LIMIT_PER_MINUTE=20 CCS_MAX_CONCURRENT_EVALUATIONS=2 \
  uvicorn ccs_screen.web.app:app --host 0.0.0.0 --port 8000 --proxy-headers --no-access-log
```

For local development, `python scripts/serve.py --no-dataset --cors-origin http://localhost:3000`
(or `--demo`) does the same without installing the package.

## Website

### Build-time settings

`NEXT_PUBLIC_*` variables are **compiled into the JavaScript bundle by
`next build`**. Changing them needs a rebuild, and they are visible to every
visitor, so they must never hold secrets. See
[`frontend/.env.example`](../frontend/.env.example).

| Variable | Required | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_CCS_API_URL` | yes for any non-local build | the backend's public HTTPS URL. A `next build` without it falls back to `http://127.0.0.1:8000` and shows a visible warning; `npm run build:static` refuses to build without an HTTPS URL. |
| `NEXT_PUBLIC_CCS_BASE_PATH` | no | URL subpath the site is served under, e.g. `/poreledger-ccs` (no trailing slash). `npm run build:static` defaults to `/poreledger-ccs`. |
| `NEXT_PUBLIC_CCS_REPO_URL` | no | an `https://` repository URL to link from the site. Unset: no link is shown. |
| `NEXT_PUBLIC_CCS_EMBED_ORIGINS` | no | parent-page origins that may embed the site in an iframe and receive its height (`{type: "poreledger-ccs:height", height}` via `postMessage`). `npm run build:static` defaults to `https://imansgh.me`. |

### Static export (used for the public demo)

```bash
cd frontend
npm ci
NEXT_PUBLIC_CCS_API_URL=https://<backend-host> npm run build:static
# -> out/ : upload to any static host, served under /poreledger-ccs/
```

`build:static` requires an HTTPS API URL and **fails if any file in `out/`
contains a loopback URL** (`http://localhost`, `127.0.0.1`, ...). It writes
`out/.nojekyll` (GitHub Pages) and `out/deployment-info.json` (the settings it
was built with). For a local smoke test only: a loopback URL plus
`-- --local-preview`. The workflow
[`.github/workflows/pages.yml`](../.github/workflows/pages.yml) runs the same
build and publishes it to GitHub Pages (manual trigger; see
[public-release.md](public-release.md)).

### Node server (alternative)

```bash
NEXT_PUBLIC_CCS_API_URL=https://<backend-host> npm run build
npm run start            # serves on port 3000
```

## Containers

Files: [`deploy/backend.Dockerfile`](../deploy/backend.Dockerfile),
[`deploy/frontend.Dockerfile`](../deploy/frontend.Dockerfile),
[`docker-compose.yml`](../docker-compose.yml), [`.dockerignore`](../.dockerignore).

```bash
docker compose up --build          # local demo stack on http://localhost:3000
docker build -f deploy/backend.Dockerfile -t poreledger-ccs-api .
docker run --rm -p 8000:8000 --env-file deploy/public-demo.env poreledger-ccs-api
```

- The backend image contains the code and the synthetic demo wells only;
  `.dockerignore` excludes `data/`, environments and build output. It sets no
  `CCS_DATA_DIR`.
- It runs **one** uvicorn process on `$PORT` (default 8000) with
  `--proxy-headers` and `--no-access-log`. Its health check probes `/ready`.
- The frontend image requires the `NEXT_PUBLIC_CCS_API_URL` build argument
  (and accepts `NEXT_PUBLIC_CCS_BASE_PATH`); build one image per backend URL.

These container files have **not been built** in the environment where they
were written (Docker was not available there); build and smoke-test them
before relying on them.

## Checklist before a public deployment

- [ ] Publication authorized; license and data decisions recorded ([release-decisions.md](release-decisions.md)).
- [ ] Backend started with [`deploy/public-demo.env`](../deploy/public-demo.env): no dataset, exact `CCS_CORS_ORIGINS`, rate and concurrency limits on.
- [ ] Backend reachable over HTTPS; platform health check on `/ready`.
- [ ] Website built with `npm run build:static` (HTTPS API URL; loopback scan passed).
- [ ] Data-handling statement ([data-handling.md](data-handling.md)) matches the hosting (platform logs and retention).
