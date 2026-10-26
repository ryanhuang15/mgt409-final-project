"""Conservative, evidence-based comparison of immutable filing reviews."""

from decimal import Decimal, localcontext
from types import SimpleNamespace

from backend.app.tools.bounds import BOUND_PATTERN, check_rate_bound

RESOLVED = "resolved_by_revised_evidence"
PRESENT = "still_present"
NEW = "newly_identified"
REVIEW = "not_comparable_requires_review"


def issue_key(finding):
    """Stable anchors; model-generated titles and finding IDs are excluded."""
    if finding["origin"] == "deterministic":
        return f"det:{finding['finding_id']}"
    documents = ",".join(sorted(finding.get("affected_documents") or []))
    segments = ",".join(sorted(finding.get("affected_segments") or []))
    return f"ai:{finding['category']}:{documents}:{segments}"


def _document(filing, identifier):
    return next((doc for doc in filing["metadata"]["documents"] if doc["document_id"] == identifier), None)


def _old_ai_status(finding, before, after):
    category = finding["category"]
    docs = finding.get("affected_documents") or []
    if category == "missing_documentation" and len(docs) == 1:
        revised = _document(after["filing"], docs[0])
        if revised and revised["status"] == "provided" and revised["text"].strip():
            return RESOLVED, "The missing document is provided in the revised inventory; its content still needs analyst review."
        if revised and revised["status"] == "not_provided":
            return PRESENT, "The document remains marked not provided in the revised inventory."
        return REVIEW, "The referenced document ID is absent from the revised inventory."

    if category == "documentation_contradiction" and "narrative.md" in docs:
        claims = list(BOUND_PATTERN.finditer(after["filing"]["narrative"]))
        if len(claims) == 1:
            rows = [SimpleNamespace(segment_id=row["segment_id"],
                                    rate_change_pct=Decimal(row["rate_change_pct"]),
                                    evidence_id=row["evidence_id"])
                    for row in after["result"]["deterministic"]["rows"]]
            check = check_rate_bound("narrative:submitted", claims[0].group(0), rows)
            if check["claim_holds"]:
                return RESOLVED, "Python verified the revised narrative bound against every revised segment."
            return PRESENT, "Python found a revised segment that still contradicts the narrative bound."

    for identifier in docs:
        if identifier == "narrative.md":
            if before["filing"]["narrative"] == after["filing"]["narrative"]:
                return PRESENT, "The cited narrative is unchanged; omission by an agent is not evidence of resolution."
            continue
        old_doc = _document(before["filing"], identifier)
        new_doc = _document(after["filing"], identifier)
        if old_doc and new_doc and old_doc["status"] == new_doc["status"] and old_doc["text"] == new_doc["text"]:
            return PRESENT, "The cited document text and inventory status are unchanged."
    return REVIEW, "The cited source changed or was removed. Its meaning requires analyst review."


def _old_det_status(finding, before, after):
    affected = (finding.get("affected_segments") or [finding.get("affected")])[0]
    if affected in {row["segment_id"] for row in before["result"]["deterministic"]["rows"]}:
        if affected not in {row["segment_id"] for row in after["result"]["deterministic"]["rows"]}:
            return REVIEW, "The affected segment is absent from the revised filing."
    if affected == "portfolio" and before["filing"]["metadata"]["claimed_overall_basis"] != after["filing"]["metadata"]["claimed_overall_basis"]:
        return REVIEW, "The claimed portfolio basis changed; compare the two bases manually."
    if before["result"]["deterministic"]["config"] != after["result"]["deterministic"]["config"]:
        return REVIEW, "Numerical tolerances changed between reviews."
    return RESOLVED, "The revised Python calculation no longer returns this condition on a comparable basis."


def compare(before, after):
    """Never infer resolution from changed AI prose or reviewer annotations."""
    original, revised = before["result"], after["result"]
    old_groups, new_groups = {}, {}
    for finding in original["findings"]:
        old_groups.setdefault(issue_key(finding), []).append(finding)
    for finding in revised["findings"]:
        new_groups.setdefault(issue_key(finding), []).append(finding)

    changes = []
    for key in dict.fromkeys([*old_groups, *new_groups]):
        old, new = old_groups.get(key, []), new_groups.get(key, [])
        if len(old) > 1 or len(new) > 1:
            status, reason = REVIEW, "Multiple findings share this source anchor; match them manually."
        elif old and new:
            status, reason = PRESENT, "The revised review returns the same issue type at the same stable source anchor."
        elif new:
            status, reason = NEW, "The issue appears in the revised review at a new stable source anchor."
        elif old[0]["origin"] == "deterministic":
            status, reason = _old_det_status(old[0], before, after)
        else:
            status, reason = _old_ai_status(old[0], before, after)
        changes.append(dict(issue_key=key, status=status, reason=reason,
                            origin=(new or old)[0]["origin"], category=(new or old)[0]["category"],
                            before=old[0] if len(old) == 1 else None,
                            after=new[0] if len(new) == 1 else None))

    before_rows = {row["segment_id"]: row for row in original["deterministic"]["rows"]}
    after_rows = {row["segment_id"]: row for row in revised["deterministic"]["rows"]}
    segments = []
    with localcontext() as context:
        context.prec = 50
        for segment_id in sorted(before_rows.keys() | after_rows.keys()):
            old, new = before_rows.get(segment_id), after_rows.get(segment_id)
            difference = Decimal(new["rate_change_pct"]) - Decimal(old["rate_change_pct"]) if old and new else None
            segments.append(dict(segment_id=segment_id,
                                 before_pct=old["rate_change_pct"] if old else None,
                                 after_pct=new["rate_change_pct"] if new else None,
                                 difference_pp=str(difference) if difference is not None else None,
                                 status="added" if not old else "removed" if not new else "changed" if difference else "unchanged",
                                 before_evidence=old["evidence_id"] if old else None,
                                 after_evidence=new["evidence_id"] if new else None))
        old_impact = original["deterministic"]["metrics"]["fixed_exposure_portfolio"]["value"]
        new_impact = revised["deterministic"]["metrics"]["fixed_exposure_portfolio"]["value"]
        impact_difference = str(Decimal(new_impact) - Decimal(old_impact)) if old_impact is not None and new_impact is not None else None
    counts = {status: sum(item["status"] == status for item in changes) for status in (RESOLVED, PRESENT, NEW, REVIEW)}
    return dict(original_review_id=original["review_id"], revised_review_id=revised["review_id"],
                original_job_id=before["job_id"], revised_job_id=after["job_id"],
                original_status=original["status"], revised_status=revised["status"],
                portfolio=dict(before_pct=old_impact, after_pct=new_impact, difference_pp=impact_difference,
                               before_evidence="metric:fixed_exposure_portfolio", after_evidence="metric:fixed_exposure_portfolio"),
                segments=segments, issues=changes, counts=counts,
                current_finding_count=len(revised["findings"]),
                method="Stable numerical code + affected source; documentation category + document/segment anchors. Changed AI wording alone never resolves an issue.")
