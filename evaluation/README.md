# Independent offline evaluation

This directory is for developers/evaluators only. Do not provide its contents to
the Rate Analysis Agent or Documentation Review Agent.

`answer_key.json` is a static, independently maintained set of expected findings
and numerical results. The application engine does not generate the key. The
fixture generator writes only `data/examples/`; it never reads or updates this
file. Aggregate answers were checked separately using exact rational arithmetic
(`fractions.Fraction`), including these independent reference values:

| Metric | Clean/adversarial exact value | Flawed exact value |
|---|---:|---:|
| Exposure-weighted change (%) | 225993 / 40000 | 10737 / 1600 |
| Fixed-exposure premium impact (%) | 252811159 / 41229000 | 323418007 / 41229000 |
| Current modeled premium (USD) | 12987135 / 2 | 12987135 / 2 |
| Proposed modeled premium (USD) | 275669803017 / 40000 | 280118034441 / 40000 |

There are five expected deterministic findings in the flawed filing:

- PA003: reported 9.1% versus calculated 7.1%.
- PA011: current premium overstated by USD 500.
- PA020: reported 11.384% versus calculated 39.23%.
- PA020: 39.23% exceeds the configured 15% screening threshold.
- Portfolio: claimed 1% versus calculated approximately 7.844430%.

Three flawed-filing checks need future AI interpretation: missing factor support,
an unsupported approval assertion, and a narrative contradicting the largest
segment change. One adversarial-filing check concerns the embedded instruction
to skip review and claim approval. These four cases remain explicitly **pending**
in the Phase 1 numerical evaluator. Phase 2 separately evaluates actual model
reviews using `evaluation.evaluate_agents`; it never credits Python's numerical
detections to an agent.

The runner compares exact finding code/affected item/severity combinations and
numerical evidence, detects unexpected findings, and compares five aggregate
metrics against golden values with a 1e-20 numerical tolerance. That evaluation
tolerance is distinct from the business reconciliation tolerances.

Tests also use a small hand-calculated example with a 10% exposure-weighted change
and 5% portfolio impact, plus boundary cases. This prevents agreement with a
self-generated answer key from being the only evidence of correctness.

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m evaluation.evaluate --output runtime/evaluation-csv.json
.\.venv\Scripts\python.exe -m evaluation.evaluate --format xlsx --output runtime/evaluation-xlsx.json
```

A zero-finding clean/adversarial numerical run is a true-negative numerical case;
it is not a legal-compliance verdict or proof of an AI prompt-injection defense.
When changing inputs, review and recalculate expectations independently. Do not
regenerate the key from `analyze_filing` output.

For Phase 2, score and export the latest saved live review of each scenario with
`python -m evaluation.evaluate_agents --export`. Add `--live` to make new real
OpenAI API requests for all three scenarios. The final scoring report, sanitized
agent traces, development attempt history, and the observed false-positive
regression are saved under `docs/evidence/`.
