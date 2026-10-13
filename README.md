# PartTrace - Machine Parts Explorer

Service parts catalogue for the AM-700 machine. **Current stage: Phase 4 demo complete.** The API and demo page run from the same process on port 8000. The single-command install/start launcher and final delivery checks remain pending.

## Requirements

Python 3.11 or newer with pip and venv (the pinned Starlette version requires 3.11). The engine itself uses only the standard library; the HTTP service uses FastAPI, Pydantic, and Uvicorn. The current suite was run on Python 3.13.3.

The supplied files belong at repository-root `data/`:

- `bom.csv`: `parent_pn,child_pn,quantity`
- `parts_master.csv`: `part_number,revision,description,category,unit_cost`
- `service_parts.csv`: `part_number,field_replaceable,serial_from,serial_to`

Replacing these files and loading a new catalogue applies the same rules to the new export. Source files are never modified. No external catalogue data is used.

## Install and run the API

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn parttrace.api:app --host 127.0.0.1 --port 8000 --lifespan on
```

On macOS/Linux use `python3 -m venv .venv`, then `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`. Stop the server with Ctrl+C. These steps have been exercised in the existing development environment; a single-command fresh-clone launcher and clean-environment verification remain for Phase 5.

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

The latest verified invocation used `--basetemp=tmp/pytest-phase4-final` to keep temporary files inside the ignored `tmp/` directory. Use a dedicated directory because pytest manages its contents. This Windows execution sandbox also blocks the async loop's internal loopback connection, so the test run required execution outside that sandbox; the test network guard remained enabled.

Latest run: **135 passed** (the prior 122 engine/API/guard cases plus 13 demo cases). Browser interactions and phone/desktop layouts were checked; see `audit/phase4-verification.md`. Assets/API were tested with application network connections blocked, but the computer's network adapter was not disabled. Final performance, machine-wide offline, and clean-startup verification remain pending.

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
- `parttrace/static/`: one HTML page, local CSS, and plain JavaScript; display text is inserted with `textContent` rather than interpreting source data as HTML.
- `tests/fixtures/appendix_q/`: the brief's worked example; descriptions/category/cost not specified there use neutral fixture values.
- `tests/`: small fixtures covering the worked example, shared assemblies, errors, serial boundaries, and row-order independence.
- `DATA.md`: findings, implemented policies, test design, and remaining ambiguities.
- `REQUIREMENTS.md`: phase-by-phase compliance checklist.
- `NOTES.md` and `AI.md`: decisions/scope and AI assistance disclosure.

For quantities, start the root at one and add `parent total * quantity per parent` into each child. The worked example's FA-9 therefore has `4 + 2 * 3 = 10`. Paths describe design routes, so multiple physical occurrences on one route do not produce repeated identical paths. Serial applicability counts distinct ready parts, not their physical quantities.

## Remaining delivery work

Phase 5 completes and verifies the single install/start command, HTTP performance, offline operation, further generalization, and final documentation. The real submission deadline is not provided in the PDF and still needs confirmation from the original assignment page. Publishing, inviting a collaborator, and submitting require separate user authorization.
