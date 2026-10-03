# Contributing

Thanks for your interest. This is research software whose value depends on
being honest about what it does and does not know, so contributions are held to
two standards: the usual software ones, and a stricter one for anything that
changes a scientific result.

> **License.** The software is released under the [MIT License](LICENSE);
> contributions are accepted under the same license. The MIT license covers
> this repository's code and documentation only: it grants no rights to
> external datasets, well reports or publications, including any you cite or
> submit (see [docs/data-contribution.md](docs/data-contribution.md)). For a
> large change, please open an issue to discuss it first.

## Kinds of contribution

| You want to... | Use |
| --- | --- |
| Report a bug | *Bug report* issue template |
| Offer real well data | Read [docs/data-contribution.md](docs/data-contribution.md), then the *Data submission* template |
| Change the model, a prior, a guard or how data is interpreted | *Scientific / model proposal* template, **before** writing code |
| Improve code, tests, docs or the website | A pull request; open an issue first for anything non-trivial |

## Development setup

Python 3.10+ and Node.js 20+.

```bash
python -m venv .venv
. .venv/bin/activate                      # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev,web]"      # add CoolProp to run the EOS reference tests

cd frontend
npm ci                                     # installs exactly the committed lockfile
```

Run the app (user assessments need no dataset; `--demo` also loads the
fictional demo wells for the optional existing-data section):

```bash
python scripts/serve.py --demo --cors-origin http://localhost:3000
cd frontend && npm run dev                 # http://localhost:3000
```

Real data is not in the repository. If you have it locally, use
`python scripts/serve.py --data-dir <dir>`; never commit it (`data/` is
git-ignored).

## Checks

Run all of these before opening a pull request; CI runs the same set.

```bash
python -m pytest -q
CCS_REQUIRE_REFERENCE_TESTS=1 python -m pytest tests/test_independent_calculation_audit.py tests/test_properties_audit.py   # needs CoolProp
cd frontend
npm test
npm run typecheck
npm run build
npm run test:assessment                    # user workflow, real backend, no dataset
npm run test:demo                          # real backend on the demo dataset
python ../scripts/make_integration_fixture.py /tmp/ccs-fixture
CCS_INTEGRATION_DATA_DIR=/tmp/ccs-fixture npm run test:integration
```

`npm run test:integration` without `CCS_INTEGRATION_DATA_DIR` uses a local
`data/` if present and skips otherwise; with the variable set, a missing or
not-ready dataset is a failure. `CCS_PYTHON` selects the interpreter the
integration suites start the backend with.

Report results honestly in the pull request: what passed, what failed, what
was skipped and why.

If you change a backend response the frontend renders, regenerate the
frontend fixtures (`python scripts/build_frontend_fixtures.py`);
`tests/test_frontend_fixtures.py` fails while they are stale.

## Pull requests

- Keep changes focused; avoid unrelated refactoring.
- Add a regression test for every bug fix and a test for every behaviour change.
- Match the surrounding code's style and comment density.
- Update the documentation the change affects (API contract, deployment, demo tables).
- Never commit credentials, local paths, real datasets or build output.

## Scientific changes

These rules protect the meaning of every number the tool reports.

- **The Model Contract is authoritative**
  ([docs/phase13-owner-decision-record.md](docs/phase13-owner-decision-record.md)).
  Equations, priors, eligible temperature methods, the depth-reference and
  envelope guards, and the validation statuses change only through an explicit,
  recorded owner decision.
- **Evidence first.** A proposal cites primary sources and states what changes,
  for which wells, and what new failure modes it introduces.
- **No silent defaults.** Never make a result appear by assuming a datum,
  inventing an interval, substituting a temperature, filling a missing value,
  or relabelling a `NOT_VALIDATED` or `UNAVAILABLE` result.
- **Provenance travels with values.** New inputs carry their source, method and
  confidence; synthetic or assumed values are labelled as such.
- **One engine.** User assessments and existing wells must keep sharing
  `api._screen_approved`; never add a second calculator, in Python or in the
  browser. Expected values in tests come from the contract or from the
  independent implementation, never from the code under test.
- **`UNAVAILABLE` is an acceptable outcome.** A change that turns many
  `UNAVAILABLE` results into numbers needs especially strong evidence.

## Reporting a security issue

Please do not open a public issue for a vulnerability; contact the maintainer
privately through the repository host.
