from decimal import Decimal

import pytest

from backend.app.config import PROJECT_ROOT
from backend.app.schemas import Filing, FilingMetadata, RateRow, SourceRow


@pytest.fixture(autouse=True)
def isolate_api_key(monkeypatch):
    # Real machine credentials are never needed by tests.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def examples():
    return PROJECT_ROOT / "data" / "examples"


@pytest.fixture
def make_filing():
    def create(records=None, **metadata_updates):
        if records is None:
            records = [
                {"segment_id": "A", "current_base_rate": "100", "proposed_base_rate": "120", "current_rating_factor": "1", "proposed_rating_factor": "1", "exposure": "1", "current_premium": "100", "reported_change_pct": "20"},
                {"segment_id": "B", "current_base_rate": "300", "proposed_base_rate": "300", "current_rating_factor": "1", "proposed_rating_factor": "1", "exposure": "1", "current_premium": "300", "reported_change_pct": "0"},
            ]
        metadata = dict(schema_version="1.0", scenario_id="test", insurer="Fictional Test Insurer", synthetic=True,
                        state="CT", line_of_business="Personal Auto", effective_date="2027-01-01",
                        premium_basis="modeled_annual_same_portfolio", claimed_overall_change_pct=Decimal("5"),
                        claimed_overall_basis="fixed_exposure_portfolio", documents=[])
        metadata.update(metadata_updates)
        rows = [RateRow.model_validate(record) for record in records]
        return Filing(metadata=FilingMetadata.model_validate(metadata), rows=rows,
                      source_rows=[SourceRow(evidence_id=f"row:{row.segment_id}", file="rates.csv", row_number=index+2) for index, row in enumerate(rows)],
                      narrative="Synthetic test narrative.", file_sha256={})
    return create
