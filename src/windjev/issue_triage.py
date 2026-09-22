from __future__ import annotations

import asyncio
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .decision import (
    ChoiceQuestion,
    DecisionProvider,
    Judgment,
    Question,
    ScoreQuestion,
)


class IssueSubject(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int | None = None
    title: str
    body: str = ""
    repository: str
    repository_description: str = ""


class ConfidenceGates(BaseModel):
    type: float = Field(default=0.80, ge=0, le=1)
    area: float = Field(default=0.80, ge=0, le=1)
    priority: float = Field(default=0.75, ge=0, le=1)
    route: float = Field(default=0.80, ge=0, le=1)


class LabelMappings(BaseModel):
    type: dict[str, str]
    area: dict[str, str]
    priority: dict[str, str]
    route: dict[str, str]
    review: str


class TriageProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    mode: Literal["observe", "apply"]
    model: str
    areas: dict[str, str]
    routes: dict[str, str]
    confidence: ConfidenceGates = Field(default_factory=ConfidenceGates)
    labels: LabelMappings

    @model_validator(mode="after")
    def require_pinned_model_in_apply_mode(self) -> TriageProfile:
        if (
            self.mode == "apply"
            and re.fullmatch(r"jev-\d+\.\d+\.\d+", self.model) is None
        ):
            raise ValueError("Apply Mode requires an immutable model version")
        managed_labels = [
            label
            for name in ("type", "area", "priority", "route")
            for label in getattr(self.labels, name).values()
        ] + [self.labels.review]
        if len(managed_labels) != len(set(managed_labels)):
            raise ValueError("Managed Labels must be unique")
        return self


class ProviderDetails(BaseModel):
    name: str
    model: str


class TriageResult(BaseModel):
    schema_version: Literal[1] = 1
    status: Literal["observed", "applied", "review_required"]
    judgments: dict[str, Judgment]
    needs_review: bool
    labels_to_add: list[str]
    labels_to_remove: list[str]
    provider: ProviderDetails
    usage: dict[str, int | float] = Field(default_factory=dict)
    timing: dict[str, int | float] = Field(default_factory=dict)


class BatchTriageItem(BaseModel):
    issue_number: int | None
    result: TriageResult | None = None
    error: str | None = None


def _questions(profile: TriageProfile) -> dict[str, Question]:
    return {
        "type": ChoiceQuestion(
            instructions="What kind of work does this issue represent?",
            criteria={
                "bug": "Existing behavior is broken or incorrect.",
                "feature": "New or expanded product behavior is requested.",
                "question": "Information or clarification is requested.",
                "maintenance": "Internal upkeep without new product behavior.",
            },
        ),
        "area": ChoiceQuestion(
            instructions="Which project area is primarily affected?",
            criteria=profile.areas,
        ),
        "priority": ScoreQuestion(
            instructions="What attention level does this issue require?",
            levels={
                "low": "Can wait without meaningful impact.",
                "medium": "Normal planned work.",
                "high": "Material impact requiring prompt attention.",
                "critical": "Immediate response is required.",
            },
        ),
        "route": ChoiceQuestion(
            instructions="Which team should take the next action?",
            criteria=profile.routes,
        ),
    }


async def async_triage(
    issue: IssueSubject,
    profile: TriageProfile,
    provider: DecisionProvider,
    *,
    existing_labels: list[str] | None = None,
) -> TriageResult:
    response = await provider.decide(
        state={
            "issue": {"title": issue.title, "body": issue.body},
            "repository": {
                "name": issue.repository,
                "description": issue.repository_description,
            },
        },
        questions=_questions(profile),
        model=profile.model,
    )

    existing = set(existing_labels or [])
    gates = profile.confidence.model_dump()
    required = ("type", "area", "priority", "route")
    allowed_values = {name: set(getattr(profile.labels, name)) for name in required}
    needs_review = any(
        name not in response.judgments
        or str(response.judgments[name].value) not in allowed_values[name]
        or response.judgments[name].confidence < gates[name]
        for name in required
    )
    labels_to_add: list[str] = []
    labels_to_remove: list[str] = []
    status: Literal["observed", "applied", "review_required"] = "observed"

    if profile.mode == "apply" and needs_review:
        status = "review_required"
        if profile.labels.review not in existing:
            labels_to_add.append(profile.labels.review)
    elif profile.mode == "apply":
        status = "applied"
        selected = {
            name: getattr(profile.labels, name)[str(response.judgments[name].value)]
            for name in required
        }
        selected_labels = set(selected.values())
        labels_to_add = [
            selected[name] for name in required if selected[name] not in existing
        ]
        managed_labels = {
            label
            for name in ("type", "area", "priority", "route")
            for label in getattr(profile.labels, name).values()
        }
        labels_to_remove = [
            label
            for label in existing_labels or []
            if (label in managed_labels and label not in selected_labels)
            or label == profile.labels.review
        ]

    return TriageResult(
        status=status,
        judgments=response.judgments,
        needs_review=needs_review,
        labels_to_add=labels_to_add,
        labels_to_remove=labels_to_remove,
        provider=ProviderDetails(name=response.provider, model=response.model),
        usage=response.usage,
        timing=response.timing,
    )


def triage(
    issue: IssueSubject,
    profile: TriageProfile,
    provider: DecisionProvider,
    *,
    existing_labels: list[str] | None = None,
) -> TriageResult:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            async_triage(
                issue,
                profile,
                provider,
                existing_labels=existing_labels,
            )
        )
    raise RuntimeError("triage() cannot run inside an event loop; use async_triage()")


async def async_triage_many(
    issues: list[IssueSubject],
    profile: TriageProfile,
    provider: DecisionProvider,
    *,
    concurrency: int = 4,
) -> list[BatchTriageItem]:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    semaphore = asyncio.Semaphore(concurrency)

    async def evaluate(issue: IssueSubject) -> BatchTriageItem:
        async with semaphore:
            try:
                result = await async_triage(issue, profile, provider)
            except Exception as error:  # noqa: BLE001 - each batch item isolates failures.
                return BatchTriageItem(
                    issue_number=issue.number,
                    error=str(error),
                )
            return BatchTriageItem(issue_number=issue.number, result=result)

    return list(await asyncio.gather(*(evaluate(issue) for issue in issues)))
