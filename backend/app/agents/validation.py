"""Check retrieved evidence and resolve all displayed numbers from Python results."""

import re
from decimal import Decimal, InvalidOperation

from backend.app.agents.contracts import AgentOutput
from backend.app.tools.bounds import BOUND_PATTERN, bound_reference

PLACEHOLDER = re.compile(r"\{\{([a-z_][a-z0-9_]*)\}\}")
SPELLED_NUMBER = re.compile(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)[\s-]+(?:percent|percentage|dollars?|usd|times|segments?|exposures?|premiums?|basis.points)\b", re.I)
FORBIDDEN_CLAIM = re.compile(
    r"approved for submission|legally compliant|regulatorily compliant|(?:is|are) compliant|"
    r"automatically approved|doi.approved|(?:connecticut|the state|state law) requires|"
    r"required by law|automatic approval (?:applies|is valid)", re.I,
)


class FindingRejected(ValueError):
    pass


def validate_note(note, registry, agent):
    delivered = registry.delivered.get(agent, set())
    missing = [ref for ref in note.evidence_refs if ref not in delivered]
    if missing:
        raise FindingRejected("evidence_not_retrieved:" + ",".join(missing))
    actual_ids = {finding.finding_id for finding in registry.analysis.findings}
    if any(ref not in actual_ids or "det:"+ref not in delivered for ref in note.related_deterministic_finding_ids):
        raise FindingRejected("unknown_deterministic_finding")
    bindings = {}
    numeric_evidence = []
    for reference in note.numeric_references:
        if reference.key in bindings or reference.evidence_id not in note.evidence_refs:
            raise FindingRejected("invalid_numeric_binding")
        record = registry.evidence.get(reference.evidence_id, {})
        if record.get("kind") != "calculation":
            raise FindingRejected("number_not_from_calculation")
        value = record.get("values", {}).get(reference.field)
        try:
            decimal = Decimal(value)
        except (InvalidOperation, TypeError):
            raise FindingRejected("unknown_numeric_field") from None
        if not decimal.is_finite():
            raise FindingRejected("nonfinite_numeric_reference")
        bindings[reference.key] = format(decimal, ".6f").rstrip("0").rstrip(".") or "0"
        numeric_evidence.append({**reference.model_dump(), "value": str(decimal), "origin": "deterministic"})
    rendered = {}
    used = set()
    for field in ("title", "explanation", "recommended_action"):
        text = getattr(note, field)
        keys = set(PLACEHOLDER.findall(text))
        used.update(keys)
        stripped = PLACEHOLDER.sub("", text)
        for segment_id in registry.rows:
            if re.search(r"\b"+re.escape(segment_id)+r"\b", stripped):
                if not any(ref.split(":")[-1] == segment_id for ref in note.evidence_refs):
                    raise FindingRejected("segment_in_prose_not_cited")
                stripped = re.sub(r"\b"+re.escape(segment_id)+r"\b", "", stripped)
        if re.search(r"\d", stripped) or SPELLED_NUMBER.search(stripped):
            raise FindingRejected("unbound_numerical_literal in " + field + ": use a calculation placeholder for quantities")
        if any(key not in bindings for key in keys):
            raise FindingRejected("unbound_numeric_placeholder:" + ",".join(sorted(keys-set(bindings))))
        if "{{" in stripped or "}}" in stripped:
            raise FindingRejected("malformed_numeric_placeholder")
        if FORBIDDEN_CLAIM.search(text):
            raise FindingRejected("unsupported_regulatory_conclusion")
        rendered[field] = PLACEHOLDER.sub(lambda match: bindings[match.group(1)], text)
    # Extra bindings remain useful as structured numerical evidence. They are safe
    # because every value was resolved from retrieved calculation records above.
    return {**rendered, "evidence_refs": note.evidence_refs, "numeric_evidence": numeric_evidence,
            "related_deterministic_finding_ids": note.related_deterministic_finding_ids,
            "evidence_status": "AI interpretation of retrieved evidence; analyst verification required"}


