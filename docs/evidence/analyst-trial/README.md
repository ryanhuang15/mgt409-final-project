# Lumen analyst usability pilot

**Status: prepared; no participants or results recorded.** This kit supports a
14-minute, paired manual-versus-Lumen usability session using the same synthetic
flawed filing. Participants may be students or business users; the exercise does
not certify actuarial expertise or legal accuracy.

## Materials

- `participant-brief.md` — read aloud and give to the participant.
- `participant-materials/` — the three synthetic source files for manual review.
- `timer.html` — open locally once for each method; it records issue timestamps,
  issue-discovery time, total review time, and a downloadable JSON record. It makes
  no network requests.
- `questionnaire.md` — administer after both methods.
- `session-log-template.csv` and `finding-log-template.csv` — observer records.
- `scoring-guide.md` — facilitator-only answer anchors, scoring rules, and limits.
- `impact-measurement-plan.md` — analysis plan and interpretation guardrails.

## Before the participant arrives

1. Obtain informed consent for an anonymous classroom usability exercise. Use a
   pseudonym only; do not collect names, emails, company data, or other personal
   information.
2. Start the actual local Lumen application using the project README and open a
   fresh browser session. Preload the built-in **Flawed** saved example so setup
   time does not consume the 14-minute task. Confirm its source rows and findings
   load. The saved example is historical and the assisted task runs no new model
   calls.
3. Provide only the participant brief and the three files in
   `participant-materials/` for manual review. Do not show the scoring guide,
   answer keys, evaluation files, or application finding list before the manual
   task. The repository contains these items, so share only the participant
   packet or a clean folder containing those four participant-facing files.
4. Assign a pseudonym and method order. For the first participant, use manual
   first; alternate order for the next participant. Both methods use the same
   filing, so record order and treat learning/carryover as a limitation.

## 14-minute schedule

| Minutes | Activity |
|---|---|
| 0–2 | Consent, short explanation, and task instructions |
| 2–7 | First method: up to 4 minutes to list issues, then 1 minute to verify one source and state a next action |
| 7–12 | Second method: same task on the same filing |
| 12–14 | Questionnaire and close |

If a participant needs more time, do not rush or fill missing data. Record the
actual elapsed time and mark the task incomplete. Record interruptions
separately. The timer’s “issue list complete” mark distinguishes discovery time
from the short source-understanding/action task.

## Manual condition

Ask the participant to inspect `filing.json`, `narrative.md`, and `rates.csv`.
They may use a calculator or spreadsheet, but no Lumen or other AI. Start the
manual timer immediately before showing the files. Ask the participant to list up to four concerns and affected segments or documents,
noting the source clue for each. Reserve the final minute for a closer source check
and next action on one selected concern.

## Lumen-assisted condition

Use the actual local Lumen UI. From **Explore a filing**, open the built-in
**Flawed** saved review. Ask the participant to repeat the same issue-list task,
then choose one concern and open its source evidence, explain what the source
shows, and state an appropriate next action. Start the assisted timer before
showing the review. The built-in saved review is a historical model run: this
session measures finding navigation and interpretation in the product, not a
fresh model run or the Phase 6 prompt’s live accuracy.

## After each session

1. Save the timer’s JSON file with the pseudonymous participant ID and method in
   its filename. Do not place participant records in the public repository.
2. Copy task completion, issue anchors, evidence checks, action score, and
   interruptions into the CSV templates. Keep one row per participant-method in
   the session log and one row per reported issue in the finding log.
3. Administer the questionnaire after both methods. Self-rated accuracy and
   trust are subjective outcomes; score issue correctness separately against
   `scoring-guide.md`.
4. Store consent and raw participant records privately. Share only de-identified
   aggregate results, and only with permission.

Do not edit the answer keys or report a trial as complete until an actual person
has performed the tasks. A non-actuary’s comments support usability findings
only. Any actuarial accuracy claim needs review by a qualified analyst.
