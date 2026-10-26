# Practical impact measurement plan

## Question and scope

Does the Lumen workspace help a reviewer find the known concerns in one
synthetic filing, trace evidence, and state a useful next action within the same
short task window as a manual review? This is a feasibility/usability pilot. It
does not test actuarial expertise, legal compliance, production accuracy, or
generalize to real filings.

## Comparison design

- **Within participant:** each participant reviews the identical 24-segment
  `flawed` filing once manually and once using the actual Lumen UI.
- **Order:** alternate manual-first and Lumen-first across participants. With
  four people, assign two to each order. Record order because seeing the same
  filing twice creates recall/carryover effects.
- **Manual condition:** provide only `participant-materials/filing.json`,
  `narrative.md`, and `rates.csv`. Calculator/spreadsheet allowed; AI prohibited.
- **Lumen condition:** participant opens the saved **Flawed** example in the
  actual local app and uses its Overview, Segments, Findings, Documentation, and
  Evidence views. The review result is a historical saved example, so the trial
  makes no API call and does not measure fresh model performance.
- **Task window:** per method, record time to first issue, time to complete the
  issue list, total active time including a source/action check, and whether the
  participant completed each part. The timer records pauses separately.

## Measures

| Outcome | Operational measure | Source |
|---|---|---|
| Discrepancy discovery time | Seconds from first exposure to first issue and to completed issue list | Timer JSON |
| Evidence comprehension time | Total active seconds minus issue-list completion seconds | Timer JSON |
| Issue quality | TP, FP, FN against the eight anchors in `scoring-guide.md`; report counts, precision, and recall | Finding log + facilitator scoring |
| Evidence traceability | Whether cited evidence supports the reported issue; record source opened and observer notes | Finding log |
| Next-action usefulness | 0–2 score for one source-backed, safe analyst action | Session log + scoring guide |
| Usability | Separate 1–5 clarity, navigation, usefulness, confidence, and trust ratings, plus open comments | Questionnaire |
| Practical comparison | Per-person manual minus assisted seconds for discovery and total time, alongside accuracy deltas | Derived only after records are checked |

For participants with both valid times, `time difference = manual seconds −
Lumen seconds`; a positive value means the assisted task was faster for that
participant. Report every paired observation, the median difference, and issue
quality beside it. A percentage difference is optional and must show its
denominator and sample size. Do not average incomplete tasks as zero.

## Ground truth and interpretation

The five numeric anchors are the existing deterministic answer key. Three
documentation anchors use the project’s existing issue rubric. Score exact
segment/document and issue type; manually adjudicate ambiguous prose and record
the reason. Do not equate participant confidence with correctness. Do not
interpret H02 post-correction performance as participant evidence.

The participant is not asked to decide whether the filing is lawful. Any
comments on accuracy from non-actuaries are usability perceptions only. A
qualified actuarial/regulatory analyst must separately validate domain
interpretation before making an expert-accuracy claim.

## Reporting rules

- Mark findings as **observed** only after real participant sessions and timer
  records exist. Include participant count, method order, interruptions, and
  missing tasks.
- Label questionnaire ratings as self-reported. Quote comments only with
  consent and anonymization.
- Keep trial files private. Do not publish raw participant JSON or identifying
  information. Publish only aggregate, consented results.
- With one to four participants, report descriptive pilot observations; do not
  make statistical or causal claims. The same-case crossover and saved AI result
  introduce practice and history effects.
- Any time-savings projection beyond observed participants must be labelled a
  scenario, show assumptions, and remain separate from measured results.

## Remaining human step

Recruit at least one willing participant (four is a better classroom pilot),
obtain consent, start the local app before the session, provide only the
participant packet, observe without coaching, and complete the private logs.
No participant has taken this trial yet; this document contains no trial
results.
