from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["financial", "industry", "event", "strategy"]
Choice = Literal["left", "right", "tie", "both_bad"]
CATEGORY_LABELS = {"financial": "财务分析", "industry": "产业研究", "event": "事件研判", "strategy": "策略研究"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidence(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=16000)
    source: str = Field(min_length=1, max_length=500)


class Participant(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,64}$")
    name: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=80)
    kind: Literal["agent", "model", "demo"] = "agent"

    @property
    def key(self) -> str:
        return f"{self.id}@{self.version}"


class Answer(StrictModel):
    participant: Participant
    content: str = Field(min_length=20, max_length=40000)
    duration_seconds: float = Field(ge=0, le=7200, allow_inf_nan=False)


class Match(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,80}$")
    category: Category
    question: str = Field(min_length=8, max_length=4000)
    as_of: str = Field(min_length=1, max_length=80)
    evidence: list[Evidence] = Field(max_length=30)
    answers: list[Answer] = Field(min_length=2, max_length=2)
    provenance: Literal["demo", "platform_run"]
    run_id: str | None = None

    @model_validator(mode="after")
    def distinct(self) -> Match:
        if self.answers[0].participant.key == self.answers[1].participant.key:
            raise ValueError("Two different participant versions are required")
        if self.provenance == "platform_run":
            if not self.run_id or any(a.participant.kind == "demo" for a in self.answers):
                raise ValueError("Platform matches require a run and non-demo participants")
        return self


class AssignmentRequest(StrictModel):
    mode: Literal["demo", "live"]
    category: Category | None = None
    question_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class VoteRequest(StrictModel):
    choice: Choice
    reasons: list[Literal["evidence", "reasoning", "numbers", "risk", "clarity"]] = Field(default_factory=list, max_length=5)


class JoinRequest(StrictModel):
    code: str = Field(min_length=10, max_length=200)


class QuestionRequest(StrictModel):
    question: str = Field(min_length=12, max_length=2000)
    category: Category
    consent: Literal[True]


class ReportRequest(StrictModel):
    reason: Literal["identity", "unsupported", "numbers", "other"]
    detail: str = Field(default="", max_length=1000)


class Holding(StrictModel):
    symbol: str = Field(pattern=r"^\d{6}\.(SH|SZ|BJ)$")
    weight: float = Field(gt=0, le=1, allow_inf_nan=False)


class Strategy(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,80}$")
    participant: Participant
    title: str = Field(min_length=4, max_length=120)
    benchmark: str = Field(min_length=2, max_length=80)
    starts_at: datetime
    ends_at: datetime
    holdings: list[Holding] = Field(min_length=1, max_length=100)
    rules: str = Field(min_length=30, max_length=6000)
    source_run_id: str = Field(min_length=1, max_length=80)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("An explicit timezone is required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def valid_portfolio(self) -> Strategy:
        if self.ends_at <= self.starts_at:
            raise ValueError("End must follow start")
        if sum(h.weight for h in self.holdings) > 1.00000001:
            raise ValueError("Weights exceed 100%; no leverage in this track")
        if len({h.symbol for h in self.holdings}) != len(self.holdings):
            raise ValueError("Duplicate security")
        return self
