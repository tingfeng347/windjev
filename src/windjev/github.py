from __future__ import annotations

import httpx

from .errors import GitHubError
from .issue_triage import IssueSubject


class GitHubClient:
    def __init__(
        self,
        *,
        token: str,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.github.com",
    ) -> None:
        self._token = token
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def fetch_issue(
        self, repository: str, issue_number: int
    ) -> tuple[IssueSubject, list[str]]:
        try:
            issue_response = await self._http_client.get(
                f"{self._base_url}/repos/{repository}/issues/{issue_number}",
                headers=self._headers,
            )
            issue_response.raise_for_status()
            repository_response = await self._http_client.get(
                f"{self._base_url}/repos/{repository}",
                headers=self._headers,
            )
            repository_response.raise_for_status()
        except httpx.HTTPError as error:
            raise GitHubError("GitHub issue could not be read") from error
        issue_data = issue_response.json()
        repository_data = repository_response.json()
        labels = [
            label["name"]
            for label in issue_data.get("labels", [])
            if isinstance(label, dict) and isinstance(label.get("name"), str)
        ]
        return (
            IssueSubject(
                number=issue_data["number"],
                title=issue_data["title"],
                body=issue_data.get("body") or "",
                repository=repository_data["full_name"],
                repository_description=repository_data.get("description") or "",
            ),
            labels,
        )

    async def apply_labels(
        self,
        *,
        repository: str,
        issue_number: int,
        existing_labels: list[str],
        labels_to_add: list[str],
        labels_to_remove: list[str],
    ) -> None:
        removed = set(labels_to_remove)
        final_labels = [label for label in existing_labels if label not in removed]
        final_labels.extend(
            label for label in labels_to_add if label not in final_labels
        )
        try:
            response = await self._http_client.patch(
                f"{self._base_url}/repos/{repository}/issues/{issue_number}",
                headers=self._headers,
                json={"labels": final_labels},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise GitHubError("GitHub labels could not be updated") from error
