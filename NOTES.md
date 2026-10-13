# PartTrace notes

**Decisions:** Use a standard-library CSV/graph engine behind FastAPI. Normalize identities, deduplicate design relationships, remove unambiguous upward edges, and aggregate every assembly occurrence. Load completely before reporting healthy. Required responses preserve exact fields, types, nulls, and sorting. Source CSV bytes stay intact.

**Ambiguities:** Reject relevant conflicting quantities, selected descriptions, service flags, malformed ready ranges, and unresolved multi-entry cycles. Union multiple valid Y ranges. Serial URLs accept nonnegative ASCII digits. DATA.md explains these engineering policies; the brief supplies no tie-breakers, so hidden-grader expectations remain uncertain.

**Scope:** All required behavior is implemented. Optional search, calculation explanations, serial reasons, quality summary, and lazy hierarchy use separate demo endpoints. Search displays 50 matches and the total. No training, external runtime calls, editing/import workflow, or deployment was added. Finishing and testing the required catalogue took priority over extra presentation features.

**Evidence:** 155 tests passed in development and a fresh local clone. All 1,963 measured HTTP responses were below one second (required API maximum 40.860 ms). Application network calls were blocked during tests and a live-server check. The one-command launcher created a clean virtual environment; pip reused cached wheels. Browser checks covered errors and phone/desktop layouts.

**Limits and next steps:** Physical network disconnection, Linux/macOS, other Python versions, hidden data, and a new OS image were not tested. All-path output can grow exponentially. Resolve genuinely ambiguous future exports with the data owner. Confirm the actual deadline, review the walkthrough, and complete the private repository/collaborator/form steps only with explicit authorization. Work remains confidential; no remote publication or submission occurred.
