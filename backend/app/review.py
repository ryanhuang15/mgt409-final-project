"""Controller preserves mandatory calculations and coordinates bounded AI stages."""

import hashlib
import json
import time
import uuid

from backend.app.agents.prompts import PROMPT_VERSION
from backend.app.agents.runner import run_agent
from backend.app.config import load_settings
from backend.app.schemas import Filing
from backend.app.services.audit import AuditLog, utc_now
from backend.app.services.model import ModelFailure, ModelSession, OpenAIGateway, usage_summary
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.registry import ToolRegistry


def numerical_findings(analysis):
    return [dict(finding_id=f.finding_id, origin="deterministic", category=f.basis, severity=f.severity,
                 title=f.code.replace("_", " ").title(), explanation=f.message, evidence_refs=f.evidence_refs,
                 affected_segments=[f.affected] if f.affected in {row.segment_id for row in analysis.rows} else [],
                 affected_documents=[], affected=f.affected, recommended_action=f.recommended_action,
                 evidence_strength="deterministic", numerical_evidence={"reported_value": str(f.reported_value) if f.reported_value is not None else None,
                    "calculated_value": str(f.calculated_value) if f.calculated_value is not None else None,
                    "difference": str(f.difference) if f.difference is not None else None, "unit": f.unit}) for f in analysis.findings]


async def run_review(filing: Filing, settings=None, gateway=None, persist=True, progress=None):
    started = time.monotonic()
    settings = settings or load_settings()
    # Revalidate callers' objects so model_copy or a later API cannot bypass contracts.
    filing = Filing.model_validate_json(filing.model_dump_json())
    if len(filing.narrative) > settings.limits.max_narrative_chars or any(len(doc.text) > settings.limits.max_document_chars for doc in filing.metadata.documents):
        raise ValueError("filing_text_limit")
    review_id, timestamp = uuid.uuid4().hex, utc_now()
    directory = settings.project_root / "runtime/reviews" / review_id if persist else None
    audit = AuditLog(review_id, directory, settings.openai_api_key)
    audit.add("controller", "review_started", model=settings.model, reasoning_effort=settings.reasoning_effort,
              prompt_version=PROMPT_VERSION, limits=settings.limits.model_dump(),
              canonical_input_sha256=hashlib.sha256(filing.model_dump_json().encode()).hexdigest(),
              source_file_sha256=filing.file_sha256)
    analysis = analyze_filing(filing)
    if progress:
        progress("rate_analysis")
    audit.add("controller", "deterministic_calculations_completed", finding_ids=[f.finding_id for f in analysis.findings],
              analysis_sha256=hashlib.sha256(analysis.model_dump_json().encode()).hexdigest())
    registry = ToolRegistry(review_id, filing, analysis, audit, settings.limits)
    owned_gateway = gateway is None
    stages = []
    try:
        gateway = gateway or OpenAIGateway(settings)
        session = ModelSession(gateway, settings, audit)
        session.deadline = started + settings.limits.review_timeout_seconds
        rate = await run_agent("rate_analysis", session, registry)
        stages.append(rate)
        if progress:
            progress("documentation_review")
        handoff = None
        if rate["result"]:
            handoff = {"summary": rate["result"]["summary"], "interpretations": rate["result"]["interpretations"][:2]}
        stages.append(await run_agent("documentation_review", session, registry, handoff))
    except ModelFailure as error:
        for agent in ("rate_analysis", "documentation_review"):
            if not any(stage["agent"] == agent for stage in stages):
                stages.append(dict(agent=agent, status="incomplete", duration_ms=0, tool_calls=0,
                                   error=error.code, rejected_outputs=[], result=None))
        audit.add("controller", "model_unavailable", status="error", error=error.code)
    finally:
        if owned_gateway and gateway:
            try:
                await gateway.close()
            except Exception:
                audit.add("controller", "client_cleanup_failed", status="error")
    merged = numerical_findings(analysis)
    for stage in stages:
        if stage["result"]:
            merged.extend(stage["result"]["findings"])
    status = "complete" if all(stage["status"] == "complete" for stage in stages) else "partial"
    audit.add("controller", "review_finished", status=status, duration_ms=round((time.monotonic()-started)*1000, 3))
    result = dict(schema_version="2.0", review_id=review_id, timestamp=timestamp, status=status,
                  disposition="human_review_required", regulatory_checks="not_implemented", model=settings.model,
                  tool_calling="native_chat_completions", structured_output="strict_json_schema",
                  duration_ms=round((time.monotonic()-started)*1000, 3), deterministic=analysis.model_dump(mode="json"),
                  findings=merged, agents=stages, usage=usage_summary(audit.events, settings.model), audit=audit.events,
                  documentation_evidence={key: item for key, item in registry.evidence.items() if item["kind"].startswith("untrusted")},
                  supplemental_evidence={key: item for key, item in registry.evidence.items() if key not in analysis.evidence})
    # Both storage and returned output are redacted even if hostile input repeats a known key.
    result = audit.sanitize(result)
    audit.save_result(result)
    return result
