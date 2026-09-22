from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

import yaml
from pydantic import BaseModel

from .decision import DecisionProvider
from .issue_triage import IssueSubject, TriageProfile, async_triage_many

JUDGMENT_NAMES = ("type", "area", "priority", "route")


class ExpectedJudgments(BaseModel):
    type: str
    area: str
    priority: str
    route: str


class EvaluationCase(BaseModel):
    issue: int
    expected: ExpectedJudgments


class EvaluationSet(BaseModel):
    version: Literal[1]
    repository: str
    cases: list[EvaluationCase]


class EvaluationReport(BaseModel):
    schema_version: Literal[1] = 1
    case_count: int
    failed_cases: int
    accuracy: dict[str, float]
    automatic_coverage: float
    automatic_error_rate: float | None
    review_rate: float
    usage: dict[str, int | float]
    timing: dict[str, int | float]
    warning: str | None = None


class IssueSource(Protocol):
    async def fetch_issue(
        self, repository: str, issue_number: int
    ) -> tuple[IssueSubject, list[str]]: ...


def load_evaluation_set(path: str | Path) -> EvaluationSet:
    with Path(path).open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    return EvaluationSet.model_validate(data)


async def async_evaluate(
    evaluation: EvaluationSet,
    profile: TriageProfile,
    provider: DecisionProvider,
    issues: IssueSource,
    *,
    concurrency: int = 4,
) -> EvaluationReport:
    subjects = [
        (await issues.fetch_issue(evaluation.repository, case.issue))[0]
        for case in evaluation.cases
    ]
    items = await async_triage_many(
        subjects,
        profile,
        provider,
        concurrency=concurrency,
    )
    successful = [
        (case, item.result)
        for case, item in zip(evaluation.cases, items, strict=True)
        if item.result is not None
    ]
    correct = {name: 0 for name in JUDGMENT_NAMES}
    automatic_count = 0
    automatic_errors = 0
    usage: dict[str, int | float] = {}
    elapsed_ms = 0.0

    for case, result in successful:
        assert result is not None
        case_is_correct = True
        for name in JUDGMENT_NAMES:
            matches = str(result.judgments[name].value) == getattr(case.expected, name)
            correct[name] += int(matches)
            case_is_correct = case_is_correct and matches
        if not result.needs_review:
            automatic_count += 1
            automatic_errors += int(not case_is_correct)
        for key, value in result.usage.items():
            usage[key] = usage.get(key, 0) + value
        elapsed_ms += float(result.timing.get("elapsed_ms", 0))

    denominator = len(successful)
    case_count = len(evaluation.cases)
    return EvaluationReport(
        case_count=case_count,
        failed_cases=case_count - denominator,
        accuracy={
            name: correct[name] / denominator if denominator else 0.0
            for name in JUDGMENT_NAMES
        },
        automatic_coverage=automatic_count / case_count if case_count else 0.0,
        automatic_error_rate=(
            automatic_errors / automatic_count if automatic_count else None
        ),
        review_rate=(case_count - automatic_count) / case_count if case_count else 0.0,
        usage=usage,
        timing={"elapsed_ms": elapsed_ms},
        warning="Fewer than 30 representative cases" if case_count < 30 else None,
    )
