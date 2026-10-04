# PoreLedger CCS frontend

Next.js interface for the 0.2.0 assessment workflow. The frontend package has
its own version (0.1.0); the Python/project release target is 0.2.0.
Scientific calculations run in FastAPI, not in this interface.

## Run locally

From the repository root, using Python 3.10+:

```bash
python -m pip install -e ".[dev,web]"
python scripts/serve.py --no-dataset --cors-origin http://localhost:3000
```

In another terminal, from this directory (Node.js 20+):

```bash
npm ci
npm run dev
```

Open `http://localhost:3000`. The default API is `http://127.0.0.1:8000`.
Use manual inputs, CSV/JSON upload or the shipped synthetic examples; no real
well dataset is needed. See [input schema](../docs/assessment-input-schema.md).

## Checks

```bash
npm test
npm run typecheck
npm run build
npm run test:assessment
npm run test:demo
```

Integration suites require the Python backend dependencies. `CCS_PYTHON`
selects their Python executable. See [CONTRIBUTING](../CONTRIBUTING.md) for
the existing-data integration fixture and the complete CI sequence.

## Static hosting and portfolio integration

`npm run build:static` requires `NEXT_PUBLIC_CCS_API_URL` to be a real HTTPS
backend URL. Set it before building; changing it afterwards does not update
the bundle. Default static base path: `/poreledger-ccs`.
`--local-preview` is for loopback rehearsals only.

The separate Lovable portfolio page embeds this frontend only after a demo URL
is configured. `NEXT_PUBLIC_CCS_EMBED_ORIGINS` allows parent origins to receive
height messages; it is independent of the API's `CCS_CORS_ORIGINS` setting.
The API must allow the frame's origin, not merely the portfolio's origin.

The public demo is not active. Do not deploy placeholder `.invalid` API URLs.
See [publication guide](../docs/public-release.md) for activation and remaining
end-to-end checks. Code and project documentation are [MIT licensed](../LICENSE).
