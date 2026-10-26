"""Independent, exact-anchor holdout scoring. No labels enter the reviewing agents."""

import argparse
import asyncio
import csv
import json
import time
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from backend.app.config import PROJECT_ROOT
from backend.app.review import run_review
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.inputs import load_filing

ROOT = Path(__file__).resolve().parent
KEY = ROOT / "answer_key.json"
EVIDENCE = PROJECT_ROOT / "docs/evidence"


def fraction_oracle(path):
    """Recompute directly from submitted CSV fields using rational arithmetic."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    current, proposed, exposures, changes, supplied = [], [], [], [], []
    for row in rows:
        old = Fraction(row["current_base_rate"]) * Fraction(row["current_rating_factor"])
        new = Fraction(row["proposed_base_rate"]) * Fraction(row["proposed_rating_factor"])
        exposure = Fraction(row["exposure"])
        current.append(old * exposure)
        proposed.append(new * exposure)
        exposures.append(exposure)
        changes.append((new / old - 1) * 100)
        supplied.append(Fraction(row["current_premium"]) if row["current_premium"] else None)
    weighted = sum(e * d for e, d in zip(exposures, changes)) / sum(exposures)
    impact = (sum(proposed) / sum(current) - 1) * 100
    premium = None if any(item is None for item in supplied) or any(p != c for p, c in zip(supplied, current)) else sum(p * d for p, d in zip(supplied, changes)) / sum(supplied)
    return dict(exposure_weighted=weighted, fixed_exposure_portfolio=impact,
                current_premium_weighted=premium, current_modeled_premium=sum(current),
                proposed_modeled_premium=sum(proposed))


def metric_errors(analysis, expected):
    with localcontext() as context:
        context.prec = 65
        errors = []
        for key, value in expected.items():
            actual = analysis["metrics"][key]["value"]
            if value is None:
                if actual is not None:
                    errors.append(key)
            elif actual is None or abs(Decimal(actual) - Decimal(value.numerator) / Decimal(value.denominator)) > Decimal("0.000000000000000001"):
                errors.append(key)
    return errors


def documentation_anchor(finding):
    category = finding["category"]
    docs = finding.get("affected_documents") or []
    preferred = {"missing_documentation": "DOC-FACTORS", "unsupported_claim": "DOC-APPROVAL",
                 "documentation_contradiction": "narrative.md"}.get(category)
    return f"{category}:{preferred if preferred in docs else ','.join(sorted(docs))}"


def actual_keys(result, include_ai):
    keys = [item["finding_id"] for item in result["deterministic"]["findings"]]
    if include_ai:
        keys += [documentation_anchor(item) for item in result["findings"] if item["origin"] == "ai"]
    return keys


def detection(expected, actual):
    labels = Counter(expected)
    observed = Counter(actual)
    tp = sum(min(labels[key], observed[key]) for key in labels)
    fp = sum((observed - labels).values())
    fn = sum((labels - observed).values())
    return dict(true_positives=tp, false_positives=fp, false_negatives=fn,
                precision=None if tp + fp == 0 else tp / (tp + fp),
                recall=None if tp + fn == 0 else tp / (tp + fn),
                missed=list((labels - observed).elements()), unexpected=list((observed - labels).elements()))


def score_case(case_id, key, analysis, result=None):
    expected = [issue["anchor"] for issue in key["issues"]]
    numeric_expected = [issue["anchor"] for issue in key["issues"] if issue["kind"] == "deterministic"]
    exact = fraction_oracle(ROOT / "cases" / case_id / "rates.csv")
    base = dict(case=case_id, segment_count=key["segments"], expected_issues=len(expected),
                metric_errors=metric_errors(analysis, exact),
                deterministic=detection(numeric_expected, actual_keys(dict(deterministic=analysis), False)))
    if result is None:
        return base
    refs = set(result["deterministic"]["evidence"]) | set(result.get("documentation_evidence", {})) | set(result.get("supplemental_evidence", {}))
    invalid = [ref for finding in result["findings"] for ref in finding["evidence_refs"] if ref not in refs]
    doc_expected = [issue["anchor"] for issue in key["issues"] if issue["kind"] == "documentation"]
    doc_actual = [documentation_anchor(item) for item in result["findings"] if item["origin"] == "ai"]
    base["complete_workflow"] = dict(status=result["status"], issues=detection(expected, actual_keys(result, True)),
                                     documentation=detection(doc_expected, doc_actual),
                                     invalid_evidence_references=invalid, duration_ms=result["duration_ms"],
                                     model_latency_ms=result["usage"]["model_latency_ms"], usage=result["usage"],
                                     review_id=result["review_id"])
    return base


async def run(live=False):
    key = json.loads(KEY.read_text(encoding="utf-8"))["cases"]
    rows = []
    for case_id, label in key.items():
        filing = load_filing(ROOT / "cases" / case_id)
        before = time.monotonic()
        analysis = analyze_filing(filing).model_dump(mode="json")
        baseline_ms = round((time.monotonic() - before) * 1000, 3)
        path = EVIDENCE / f"phase4-holdout-{case_id}.json"
        result = None
        if live:
            result = await run_review(filing)
            path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        elif path.is_file():
            result = json.loads(path.read_text(encoding="utf-8"))
            if result["deterministic"]["source_file_sha256"] != filing.file_sha256:
                raise ValueError(f"Recorded run {case_id} does not match current filing inputs")
        score = score_case(case_id, label, analysis, result)
        score["deterministic_latency_ms"] = baseline_ms
        rows.append(score)
        combined = score.get("complete_workflow")
        print(f"{case_id}: engine TP={score['deterministic']['true_positives']} FP={score['deterministic']['false_positives']} "
              f"FN={score['deterministic']['false_negatives']}, numeric_errors={score['metric_errors']}; "
              + (f"full TP={combined['issues']['true_positives']} FP={combined['issues']['false_positives']} FN={combined['issues']['false_negatives']} "
                 f"status={combined['status']} tokens={combined['usage']['total_tokens']}" if combined else "full run pending"))
    # Aggregate actual counts from case-level exact matches, avoiding any semantic merging.
    def aggregate(field):
        tp = sum(row[field]["true_positives"] for row in rows)
        fp = sum(row[field]["false_positives"] for row in rows)
        fn = sum(row[field]["false_negatives"] for row in rows)
        return dict(true_positives=tp, false_positives=fp, false_negatives=fn,
                    precision=None if tp+fp==0 else tp/(tp+fp), recall=None if tp+fn==0 else tp/(tp+fn))
    deterministic = aggregate("deterministic")
    full_rows = [row for row in rows if row.get("complete_workflow")]
    def aggregate_full(field):
        tp=sum(row["complete_workflow"][field]["true_positives"] for row in full_rows)
        fp=sum(row["complete_workflow"][field]["false_positives"] for row in full_rows)
        fn=sum(row["complete_workflow"][field]["false_negatives"] for row in full_rows)
        return dict(true_positives=tp,false_positives=fp,false_negatives=fn,
                    precision=None if tp+fp==0 else tp/(tp+fp),recall=None if tp+fn==0 else tp/(tp+fn))
    report=dict(method="Exact code/affected segment for deterministic findings; category plus explicit source document for documentation. Counts use multiset matching; no semantic partial credit.",
                cases=rows, aggregate_deterministic=deterministic,
                aggregate_full=aggregate_full("issues") if len(full_rows)==len(rows) else None,
                aggregate_documentation=aggregate_full("documentation") if len(full_rows)==len(rows) else None,
                case_count=len(rows), live_results_available=len(full_rows),
                limitation="Five seeded synthetic cases measure performance on this set only, not statistical generalization.")
    (EVIDENCE / "phase4-holdout-evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true",help="Run each unseen case through the course model once")
    args=parser.parse_args()
    asyncio.run(run(args.live))


if __name__=="__main__":
    main()
