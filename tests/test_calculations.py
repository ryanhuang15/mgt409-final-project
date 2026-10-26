from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from backend.app.schemas import AnalysisResult, CalculationConfig, RateRow
from backend.app.tools.calculations import analyze_filing

D = Decimal


def update_rows(filing, **updates):
    rows = [RateRow.model_validate({**row.model_dump(), **updates}) for row in filing.rows]
    return filing.model_copy(update={"rows": rows})


def test_hand_calculated_weighting_example(make_filing):
    result = analyze_filing(make_filing())
    assert result.rows[0].current_modeled_rate == D("100")
    assert result.rows[0].proposed_modeled_rate == D("120")
    assert result.rows[0].absolute_rate_change == D("20")
    assert result.rows[0].rate_change_pct == D("20")
    assert result.metrics["exposure_weighted"].value == D("10")
    assert result.metrics["fixed_exposure_portfolio"].value == D("5")
    assert result.metrics["current_premium_weighted"].value == D("5")
    assert result.metrics["current_modeled_premium"].value == D("400")
    assert result.metrics["proposed_modeled_premium"].value == D("420")
    assert result.metrics["exposure_weighted"].category == "rate_level"
    assert result.metrics["fixed_exposure_portfolio"].category == "premium_impact"


def test_base_and_factor_changes_multiply(make_filing):
    filing = make_filing([dict(segment_id="A", current_base_rate="100", proposed_base_rate="105",
                               current_rating_factor="1.2", proposed_rating_factor="1.26",
                               exposure="2.5", current_premium="300", reported_change_pct="10.25")],
                         claimed_overall_change_pct="10.25")
    result = analyze_filing(filing)
    assert result.rows[0].proposed_modeled_rate == D("132.30")
    assert result.rows[0].absolute_rate_change == D("12.30")
    assert result.rows[0].rate_change_pct == D("10.25")
    assert result.metrics["proposed_modeled_premium"].value == D("330.75")
    assert result.findings == []


@pytest.mark.parametrize("field", ["exposure", "current_premium"])
@pytest.mark.parametrize("value,reason", [(None, "missing_weights"), ("0", "zero_total_weight"), ("-1", "negative_weights")])
def test_unusable_weights(make_filing, field, value, reason):
    result = analyze_filing(update_rows(make_filing(), **{field: value}))
    target = "exposure_weighted" if field == "exposure" else "current_premium_weighted"
    assert result.metrics[target].value is None
    assert result.metrics[target].reason == reason
    assert len(result.rows) == 2
    assert any(f.code == "WEIGHT_UNAVAILABLE" and f.affected == field for f in result.findings)


@pytest.mark.parametrize("field", ["exposure", "current_premium"])
def test_incomplete_weights_not_silently_dropped(make_filing, field):
    filing = make_filing()
    rows = [RateRow.model_validate({**filing.rows[0].model_dump(), field: None}), filing.rows[1]]
    result = analyze_filing(filing.model_copy(update={"rows": rows}))
    target = "fixed_exposure_portfolio" if field == "exposure" else "current_premium_weighted"
    assert result.metrics[target].reason == "incomplete_weights"
    assert result.metrics[target].value is None


def test_individual_zero_weights_are_valid(make_filing):
    filing = make_filing()
    rows = [RateRow.model_validate({**filing.rows[0].model_dump(), "exposure": "0", "current_premium": "0"}), filing.rows[1]]
    result = analyze_filing(filing.model_copy(update={"rows": rows}))
    for name in ("exposure_weighted", "fixed_exposure_portfolio", "current_premium_weighted"):
        assert result.metrics[name].value == 0
        assert result.metrics[name].status == "available"


def test_premium_weighting_can_exist_without_exposures(make_filing):
    result = analyze_filing(update_rows(make_filing(), exposure=None))
    assert result.metrics["fixed_exposure_portfolio"].value is None
    assert result.metrics["current_premium_weighted"].value == D("5")
    assert any(f.code == "OVERALL_CLAIM_UNVERIFIABLE" for f in result.findings)


def test_unverified_premium_basis(make_filing):
    result = analyze_filing(make_filing(premium_basis="unknown"))
    assert result.metrics["current_premium_weighted"].reason == "unverified_premium_basis"
    assert result.metrics["fixed_exposure_portfolio"].value == D("5")


def test_inconsistent_premium_blocks_premium_weighted_metric(make_filing):
    filing = make_filing()
    rows = [RateRow.model_validate({**filing.rows[0].model_dump(), "current_premium": "101"}), filing.rows[1]]
    result = analyze_filing(filing.model_copy(update={"rows": rows}))
    assert result.metrics["current_premium_weighted"].reason == "inconsistent_current_premiums"
    assert result.metrics["fixed_exposure_portfolio"].value == D("5")
    found = next(f for f in result.findings if f.code == "CURRENT_PREMIUM_MISMATCH")
    assert found.difference == D("1")


@pytest.mark.parametrize("difference,flagged", [("0.009", False), ("0.01", False), ("0.010001", True), ("-0.010001", True)])
def test_percentage_point_tolerance_boundary(make_filing, difference, flagged):
    filing = make_filing(claimed_overall_change_pct=D("5")+D(difference))
    result = analyze_filing(filing)
    assert any(f.code == "OVERALL_CHANGE_MISMATCH" for f in result.findings) == flagged


