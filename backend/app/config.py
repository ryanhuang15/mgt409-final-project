"""Select one dotenv file without depending on the terminal's directory."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ReviewLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_model_requests: int = Field(default=12, ge=1, le=20)
    max_requests_per_agent: int = Field(default=6, ge=1, le=10)
    max_tool_calls_per_agent: int = Field(default=16, ge=1, le=24)
    max_output_tokens: int = Field(default=3600, ge=64, le=4000)
    max_request_bytes: int = Field(default=80000, ge=2000, le=160000)
    max_reported_tokens: int = Field(default=80000, ge=1000, le=160000)
    max_retries: int = Field(default=1, ge=0, le=2)
    retry_delay_seconds: float = Field(default=0.5, ge=0, le=3)
    request_timeout_seconds: float = Field(default=45, gt=0, le=60)
    review_timeout_seconds: float = Field(default=180, gt=0, le=300)
    max_narrative_chars: int = Field(default=20000, ge=1, le=20000)
    max_document_chars: int = Field(default=12000, ge=1, le=12000)
    max_tool_output_bytes: int = Field(default=24000, ge=1000, le=32000)


@dataclass(frozen=True)
class Settings:
    project_root: Path
    env_file: Path | None
    openai_api_key: str | None = field(repr=False)
    model: str = "gpt-6-luna"
    reasoning_effort: str = "none"
    limits: ReviewLimits = field(default_factory=ReviewLimits)

    @property
    def api_key_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())


def load_settings(project_root: Path | None = None) -> Settings:
    """Local file first; parent only when local is absent; process env wins.

    Reading rather than mutating os.environ makes repeated tests independent.
    A blank/incomplete local file does not trigger merging with the parent.
    Keys are intentionally excluded from repr and never returned by the API.
    """
    root = (project_root or PROJECT_ROOT).resolve()
    local = root / ".env"
    parent = root.parent / ".env"
    selected = local if local.is_file() else parent if parent.is_file() else None
    values = dotenv_values(selected, interpolate=False) if selected else {}
    key = os.environ.get("OPENAI_API_KEY", values.get("OPENAI_API_KEY"))
    limit_values = {}
    for name in ReviewLimits.model_fields:
        variable = "REVIEW_" + name.upper()
        value = os.environ.get(variable, values.get(variable))
        if value is not None:
            limit_values[name] = value
    return Settings(root, selected, key, limits=ReviewLimits.model_validate(limit_values))
