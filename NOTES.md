# PartTrace notes

**Stage:** Phase 4 interface complete; Phase 5 awaits user review. Final delivery verification remains pending.

**Decisions:** Standard-library Python engine with FastAPI/Pydantic HTTP contracts. Source CSV bytes remain intact. Normalize identity, deduplicate relationships, remove provably upward containment, exclude outside parents, and sum quantities in parent-before-child order. Load the complete snapshot before reporting healthy. Required responses use strict types and retain null fields. CDN-dependent API documentation pages are disabled.

**Verified:** 135 pytest cases passed with application network access blocked (Windows internal socket pairs permitted). Browser checks covered search, selection, serial/error recovery, raw responses, hierarchy, data quality, and phone/desktop widths. Counts: 875 parts, 483 ready, 25 missing, 367 not replaceable; serial 2500 count 448. Comprehensive latency, machine-wide offline, and clean-install checks remain pending.

**Scope:** No training, request-time AI, external runtime service, or additional catalogue data. Search, deterministic explanations, serial reasons, quality summary, and lazy hierarchy are implemented under separate demo endpoints. Search shows at most 50 matches with a total. No required feature has been cut.

**Policies:** Reject relevant conflicting quantities/descriptions/service flags, invalid ready ranges, and unresolved multi-entry cycles. Union valid Y ranges. Missing-master status takes precedence. Serial URLs accept nonnegative ASCII digits, including leading zeros; signed/decimal/exponent syntax returns 422. DATA.md distinguishes decisions from official rules; hidden-test risk remains for unspecified cases. Actual deadline is still unknown.

**Next:** Review the demo, then finish generalization/offline/performance/startup verification and the single-command launcher. Complete final documentation and the candidate walkthrough. README currently documents API/page setup and tests.

**Submission:** Confidential brief and work; no sharing with candidates. No remote repository, invitation, publication, or form submission is authorized. The deadline and later submission steps remain the user's responsibility until explicitly delegated.
