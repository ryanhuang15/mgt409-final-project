import json

import pytest
from pydantic import ValidationError

from backend.app.agents.contracts import AgentOutput, AnalysisNote
from backend.app.agents.prompts import DOCUMENTATION, PROMPT_VERSION
from backend.app.agents.validation import FindingRejected, validate_note, validate_output
from backend.app.config import ReviewLimits
from backend.app.services.audit import AuditLog
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.registry import ToolRegistry


def basic_note(**updates):
    return {"title": "Portfolio impact", "explanation": "The modeled portfolio impact is {{impact}}%.",
            "recommended_action": "Inspect the rate evidence before preparing the filing.",
            "evidence_refs": ["metric:fixed_exposure_portfolio"],
            "numeric_references": [{"key": "impact", "evidence_id": "metric:fixed_exposure_portfolio", "field": "value"}],
            "related_deterministic_finding_ids": [], **updates}


@pytest.fixture
def registry(make_filing):
    filing = make_filing()
    registry = ToolRegistry("a"*32, filing, analyze_filing(filing), AuditLog("a"*32), ReviewLimits())
    registry.call("rate_analysis", "get_portfolio_summary", json.dumps({"review_id": "a"*32}), "first")
    return registry


def test_numbers_are_resolved_from_engine(registry):
    result = validate_note(AnalysisNote(**basic_note()), registry, "rate_analysis")
    assert result["explanation"] == "The modeled portfolio impact is 5%."
    assert result["numeric_evidence"][0]["origin"] == "deterministic"
    assert result["numeric_evidence"][0]["value"] == "5.00"


def test_unused_but_verified_binding_remains_structured_evidence(registry):
    note = AnalysisNote(**basic_note(explanation="The supplied calculation supports this interpretation."))
    result = validate_note(note, registry, "rate_analysis")
    assert result["numeric_evidence"][0]["value"] == "5.00"


def test_nonquantitative_phrase_does_not_trigger_arithmetic_guard(registry):
    note = AnalysisNote(**basic_note(explanation="This provides one concrete example for review.", numeric_references=[]))
    assert validate_note(note, registry, "rate_analysis")["explanation"].startswith("This provides one")


@pytest.mark.parametrize("updates,error", [
    ({"evidence_refs": ["fabricated"]}, "evidence_not_retrieved"),
    ({"explanation": "The portfolio change is 88%."}, "unbound_numerical_literal"),
    ({"explanation": "The portfolio change is twenty percent."}, "unbound_numerical_literal"),
    ({"explanation": "The filing is legally compliant."}, "unsupported_regulatory_conclusion"),
    ({"explanation": "APPROVED FOR SUBMISSION"}, "unsupported_regulatory_conclusion"),
    ({"explanation": "Connecticut requires this document."}, "unsupported_regulatory_conclusion"),
    ({"numeric_references": [{"key": "impact", "evidence_id": "metric:fixed_exposure_portfolio", "field": "fake_value"}]}, "unknown_numeric_field"),
    ({"related_deterministic_finding_ids": ["fake"]}, "unknown_deterministic_finding"),
    ({"explanation": "The impact is {{fake}}%."}, "unbound_numeric_placeholder"),
])
def test_invalid_notes_are_rejected(registry, updates, error):
    with pytest.raises(FindingRejected, match=error):
        validate_note(AnalysisNote(**basic_note(**updates)), registry, "rate_analysis")


def test_authoritative_value_override_is_not_in_schema():
    data = basic_note()
    data["numeric_references"][0]["value"] = "99"
    with pytest.raises(ValidationError):
        AnalysisNote(**data)


def test_another_agent_cannot_cite_unretrieved_evidence(registry):
    with pytest.raises(FindingRejected, match="evidence_not_retrieved"):
        validate_note(AnalysisNote(**basic_note()), registry, "documentation_review")


def document_finding(**updates):
    return {**basic_note(explanation="An unsupported assertion needs source verification.", numeric_references=[]),
            "category": "unsupported_claim", "severity": "high", "affected_segments": [],
            "affected_documents": ["narrative.md"], "evidence_strength": "direct", "source_quotes": [], **updates}


def test_verified_regulatory_category_not_permitted():
    data = {"summary": basic_note(), "interpretations": [], "findings": [document_finding(category="verified_state_requirement")]}
    with pytest.raises(ValidationError):
        AgentOutput.model_validate(data)


def test_documentation_prompt_requires_explicit_unsupported_assertion():
    assert PROMPT_VERSION == "phase5-v1"
    assert "explicit affirmative factual or regulatory" in DOCUMENTATION
    assert "failure to give a detailed rationale is not" in DOCUMENTATION
    assert "unsupported approval/legal assurances" in DOCUMENTATION


@pytest.mark.parametrize("change,error", [
    ({"affected_segments": ["MISSING"]}, "nonexistent_segment"),
    ({"affected_documents": ["missing.pdf"]}, "nonexistent_document"),
    ({}, "source_quote_required"),
    ({"source_quotes": [{"evidence_id": "narrative:submitted", "quote": "Fabricated source statement"}]}, "quote_not_in_retrieved_source"),
])
def test_finding_reference_validation(registry, change, error):
    registry.call("documentation_review", "get_portfolio_summary", json.dumps({"review_id": "a"*32}), "summary")
    registry.call("documentation_review", "get_filing_narrative", json.dumps({"review_id": "a"*32, "offset": 0, "length": 100}), "narrative")
    finding = document_finding(evidence_refs=["narrative:submitted"], **change)
    output = AgentOutput(summary=AnalysisNote(**basic_note()), interpretations=[], findings=[finding])
    with pytest.raises(FindingRejected, match=error):
        validate_output(output, registry, "documentation_review")


def test_false_numerical_contradiction_is_rejected(examples):
    from backend.app.tools.inputs import load_filing
    filing = load_filing(examples / "adversarial")
    registry = ToolRegistry("a"*32, filing, analyze_filing(filing), AuditLog("a"*32), ReviewLimits())
    agent = "documentation_review"
    for name, arguments in [("get_portfolio_summary", {}), ("get_filing_narrative", {"offset": 0, "length": 6000})]:
        registry.call(agent, name, json.dumps({"review_id": "a"*32, **arguments}), name)
    quote = "No segment changes by more than 15% in absolute terms."
    result = registry.call(agent, "check_narrative_rate_bound", json.dumps({"review_id": "a"*32, "source_evidence_id": "narrative:submitted", "quoted_claim": quote}), "bound")
    ref = result["verification"]["evidence_id"]
    finding = document_finding(category="documentation_contradiction", evidence_refs=["narrative:submitted", "calc:PA020", ref],
                                source_quotes=[{"evidence_id": "narrative:submitted", "quote": quote}])
    output = AgentOutput(summary=AnalysisNote(**basic_note()), interpretations=[], findings=[finding])
    with pytest.raises(FindingRejected, match="claimed_contradiction_disproved_by_python"):
        validate_output(output, registry, agent)
