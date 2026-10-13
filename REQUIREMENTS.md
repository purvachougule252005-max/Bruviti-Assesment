# PartTrace compliance checklist

Authority: supplied `use_case_5_parts_catalogue_api.pdf`, all five pages, especially sections 3-7 and Appendix Q. User instructions add phase review gates and optional features. This checklist was created before application implementation. Unchecked items are not verified.

Final local status: implementation and available verification complete. Evidence is in `audit/phase5-verification.md`. Deadline and external submission steps remain open. Physical adapter disconnection and other operating systems were not tested; do not interpret a checked offline/performance item as an unlimited guarantee.

## Phase 1: specification and audit
- [x] Read the entire five-page specification, including timing, submission, and worked example.
- [x] Inspect all three supplied CSVs and preserve original bytes under root `data/`.
- [x] Record duplicates, normalization, revisions, missing references, cycles, disconnected parts, and serial issues in DATA.md.
- [x] Distinguish official rules, evidence, proposed policies, and unresolved ambiguities.
- [x] Prepare Phase 1 results and stop before application implementation.
- [x] User authorizes beginning Phase 2 with "Continue" after the Phase 1 report.

## Catalogue engine (Appendix Q; Phase 2)
- [x] Read `data/bom.csv` (`parent_pn,child_pn,quantity`), `data/parts_master.csv` (`part_number,revision,description,category,unit_cost`), and `data/service_parts.csv` (`part_number,field_replaceable,serial_from,serial_to`) from repository root.
- [x] Handle replacement exports with the same schema by general rules, without row/count-specific fixes; verified on independent small exports. Unspecified conflict policies are documented in DATA.md; hidden-grader compatibility is not guaranteed.
- [x] Catalogue is AS-40000 and all descendants; exclude all outside parts.
- [x] Normalize part identity consistently across sources and lookups.
- [x] Repeated design relationships do not multiply quantities.
- [x] Remove self-containment and unambiguous edges pointing back up from inside the root hierarchy; report removed edges in DATA.md. Reject unresolved multi-entry cycles under the documented policy.
- [x] Select highest-letter master revision and its description.
- [x] Status precedence: missing if absent from master; otherwise ready if marked Y; otherwise not_replaceable, with documented rejection of conflicting Y/not-Y records.
- [x] Missing parts have null description and null revision.
- [x] Root total quantity is 1; descendants count every assembly occurrence and multiply quantities along paths.
- [x] Direct parents are unique, in-machine, sorted; children are sorted by part number with per-parent quantity.
- [x] Return every root-to-part path, sorted lexicographically part by part.
- [x] Serial applicability counts distinct ready parts; bounded ranges include both endpoints; no range means all accepted serials.
- [x] Independently understandable offline fixtures cover the entire Appendix Q worked example, including configurable fixture root AS-1.
- [x] Prepare engine results and explanations; stop before Phase 3. Actual verification: 75 pytest cases passed; supplied-data engine smoke check recorded.
- [x] User authorizes beginning Phase 3 with "start phase 3".

## Exact required HTTP contracts (section 3; Phase 3)
- [x] `GET /api/validation`: only `parts`, `ready`, `missing`, `not_replaceable`, all integer counts.
- [x] `GET /api/parts/{part_number}`: `part_number` string, `description` string or null, `revision` string or null, `status` one of the three strings, `total_quantity` integer, `parents` string array, `children` array of `{part_number,quantity}` with integer quantities. Integer-only quantities follow the documented policy for this unspecified case.
- [x] `GET /api/parts/{part_number}/paths`: `{part_number: string, paths: string[][]}` in specified order.
- [x] `GET /api/serial/{serial}`: `{serial: integer, applicable_parts: integer}`.
- [x] Both part endpoints match case-insensitively and return HTTP 404 for out-of-machine/unknown parts.
- [x] Non-whole-number serial input returns 422; ASCII nonnegative digit syntax, leading zeros, and rejected formats are documented.
- [x] `GET /health` returns HTTP 200 and exactly `{"status":"ok"}` only when ready. Unavailable catalogue state returns 503; loading errors abort startup.
- [x] Verify schemas, field names, types, nulls, ordering, and errors with actual requests. Final suite: 122 passed, including 47 new HTTP/network-guard cases; eleven real HTTP responses captured in `audit/phase3-http.json`.
- [x] Prepare actual requests/responses and stop before Phase 4.
- [x] User authorizes Phase 4 with "Continue" after the Phase 3 report, and reinforces continuation during the phase.

