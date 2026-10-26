"""Model-output contracts contain references, never authoritative numeric values."""

from typing import Annotated, Literal

from pydantic import Field

from backend.app.schemas import Contract

Ref = Annotated[str, Field(min_length=1, max_length=150)]


class NumericReference(Contract):
    key: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,39}$")
    evidence_id: Ref
    field: str = Field(min_length=1, max_length=60)


class SourceQuote(Contract):
    evidence_id: Ref
    quote: str = Field(min_length=8, max_length=500)


class AnalysisNote(Contract):
    title: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=1, max_length=1000)
    recommended_action: str = Field(min_length=1, max_length=400)
    evidence_refs: list[Ref] = Field(min_length=1, max_length=10)
    numeric_references: list[NumericReference] = Field(max_length=8)
    related_deterministic_finding_ids: list[Ref] = Field(max_length=8)


class AIFinding(AnalysisNote):
    category: Literal["missing_documentation", "documentation_contradiction", "unsupported_claim", "suspicious_instruction", "general_review"]
    severity: Literal["high", "medium", "low"]
    affected_segments: list[Ref] = Field(max_length=8)
    affected_documents: list[Ref] = Field(max_length=8)
    evidence_strength: Literal["direct", "inference"]
    source_quotes: list[SourceQuote] = Field(max_length=4)


class AgentOutput(Contract):
    summary: AnalysisNote
    interpretations: list[AnalysisNote] = Field(max_length=6)
    findings: list[AIFinding] = Field(max_length=8)


def output_format():
    return {"type": "json_schema", "json_schema": {
        "name": "filing_agent_review", "strict": True, "schema": AgentOutput.model_json_schema(),
    }}
