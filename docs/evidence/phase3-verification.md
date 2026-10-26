# Phase 3 verification

Verified October 24–25, 2026. All implementation changes are inside `Final Project`.
The parent environment file and other course folders were not modified. No final
course report or slides were started. No application has been published externally.

## Actual results

| Check | Result |
|---|---|
| Python automated suite | **230 passed**, 0 failed, 8.19 seconds |
| Production Vite build | Passed, 2,431 modules; JS 602.77 kB / 182.02 kB gzip |
| Chromium browser suite | **8 passed**, 0 skipped, 0 flaky, 41.28 seconds |
| CSV deterministic evaluation | All 3 scenarios passed; no unexpected numerical findings |
| XLSX deterministic evaluation | All 3 scenarios passed; no unexpected numerical findings |
| `pip check` | No broken requirements |
| Production npm advisory check | 0 known vulnerabilities reported by `npm audit --omit=dev` |
| Parent `.env` selection | Confirmed, key presence only; values not exposed |
| Frontend / Phase 3 evidence key scan | No configured key found |
| Docker / hosted smoke test | Not run: Docker is unavailable and publication is not approved |

The Python warning is the existing upstream Starlette/AnyIO `BlockingPortal`
deprecation. An initial sandbox run encountered Windows temporary-directory
permissions; authorized execution within project-local runtime folders resolved
it. An initial stylesheet import error was corrected before the successful build.
Chart animation was disabled to ensure the chart displays its actual data
immediately and screenshots do not capture an empty animation frame.

## Fresh browser-to-agent run

The browser selected **Upload filing**, uploaded the real synthetic flawed CSV,
JSON document inventory and narrative, validated the package, started a background
review, polled actual stages, displayed its completed result, and reloaded it from
session-scoped storage. No mocked model response was used in this test.

- Review ID: `6993029591d74ddbb15bf040481a4afa`
- Result: **complete**, both agents complete, human review required.
- Total review duration: **24.122 seconds**.
- Measured model latency: **23.885 seconds**.
- **9** genuine `gpt-6-luna` model requests through the official Portkey client.
- **13** successful native tool calls (4 Rate Analysis, 9 Documentation Review).
- **5/5** expected deterministic findings; **3/3** documentation findings.
- No unexpected findings, no severity mismatches, no invalid evidence references.
- Input tokens: **53,775**; cached input subset: **42,649**.
- Output tokens: **2,297**; total reported tokens: **56,072**.
- Exact billing was not supplied; no dollar cost is asserted.

The evaluation-only script uses the existing independent answer key after the
review finishes. Neither the answer key nor evaluation results enter the agents'
context. The live findings and source quotes were also inspected for their meaning:
factor support not provided, unsupported approval assertion, and the narrative
bound contradicted by PA020. The exact bound is still checked by Python.

The clean and adversarial browser workflows use clearly labeled genuine Phase 2
reviews, including the prior successful prompt-injection resistance test. This
phase made **one fresh live review**, not three new live scenario runs. The
adversarial UI test confirms that injected text is displayed as source content
while the human-review disposition and suspicious-instruction finding remain.

## Coverage

Browser: onboarding; saved examples; overview; findings/origin filtering;
segment search; scatter plot; evidence inspector and Escape/focus behavior;
missing documentation; tool-ledger filtering/expansion; HTML/CSV/JSON downloads;
actual clean CSV and flawed XLSX parsing; actionable invalid-upload errors;
adversarial source rendering; clean empty state; narrow mobile overflow checks;
live CSV-to-agent workflow, progress display and reload recovery.

Backend: preserves all 202 earlier tests, with additional multipart validation,
file-name isolation, source references, preview without model calls, scoped job and
export access, persisted global/browser quotas, restart recovery, retention expiry,
cross-origin rejection, disabled public legacy route, public HTTPS/code settings,
live kill switch, request-body and burst limits, escaped report content, CSV formula
neutralization, deterministic dollar reconciliation and unavailable weights, and a
missing-key partial-review case that retains all five numerical findings.

## Evidence files

- [Machine-readable verification](phase3-verification.json)
- [Fresh browser review, source data and sanitized trace](phase3-live-browser.json)
- [Onboarding screenshot](phase3-home.png)
- [Overview screenshot](phase3-overview.png)
- [Findings screenshot](phase3-findings.png)
- [Evidence inspector screenshot](phase3-evidence.png)
- [Execution ledger screenshot](phase3-audit.png)
- [CSV upload screenshot](phase3-upload-csv.png)
- [XLSX upload screenshot](phase3-upload-xlsx.png)
- [Mobile screenshot](phase3-mobile.png)
- [Segment and premium-contribution analytics](phase3-segments.png)
- [Actual running review](phase3-live-running.png)
- [Actual completed review](phase3-live-complete.png)
- [Downloadable example memo](phase3-example-memo.html)
- [Memo screenshot](phase3-memo.png)
- [Verified browser-generated PDF](phase3-example-memo.pdf)

`runtime/pytest-phase3.xml` and `runtime/playwright-results.json` retain test-run
details locally. `python -m scripts.verify_phase3` reproduces the offline score and
secret scan from those files; it does not call the model.

## Remaining limitations and worthwhile next work

1. Approve a hosting mode, then verify the container and live host, disk durability,
   memory, secret settings, limits and incognito professor workflow. Render paid
   Docker plus a disk is recommended for live use; a free preview keeps AI off.
2. Improve analyst workflow with persistent finding dispositions, reviewer notes
   and a revised-versus-original filing comparison. These are not implemented yet.
3. Broaden robustness evaluation with additional missing-weight patterns, longer
   document packages and new injection attacks before expanding scope.
4. Add verified, applicable Connecticut authority only after independent source
   research. No existing heuristic should be relabeled a regulatory requirement.
5. Consider direct server-rendered PDF export and a formal accessibility audit.
   Current reports download as self-contained HTML and print to PDF in the browser.

The single-process SQLite design is deliberate for a bounded demonstration. It
does not provide distributed workers, user accounts or multi-tenant governance.
The public shared code is an abuse barrier, not identity management. Uploads are
restricted to synthetic data. A host restart during an AI request can interrupt
it; the job is not automatically replayed. No final course report or slides are
included in this phase.
