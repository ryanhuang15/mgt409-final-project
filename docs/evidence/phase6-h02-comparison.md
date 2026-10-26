# Phase 6 targeted H02 post-correction check

**Classification:** one targeted regression on previously inspected case H02;
not independent holdout evidence and not added to the Phase 4 aggregate.

The original Phase 4 result used `phase2-v6` and recorded 5 expected issues, 1
false positive, 0 misses. Its documentation-agent score was 1 TP, 1 FP, 0 FN.
The extra finding was `unsupported_claim` for “Factor selection support is
limited,” based on a narrative assertion pointing to a document that was
provided but did not give detailed factor rationale. That was an overcall, not
an unsupported approval assertion.

The Phase 6 run used the unchanged synthetic H02 inputs, the direct OpenAI SDK,
`gpt-6-luna`, and corrected prompt `phase5-v1`. The answer key was not supplied
to either agent. It completed in 26.6 seconds with 8 successful calls. The new
documentation output contains the expected narrative-bound contradiction and
no unsupported-claim finding. All four deterministic finding signatures match
the original result exactly; no expected finding was lost and no evidence
references were invalid.

| H02 run | Full workflow | Documentation agent | Deterministic signatures |
|---|---:|---:|---|
| Phase 4 original | 5 TP / 1 FP / 0 FN | 1 TP / 1 FP / 0 FN | 4 retained |
| Phase 6 targeted rerun | 5 TP / 0 FP / 0 FN | 1 TP / 0 FP / 0 FN | Same 4 of 4 |

The post-correction call used 48,303 input tokens, including 32,005 cached input
tokens, and 2,261 output tokens (50,564 total). A standard-rate estimate is
**$0.00308035**: 16,298 uncached input tokens × $0.10/M, 32,005 cached input ×
$0.01/M, and 2,261 output × $0.50/M. This is a token-rate estimate, not an
invoice; the [official GPT-6 Luna pricing page](https://developers.openai.com/api/docs/models/gpt-6-luna)
lists those standard rates. The earlier Phase 4 gateway run has no billable cost
estimate in its record, so only token counts/quality can be compared.

**Conclusion:** the H02 false positive did not recur in this targeted test, and
the expected H02 finding and deterministic results were preserved. This is
evidence that the prompt correction behaves as intended on this one known case;
it does not establish a general precision improvement or prove that recall is
unchanged across other cases. The original Phase 4 result and aggregate remain
unchanged. Full raw records: `phase4-holdout-H02.json` and
`phase6-post-correction-H02.json`.
