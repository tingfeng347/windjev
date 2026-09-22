from collections.abc import Mapping
from typing import Any

import pytest

from windjev import (
    DecisionResponse,
    EvaluationSet,
    IssueSubject,
    Judgment,
    TriageProfile,
    async_evaluate,
)


class EvaluationProvider:
    async def decide(
        self, *, state: Mapping[str, Any], questions: Mapping[str, Any], model: str
    ) -> DecisionResponse:
        is_bug = state["issue"]["title"] == "Bug"
        return DecisionResponse(
            judgments={
                "type": Judgment(
                    value="bug" if is_bug else "feature",
                    confidence=0.95,
                ),
                "area": Judgment(value="api", confidence=0.90),
                "priority": Judgment(
                    value="high",
                    confidence=0.85 if is_bug else 0.50,
                ),
                "route": Judgment(value="backend", confidence=0.90),
            },
            provider="test",
            model="jev-1.13.0",
            usage={"input_tokens": 10},
            timing={"elapsed_ms": 5},
        )


class EvaluationIssues:
    async def fetch_issue(
        self, repository: str, issue_number: int
    ) -> tuple[IssueSubject, list[str]]:
        return (
            IssueSubject(
                number=issue_number,
                title="Bug" if issue_number == 1 else "Feature",
                repository=repository,
            ),
            [],
        )


@pytest.mark.asyncio
async def test_evaluation_reports_quality_and_automatic_coverage() -> None:
    profile = TriageProfile.model_validate(
        {
            "version": 1,
            "mode": "observe",
            "model": "jev-latest",
            "areas": {"api": "Public API"},
            "routes": {"backend": "Backend maintainers"},
            "labels": {
                "type": {"bug": "type: bug", "feature": "type: feature"},
                "area": {"api": "area: api"},
                "priority": {"high": "priority: high", "low": "priority: low"},
                "route": {"backend": "route: backend"},
                "review": "needs-human-review",
            },
        }
    )
    evaluation = EvaluationSet.model_validate(
        {
            "version": 1,
            "repository": "acme/shop",
            "cases": [
                {
                    "issue": 1,
                    "expected": {
                        "type": "bug",
                        "area": "api",
                        "priority": "high",
                        "route": "backend",
                    },
                },
                {
                    "issue": 2,
                    "expected": {
                        "type": "bug",
                        "area": "api",
                        "priority": "low",
                        "route": "backend",
                    },
                },
            ],
        }
    )

    report = await async_evaluate(
        evaluation,
        profile,
        EvaluationProvider(),
        EvaluationIssues(),
    )

    assert report.case_count == 2
    assert report.accuracy == {
        "type": 0.5,
        "area": 1.0,
        "priority": 0.5,
        "route": 1.0,
    }
    assert report.automatic_coverage == 0.5
    assert report.automatic_error_rate == 0.0
    assert report.review_rate == 0.5
    assert report.warning == "Fewer than 30 representative cases"


@pytest.mark.asyncio
async def test_failed_evaluation_cases_count_as_human_review() -> None:
    class BrokenProvider:
        async def decide(self, **kwargs: Any) -> DecisionResponse:
            raise RuntimeError("provider unavailable")

    profile = TriageProfile.model_validate(
        {
            "version": 1,
            "mode": "observe",
            "model": "jev-latest",
            "areas": {"api": "Public API"},
            "routes": {"backend": "Backend maintainers"},
            "labels": {
                "type": {"bug": "type: bug"},
                "area": {"api": "area: api"},
                "priority": {"high": "priority: high"},
                "route": {"backend": "route: backend"},
                "review": "needs-human-review",
            },
        }
    )
    evaluation = EvaluationSet.model_validate(
        {
            "version": 1,
            "repository": "acme/shop",
            "cases": [
                {
                    "issue": 1,
                    "expected": {
                        "type": "bug",
                        "area": "api",
                        "priority": "high",
                        "route": "backend",
                    },
                }
            ],
        }
    )

    report = await async_evaluate(
        evaluation,
        profile,
        BrokenProvider(),
        EvaluationIssues(),
    )

    assert report.failed_cases == 1
    assert report.automatic_coverage == 0.0
    assert report.review_rate == 1.0
