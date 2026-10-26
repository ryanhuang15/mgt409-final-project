# Final submission validation

Recorded October 2026 after preparing `report.html`, `slides.html`, and the
repository-root GitHub Actions workflow. Existing Phase 1-4 evidence was not
rewritten. These checks used no model calls and did not update evaluation records.

| Check | Result |
|---|---|
| Offline Python tests | **233 passed**, 1 existing Starlette/AnyIO deprecation warning |
| Deterministic CSV evaluation | Clean, flawed, and adversarial scenarios passed |
| Deterministic XLSX evaluation | Clean, flawed, and adversarial scenarios passed |
| `pip check` | No broken requirements |
| Vite production build | Passed; 2,432 modules; JS 617.34 kB / 185.62 kB gzip |
| Report/deck links | All 12 relative links resolve; section anchors are present |
| Report/holdout metrics | Headline totals match the preserved Phase 4 scoring JSON |
| GitHub workflow | Added; not executed remotely from this workspace |

The first sandboxed Vite build was blocked by Windows filesystem permissions;
the approved elevated rerun passed. The Python and deterministic checks passed in
the workspace. No API credentials were used by these checks.

This workspace does not contain `.git` metadata, so Git status and an actual
GitHub Actions run could not be verified. To use the workflow, make `Final
Project` the repository root; it uses only locked dependencies, needs no API key,
and does not run live evaluations. The course's professor-issued final rubric
was not present in the available project files, so the report marks its crosswalk
as provisional.

The recorded analyst trial remains unrun. Its instructions and blank form are
preserved under `evaluation/human_trial/`; no usability or time-saving result is
claimed.

## Official rubric and Phase 5 follow-up audit · October 2026

The official [MGT 409 project requirements](https://zlisto.github.io/mgt_409_fa26/project_requirements.html)
were fetched and used to replace the earlier provisional crosswalk. `report.html`
now follows the required manager-facing order and prints to 12 letter pages in
Chromium. `slides.html` now embeds Reveal.js 5.2.1, its styles, and screenshots;
it has 9 slides, works from a local file, and was verified with arrow navigation
and F fullscreen. Four embedded slide images loaded successfully. The report and
slides were visually inspected in headless Chromium; their render screenshots
and the temporary PDF used to count pages were removed after inspection.

The report now includes named adjacent-product comparisons with links, a
measured direct-API token/cost sample and clearly qualified 100/10,000-user
scenarios, preserved evaluation/safety evidence, and an explicit statement that
no human analyst trial was completed. It does not invent impact results. The
Phase 4 H02 `unsupported_claim` overcall motivated a narrow prompt rule requiring
an explicit unsupported affirmative factual/regulatory assertion. The new
offline prompt-contract test passed. H02 was not re-run against the live model;
no accuracy improvement is claimed and original scoring JSON remains intact.

Validation after the prompt and deliverable updates: **234 offline Python tests
passed** (the existing Starlette/AnyIO deprecation warning plus a pytest-cache
warning caused by an existing cache path); CSV and XLSX deterministic scenarios
passed; `pip check` passed; Vite production build passed (2,432 modules). The
full frontend build required the previously documented elevated Windows
filesystem path. No paid API calls were made in this audit.

Repository status remains unresolved: neither `Final Project` nor its parent
has Git metadata, the saved `gh` credential for `ryanhuang15` is invalid, and
there is no authenticated GitHub connection to list private repositories. An
anonymous search found the unrelated public HW5 project, but this cannot rule
out a private original final-project repository. No replacement repository was
initialized, no history was overwritten, and nothing was published. The report
and slides state this limitation instead of inventing a GitHub URL. A verified
repository link is still required before these HTML files are submission-ready.
