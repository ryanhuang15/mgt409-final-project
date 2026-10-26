"""Check the separately labeled post-correction H02 regression evidence."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_h02_post_correction_regression_record_is_scored_and_labeled():
    record = json.loads((ROOT / "docs/evidence/phase6-post-correction-H02.json").read_text(encoding="utf-8"))

    assert record["record_type"] == "targeted_post_correction_regression"
    assert "not independent holdout evidence" in record["evidence_classification"]
    assert record["case"] == "H02"
    assert record["prompt_version"] == "phase5-v1"
    assert record["status"] == "complete"

    score = record["post_correction_score"]["complete_workflow"]
    assert score["issues"]["true_positives"] == 5
    assert score["issues"]["false_positives"] == 0
    assert score["issues"]["false_negatives"] == 0
    assert score["documentation"]["true_positives"] == 1
    assert score["documentation"]["false_positives"] == 0
    assert score["documentation"]["false_negatives"] == 0
    assert score["invalid_evidence_references"] == []

    compared = record["deterministic_signature_comparison"]
    assert compared["baseline_only"] == []
    assert compared["new_only"] == []

    ai_categories = [
        finding["category"]
        for finding in record["result"]["findings"]
        if finding["origin"] == "ai"
    ]
    assert ai_categories == ["documentation_contradiction"]
