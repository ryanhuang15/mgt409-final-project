"""Deterministic calculations only: no AI, network, or evaluation-key imports."""

from decimal import Decimal, localcontext

from backend.app.schemas import (
    AnalysisResult, CalculationConfig, Evidence, Filing, Finding, Metric, RowCalculation,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def weight_problem(values: list[Decimal | None]) -> str | None:
    """A zero-weight row is valid; a zero total is not a usable denominator."""
    if any(value is not None and value < 0 for value in values):
        return "negative_weights"
    if all(value is None for value in values):
        return "missing_weights"
    if any(value is None for value in values):
        return "incomplete_weights"
    if sum(values, ZERO) == 0:
        return "zero_total_weight"
    return None


def analyze_filing(filing: Filing, config: CalculationConfig | None = None) -> AnalysisResult:
    """Calculate at fixed precision without changing the caller's Decimal context."""
    with localcontext() as context:
        context.prec = 50
        return _analyze(filing, config or CalculationConfig())


def _analyze(filing: Filing, config: CalculationConfig) -> AnalysisResult:
    evidence, findings, calculated, metrics = {}, [], [], {}
    for row, source in zip(filing.rows, filing.source_rows):
        evidence[source.evidence_id] = Evidence(
            evidence_id=source.evidence_id, kind="source_row", source_file=source.file,
            row_number=source.row_number, sheet=source.sheet,
            values={key: None if value is None else str(value) for key, value in row.model_dump().items()},
        )
    metadata_ref = "metadata:filing"
    evidence[metadata_ref] = Evidence(
        evidence_id=metadata_ref, kind="source_metadata", source_file="filing.json",
        field="claimed_overall_change_pct, claimed_overall_basis, premium_basis",
        values={
            "claimed_overall_change_pct": str(filing.metadata.claimed_overall_change_pct),
            "claimed_overall_basis": filing.metadata.claimed_overall_basis,
            "premium_basis": filing.metadata.premium_basis,
        },
    )

    def finding(code, severity, affected, message, refs, action, basis="data_quality", **numbers):
        findings.append(Finding(
            finding_id=f"{code}:{affected}", code=code, severity=severity, affected=affected,
            message=message, evidence_refs=refs, recommended_action=action, basis=basis, **numbers,
        ))

    inconsistent_premiums = []
    for row in filing.rows:
        current = row.current_base_rate * row.current_rating_factor
        proposed = row.proposed_base_rate * row.proposed_rating_factor
        absolute = proposed - current
        change_pct = absolute / current * HUNDRED
        source_ref = f"row:{row.segment_id}"
        calc_ref = f"calc:{row.segment_id}"
        calculated.append(RowCalculation(
            segment_id=row.segment_id, current_modeled_rate=current, proposed_modeled_rate=proposed,
            absolute_rate_change=absolute, rate_change_pct=change_pct, evidence_id=calc_ref,
        ))
        evidence[calc_ref] = Evidence(
            evidence_id=calc_ref, kind="calculation", input_refs=[source_ref],
            formula="current=base_current*factor_current; proposed=base_proposed*factor_proposed; absolute=proposed-current; pct=100*absolute/current",
            values={"current_rate": str(current), "proposed_rate": str(proposed), "absolute_change": str(absolute), "change_pct": str(change_pct)},
        )
        if row.reported_change_pct is None:
            finding("MISSING_REPORTED_CHANGE", "low", row.segment_id,
                    "No segment-level reported change was supplied for reconciliation.", [source_ref],
                    "Provide the reported segment change or document why it is omitted.")
        elif abs(row.reported_change_pct - change_pct) > config.change_tolerance_pp:
            finding("SEGMENT_CHANGE_MISMATCH", "high", row.segment_id,
                    "Reported segment change differs from the independently calculated rate change.", [source_ref, calc_ref],
                    "Reconcile the reported percentage against the proposed base rate and combined factor.",
                    basis="numerical_reconciliation", reported_value=row.reported_change_pct,
                    calculated_value=change_pct, difference=row.reported_change_pct-change_pct, unit="percentage_points")
        if abs(change_pct) > config.large_change_threshold_pct:
            finding("LARGE_RATE_CHANGE", "medium", row.segment_id,
                    "Absolute segment rate change exceeds the configured screening threshold; this is not a regulatory limit.",
                    [calc_ref], "Confirm the factor revision and explain the large change to the analyst.",
                    basis="general_review_heuristic", calculated_value=change_pct, unit="percent")
        if (filing.metadata.premium_basis == "modeled_annual_same_portfolio"
                and row.exposure is not None and row.exposure >= 0
                and row.current_premium is not None and row.current_premium >= 0):
            expected = row.exposure * current
            premium_ref = f"premium:{row.segment_id}"
            evidence[premium_ref] = Evidence(
                evidence_id=premium_ref, kind="calculation", input_refs=[source_ref, calc_ref, metadata_ref],
                formula="expected_current_premium=exposure*current_modeled_rate",
                values={"expected_current_premium": str(expected), "supplied_current_premium": str(row.current_premium)},
            )
            if abs(row.current_premium - expected) > config.premium_tolerance_usd:
                inconsistent_premiums.append(row.segment_id)
                finding("CURRENT_PREMIUM_MISMATCH", "high", row.segment_id,
                        "Supplied current premium is inconsistent with exposure times the modeled annual rate.", [premium_ref],
                        "Correct the premium or clarify the premium basis before using premium weights.",
                        basis="numerical_reconciliation", reported_value=row.current_premium,
                        calculated_value=expected, difference=row.current_premium-expected, unit="USD")

    all_calcs = [row.evidence_id for row in calculated]
    source_refs = [source.evidence_id for source in filing.source_rows]
    exposures = [row.exposure for row in filing.rows]
    premiums = [row.current_premium for row in filing.rows]
    exposure_problem = weight_problem(exposures)
    premium_problem = weight_problem(premiums)
    for weight_name, problem in (("exposure", exposure_problem), ("current_premium", premium_problem)):
        if problem:
            finding("WEIGHT_UNAVAILABLE", "high" if problem == "negative_weights" else "medium", weight_name,
                    f"The {weight_name} weights cannot support full-portfolio analysis: {problem}.", source_refs,
                    "Provide complete nonnegative weights with a positive total; no rows are silently removed.")
    if not premium_problem and filing.metadata.premium_basis != "modeled_annual_same_portfolio":
        premium_problem = "unverified_premium_basis"
        finding("PREMIUM_BASIS_UNVERIFIED", "medium", "current_premium",
                "Current premiums are not identified as modeled annual premiums for this fixed portfolio.", [metadata_ref],
                "Confirm a comparable premium basis before interpreting premium-weighted impacts.")
    if not premium_problem and inconsistent_premiums:
        premium_problem = "inconsistent_current_premiums"

    def metric(name, category, unit, formula, value, problem=None, refs=None):
        ref = f"metric:{name}"
        evidence[ref] = Evidence(
            evidence_id=ref, kind="calculation", formula=formula,
            input_refs=refs if refs is not None else all_calcs + source_refs,
            values={"value": None if value is None else str(value), "unavailable_reason": problem},
        )
        metrics[name] = Metric(metric_id=name, category=category, unit=unit, value=value,
                               status="unavailable" if problem else "available", reason=problem, evidence_id=ref)

    current_total = proposed_total = exposure_average = portfolio_change = None
    if exposure_problem is None:
        total_exposure = sum(exposures, ZERO)
        current_total = sum((e * row.current_modeled_rate for e, row in zip(exposures, calculated)), ZERO)
        proposed_total = sum((e * row.proposed_modeled_rate for e, row in zip(exposures, calculated)), ZERO)
        exposure_average = sum((e * row.rate_change_pct for e, row in zip(exposures, calculated)), ZERO) / total_exposure
        portfolio_change = (proposed_total-current_total) / current_total * HUNDRED
    metric("exposure_weighted", "rate_level", "percent", "sum(exposure*segment_change_pct)/sum(exposure)", exposure_average, exposure_problem)
    metric("fixed_exposure_portfolio", "premium_impact", "percent", "100*(sum(exposure*proposed_rate)-sum(exposure*current_rate))/sum(exposure*current_rate)", portfolio_change, exposure_problem)
    metric("current_modeled_premium", "premium_total", "USD", "sum(exposure*current_rate)", current_total, exposure_problem)
    metric("proposed_modeled_premium", "premium_total", "USD", "sum(exposure*proposed_rate)", proposed_total, exposure_problem)
    premium_average = None
    if premium_problem is None:
        premium_average = sum((p * row.rate_change_pct for p, row in zip(premiums, calculated)), ZERO) / sum(premiums, ZERO)
    metric("current_premium_weighted", "premium_impact", "percent", "sum(current_premium*segment_change_pct)/sum(current_premium)",
           premium_average, premium_problem, all_calcs + source_refs + [metadata_ref])

    claimed = filing.metadata.claimed_overall_change_pct
    claimed_metric = metrics[filing.metadata.claimed_overall_basis]
    if claimed is None:
        finding("MISSING_OVERALL_CLAIM", "low", "portfolio", "No claimed overall change was provided.", [metadata_ref],
                "Provide an overall percentage and its explicitly stated weighting basis.")
    elif claimed_metric.status == "unavailable":
        finding("OVERALL_CLAIM_UNVERIFIABLE", "medium", "portfolio",
                "The claimed overall change cannot be reconciled because its stated weighting measure is unavailable.",
                [metadata_ref, claimed_metric.evidence_id], "Resolve the weight or premium-basis issues; do not substitute another measure.")
    elif abs(claimed - claimed_metric.value) > config.change_tolerance_pp:
        finding("OVERALL_CHANGE_MISMATCH", "high", "portfolio",
                "Claimed overall change differs from the calculated result on the explicitly stated basis.",
                [metadata_ref, claimed_metric.evidence_id], "Reconcile the filing summary to the calculated portfolio result.",
                basis="numerical_reconciliation", reported_value=claimed, calculated_value=claimed_metric.value,
                difference=claimed-claimed_metric.value, unit="percentage_points")
    return AnalysisResult(
        scenario_id=filing.metadata.scenario_id, config=config, source_file_sha256=filing.file_sha256,
        rows=calculated, metrics=metrics, findings=findings, evidence=evidence,
    )
