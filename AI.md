# AI assistance record

This log is cumulative and will be updated as work proceeds. AI assistance is permitted by section 4 of the brief. The candidate must review, understand, and be able to explain the final implementation.

| Tool | Actual use so far |
| --- | --- |
| OpenAI Codex desktop assistant (session identified as GPT-6; no more specific model version verified) | Read and reason about the complete supplied specification; create the compliance checklist; generate and execute local audit code; inspect CSV and graph evidence; propose handling policies and testing strategy; draft DATA.md, NOTES.md, and this disclosure. |
| Codex PDF skill and local tool execution | Guide local PDF extraction/rendering and visual review of all five pages using pypdf and pypdfium2. Run standard-library Python CSV/ZIP/hash/graph analysis and independent audit assertions. These are tool-assisted checks, not additional generative models. |

Phase 1 produced documentation and audit utilities only. No application implementation, pytest results, or API behavior is claimed. No external AI API or external dataset was called by the audit scripts. The development assistant is AI; the proposed running service uses deterministic code without request-time AI. No other AI tools, subagents, or collaborators were used in this phase. Later tools and purposes must be added honestly if used.

## Phase 2

Codex generated the Python catalogue engine, rooted graph repair, CSV validation and diagnostic policies, and pytest fixtures/tests. It executed the suite locally, inspected real-data engine responses, checked source preservation, and updated the documentation/checklist. The final run passed 75 tests using Python 3.13.3 and pytest 9.1.1. Test socket/DNS connections are blocked; dependency installation used pip with approved network access before testing. pip and pytest are development tools, not additional AI models.

Cycle repair and unspecified-record handling are documented engineering choices, not assurances about hidden grading. No API or interface was built in this phase. No other AI tools, subagents, external datasets, remote repositories, invitations, or submissions were used. The implemented engine uses only Python's standard library and performs no network requests.

## Phase 3

Codex implemented the FastAPI layer, strict Pydantic response models, startup/readiness handling, serial URL parsing, and HTTP error mapping. It generated HTTP contract tests, diagnosed the Windows async socket-pair issue in the test network blocker, added a narrowly scoped internal-pair exception and regression tests, and executed the final 122-test suite successfully. The execution sandbox required approved external execution for Windows loopback; application network blocking remained active in tests.

Codex installed FastAPI/Uvicorn/Pydantic and test dependencies through pip, inspected installed package source/metadata, and switched the test dependency from deprecated HTTPX to HTTPX2 as required by the installed Starlette version. It started the local API and sent eleven real HTTP requests with Python's standard-library client, saved their responses, confirmed source hashes, and updated documentation. No generative model other than this Codex assistant, external dataset, collaborator, publication, or submission was used. No interface was built in this phase.

## Phase 4

Codex created the local HTML/CSS/JavaScript demo, separate optional search/explanation/quality endpoints, revision/service provenance fields, and demo tests. It used the Sites skill's local-only guidance for implementation and local preview. It used the browser automation tool to operate the existing local browser tab, inspect the DOM and screenshots, test interactions and responsive widths, inspect browser logs, and save a preview image. No Site was registered or published.

The final suite passed 135 tests; JavaScript syntax checks and source-hash comparisons also ran. Codex documented the limit that the computer's network adapter was not disabled, even though assets are local and automated tests block application network connections. No image-generation model, other AI assistant, subagent, external catalogue data, collaborator, remote publication, or submission was used. Explanations in the product are deterministic Python output rather than AI-generated text.

## Phase 5

Codex added the cross-platform Python startup launcher, generated-export HTTP tests using an independent forward-path oracle, and a real HTTP latency/offline verification script. It ran 155 tests successfully in the development checkout and a fresh local clone, measured 1,963 requests with server outbound calls blocked, checked source-byte preservation, and tested clean installation/startup and an installed restart with package-index access disabled. An initial custom pytest temporary-path invocation failed with setup errors; the documented default-temp command passed, as recorded in the audit.

Codex initialized and committed the local Git repository using the user's existing Git identity, created an ignored temporary local clone, installed dependencies there, checked package consistency, reviewed tracked-file sizes/secret patterns, and finalized the checklist, documentation, and walkthrough. It reread the supplied brief locally using the PDF tooling and consulted the local preview teardown instructions. No additional AI model, subagent, external catalogue data, remote repository, invitation, publication, or submission was used. Test data is synthetic verification input only; all product explanations remain deterministic.
