# Calculation definitions and assumptions

## Scope and units

A row is a disjoint homogeneous segment of a fixed Personal Auto portfolio.
Exposure is annual vehicle-years (fractional values are allowed). Base rates and
modeled rates are USD per annual vehicle exposure. `current_premium` is the
aggregate annual modeled USD premium for the entire segment, **not** a premium
per policy. Combined rating factors are dimensionless and already aggregate the
factors used in this simplified model.

Current and proposed coverage, limits, deductibles, exposure mix, and exposure
period are held fixed. Taxes, fees, minimum premiums, policy rounding rules,
proration, trend/development, loss indications, demand changes, and retention
effects are excluded. No insurer data or authoritative state rules are used.

## Row calculations

For segment i, let B be base rate, F combined factor, E exposure, P supplied
current premium, and primes indicate proposed values.

- Current modeled rate: `R_i = B_i * F_i`.
- Proposed modeled rate: `R'_i = B'_i * F'_i`.
- Absolute **rate** change: `A_i = R'_i - R_i` (USD per exposure).
- Segment rate change: `d_i = 100 * (R'_i - R_i) / R_i` (percent).
- Expected current **segment premium**: `P_expected_i = E_i * R_i` (USD).

Rates and factors must be positive. New segments with no positive current rate
are unsupported; the app does not invent a baseline or divide by zero.
Base and factor changes compound multiplicatively, so a 5% base increase plus a
5% factor increase produces 10.25%, not 10%.

## Portfolio measures: never substitute one for another

| Metric ID | Formula | Interpretation |
|---|---|---|
| `exposure_weighted` | `sum(E_i * d_i) / sum(E_i)` | Exposure-weighted average segment **rate** change |
| `current_modeled_premium` | `sum(E_i * R_i)` | Current modeled portfolio premium |
| `proposed_modeled_premium` | `sum(E_i * R'_i)` | Proposed modeled portfolio premium at fixed exposure |
| `fixed_exposure_portfolio` | `100 * (sum(E_i * R'_i) - sum(E_i * R_i)) / sum(E_i * R_i)` | Fixed-exposure portfolio **premium impact** |
| `current_premium_weighted` | `sum(P_i * d_i) / sum(P_i)` | Impact using supplied current segment premiums as weights |

When `P_i = E_i * R_i`, the last two percentage measures are algebraically equal
apart from finite Decimal precision. An exposure-weighted rate average generally
differs because each dollar of current premium does not receive the same weight
as each unit of exposure.

Worked example: two segments each have one exposure. Rates change from 100 to 120
and from 300 to 300. Segment changes are 20% and 0%. The exposure-weighted average
is 10%, while total premium changes from 400 to 420, an impact of 5%. The supplied
current-premium weights 100 and 300 also yield 5%.

## Weight availability

- Missing all weights: corresponding metrics are unavailable (`missing_weights`).
- Missing any weights: full-portfolio metrics are unavailable (`incomplete_weights`).
- Negative weights: retained as data-quality evidence; corresponding metrics are
  unavailable (`negative_weights`).
- Individual zero weights: valid, with zero contribution. Rows remain in evidence
  and their rate-level calculations and screening still run.
- All zero weights: corresponding metrics are unavailable (`zero_total_weight`).
- Malformed, boolean, NaN, or infinite numerical values: reject input before calculation.

Exposure and premium weights are assessed independently. If exposure is missing
but all current-premium weights are valid, premium-weighted analysis can proceed
only with the explicit `modeled_annual_same_portfolio` declaration. Without
exposures, that declaration cannot be fully reconciled independently; it remains
an input assumption, not an externally verified fact.

Premium weighting is unavailable if the declared premium basis is `unknown` or
if a comparable supplied premium fails reconciliation to exposure times the
current modeled rate. Exposure-based totals remain independent of supplied
current-premium discrepancies. Zero exposure with nonzero modeled current
premium also fails reconciliation.

The engine never silently drops rows, fills missing weights with zero, assumes
equal weights, or replaces an unavailable claimed measure with another measure.

## Reconciliation, tolerances, and screening

All `*_pct` values use percentage units: **5.0 means 5%**, not 500%. Differences
between percentages use **percentage points**: 7% versus 5% differs by 2 points.

`CalculationConfig` provides three nonnegative settings:

| Setting | Default | Behavior |
|---|---:|---|
| `change_tolerance_pp` | 0.01 percentage points | Flag segment/overall reported difference strictly greater than this value |
| `premium_tolerance_usd` | USD 0.01 per segment | Flag supplied-vs-modeled current premium difference strictly greater than this value |
| `large_change_threshold_pct` | 15% | Screen absolute segment rate changes strictly greater than this value |

The overall claim is compared only against `claimed_overall_basis`, one of the
three explicit percentage metric IDs. An unavailable metric produces an
unverifiable-claim finding. An omitted claim is identified separately.

Reconciliation differences are signed `reported - calculated`; comparisons use
their absolute values. The 15% threshold is a configurable **review heuristic**,
not a Connecticut legal requirement, an actuarial standard, or a compliance test.
Both increases and decreases are screened.

Input Decimals are limited to 20 digits and 8 decimal places. Calculations use an
isolated 50-digit Decimal context without intermediate currency rounding. Output
is not rounded before reconciliation. The CLI displays six decimals for readable
summaries; JSON preserves Decimal strings. Synthetic segment premiums can have
fractional cents under this illustrative model; actual carrier rounding rules
are not modeled. Source percentage claims are rounded to six decimal places.

## Validation and evidence

The reader requires unique segment IDs, positive base rates/factors, exact known
column names, finite numeric values, and at least one row. Limits are 5,000 rows,
2 MB per input file, 20 MB expanded XLSX size, 20,000 narrative characters, and
12 document inventory entries. XLSX requires a `rates` worksheet and values only;
formulas are rejected rather than evaluated or trusted from stale cached values.

Each source reference identifies a file, physical row, optional worksheet, and
segment ID. Calculation evidence points to its source rows and records formulas
and values. Portfolio evidence points to all participating segment calculations
and weight rows. Findings link back to these evidence IDs. Input SHA-256 hashes
and the configuration snapshot support reproduction. This is calculation
provenance; the richer chronological agent audit trail belongs to Phase 2.

Malformed required inputs stop the review with structured validation errors.
Weight-quality problems allow valid rate-level calculations to remain available.
No regulatory requirements, approvals, or legal-compliance conclusions are emitted.
