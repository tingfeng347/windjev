from __future__ import annotations

from typing import Any, Protocol

from .decision import DecisionProvider
from .errors import ProviderError
from .issue_triage import TriageProfile, TriageResult, async_triage


class GitHubIssuePort(Protocol):
    async def fetch_issue(
        self, repository: str, issue_number: int
    ) -> tuple[Any, list[str]]: ...

    async def apply_labels(
        self,
        *,
        repository: str,
        issue_number: int,
        existing_labels: list[str],
        labels_to_add: list[str],
        labels_to_remove: list[str],
    ) -> None: ...


async def async_triage_github_issue(
    *,
    repository: str,
    issue_number: int,
    profile: TriageProfile,
    provider: DecisionProvider,
    github: GitHubIssuePort,
) -> TriageResult:
    issue, existing_labels = await github.fetch_issue(repository, issue_number)
    try:
        result = await async_triage(
            issue,
            profile,
            provider,
            existing_labels=existing_labels,
        )
    except ProviderError:
        if profile.mode == "apply" and profile.labels.review not in existing_labels:
            await github.apply_labels(
                repository=repository,
                issue_number=issue_number,
                existing_labels=existing_labels,
                labels_to_add=[profile.labels.review],
                labels_to_remove=[],
            )
        raise
    if profile.mode == "apply" and (result.labels_to_add or result.labels_to_remove):
        await github.apply_labels(
            repository=repository,
            issue_number=issue_number,
            existing_labels=existing_labels,
            labels_to_add=result.labels_to_add,
            labels_to_remove=result.labels_to_remove,
        )
    return result
