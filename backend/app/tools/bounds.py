"""Deterministic verification of explicitly supported numerical narrative claims."""

import hashlib
import re
from decimal import Decimal

BOUND_PATTERN = re.compile(r"\bno segment changes by more than (\d+(?:\.\d+)?)\s*% in absolute terms\b", re.I)


def bound_reference(source_ref, quote):
    return "bound:" + hashlib.sha256((source_ref+"\n"+quote).encode()).hexdigest()[:16]


def check_rate_bound(source_ref, quote, rows):
    match = BOUND_PATTERN.search(quote)
    if not match:
        raise ValueError("unsupported_bound_statement")
    bound = Decimal(match.group(1))
    largest = max(rows, key=lambda row: abs(row.rate_change_pct))
    violations = [row.segment_id for row in rows if abs(row.rate_change_pct) > bound]
    ref = bound_reference(source_ref, quote)
    return {
        "evidence_id": ref, "kind": "calculation", "source_evidence_id": source_ref, "source_quote": quote,
        "formula": "claim_holds = all(abs(segment_rate_change_pct) <= parsed_bound_pct)",
        "input_refs": [source_ref, largest.evidence_id], "claim_holds": not violations,
        "values": {"bound_pct": str(bound), "largest_absolute_change_pct": str(abs(largest.rate_change_pct))},
        "violating_segment_ids": violations[:24], "violation_count": len(violations),
        "violations_truncated": len(violations) > 24,
    }
