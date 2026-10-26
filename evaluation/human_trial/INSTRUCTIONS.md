# Independent analyst trial · participant instructions

You are reviewing a fictional Connecticut Personal Auto rate revision. Every
insurer, territory, vehicle class, exposure and premium is synthetic. This is an
analyst exercise, not a legal-compliance assessment.

The facilitator will assign you either `T01` or `T02`, and a review method:

- **Manual:** use the three supplied files in `filings/<case>`. You may use a
  calculator or spreadsheet, but do not use Lumen or an AI assistant.
- **Assisted:** upload the three supplied files to Lumen, validate the package,
  run the complete AI review, and investigate the results. You may use Lumen's
  segment, findings, documentation and evidence views.

Start the timer in `trial_timer.html` when you first see the filing materials.
Stop after you have recorded the issues you would raise to a filing manager.
Enter each issue separately with its affected segment or document, the evidence
you used, and the action you recommend. Include both numerical and documentation
concerns. Record uncertainty honestly. Do not assume an AI finding is correct
without checking its cited source. The facilitator will supply the answer key only
after all assigned sessions are finished.

The main questions are:

1. Does the claimed portfolio change agree with the independent fixed-exposure
   calculation, and do supplied premiums support the declared basis?
2. Are reported segment changes consistent with base rates and factors? Are any
   unusually large movements worth investigation?
3. Does the narrative agree with the calculations? Is the cited supporting
   documentation actually provided? Are approval claims supported?

Use the downloadable HTML review memo if helpful in the assisted session. Do not
include real customer or company data. Export the timer's JSON file and complete
`FEEDBACK.md` after both sessions. Do not alter the answer key or consult it during
the trial.

## Facilitator protocol

Assign **different cases** to manual and assisted sessions for each participant.
If two participants are available, counterbalance: participant A does T01 manual
then T02 assisted; participant B does T02 manual then T01 assisted. If possible,
reverse order for additional participants. Give each a fresh browser session and
the same 15-minute cap per session. The timer records observed elapsed time; do
not fill missing time by estimation. Record any interruptions separately.

After all sessions, score exact issue anchors against the private
`answer_key.json`: `CODE:segment` for numerical issues, `category:document` for
documentation. Compute TP/FP/FN, precision and recall at the issue level. Mark
ambiguous descriptions for manual adjudication; do not silently grant semantic
credit. Report actual observed time and accuracy by method, with participant and
order context. A single tester or sequential same-case comparison cannot establish
time savings or generalization. No human results are included in the project yet.
