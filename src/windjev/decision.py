from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ChoiceQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, str]


class ScoreQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["score"] = "score"
    instructions: str
    levels: dict[str, str]


class NoulQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["noul"] = "noul"
    instructions: str
    criteria: str


Question = ChoiceQuestion | ScoreQuestion | NoulQuestion


class Judgment(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str | float | bool
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float] = Field(default_factory=dict)


class DecisionResponse(BaseModel):
    judgments: dict[str, Judgment]
    provider: str
    model: str
    usage: dict[str, int | float] = Field(default_factory=dict)
    timing: dict[str, int | float] = Field(default_factory=dict)


class DecisionProvider(Protocol):
    async def decide(
        self,
        *,
        state: Mapping[str, Any],
        questions: Mapping[str, Question],
        model: str,
    ) -> DecisionResponse: ...
