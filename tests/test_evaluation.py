import ast
from decimal import Decimal

import pytest

from backend.app.config import PROJECT_ROOT
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.inputs import load_filing
from evaluation.evaluate import evaluate_scenario, load_answer_key


@pytest.mark.parametrize("scenario", ["clean", "flawed", "adversarial"])
@pytest.mark.parametrize("file_format", ["csv", "xlsx"])
def test_scenarios_against_independent_key(scenario, file_format):
    report = evaluate_scenario(scenario, load_answer_key(), file_format)
    assert report["passed"], report
    assert report["unexpected_findings"] == []


@pytest.mark.parametrize("scenario", ["clean", "flawed", "adversarial"])
def test_csv_xlsx_equivalence(examples, scenario):
    csv = load_filing(examples / scenario)
    xlsx = load_filing(examples / scenario, "rates.xlsx")
    assert csv.rows == xlsx.rows
    assert analyze_filing(csv).metrics == analyze_filing(xlsx).metrics
    assert xlsx.source_rows[0].file == "rates.xlsx"
    assert xlsx.source_rows[0].sheet == "rates"


def test_premium_consistency_for_clean_data(examples):
    filing = load_filing(examples / "clean")
    assert len(filing.rows) == 24
    assert sum(row.exposure for row in filing.rows) == Decimal("8400")
    for row in filing.rows:
        assert row.current_premium == row.exposure * row.current_base_rate * row.current_rating_factor


def test_adversarial_text_is_data_only(examples):
    clean = load_filing(examples / "clean")
    adversarial = load_filing(examples / "adversarial")
    assert "SYSTEM OVERRIDE" in adversarial.narrative
    assert "APPROVED FOR SUBMISSION" in adversarial.narrative
    assert clean.rows == adversarial.rows
    clean_result = analyze_filing(clean)
    adversarial_result = analyze_filing(adversarial)
    assert adversarial_result.metrics == clean_result.metrics
    assert adversarial_result.rows == clean_result.rows
    assert adversarial_result.findings == []
    assert "APPROVED FOR SUBMISSION" not in adversarial_result.model_dump_json()


def test_answer_key_is_not_filing_input(examples, tmp_path):
    source = examples / "clean"
    for name in ("rates.csv", "filing.json", "narrative.md"):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    (tmp_path / "answer_key.json").write_text('{"secret_label":"DO_NOT_LOAD_THIS_LABEL"}', encoding="utf-8")
    filing = load_filing(tmp_path)
    assert "DO_NOT_LOAD_THIS_LABEL" not in filing.model_dump_json()
    assert set(filing.file_sha256) == {"rates.csv", "filing.json", "narrative.md"}


def test_application_keeps_evaluation_out_and_model_client_in_adapter():
    for path in (PROJECT_ROOT / "backend").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            assert not any(name.split(".")[0] == "evaluation" for name in imports)
            if any(name.split(".")[0] == "openai" for name in imports):
                assert path == PROJECT_ROOT / "backend/app/services/model.py"


def test_ai_findings_are_explicitly_pending():
    key = load_answer_key()
    flawed = evaluate_scenario("flawed", key)
    adversarial = evaluate_scenario("adversarial", key)
    assert flawed["pending_ai_issue_ids"] == ["FL-D01", "FL-D02", "FL-D03"]
    assert adversarial["pending_ai_issue_ids"] == ["AD-S01"]
    assert adversarial["ai_evaluation"] == "not_implemented"


def test_flawed_finding_evidence_resolves(examples):
    result = analyze_filing(load_filing(examples / "flawed"))
    for finding in result.findings:
        assert finding.evidence_refs
        assert all(ref in result.evidence for ref in finding.evidence_refs)
    assert result.regulatory_checks == "not_implemented"
    assert all(f.basis != "verified_requirement" for f in result.findings)
