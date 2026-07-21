from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="Knowledge document path shown in context")
    section: str = Field(description="Section heading shown in context")
    chunk_id: str = Field(description="Exact chunk identifier shown in context")
    quote: str = Field(
        min_length=1,
        max_length=400,
        description="Short verbatim quote copied from the retrieved chunk",
    )


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str = Field(pattern=r"^ISSUE-\d{3}$")
    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    category: Literal[
        "correctness",
        "security",
        "reliability",
        "maintainability",
        "style",
        "architecture",
        "performance",
        "testing",
    ]
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    problem: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_line_range(self) -> "ReviewIssue":
        if self.line_end < self.line_start:
            raise ValueError("line_end must be greater than or equal to line_start")
        return self


class ReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    issues: list[ReviewIssue]


class KnowledgeChunk(BaseModel):
    chunk_id: str
    source: str
    section: str
    text: str
    distance: float | None = None


class CitationCheck(BaseModel):
    issue_id: str
    chunk_id: str
    valid: bool
    reason: str


class LocationCheck(BaseModel):
    issue_id: str
    valid: bool
    reason: str


class QualityCheck(BaseModel):
    issue_id: str
    valid: bool
    reason: str


class ReviewRun(BaseModel):
    mode: Literal["baseline", "rag"]
    model: str
    prompt_version: str
    created_at: str
    sample: str
    sample_sha256: str
    retrieval_query: str | None = None
    prompt: str
    raw_response: str
    raw_attempts: list[str]
    review: ReviewPayload
    retrieved_chunks: list[KnowledgeChunk] = Field(default_factory=list)
    citation_checks: list[CitationCheck] = Field(default_factory=list)
    location_checks: list[LocationCheck] = Field(default_factory=list)
    quality_checks: list[QualityCheck] = Field(default_factory=list)
