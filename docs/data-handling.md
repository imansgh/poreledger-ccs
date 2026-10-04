# How submitted data is handled

This describes what the software actually does with data you enter or upload.
A deployment's operator may add their own infrastructure (proxies, log
collection); check with them for a hosted instance.

| Question | Answer |
| --- | --- |
| Is my data stored? | **No.** Assessments are validated and evaluated in memory, returned in the response, and discarded. Nothing is written to a database or to disk. |
| Is it added to the well dataset? | **No.** User assessments never touch the existing-data cache or files (tested: `test_assessments_never_touch_the_cached_well_records`). |
| Temporary files? | **None.** An uploaded file is read in the browser and sent as text in the request body; the server parses that text in memory. |
| Is it logged? | The application does not log request bodies or submitted values. Run directly, the ASGI server (uvicorn) logs one access line per request: client address, method, path and status code; the container image and the public demo turn that off (`--no-access-log`). Unexpected server errors are logged with a traceback (no request body). |
| Rate limiting state? | With the opt-in rate limit on, the server keeps, in memory only, the times of each client address's recent POST requests (at most one minute, at most 10 000 addresses); nothing is written to disk and it is lost on restart. |
| Is file content executed? | **No.** JSON and CSV are parsed as data. Embedded text (notes, sources, names) is treated as text and never interpreted as an instruction or code. |
| What leaves the browser? | Only the request to the configured API URL. Exports (JSON results, CSV summary) are built in the browser from the response; downloads are not uploaded anywhere. |
| Can an exported CSV run a formula? | **No.** In the CSV summary, names and ids that start (after any leading whitespace) with `=`, `+`, `-`, `@`, tab, CR or LF are prefixed with `'`, so a spreadsheet shows the text instead of evaluating it. The JSON result keeps the text unchanged. |
| What do errors echo? | Field paths and messages; a message may quote an offending value. |
| Limits | 200 000-byte files, 50 assessments, 100 observations each, 200 000 Monte Carlo realisations per request, 256 KiB request bodies on `/assessments/*`. |

The bundled synthetic examples and templates are static files inside the
Python package (`src/ccs_screen/assessment_data/`).

## The public demo

The public demo is not deployed yet. Its planned configuration (see
[public-release.md](public-release.md)) uses [`deploy/public-demo.env`](../deploy/public-demo.env):
no well dataset, no application access log, the rate limit above, and CORS
open only to the website's origin. The planned architecture uses separate static and API hosts. Their
infrastructure logging policies must be checked when a provider is selected;
they are outside this software's control:

- the static website host (GitHub Pages) receives the page and asset
  requests, never your data;
- the backend platform's proxy sees each API request's metadata (address,
  path, time, status). Request bodies, which carry your inputs, are not
  logged by this software.

The demo is for trying the tool. For confidential data, run it locally (see
the README quick start): nothing then leaves your machine.
