# Phase 5 verification record

## Completed checks

- Development suite: `python -m pytest --basetemp=tmp/pytest-phase5 -q --tb=short`, using `.venv` Python: **155 passed in 4.47s**.
- New independent generalization coverage: 20 generated exports; compare full HTTP contracts against forward path enumeration, metadata expectations, 33 serials per export, and outside-part errors. Runtime CSVs were not replaced or edited.
- Actual local clone of implementation commit `4fc377e`, no copied virtual environment: **`python run.py` installed and started on port 8000**. Seven HTTP probes succeeded with their expected 200/404/422 statuses; source bytes match the supplied ZIP in both checkouts. See `phase5-startup.json`.
- Clean clone: install test dependencies, run `.\.venv\Scripts\python.exe -m pytest -q --tb=short`: **155 passed in 5.94s**. `pip check`: **No broken requirements found**.
- An earlier clean-clone invocation with custom `--basetemp=tmp/pytest-clean` had **47 passes and 108 setup errors**, because `tmp/` did not exist. The documented default-temp invocation above fixed the command issue; no application fix was needed.
- Installed launcher restarted with `PIP_NO_INDEX=1` and skipped pip, then reported ready on port 8000.
- Real HTTP verification server: outbound Python socket connections and DNS blocked during catalogue startup and requests. **1,963 timed requests**, all below one second, **zero blocked connection attempts**. Maximum required API time **40.860 ms**; maximum including assets **197.018 ms**. Details and repeatable measurement command are in README and `phase5-performance.json`.
- Existing Phase 4 browser checks remain applicable: interface source is unchanged in Phase 5. Search, serial errors/recovery, paths, hierarchy, raw JSON, data quality, and phone/desktop widths were exercised.

## Delivery checks

The local Git repository includes source, original data, tests, required documentation, walkthrough, and audit records. `.gitignore` excludes environments/caches/tmp; `.gitattributes` preserves source CSV bytes. A tracked-file size/path check and private-key/token-pattern scan are recorded in `phase5-packaging.json`. These checks are heuristic secret detection, not a security certification. No remote is configured and nothing was published, shared with candidates, or submitted.

## Limits explicitly retained

- Network adapters were not disabled. Server socket/DNS blocking, test guards, CSP, and local assets establish the available offline evidence; this is not a physical-disconnection test.
- Clean checkout and environment used the same Windows computer, installed Python 3.13.3, and pip cache. No Linux/macOS, other Python version, empty cache, or new OS image was tested.
- Performance measurements cover this supplied export and local concurrency. Every-path responses can grow exponentially on larger graphs; these measurements cannot guarantee unseen sizes/hardware.
- Tests establish expected behavior under documented assumptions. Conflicting-record policies are not official tie-breakers and may differ from hidden grader expectations.
- The opening-page deadline was not supplied; timing compliance cannot be certified. Private remote creation, collaborator invitation, and submission remain unperformed and require explicit authorization.
