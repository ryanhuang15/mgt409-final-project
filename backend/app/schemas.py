"""Explicit data contracts; Decimal values serialize as strings in JSON."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def reject_boolean(value):
    if isinstance(value, bool):
        raise ValueError("A number is required, not a boolean")
    return value


Number = Annotated[
    Decimal, BeforeValidator(reject_boolean),
    Field(max_digits=20, decimal_places=8, allow_inf_nan=False),
]
PositiveNumber = Annotated[Number, Field(gt=0)]
NonnegativeNumber = Annotated[Number, Field(ge=0)]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")]
Basis = Literal["exposure_weighted", "fixed_exposure_portfolio", "current_premium_weighted"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceRow(Contract):
    evidence_id: str
    file: str
    row_number: int
    sheet: str | None = None


class RateRow(Contract):
    segment_id: Identifier
    territory: str = Field(default="", max_length=100)
    driver_class: str = Field(default="", max_length=100)
    vehicle_group: str = Field(default="", max_length=100)
    current_base_rate: PositiveNumber
    proposed_base_rate: PositiveNumber
    current_rating_factor: PositiveNumber
    proposed_rating_factor: PositiveNumber
    # Negative weights are retained so analysis can explain why metrics are unavailable.
    exposure: Number | None = None
    current_premium: Number | None = None
    reported_change_pct: Number | None = None


class Document(Contract):
    document_id: Identifier
    title: str = Field(min_length=1, max_length=200)
    document_type: str = Field(min_length=1, max_length=100)
    status: Literal["provided", "not_provided"]
    text: str = Field(default="", max_length=12000)

    @model_validator(mode="after")
    def check_status(self):
        if self.status == "provided" and not self.text.strip():
            raise ValueError("Provided documents must include text")
        if self.status == "not_provided" and self.text.strip():
            raise ValueError("A document marked not_provided cannot contain text")
        return self


class FilingMetadata(Contract):
    schema_version: Literal["1.0"]
    scenario_id: Identifier
    insurer: str = Field(min_length=1, max_length=200)
    synthetic: Literal[True]
    state: Literal["CT"]
    line_of_business: Literal["Personal Auto"]
    effective_date: date
    premium_basis: Literal["modeled_annual_same_portfolio", "unknown"]
    claimed_overall_change_pct: Number | None = None
    claimed_overall_basis: Basis
    documents: list[Document] = Field(max_length=12)

    @model_validator(mode="after")
    def unique_documents(self):
        ids = [doc.document_id for doc in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("Document IDs must be unique")
        return self


class Filing(Contract):
    metadata: FilingMetadata
    rows: list[RateRow] = Field(min_length=1, max_length=5000)
    source_rows: list[SourceRow]
    narrative: str = Field(max_length=20000)
    file_sha256: dict[str, str]

    @model_validator(mode="after")
    def matching_sources(self):
        if len(self.rows) != len(self.source_rows):
            raise ValueError("Every row needs one source reference")
        ids = [row.segment_id for row in self.rows]
        if len(set(ids)) != len(ids):
            raise ValueError("Segment IDs must be unique")
        if [ref.evidence_id for ref in self.source_rows] != [f"row:{i}" for i in ids]:
            raise ValueError("Source references must match segment IDs in order")
        return self


class CalculationConfig(Contract):
    change_tolerance_pp: NonnegativeNumber = Decimal("0.01")
    premium_tolerance_usd: NonnegativeNumber = Decimal("0.01")
    large_change_threshold_pct: NonnegativeNumber = Decimal("15")


class Evidence(Contract):
    evidence_id: str
    kind: Literal["source_row", "source_metadata", "calculation"]
    source_file: str | None = None
    row_number: int | None = None
    sheet: str | None = None
    field: str | None = None
    formula: str | None = None
    input_refs: list[str] = Field(default_factory=list)
    values: dict[str, str | None] = Field(default_factory=dict)


class RowCalculation(Contract):
    segment_id: str
    current_modeled_rate: Decimal
    proposed_modeled_rate: Decimal
    absolute_rate_change: Decimal
    rate_change_pct: Decimal
    evidence_id: str


class Metric(Contract):
    metric_id: str
    category: Literal["rate_level", "premium_impact", "premium_total"]
    value: Decimal | None
    unit: Literal["percent", "USD"]
    status: Literal["available", "unavailable"]
    reason: str | None = None
    evidence_id: str


class Finding(Contract):
    finding_id: str
    code: str
    severity: Literal["high", "medium", "low"]
    affected: str
    message: str
    evidence_refs: list[str]
    reported_value: Decimal | None = None
    calculated_value: Decimal | None = None
    difference: Decimal | None = None
    unit: str | None = None
    recommended_action: str
    detection: Literal["deterministic"] = "deterministic"
    basis: Literal["numerical_reconciliation", "data_quality", "general_review_heuristic"]


class AnalysisResult(Contract):
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str
    state: Literal["CT"] = "CT"
    line_of_business: Literal["Personal Auto"] = "Personal Auto"
    regulatory_checks: Literal["not_implemented"] = "not_implemented"
    config: CalculationConfig
    source_file_sha256: dict[str, str]
    rows: list[RowCalculation]
    metrics: dict[str, Metric]
    findings: list[Finding]
    evidence: dict[str, Evidence]
