"""Read a scenario and export numerical results, without invoking AI."""

import argparse
from pathlib import Path

from backend.app.config import PROJECT_ROOT
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.inputs import InputValidationError, load_filing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["clean", "flawed", "adversarial"])
    parser.add_argument("--format", choices=["csv", "xlsx"], default="csv")
    parser.add_argument("--output", type=Path, help="Optional JSON output path inside this project")
    args = parser.parse_args()
    if args.output:
        output = args.output.resolve()
        if not output.is_relative_to(PROJECT_ROOT):
            parser.error("Output must stay inside Final Project")
    try:
        result = analyze_filing(load_filing(PROJECT_ROOT / "data" / "examples" / args.scenario, f"rates.{args.format}"))
    except InputValidationError as error:
        parser.exit(2, f"Input validation failed: {error}\n")
    print(f"Scenario: {result.scenario_id}; segments: {len(result.rows)}; deterministic findings: {len(result.findings)}")
    for name, metric in result.metrics.items():
        display = f"{metric.value:.6f} {metric.unit}" if metric.value is not None else f"unavailable ({metric.reason})"
        print(f"  {name}: {display}")
    for finding in result.findings:
        print(f"  [{finding.severity}] {finding.code}: {finding.affected}")
    if args.output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"Evidence export: {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
