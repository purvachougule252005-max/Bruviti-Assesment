# PartTrace - Machine Parts Explorer

Service parts catalogue for the AM-700 machine. The API and demo page run from the same process on port 8000. Local implementation and verification are complete, with specific verification limits listed below. Publication and submission are separate user-controlled steps.

## Requirements

Python 3.11 or newer with pip and venv (the pinned Starlette version requires 3.11). The engine itself uses only the standard library; the HTTP service uses FastAPI, Pydantic, and Uvicorn. The current suite was run on Python 3.13.3.

The supplied files belong at repository-root `data/`:

- `bom.csv`: `parent_pn,child_pn,quantity`
- `parts_master.csv`: `part_number,revision,description,category,unit_cost`
- `service_parts.csv`: `part_number,field_replaceable,serial_from,serial_to`

Replacing these files and loading a new catalogue applies the same rules to the new export. Source files are never modified. No external catalogue data is used.

## Install and start with one command

From the repository root, with Python 3.11+ installed:

```powershell
python run.py
```

On macOS/Linux use `python3 run.py` if Python is named `python3`; the OS must provide Python's `venv`/pip support. The launcher creates an isolated `.venv`, installs pinned service dependencies, and starts Uvicorn at **http://127.0.0.1:8000/**. Stop it with Ctrl+C. Port 8000 must be free. No environment variables or credentials are needed.

First-time dependency installation needs a package index or populated pip cache. Later starts skip installation when the pinned packages are present; the running service needs no network. The launcher resolves paths from its own file, including paths with spaces. Recreate `.venv` when changing Python versions.

This exact command was verified in a fresh local Git clone with a new virtual environment on Windows/Python 3.13.3. pip reused cached wheels. Linux/macOS and a completely new operating-system image were not exercised. See `audit/phase5-startup.json`.

The catalogue loads once before the server accepts requests. Relevant data conflicts abort startup. Restart after replacing `data/`. `GET /health` returns HTTP 200 with `{"status":"ok"}` once loading has succeeded. A request without an available catalogue receives 503.

| GET path | Successful response |
| --- | --- |
| `/api/validation` | Integer `parts`, `ready`, `missing`, `not_replaceable` counts |
| `/api/parts/{part_number}` | Part metadata, status, total quantity, sorted direct parents and children |
| `/api/parts/{part_number}/paths` | Canonical part number and every sorted root-to-part path |
| `/api/serial/{serial}` | Integer `serial` and `applicable_parts` |
| `/health` | `{"status":"ok"}` |

Part lookups ignore case and outer whitespace; both return 404 for unknown or outside-machine parts. Missing parts remain queryable with null description and revision. Serial URLs accept ASCII digits, zero, and leading zeros; the response uses an integer. Signed, decimal (including `2500.0`), exponent, whitespace, and nonnumeric strings return 422. This syntax is a documented choice where the brief is not explicit. Values exceeding Python's integer-string parsing limit also receive 422.

Example request from a second PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/serial/2500
```

Recorded real HTTP responses appear in `audit/phase3-http.json`. The generated schema is available at `/openapi.json`; CDN-dependent interactive documentation is disabled. Open `http://127.0.0.1:8000/` for the demo page.

## Use the demo

1. Search by part number or current description; select a result to inspect it. Search is case-insensitive and returns up to 50 results with the total match count.
2. Read the selected revision, replacement status, and quantity explanation. Expand the contribution table for the parent count multiplied by quantity per parent.
3. Enter a machine serial and choose **Check fit**. The page explains this part's compatibility and shows the total number of applicable ready parts.
4. Navigate through parent/child links, expand all paths, or browse the lazily loaded machine hierarchy.
5. Review data-quality counts and source lines for removed edges. Expand **Inspect the API responses** to see the last actual Part, Paths, Serial, Validation, or Health response.

For the supplied export, try `washer`, choose FA-30019, and check serial 2500. FA-30019 has quantity 178 across 22 paths and applies without a serial restriction; 448 ready parts overall apply to that serial. EL-10024 demonstrates missing metadata; `2.5` demonstrates a serial error. These are walkthrough examples, not hardcoded answers.

All page assets and fonts are local/system-provided. Search and deterministic explanations use separate `/demo/search`, `/demo/quality`, and `/demo/parts/{part_number}/explanation` endpoints. Required `/api` responses retain their exact schemas. Synthetic fixtures never appear in the normal page.

## Install test dependencies and run tests

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Dependency installation may use the network. Once dependencies are installed, the tests run without external network access. HTTP tests use an in-process ASGI client. A fixture blocks application socket connections and DNS resolution, permitting only the internal socket pair that Windows needs to create an async event loop. Regression tests ensure this exception cannot enable normal application connections.

