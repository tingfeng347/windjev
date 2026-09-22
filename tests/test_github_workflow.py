from collections.abc import Mapping
from typing import Any

import pytest

from windjev import (
    DecisionResponse,
    IssueSubject,
    Judgment,
    ProviderError,
    TriageProfile,
    async_triage_github_issue,
)


class WorkflowProvider:
    async def decide(
        self, *, state: Mapping[str, Any], questions: Mapping[str, Any], model: str
    ) -> DecisionResponse:
        return DecisionResponse(
            judgments={
                "type": Judgment(value="bug", confidence=0.95),
                "area": Judgment(value="api", confidence=0.90),
                "priority": Judgment(value="high", confidence=0.85),
                "route": Judgment(value="backend", confidence=0.90),
            },
            provider="test",
            model=model,
        )


class WorkflowGitHub:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    async def fetch_issue(
        self, repository: str, issue_number: int
    ) -> tuple[IssueSubject, list[str]]:
        return (
            IssueSubject(
                number=issue_number,
                title="Broken checkout",
                repository=repository,
            ),
            ["type: feature", "customer-visible"],
        )

    async def apply_labels(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


class BrokenWorkflowProvider:
    async def decide(self, **kwargs: Any) -> DecisionResponse:
        raise ProviderError("provider unavailable")


def profile(mode: str) -> TriageProfile:
    return TriageProfile.model_validate(
        {
            "version": 1,
            "mode": mode,
            "model": "jev-1.13.0" if mode == "apply" else "jev-latest",
            "areas": {"api": "Public API"},
            "routes": {"backend": "Backend maintainers"},
            "labels": {
                "type": {"bug": "type: bug", "feature": "type: feature"},
                "area": {"api": "area: api"},
                "priority": {"high": "priority: high"},
                "route": {"backend": "route: backend"},
                "review": "needs-human-review",
            },
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode, update_count", [("observe", 0), ("apply", 1)])
async def test_github_workflow_writes_labels_only_in_apply_mode(
    mode: str, update_count: int
) -> None:
    github = WorkflowGitHub()

    result = await async_triage_github_issue(
        repository="acme/shop",
        issue_number=42,
        profile=profile(mode),
        provider=WorkflowProvider(),
        github=github,
    )

    assert len(github.updates) == update_count
    assert result.status == ("observed" if mode == "observe" else "applied")
    if github.updates:
        assert github.updates[0]["labels_to_add"] == [
            "type: bug",
            "area: api",
            "priority: high",
            "route: backend",
        ]
        assert github.updates[0]["labels_to_remove"] == ["type: feature"]


@pytest.mark.asyncio
async def test_provider_failure_preserves_labels_and_marks_human_review() -> None:
    github = WorkflowGitHub()

    with pytest.raises(ProviderError, match="provider unavailable"):
        await async_triage_github_issue(
            repository="acme/shop",
            issue_number=42,
            profile=profile("apply"),
            provider=BrokenWorkflowProvider(),
            github=github,
        )

    assert github.updates == [
        {
            "repository": "acme/shop",
            "issue_number": 42,
            "existing_labels": ["type: feature", "customer-visible"],
            "labels_to_add": ["needs-human-review"],
            "labels_to_remove": [],
        }
    ]
