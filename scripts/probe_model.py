"""Check model access, then run one bounded review through both live agents."""

import asyncio
import json

from openai import AsyncOpenAI

from backend.app.config import PROJECT_ROOT, load_settings
from backend.app.review import run_review
from backend.app.services.audit import AuditLog
from backend.app.tools.inputs import load_filing


async def probe():
    settings = load_settings()
    report = {"model": settings.model, "reasoning_effort": settings.reasoning_effort,
              "model_access": False, "connectivity": False, "agents": [], "usage": {}}
    if not settings.api_key_configured:
        report["error"] = "missing_api_key"
        return report
    try:
        async with AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0) as client:
            await client.models.retrieve(settings.model)
            report["model_access"] = True
        filing = load_filing(PROJECT_ROOT / "data/examples/clean")
        result = await run_review(filing, settings=settings, persist=False)
        report["connectivity"] = result["usage"]["successful_responses"] > 0
        report["agents"] = [{"agent": agent["agent"], "status": agent["status"], "error": agent.get("error")}
                           for agent in result["agents"]]
        report["usage"] = result["usage"]
        report["audit"] = result["audit"]
        report["review_status"] = result["status"]
    except Exception as error:
        # Do not print exception text; SDK errors can contain request details.
        report["error"] = type(error).__name__
    safe = AuditLog("connectivity", secret=settings.openai_api_key).sanitize(report)
    target = PROJECT_ROOT / "docs/evidence/openai-connectivity.json"
    target.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in safe.items() if key != "audit"}, indent=2))
    return safe


if __name__ == "__main__":
    result = asyncio.run(probe())
    agents_ok = {agent["agent"] for agent in result.get("agents", []) if agent["status"] == "complete"}
    raise SystemExit(0 if result.get("model_access") and result.get("connectivity") and
                     agents_ok == {"rate_analysis", "documentation_review"} else 1)