def validate_output(output: AgentOutput, registry, agent):
    summary = validate_note(output.summary, registry, agent)
    interpretations = [validate_note(note, registry, agent) for note in output.interpretations]
    findings = []
    if agent == "rate_analysis" and output.findings:
        raise FindingRejected("rate_findings_must_remain_deterministic")
    for index, finding in enumerate(output.findings, start=1):
        rendered = validate_note(finding, registry, agent)
        if any(segment not in registry.rows for segment in finding.affected_segments):
            raise FindingRejected("nonexistent_segment")
        if any(doc not in registry.documents and doc != "narrative.md" for doc in finding.affected_documents):
            raise FindingRejected("nonexistent_document")
        if not finding.affected_documents and not finding.affected_segments:
            raise FindingRejected("missing_affected_item")
        for quote in finding.source_quotes:
            chunks = registry.delivered_text.get(agent, {}).get(quote.evidence_id, [])
            if quote.evidence_id not in finding.evidence_refs or not any(quote.quote in chunk for chunk in chunks):
                raise FindingRejected("quote_not_in_retrieved_source")
        if finding.category in {"unsupported_claim", "suspicious_instruction", "documentation_contradiction"} and not finding.source_quotes:
            raise FindingRejected("source_quote_required")
        if finding.category == "documentation_contradiction" and not any(registry.evidence[ref].get("kind") == "calculation" for ref in finding.evidence_refs):
            raise FindingRejected("contradiction_requires_calculation")
        if finding.category == "documentation_contradiction":
            for quote in finding.source_quotes:
                if BOUND_PATTERN.search(quote.quote):
                    ref = bound_reference(quote.evidence_id, quote.quote)
                    if ref not in finding.evidence_refs or ref not in registry.delivered.get(agent, set()):
                        raise FindingRejected("numeric_bound_verification_required: call check_narrative_rate_bound and cite its evidence_id")
                    if registry.evidence[ref]["claim_holds"]:
                        raise FindingRejected("claimed_contradiction_disproved_by_python: the narrative bound holds; omit this finding")
        if finding.category == "missing_documentation":
            absent = [doc for doc in finding.affected_documents if doc in registry.documents and registry.documents[doc].status == "not_provided"]
            if not absent or not any("doc:"+doc in finding.evidence_refs for doc in absent):
                raise FindingRejected("missing_document_not_supported_by_inventory: affected_documents must include the actual cited inventory document_id marked not_provided")
        for doc in finding.affected_documents:
            ref = "narrative:submitted" if doc == "narrative.md" else "doc:"+doc
            if ref not in finding.evidence_refs:
                raise FindingRejected("affected_document_not_cited")
        for segment in finding.affected_segments:
            if not any(segment == ref.split(":")[-1] for ref in finding.evidence_refs):
                raise FindingRejected("affected_segment_not_cited")
        already_detected = [ref[4:] for ref in finding.evidence_refs if ref.startswith(("det:SEGMENT_CHANGE_MISMATCH:", "det:CURRENT_PREMIUM_MISMATCH:", "det:OVERALL_CHANGE_MISMATCH:"))]
        repeats_numeric_comparison = any(ref.field in {"reported_value", "calculated_value", "difference", "expected_current_premium", "supplied_current_premium"} for ref in finding.numeric_references)
        if finding.category in {"documentation_contradiction", "general_review"} and already_detected and repeats_numeric_comparison:
            interpretations.append({**rendered, "detection_origin": "deterministic", "related_deterministic_finding_ids": already_detected,
                                    "classification_note": "AI explanation of an existing numerical discrepancy; not counted as a new AI detection."})
            continue
        findings.append({**rendered, "finding_id": f"AI-{agent}-{index}", "origin": "ai", "category": finding.category,
                         "severity": finding.severity, "affected_segments": finding.affected_segments,
                         "affected_documents": finding.affected_documents, "evidence_strength": finding.evidence_strength,
                         "source_quotes": [quote.model_dump() for quote in finding.source_quotes],
                         "regulatory_status": "unverified_no_legal_determination"})
    return {"summary": summary, "interpretations": interpretations, "findings": findings}