## Runtime and interface (sections 4-5; Phase 4)
- [x] No LLM/external API calls at request time. API/assets pass with application connections blocked; browser assets/fetches are same-origin under CSP. A real server also completed startup and requests with outbound Python sockets/DNS blocked. Physical adapter disconnection was not performed.
- [x] Measure the under-one-second requirement: all 1,963 observed responses passed, including every supplied part/path and 16 serial boundary values. Required API maximum 40.860 ms. Unseen input sizes/hardware remain unverified; all-path output can grow exponentially.
- [x] Use supplied source data only; synthetic fixtures are test inputs, not added catalogue data. Source bytes match the original ZIP through Phase 5 and in the clean clone.
- [x] No training is used; the CPU training budget is not applicable.
- [x] One documented command, `python run.py`, installs dependencies and starts on port 8000; verified in an actual local clone and new virtual environment on Windows/Python 3.13.3 with cached wheels.
- [x] API and single demo page `/` run in the same process on port 8000.
- [x] Page accepts input and shows responses; local assets, system fonts, no externally hosted scripts/fonts/services.
- [x] Optional search, explanations, serial reasons, data quality, and hierarchy stay separate under `/demo/`; required responses remain unchanged.
- [x] Verify local-only dependencies and API/assets under the test network guard; perform browser interaction/phone/desktop checks. The machine's network adapter was not disabled; record this limit in `audit/phase4-verification.md`.
- [x] Prepare Phase 4 results and pause before final delivery work.
- [x] User authorizes Phase 5 with "continue" after the Phase 4 report.

## Delivery and final verification (sections 4-6; Phase 5)
- [x] Local Git repository contains working service and required deliverables; no remote configured.
- [x] README.md: fresh-reader setup/start command, prerequisites, and test instructions.
- [x] DATA.md: source, findings, handling decisions, and test design.
- [x] NOTES.md: concise one-page-length decisions, scope cuts, and next steps (under 300 words).
- [x] AI.md: actual AI/tool uses across all five phases recorded.
- [x] `tests/` contains meaningful engine and HTTP tests runnable without external network access. Windows internal socket pairs are permitted; application connections remain blocked.
- [x] Generalization verified using 20 generated exports and an independent path-enumeration oracle; supplied CSVs unchanged. Final suite: 155 passed in both development and clean-clone environments.
- [x] Startup checked in a fresh local clone/new virtual environment; documented limits include reused OS/Python/pip cache, no Linux/macOS check, and no physical adapter disconnection.
- [x] Check tracked files for secret patterns, virtual environments, and files over 50 MB; evidence in `audit/phase5-packaging.json`. Pattern checks found no credentials; this is not a guarantee of exhaustive secret detection.
- [x] Final checklist, verification record, and `WALKTHROUGH.md` completed; actual test failure/recovery and unperformed checks disclosed.

## Timing, confidentiality, and submission (sections 1, 6-7)
- [ ] User supplies actual deadline and timezone from original brief-opening page. PDF gives only 24 hours after opening; current chat date is not the deadline.
- [x] Work kept local and not shared with other candidates; ongoing confidentiality duty remains until the deadline.
- [ ] Finish relevant commits before deadline; later commits/form submissions are ignored.
- [ ] Private GitHub repository (future action, requires explicit user authorization).
- [ ] Add `bruviti-campus` collaborator (future action, requires explicit user authorization).
- [ ] Submit repository link through specified form, selecting use case 5, before deadline (future action, requires explicit user authorization). Last pre-deadline submission counts.

No remote repository, collaborator invitation, publication, or submission is authorized by the attachment. Phase progression requires user review. Submission tasks remain separate from local build completion.
