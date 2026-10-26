# Facilitator scoring guide — do not show before both tasks

This is a usability pilot on one synthetic filing. The detailed scoring key is
deliberately separate from the participant packet. The answer is never shown to
the reviewing model; participants should not see it until their tasks are done.

## Expected issue anchors

Score an issue only when the participant identifies the concern and its affected
segment/document. Match the following eight anchors to the existing project
answer key; do not grant credit from a vague statement alone.

| Anchor | Ground truth | Evidence/action that demonstrates understanding |
|---|---|---|
| `SEGMENT_CHANGE_MISMATCH:PA003` | Reported segment change does not match base-rate/factor calculation. | Reconcile the PA003 row against the calculated change; correct or investigate the exhibit. |
| `CURRENT_PREMIUM_MISMATCH:PA011` | Supplied current premium differs from exposure × modeled current rate. | Recompute PA011 premium and correct the source exhibit. |
| `SEGMENT_CHANGE_MISMATCH:PA020` | Reported PA020 change does not match its proposed rate/factor. | Reconcile the segment row and proposed factor. |
| `LARGE_RATE_CHANGE:PA020` | The calculated PA020 change exceeds the app’s 15% review screen. This is a heuristic, not a legal threshold. | Ask for actuarial rationale and verify supporting detail; do not call it a violation. |
| `OVERALL_CHANGE_MISMATCH:portfolio` | Claimed 1% portfolio change conflicts with the fixed-exposure calculation. | Reconcile the filing summary to the calculated portfolio measure and stated basis. |
| `missing_documentation:DOC-FACTORS` | Narrative relies on factor support marked not provided. | Request the missing support; do not invent a statutory obligation. |
| `unsupported_claim:DOC-APPROVAL` | Narrative contains an unsupported automatic DOI approval claim. | Remove or substantiate the assurance using authoritative sources; never endorse it. |
| `documentation_contradiction:narrative.md` | Narrative says no segment exceeds 15%; PA020 contradicts that assertion. | Correct the narrative and confirm the cited segment calculation. |

The five numerical anchors come from `evaluation/answer_key.json`; the
documentation anchors use the project’s existing exact category/document rubric.
Do not score the single targeted H02 post-correction result as a user-trial
answer key or as independent holdout evidence.

## Matching and metrics

1. Break the participant’s list into distinct concerns. One item can match one
   anchor. A participant may earn two anchors for PA020 only if they distinguish
   the reported-versus-calculated mismatch from the large-movement screen.
2. A true positive needs the correct affected segment/document and the core issue.
   A valid next action strengthens the usability score but is not required for
   issue-detection credit.
3. A claim that the 15% heuristic is a legal rule is not a correct next action.
   An unexplained “looks wrong” is not an exact match.
4. Count every unmatched distinct concern as a false positive after facilitator
   review. Count each unreported anchor as a false negative. Note ambiguous
   wording and adjudicate consistently before comparing methods.
5. Calculate issue-level `precision = TP / (TP + FP)` and `recall = TP / (TP + FN)`;
   retain counts when a denominator is zero. Score each method separately.
6. Score the source/action check from 0–2: **0** no support or an unsafe/legal
   assertion; **1** broadly appropriate action but weak source tie; **2** names a
   relevant source and proposes a concrete, bounded analyst follow-up.

Record actual times from timer JSON. A blank or unfinished time remains missing;
never estimate it. Separate usability ratings from this anchor scoring. A
non-actuary can report clarity and navigation problems, but their score does not
validate actuarial or regulatory correctness.