The documented `pytest -q` command works from a fresh clone. For a custom `--basetemp`, create its parent directory first and use a dedicated location because pytest manages its contents. This Windows execution sandbox blocks the async loop's internal loopback connection, so verification ran outside that sandbox; the test network guard remained enabled.

Final suite: **155 passed**, including 20 generated exports checked through HTTP against independent forward path enumeration. It also passed in the clean clone (5.94 seconds). Browser interactions and phone/desktop layouts were checked; see `audit/phase4-verification.md`.

## Verification and its limits

`audit/phase5-verification.md` records final evidence. A separate real HTTP server ran with outbound socket connections and DNS blocked during catalogue startup and requests. All 1,963 timed responses finished under one second, including all 875 part responses and 875 path responses. The slowest required API request was 40.860 ms; the slowest response including page/assets was 197.018 ms. Eight concurrent clients also exercised the largest supplied path result. Timings include a local TCP connection and the full response body.

Repeat this measurement after installing dependencies:

```powershell
.\.venv\Scripts\python.exe tools/verify_service.py
```

On macOS/Linux use `.venv/bin/python`. The script starts and stops its own server on a free loopback port and writes `audit/phase5-performance.json`. It checks the supplied dataset, not hidden grading data. Raw timings and platform details are in that JSON file.

The network adapter was not physically disabled. Offline evidence consists of blocked application connections/DNS, local-only assets, and successful runtime behavior under that guard. Performance on arbitrary graphs or another computer is not guaranteed: returning every path can produce exponentially large output. Unspecified conflicting-record policies remain documented assumptions in DATA.md.

## Try the engine

Run with Python from the repository root (no dependency installation needed):

```sh
python -c "from parttrace import Catalogue; print(Catalogue.from_directory().validation())"
```

Python usage:

```python
from parttrace import Catalogue

catalogue = Catalogue.from_directory()  # Default data path is relative to the source, not the working directory.
catalogue.validation()
catalogue.part("fa-30019")
catalogue.paths("FA-30019")
catalogue.serial(2500)
```

Construction reads the files once. Query methods use the loaded snapshot and return independent dictionaries. Reload by constructing a new catalogue after changing files. Unknown/outside-machine identifiers raise `PartNotFound`; unresolved relevant data conflicts raise `CatalogueDataError`. The API translates lookup errors to HTTP 404. The engine accepts nonnegative integer serial values; the API parses digit-only URL strings before invoking it.

## Understand the code

- `parttrace/catalogue.py`: read/normalize CSVs, resolve revisions and service ranges, calculate quantities, expose query methods and source-linked diagnostics.
- `parttrace/graph.py`: follow directed containment from the root, remove self-edges and unavoidable-ancestor edges, reject unresolved cycles, order parents before children.
- `parttrace/api.py`: load the snapshot during startup, enforce exact response models, parse serial inputs, and translate lookup errors into HTTP responses.
- `run.py`: create/check the virtual environment, install dependencies when needed, and launch the service.
- `parttrace/static/`: one HTML page, local CSS, and plain JavaScript; display text is inserted with `textContent` rather than interpreting source data as HTML.
- `tests/fixtures/appendix_q/`: the brief's worked example; descriptions/category/cost not specified there use neutral fixture values.
- `tests/`: small fixtures covering the worked example, shared assemblies, errors, serial boundaries, and row-order independence.
- `DATA.md`: findings, implemented policies, test design, and remaining ambiguities.
- `REQUIREMENTS.md`: phase-by-phase compliance checklist.
- `NOTES.md` and `AI.md`: decisions/scope and AI assistance disclosure.

For quantities, start the root at one and add `parent total * quantity per parent` into each child. The worked example's FA-9 therefore has `4 + 2 * 3 = 10`. Paths describe design routes, so multiple physical occurrences on one route do not produce repeated identical paths. Serial applicability counts distinct ready parts, not their physical quantities.

## Walkthrough and submission status

See `WALKTHROUGH.md` for a short demo script and explanations to practice, and `REQUIREMENTS.md` for the final checklist. All supplied CSV bytes remain unchanged; `.gitattributes` preserves them across Git checkouts. Virtual environments, caches, and temporary verification clones are ignored. Use the Git repository rather than copying the entire working directory when preparing a submission.

The repository is local only. The real deadline still needs confirmation from the original assignment page. A private remote repository, the required collaborator invitation, and form submission have not been performed; they require separate user authorization. Confidentiality continues to apply.
