# PartTrace walkthrough

## A three-minute demonstration

1. From the repository root run `python run.py`, then open `http://127.0.0.1:8000/`. Startup loads all three CSVs before `/health` reports `{"status":"ok"}`.
2. Point to the supplied-export counts: 875 machine parts, 483 ready, 25 missing, 367 not replaceable. These are calculated at startup, not constants.
3. Search `washer` or lowercase `fa-30019`. Select FA-30019: revision A, total quantity 178, 22 root-to-part paths. Expand quantity contributions to see each parent occurrence count multiplied by its per-parent quantity.
4. Enter serial `2500`. This ready part has no serial restriction; 448 distinct ready parts overall apply. Enter `2.5` to demonstrate the 422 error, then restore `2500`.
5. Search `EL-10024` to show missing master metadata, null description/revision in the raw response, and why a missing part cannot be serial-applicable.
6. Expand data-quality evidence: `AS-40209 -> AS-40002` points upward and is excluded, with `bom.csv:55` retained as provenance. Expand the hierarchy or a path to navigate assemblies.
7. Show the required JSON responses in the inspector. Explain that `/demo/` endpoints supply optional details without changing the graded `/api/` schemas.

These examples describe the supplied export. Counts and identifiers can differ after replacement data is loaded.

## Explain the design in plain language

**Why a graph instead of a nested tree?** The same part or subassembly can appear under several parents. A graph stores each design relationship once while retaining every route through the machine.

**How are quantities calculated?** The root represents one machine. Process parents before children. For each relationship, add `parent total × quantity per parent` to the child's total. In Appendix Q, FA-9 has four directly in AS-1 and three in each of two AS-2 assemblies: `4 + 2 × 3 = 10`. Repeated CSV rows describe the same relationship and do not add physical parts.

**Why is a repeated part not a cycle?** Multiple parents are allowed. A cycle means following containment brings you back to a part already inside itself. The repair removes self-edges and edges to an ancestor present on every root-to-parent route. Remaining ambiguous cycles stop startup rather than depending on CSV row order.

**How are revisions and statuses chosen?** Choose the highest letter and its matching description. No master record means missing. Otherwise Y means ready and everything not marked Y means not replaceable. Serial compatibility is a separate filter over ready identities, not a count of physical units.

**Why load once?** CSV reconciliation happens before the app accepts traffic. Requests use an in-memory snapshot, avoiding disk reads and external calls. Restart after replacing `data/`.

**How do tests avoid merely repeating the implementation?** Hand-calculated fixtures cover the brief and edge cases. Generated fixtures enumerate forward routes and multiply each route's quantities. That independent oracle is compared through HTTP against the production topological calculation and backward path traversal.

**What assumptions should I disclose?** The brief does not define conflicting quantities/flags/descriptions, one-sided ranges, or ambiguous multi-entry cycles. DATA.md states explicit policies. Do not describe those choices as official rules or promise hidden-test results.

**What are the performance/offline limits?** All 1,963 local timed requests were below one second. Tests and a real server ran with application outbound calls blocked. The physical adapter stayed enabled, and arbitrary graphs can have exponentially many paths. A clean Windows clone and new virtual environment were tested; other operating systems were not.

## Code-reading order

Read `run.py`, `parttrace/api.py`, `parttrace/catalogue.py`, then `parttrace/graph.py`. Follow `tests/fixtures/appendix_q/` and `tests/test_catalogue.py` before the generated tests. The interface lives in `parttrace/static/`. `AI.md` records the assistance used; review and explain the code in your own words.
