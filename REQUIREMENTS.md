# PartTrace compliance checklist

Authority: supplied `use_case_5_parts_catalogue_api.pdf`, all five pages, especially sections 3-7 and Appendix Q. User instructions add phase review gates and optional features. This checklist was created before application implementation. Unchecked items are not verified.

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
- [x] No LLM/external API calls at request time. API/assets pass with application connections blocked; browser assets/fetches are same-origin under CSP. Machine-wide network-off verification remains a Phase 5 check.
- [ ] Every required request completes in under one second; measure representative/worst available cases and state limits of evidence.
- [x] Use supplied source data only; synthetic fixtures are test inputs, not added catalogue data. Source hashes unchanged through Phase 4.
- [x] No training is used; the CPU training budget is not applicable.
- [ ] One documented command installs dependencies and starts from a fresh clone on port 8000.
- [x] API and single demo page `/` run in the same process on port 8000.
- [x] Page accepts input and shows responses; local assets, system fonts, no externally hosted scripts/fonts/services.
- [x] Optional search, explanations, serial reasons, data quality, and hierarchy stay separate under `/demo/`; required responses remain unchanged.
- [x] Verify local-only dependencies and API/assets under the test network guard; perform browser interaction/phone/desktop checks. The machine's network adapter was not disabled; record this limit in `audit/phase4-verification.md`.
- [x] Prepare Phase 4 results and pause before final delivery work.
- [ ] User reviews Phase 4 and authorizes Phase 5.

## Delivery and final verification (sections 4-6; Phase 5)
- [ ] Local Git repository contains working service and required deliverables.
- [ ] README.md: fresh-reader setup/start command, prerequisites, and test instructions.
- [ ] DATA.md: source, findings, handling decisions, and test design.
- [ ] NOTES.md: decisions, scope cuts, next steps, at most one page.
- [ ] AI.md: honestly record every AI tool and purpose; keep current throughout work.
- [x] `tests/` contains meaningful engine and HTTP tests runnable without external network access. Windows internal socket pairs are permitted; application connections remain blocked.
- [ ] Generalization verified using independent fixtures without changing supplied CSVs.
- [ ] Startup checked in clean environment where possible; unperformed checks reported explicitly.
- [ ] Check repository for secrets, virtual environments, and files over 50 MB.
- [ ] Final checklist and simple project walkthrough completed; no unrun tests claimed as passing.

## Timing, confidentiality, and submission (sections 1, 6-7)
- [ ] User supplies actual deadline and timezone from original brief-opening page. PDF gives only 24 hours after opening; current chat date is not the deadline.
- [ ] Keep brief and submission confidential until deadline; do not share with other candidates.
- [ ] Finish relevant commits before deadline; later commits/form submissions are ignored.
- [ ] Private GitHub repository (future action, requires explicit user authorization).
- [ ] Add `bruviti-campus` collaborator (future action, requires explicit user authorization).
- [ ] Submit repository link through specified form, selecting use case 5, before deadline (future action, requires explicit user authorization). Last pre-deadline submission counts.

No remote repository, collaborator invitation, publication, or submission is authorized by the attachment. Phase progression requires user review. Submission tasks remain separate from local build completion.
