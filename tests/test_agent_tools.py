import json

import pytest

from backend.app.config import ReviewLimits
from backend.app.services.audit import AuditLog
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.registry import ToolRegistry

REVIEW_ID = "a" * 32


@pytest.fixture
def registry(make_filing):
    filing = make_filing()
    return ToolRegistry(REVIEW_ID, filing, analyze_filing(filing), AuditLog(REVIEW_ID), ReviewLimits())


def call(registry, name, arguments=None, agent="rate_analysis"):
    return registry.call(agent, name, json.dumps({"review_id": REVIEW_ID, **(arguments or {})}), "call-test")


def test_summary_returns_authoritative_values_and_audit(registry):
    result = call(registry, "get_portfolio_summary")
    assert result["metrics"]["fixed_exposure_portfolio"]["value"] == "5.00"
    assert registry.audit.events[-1]["data"]["validated_arguments"] == {"review_id": REVIEW_ID}
    assert registry.audit.events[-1]["data"]["result"] == result
    assert "metric:fixed_exposure_portfolio" in registry.delivered["rate_analysis"]


@pytest.mark.parametrize("name,arguments,error", [
    ("exec_python", {"code": "print('hello')"}, "unsupported_tool"),
    ("get_portfolio_summary", {"review_id": "b" * 32}, "wrong_review"),
    ("get_portfolio_summary", {"path": "../../evaluation/answer_key.json"}, "invalid_parameters"),
    ("get_segment_calculations", {"segment_ids": ["NOT-A-SEGMENT"]}, "unknown_segment"),
    ("get_segment_calculations", {"segment_ids": []}, "invalid_parameters"),
    ("get_segment_calculations", {"segment_ids": ["A"] * 9}, "invalid_parameters"),
    ("get_calculation_evidence", {"evidence_ids": ["fabricated"]}, "unknown_calculation_evidence"),
    ("get_filing_narrative", {"offset": 0, "length": 100}, "unsupported_tool"),
])
def test_invalid_tool_requests_are_rejected(registry, name, arguments, error):
    result = call(registry, name, arguments)
    assert result["error"] == error
    assert registry.audit.events[-1]["status"] == "rejected"
    assert registry.delivered == {}


@pytest.mark.parametrize("arguments", ["not json", "[]", '{"review_id":true}', "x"*4097])
def test_malformed_arguments(registry, arguments):
    assert "error" in registry.call("rate_analysis", "get_portfolio_summary", arguments, "bad")


def test_strict_integer_parameters(registry):
    result = call(registry, "get_filing_narrative", {"offset": True, "length": 100}, "documentation_review")
    assert result["error"] == "invalid_parameters"


def test_narrative_pagination_and_trust(registry):
    first = call(registry, "get_filing_narrative", {"offset": 0, "length": 10}, "documentation_review")
    assert first["trust"] == "untrusted_filing_content"
    assert first["next_offset"] == 10
    assert len(first["text"]) == 10
    assert "unread:narrative:submitted" in registry.missing_coverage("documentation_review")
    call(registry, "get_filing_narrative", {"offset": 10, "length": 6000}, "documentation_review")
    assert "unread:narrative:submitted" not in registry.missing_coverage("documentation_review")


def test_narrative_negative_offset(registry):
    assert call(registry, "get_filing_narrative", {"offset": -1, "length": 10}, "documentation_review")["error"] == "invalid_parameters"


def test_document_scope_and_missing_status(examples):
    from backend.app.tools.inputs import load_filing
    filing = load_filing(examples / "flawed")
    registry = ToolRegistry(REVIEW_ID, filing, analyze_filing(filing), AuditLog(REVIEW_ID), ReviewLimits())
    result = call(registry, "get_document_excerpt", {"document_id": "DOC-FACTORS", "offset": 0, "length": 100}, "documentation_review")
    assert result["error"] == "document_not_provided"
    result = call(registry, "get_document_excerpt", {"document_id": "../../answer_key.json", "offset": 0, "length": 100}, "documentation_review")
    assert result["error"] == "unknown_document"


def test_tool_output_limit_does_not_mark_evidence_delivered(registry):
    registry.limits = ReviewLimits(max_tool_output_bytes=1000)
    assert call(registry, "get_portfolio_summary")["error"] == "tool_output_limit"
    assert registry.delivered == {}


def test_no_file_or_execution_tool_schemas(registry):
    for definition in registry.definitions("documentation_review"):
        schema = definition["function"]["parameters"]
        assert schema["additionalProperties"] is False
        assert "review_id" in schema["required"]
        assert not {"filename", "path", "url", "code", "command"} & set(schema["properties"])


def test_reconciliation_exposes_actual_supporting_evidence(registry):
    result = call(registry, "get_reconciliation_findings", {"offset": 0, "limit": 12})
    assert "calc:A" in result["supporting_evidence"]
    assert "calc:A" in registry.delivered["rate_analysis"]
    assert result["supporting_evidence"]["calc:A"]["values"]["rate_change_pct"] == "20.0"


@pytest.mark.parametrize("scenario,holds", [("clean", True), ("flawed", False), ("adversarial", True)])
def test_narrative_bound_comparison_uses_python(examples, scenario, holds):
    from backend.app.tools.inputs import load_filing
    filing = load_filing(examples / scenario)
    registry = ToolRegistry(REVIEW_ID, filing, analyze_filing(filing), AuditLog(REVIEW_ID), ReviewLimits())
    call(registry, "get_filing_narrative", {"offset": 0, "length": 6000}, "documentation_review")
    result = call(registry, "check_narrative_rate_bound", {"source_evidence_id": "narrative:submitted", "quoted_claim": "No segment changes by more than 15% in absolute terms."}, "documentation_review")
    assert result["verification"]["claim_holds"] is holds
    assert result["verification"]["values"]["bound_pct"] == "15"
    assert result["verification"]["violating_segment_ids"] == ([] if holds else ["PA020"])


def test_bound_quote_cannot_be_invented(registry):
    result = call(registry, "check_narrative_rate_bound", {"source_evidence_id": "narrative:submitted", "quoted_claim": "No segment changes by more than 1% in absolute terms."}, "documentation_review")
    assert result["error"] == "bound_quote_not_retrieved"
