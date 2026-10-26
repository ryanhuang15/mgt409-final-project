# Phase 1 verification — October 24, 2026

Environment: Windows, Python 3.14.7, project-local `.venv`. Direct dependencies
are pinned in `requirements.txt`; the installed set is recorded in
`requirements.lock.txt`. No model calls were made and no server was started.

## Automated tests

Command, from `Final Project`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp runtime/pytest-final --junitxml=runtime/pytest-results.xml
```

Actual result: **137 passed, 1 warning in 1.91 seconds**. Exit code 0.
The warning is an upstream Starlette TestClient reference to the deprecated
`anyio.abc.BlockingPortal` alias. It does not fail tests or prevent API execution;
the pinned/locked package set preserves the tested environment.

Coverage includes hand-calculated weighting examples, base/factor compounding,
positive and negative changes, all missing/partial/zero/negative weight cases,
premium-basis checks, exact tolerance boundaries, configurable tolerances,
positive subcent rates, invalid numbers, schema limits, duplicate segments,
CSV/XLSX errors and equivalence, evidence resolution, JSON serialization,
configuration precedence, scope restrictions, answer-key separation, and the
FastAPI health endpoint using TestClient.

`python -m pip check` returned **No broken requirements found.**

## Independent scenario evaluation

Both commands exited successfully:

```powershell
.\.venv\Scripts\python.exe -m evaluation.evaluate --output runtime/evaluation-csv.json
.\.venv\Scripts\python.exe -m evaluation.evaluate --format xlsx --output runtime/evaluation-xlsx.json
```

| Scenario | CSV | XLSX | Matched deterministic findings | Unexpected findings | Pending AI checks |
|---|---|---|---:|---:|---:|
| Clean | PASS | PASS | 0 / 0 | 0 | 0 |
| Flawed | PASS | PASS | 5 / 5 | 0 | 3 |
| Adversarial | PASS | PASS | 0 / 0 | 0 | 1 |

The clean/adversarial exposure-weighted rate change is 5.649825%; their fixed-
exposure premium impact is approximately 6.131877%. The flawed counterparts are
6.710625% and approximately 7.844430%. Its premium-weighted metric is unavailable
because the supplied current premium for PA011 is inconsistent.

The four pending AI checks are not implemented and are not counted as passed.
The adversarial test shows that narrative text cannot redirect the deterministic
engine; it does not claim that an AI agent has been secured or evaluated yet.

## Configuration and reproducibility

The real parent `.env` was selected with the process `PORTKEY_API_KEY` temporarily
removed in an isolated verification process. A nonempty key was found, the
selected file was confirmed as the parent, and its SHA-256 digest was unchanged
before/after loading. Only boolean presence and source location classification
were printed. API key validity was not tested against a service.

Two consecutive fixture builds produced identical bytes for all 12 CSV, XLSX,
JSON, and Markdown inputs. The independent answer key's SHA-256 digest was
unchanged. Input-file hashes also appear in the calculation exports.

## Implementation notes

Windows sandbox permissions initially blocked pip bootstrapping in Python-created
temporary directories. Setup was completed with the authorized execution path,
keeping the virtual environment, package cache, and successful temporary-file
operations inside `Final Project`. All planned Phase 1 functionality is complete.
The only remaining observed issue is the non-blocking dependency warning above.

Model orchestration, tokenomics measurements from real AI calls, documentation
interpretation, a chronological agent audit trail, the review memo, and the React
frontend remain later-phase work. No Connecticut requirements were implemented.
