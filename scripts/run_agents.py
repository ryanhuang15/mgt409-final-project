"""Run a real review of a bundled synthetic filing (uses the course API key)."""

import argparse
import asyncio
import json

from backend.app.config import PROJECT_ROOT
from backend.app.review import run_review
from backend.app.tools.inputs import load_filing


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["clean", "flawed", "adversarial"])
    parser.add_argument("--format", choices=["csv", "xlsx"], default="csv")
    args = parser.parse_args()
    result = await run_review(load_filing(PROJECT_ROOT / "data/examples" / args.scenario, f"rates.{args.format}"))
    print(json.dumps({"review_id": result["review_id"], "scenario": args.scenario, "status": result["status"],
                      "agents": [{key: stage[key] for key in ("agent", "status", "tool_calls", "error", "rejected_outputs")} for stage in result["agents"]],
                      "findings": [{key: finding[key] for key in ("origin", "category", "title")} for finding in result["findings"]],
                      "usage": result["usage"], "duration_ms": result["duration_ms"]}, indent=2))
    return result["status"] == "complete"


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
