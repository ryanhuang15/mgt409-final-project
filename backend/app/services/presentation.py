"""Deterministic dollar contributions for the analyst's interactive exhibit."""

from decimal import Decimal, localcontext


def enrich(envelope):
    if not envelope.get("result"):
        return envelope
    analysis = envelope["result"]["deterministic"]
    impact = analysis["metrics"]["fixed_exposure_portfolio"]
    if impact["status"] != "available":
        envelope["analytics"] = {"status": "unavailable", "reason": impact["reason"], "segments": []}
        return envelope
    inputs = {row["segment_id"]: row for row in envelope["filing"]["rows"]}
    with localcontext() as context:
        context.prec = 50
        segments = []
        for row in analysis["rows"]:
            exposure = Decimal(inputs[row["segment_id"]]["exposure"])
            contribution = exposure * Decimal(row["absolute_rate_change"])
            segments.append(dict(segment_id=row["segment_id"], premium_contribution_usd=str(contribution),
                                 evidence_refs=[row["evidence_id"], f"row:{row['segment_id']}"]))
        envelope["analytics"] = dict(status="available", reason=None, segments=segments,
            total_exposure=str(sum(Decimal(row["exposure"]) for row in inputs.values())),
            premium_change_usd=str(sum(Decimal(row["premium_contribution_usd"]) for row in segments)),
            formula="Segment premium contribution = exposure × (proposed modeled rate − current modeled rate)")
    return envelope
