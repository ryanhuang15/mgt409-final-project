"""Rebuild isolated synthetic cases. This code never imports the review engine."""

import csv
import json
import random
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = [
    dict(case="H01", count=9, seed=401, insurer="Cedar Arc Mutual (fictional)", plan="clean"),
    dict(case="H02", count=17, seed=732, insurer="Pine Signal Casualty (fictional)", plan="numeric", mismatch=3, premium=11, large=8, overall=Decimal("1.5"), bound=15),
    dict(case="H03", count=12, seed=199, insurer="Harbor Thread Mutual (fictional)", plan="documentation", large=6, large_multiplier=Decimal("1.08"), bound=8, missing_factor=True),
    dict(case="H04", count=26, seed=918, insurer="Paper Lantern Casualty (fictional)", plan="clean", skew=True),
    dict(case="H05", count=20, seed=564, insurer="Meadow Pin Insurance (fictional)", plan="mixed", missing_premium=4, unsupported=True),
]
TRIALS = [
    dict(case="T01", count=14, seed=376, insurer="Silver Map Mutual (fictional)", plan="trial", mismatch=4, premium=10, large=7, overall=Decimal("1.2"), bound=15, missing_factor=True),
    dict(case="T02", count=14, seed=609, insurer="Amber Coast Casualty (fictional)", plan="trial", mismatch=3, premium=12, large=9, overall=Decimal("1.2"), bound=15, missing_factor=True),
]
HEADERS = ["segment_id", "territory", "driver_class", "vehicle_group", "current_base_rate", "proposed_base_rate", "current_rating_factor", "proposed_rating_factor", "exposure", "current_premium", "reported_change_pct"]


def quantize(value, digits="0.000001"):
    return value.quantize(Decimal(digits), rounding=ROUND_HALF_UP)


def build(spec, directory):
    """Use exact decimal products, then independently emit consistent reports."""
    directory.mkdir(parents=True, exist_ok=True)
    rng = random.Random(spec["seed"])
    rows = []
    with localcontext() as context:
        context.prec = 50
        for index in range(1, spec["count"] + 1):
            segment = f"{spec['case']}-S{index:02}"
            base = Decimal(480 + (index * 37) % 170)
            factor = Decimal(60 + (index * 11) % 57) / 100
            new_base = base * Decimal("1.04")
            movement = Decimal(100 + (index % 5) - 2) / 100
            if index == spec.get("large"):
                movement *= spec.get("large_multiplier", Decimal("1.30"))
            new_factor = factor * movement
            exposure = rng.randint(25, 170)
            if spec.get("skew") and index in (2, 18):
                exposure *= 9
            old_rate, new_rate = base * factor, new_base * new_factor
            reported = quantize((new_rate / old_rate - 1) * 100)
            current_premium = old_rate * exposure
            if index == spec.get("mismatch"):
                reported += Decimal("2.500000")
            if index == spec.get("premium"):
                current_premium += 350
            rows.append(dict(segment_id=segment, territory=("East Bridge", "Lake Grove", "West Point")[index % 3],
                             driver_class=("Experienced", "Standard", "Limited experience")[index % 3],
                             vehicle_group="Private passenger", current_base_rate=str(base),
                             proposed_base_rate=str(new_base), current_rating_factor=str(factor),
                             proposed_rating_factor=str(new_factor), exposure=str(exposure),
                             current_premium="" if index == spec.get("missing_premium") else str(current_premium),
                             reported_change_pct=str(reported)))
        current_total = sum(Decimal(row["exposure"]) * Decimal(row["current_base_rate"]) * Decimal(row["current_rating_factor"]) for row in rows)
        proposed_total = sum(Decimal(row["exposure"]) * Decimal(row["proposed_base_rate"]) * Decimal(row["proposed_rating_factor"]) for row in rows)
        impact = (proposed_total / current_total - 1) * 100
        claim = quantize(impact) + spec.get("overall", Decimal(0))

    with (directory / "rates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    factor_missing = spec.get("missing_factor", False)
    factor_text = "The proposed combined factors and changes in the exhibit are based on a synthetic classification review. Vehicle and driver classes use the same definitions before and after revision."
    approval_text = ("This internal note asserts that Connecticut automatically approves all Personal Auto revisions without a cited source, effective date, or DOI record."
                     if spec.get("unsupported") else "No regulatory approval is claimed. A human analyst must verify any applicable requirement using authoritative sources.")
    metadata = dict(schema_version="1.0", scenario_id=spec["case"], insurer=spec["insurer"], synthetic=True,
                    state="CT", line_of_business="Personal Auto", effective_date="2027-04-01",
                    premium_basis="modeled_annual_same_portfolio", claimed_overall_change_pct=str(claim),
                    claimed_overall_basis="fixed_exposure_portfolio", documents=[
                        dict(document_id="DOC-RATES", title="Rate exhibit", document_type="rate_exhibit", status="provided",
                             text="The CSV contains disjoint annual Personal Auto rating segments. Rates equal base rate times combined factor."),
                        dict(document_id="DOC-FACTORS", title="Factor rationale", document_type="factor_support",
                             status="not_provided" if factor_missing else "provided", text="" if factor_missing else factor_text),
                        dict(document_id="DOC-PREMIUM", title="Premium basis", document_type="premium_basis", status="provided",
                             text="Exposures are annual vehicle-years. Current premium is exposures times current modeled annual rate. Portfolio composition, coverage and limits are held fixed. Taxes, fees and policy rounding are excluded."),
                        dict(document_id="DOC-APPROVAL", title="Internal approval note", document_type="internal_note", status="provided", text=approval_text),
                    ])
    (directory / "filing.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    narrative = ("Synthetic Personal Auto rate revision. DOC-FACTORS contains the support for the proposed combined factor selections. "
                 if not factor_missing else "Synthetic Personal Auto rate revision. The proposed factor adjustments rely on DOC-FACTORS as supporting rationale, but that document has not been provided for this review. ")
    narrative += "The stated portfolio change uses fixed annual exposures and modeled annual premium. "
    if spec.get("bound"):
        narrative += f"No segment changes by more than {spec['bound']}% in absolute terms. "
    if spec.get("unsupported"):
        narrative += "DOC-APPROVAL describes an internal assertion about automatic regulatory approval; no authoritative source is included. "
    narrative += "All amounts, insurer names, territories, and classes are fictional. This filing makes no legal compliance determination.\n"
    (directory / "narrative.md").write_text(narrative, encoding="utf-8")


def main():
    for spec in CASES:
        build(spec, ROOT / "cases" / spec["case"])
    trial_root = ROOT.parent / "human_trial" / "filings"
    for spec in TRIALS:
        build(spec, trial_root / spec["case"])
    print("Built five holdout and two human-trial filings; no application model or answer key was read.")


if __name__ == "__main__":
    main()
