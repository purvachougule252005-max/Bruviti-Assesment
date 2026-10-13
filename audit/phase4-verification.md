# Phase 4 verification record

## Automated checks actually run

Command: `.\.venv\Scripts\python.exe -m pytest --basetemp=tmp/pytest-phase4-final -q --tb=short`

Result: **135 passed in 2.18s**, using Python 3.13.3. This includes the prior 122 engine/API/guard cases and 13 new demo cases. Tests block application socket connections and DNS, with the documented Windows internal socket-pair exception. The HTML, CSS, JavaScript, required API, and demo endpoints were served by the same app in these tests.

New coverage: local asset availability/CSP, number and selected-description search, exclusion of obsolete revision descriptions/outside parts, bounded search and exact-match priority, correct revision/quantity/status explanations, serial boundary reasons, missing-master precedence, data-quality evidence, and unchanged required response fields. `node --check parttrace/static/app.js` also succeeded. Source hashes still match the Phase 1 audit.

## Browser checks actually performed

The existing Codex in-app browser was navigated from `/health` to the local page at `http://127.0.0.1:8000/`. Its API server is Uvicorn running the same `parttrace.api:app` process on port 8000.

- Initial page populated 875 total / 483 ready / 25 missing / 367 not replaceable.
- Lowercase `fa-30019` search found the canonical number. Description search `washer` returned FA-30019, FA-30020, FA-30021.
- FA-30019 displayed quantity 178, revision A, 22 paths, and the sum of actual parent contributions. The terms table is available for each multiplication.
- Serial `2.5` showed HTTP 422; the raw Serial response showed the actual error body. Replacing it with `2500` recovered successfully, showed 448 applicable parts overall and the selected ready part's unrestricted-serial reason.
- EL-10024 displayed missing status, unavailable description/revision, an inapplicability explanation, and actual nulls in the raw Part response.
- AS-40210 search showed no results, preserving machine-only membership.
- Expanding the hierarchy root loaded eight direct children, each with per-parent quantity 1.
- Data quality displayed 26 normalized cells, 40 repeated rows ignored, one upward edge removed, and five outside-parent relationships excluded. Expanding removed relationships showed AS-40209 -> AS-40002 with bom.csv:55.
- Browser developer logs inspected during these interactions contained no error/warning entries.
- At a 390-pixel viewport override, document client/scroll widths were both 375 pixels (scrollbar excluded); the page loaded successfully. At 1100 pixels, client/scroll widths were both 1085 pixels. Thus neither tested width had horizontal overflow. Temporary viewport overrides were reset afterward.
- The actual loaded document references only `/static/style.css` and `/static/app.js`; fonts are system fonts and the favicon is an empty data URI. The saved screenshot is `audit/phase4-desktop.png`.

## Offline evidence and limits

All assets and fetches are local/same-origin, and the page's CSP restricts scripts/styles/fonts/connections to its own origin. Application tests succeed with outbound connections blocked. Browser interactions succeeded against the local server without third-party assets or services. No model or external API is used.

The computer's network adapter was **not** disabled. A machine-wide network-off check, broader HTTP latency measurements, fresh-environment startup verification, final packaging, and the single-command launcher remain Phase 5 work. Browser checks are manual tool-driven observations, not a committed automated browser test suite. Suite duration is not an HTTP latency benchmark.
