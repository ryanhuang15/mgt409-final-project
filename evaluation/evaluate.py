"""Offline comparison to the separately maintained answer key."""

import argparse
import json
from decimal import Decimal, localcontext
from pathlib import Path

from backend.app.config import PROJECT_ROOT
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.inputs import load_filing

KEY_PATH = Path(__file__).with_name("answer_key.json")


def load_answer_key():
    return json.loads(KEY_PATH.read_text(encoding="utf-8"))


def evaluate_scenario(scenario: str, key: dict, file_format="csv") -> dict:
    # The application receives only a Filing. Labels remain in this offline process.
    result = analyze_filing(load_filing(PROJECT_ROOT / "data" / "examples" / scenario, f"rates.{file_format}"))
    expected = key["scenarios"][scenario]
    issues = [issue for issue in key["issues"] if issue["scenario"] == scenario]
    deterministic = [issue for issue in issues if issue["detection"] == "deterministic"]
    expected_signatures = {(item["finding_code"], item["affected"], item["severity"]) for item in deterministic}
    actual_signatures = {(item.code, item.affected, item.severity) for item in result.findings}
    errors = []
    if len(result.rows) != expected["segment_count"]:
        errors.append("segment_count")
    if len(result.findings) != len(actual_signatures):
        errors.append("duplicate_findings")
    with localcontext() as context:
        context.prec = 50
        tolerance = Decimal(key["metric_tolerance"])
        for name, value in expected["metrics"].items():
            actual = result.metrics[name]
            if value is None:
                if actual.value is not None or actual.status != "unavailable" or actual.reason != expected["unavailable_reasons"][name]:
                    errors.append(f"metric:{name}")
            elif actual.status != "available" or actual.value is None or abs(actual.value-Decimal(value)) > tolerance:
                errors.append(f"metric:{name}")
        for issue in deterministic:
            finding = next((f for f in result.findings if f.code == issue["finding_code"] and f.affected == issue["affected"]), None)
            if finding:
                for expected_field, result_field in (("expected_calculated_value", "calculated_value"), ("expected_reported_value", "reported_value"), ("expected_difference", "difference")):
                    if expected_field in issue:
                        actual_value = getattr(finding, result_field)
                        if actual_value is None or abs(actual_value-Decimal(issue[expected_field])) > tolerance:
                            errors.append(f"{issue['issue_id']}:{result_field}")
    missing = sorted(expected_signatures-actual_signatures)
    unexpected = sorted(actual_signatures-expected_signatures)
    return {
        "scenario": scenario, "format": file_format,
        "passed": not errors and not missing and not unexpected,
        "matched_deterministic_findings": len(expected_signatures & actual_signatures),
        "expected_deterministic_findings": len(expected_signatures),
        "missing_findings": missing, "unexpected_findings": unexpected, "numeric_errors": errors,
        "ai_evaluation": "not_implemented",
        "pending_ai_issue_ids": [item["issue_id"] for item in issues if item["detection"] == "ai_interpretation"],
    }


def run_evaluation(file_format="csv"):
    key = load_answer_key()
    return [evaluate_scenario(scenario, key, file_format) for scenario in key["scenarios"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["csv", "xlsx"], default="csv")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and not args.output.resolve().is_relative_to(PROJECT_ROOT):
        parser.error("Output must stay inside Final Project")
    results = run_evaluation(args.format)
    report = {"phase": 1, "model_calls": 0, "results": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['scenario']} ({result['format']}): {'PASS' if result['passed'] else 'FAIL'}; "
              f"deterministic {result['matched_deterministic_findings']}/{result['expected_deterministic_findings']}; "
              f"unexpected {len(result['unexpected_findings'])}; AI pending {len(result['pending_ai_issue_ids'])}")
        if not result["passed"]:
            print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(result["passed"] for result in results) else 1)


if __name__ == "__main__":
    main()