@pytest.mark.parametrize("difference,flagged", [("0.01", False), ("0.010001", True)])
def test_premium_tolerance_boundary(make_filing, difference, flagged):
    filing = make_filing()
    rows = [RateRow.model_validate({**filing.rows[0].model_dump(), "current_premium": D("100")+D(difference)}), filing.rows[1]]
    result = analyze_filing(filing.model_copy(update={"rows": rows}))
    assert any(f.code == "CURRENT_PREMIUM_MISMATCH" for f in result.findings) == flagged


def test_configurable_reconciliation_tolerances(make_filing):
    filing = make_filing(claimed_overall_change_pct="5.25")
    rows = [RateRow.model_validate({**filing.rows[0].model_dump(), "reported_change_pct": "20.25", "current_premium": "100.25"}), filing.rows[1]]
    filing = filing.model_copy(update={"rows": rows})
    strict = analyze_filing(filing)
    relaxed = analyze_filing(filing, CalculationConfig(change_tolerance_pp="0.25", premium_tolerance_usd="0.25"))
    reconciliation_codes = {"SEGMENT_CHANGE_MISMATCH", "CURRENT_PREMIUM_MISMATCH", "OVERALL_CHANGE_MISMATCH"}
    assert reconciliation_codes <= {f.code for f in strict.findings}
    assert not reconciliation_codes & {f.code for f in relaxed.findings}


def test_zero_exposure_nonzero_premium_inconsistent(make_filing):
    filing = make_filing()
    rows = [RateRow.model_validate({**filing.rows[0].model_dump(), "exposure": "0"}), filing.rows[1]]
    result = analyze_filing(filing.model_copy(update={"rows": rows}))
    assert result.metrics["fixed_exposure_portfolio"].value == 0
    assert result.metrics["current_premium_weighted"].reason == "inconsistent_current_premiums"


def test_positive_subcent_baseline_is_not_rounded_to_zero(make_filing):
    filing = make_filing([dict(segment_id="A", current_base_rate="0.00000001", proposed_base_rate="0.00000002",
                               current_rating_factor="1", proposed_rating_factor="1", exposure="1",
                               current_premium="0.00000001", reported_change_pct="100")], claimed_overall_change_pct="100")
    result = analyze_filing(filing)
    assert result.rows[0].rate_change_pct == 100
    assert result.metrics["fixed_exposure_portfolio"].value == 100


@pytest.mark.parametrize("threshold,flagged", [("20", False), ("19.999", True)])
def test_large_change_screening_boundary(make_filing, threshold, flagged):
    result = analyze_filing(make_filing(), CalculationConfig(large_change_threshold_pct=threshold))
    assert any(f.code == "LARGE_RATE_CHANGE" for f in result.findings) == flagged


def test_large_decrease_is_screened(make_filing):
    filing = make_filing([dict(segment_id="A", current_base_rate="100", proposed_base_rate="80", current_rating_factor="1",
                               proposed_rating_factor="1", exposure="1", current_premium="100", reported_change_pct="-20")],
                         claimed_overall_change_pct="-20")
    result = analyze_filing(filing)
    assert result.rows[0].absolute_rate_change == D("-20")
    assert [f.code for f in result.findings] == ["LARGE_RATE_CHANGE"]


@pytest.mark.parametrize("basis,claim", [("exposure_weighted", "10"), ("fixed_exposure_portfolio", "5"), ("current_premium_weighted", "5")])
def test_reconciliation_uses_declared_measure(make_filing, basis, claim):
    result = analyze_filing(make_filing(claimed_overall_basis=basis, claimed_overall_change_pct=claim))
    assert not any(f.code == "OVERALL_CHANGE_MISMATCH" for f in result.findings)


def test_missing_claim_and_reported_changes(make_filing):
    result = analyze_filing(update_rows(make_filing(claimed_overall_change_pct=None), reported_change_pct=None))
    assert sum(f.code == "MISSING_REPORTED_CHANGE" for f in result.findings) == 2
    assert any(f.code == "MISSING_OVERALL_CLAIM" for f in result.findings)


def test_precision_is_independent_of_global_context(make_filing):
    with localcontext() as context:
        context.prec = 6
        result = analyze_filing(make_filing())
        assert context.prec == 6
    assert result.metrics["fixed_exposure_portfolio"].value == D("5")


def test_evidence_links_and_serialization(make_filing):
    result = analyze_filing(make_filing())
    for item in result.findings:
        assert all(ref in result.evidence for ref in item.evidence_refs)
    for item in result.evidence.values():
        assert all(ref in result.evidence for ref in item.input_refs)
    assert result.evidence["row:A"].row_number == 2
    assert result.evidence["calc:A"].input_refs == ["row:A"]
    assert result.evidence["row:A"].values["current_base_rate"] == "100"
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("field", ["change_tolerance_pp", "premium_tolerance_usd", "large_change_threshold_pct"])
@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", True])
def test_invalid_config(field, value):
    with pytest.raises(ValidationError):
        CalculationConfig.model_validate({field: value})
