from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest

from windjev import (
    DecisionResponse,
    IssueSubject,
    Judgment,
    TriageProfile,
    async_triage,
    async_triage_many,
    triage,
)


@dataclass
class StubProvider:
    judgments: Mapping[str, Judgment]

    async def decide(
        self, *, state: Mapping[str, Any], questions: Mapping[str, Any], model: str
    ) -> DecisionResponse:
        return DecisionResponse(
            judgments=dict(self.judgments),
            provider="stub",
            model=model,
        )


@pytest.mark.asyncio
async def test_observe_mode_returns_complete_triage_without_label_changes() -> None:
    profile = TriageProfile.model_validate(
        {
            "version": 1,
            "mode": "observe",
            "model": "jev-latest",
            "areas": {"api": "Public API and request handling"},
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
    provider = StubProvider(
        {
            "type": Judgment(value="bug", confidence=0.96),
            "area": Judgment(value="api", confidence=0.91),
            "priority": Judgment(value="high", confidence=0.84),
            "route": Judgment(value="backend", confidence=0.89),
        }
    )

    result = await async_triage(
        IssueSubject(
            number=42,
            title="POST /orders returns 500",
            body="The request fails after upgrading.",
            repository="acme/shop",
            repository_description="Storefront API",
        ),
        profile,
        provider,
    )

    assert result.model_dump(mode="json") == {
        "schema_version": 1,
        "status": "observed",
        "judgments": {
            "type": {"value": "bug", "confidence": 0.96, "probabilities": {}},
            "area": {"value": "api", "confidence": 0.91, "probabilities": {}},
            "priority": {"value": "high", "confidence": 0.84, "probabilities": {}},
            "route": {
                "value": "backend",
                "confidence": 0.89,
                "probabilities": {},
            },
        },
        "needs_review": False,
        "labels_to_add": [],
        "labels_to_remove": [],
        "provider": {"name": "stub", "model": "jev-latest"},
        "usage": {},
        "timing": {},
    }


@pytest.mark.asyncio
async def test_apply_mode_builds_an_atomic_idempotent_label_update() -> None:
    profile = TriageProfile.model_validate(
        {
            "version": 1,
            "mode": "apply",
            "model": "jev-1.13.0",
            "areas": {"api": "Public API"},
            "routes": {"backend": "Backend maintainers"},
            "labels": {
                "type": {
                    "bug": "type: bug",
                    "feature": "type: feature",
                    "question": "type: question",
                    "maintenance": "type: maintenance",
                },
                "area": {"api": "area: api"},
                "priority": {
                    "low": "priority: low",
                    "medium": "priority: medium",
                    "high": "priority: high",
                    "critical": "priority: critical",
                },
                "route": {"backend": "route: backend"},
                "review": "needs-human-review",
            },
        }
    )
    provider = StubProvider(
        {
            "type": Judgment(value="bug", confidence=0.96),
            "area": Judgment(value="api", confidence=0.91),
            "priority": Judgment(value="high", confidence=0.84),
            "route": Judgment(value="backend", confidence=0.89),
        }
    )

    result = await async_triage(
        IssueSubject(title="Failure", repository="acme/shop"),
        profile,
        provider,
        existing_labels=[
            "type: feature",
            "area: api",
            "needs-human-review",
            "customer-visible",
        ],
    )

    assert result.status == "applied"
    assert result.needs_review is False
    assert result.labels_to_add == ["type: bug", "priority: high", "route: backend"]
    assert result.labels_to_remove == ["type: feature", "needs-human-review"]


@pytest.mark.asyncio
async def test_low_confidence_requires_review_without_partial_triage() -> None:
    profile = TriageProfile.model_validate(
        {
            "version": 1,
            "mode": "apply",
            "model": "jev-1.13.0",
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
    provider = StubProvider(
        {
            "type": Judgment(value="bug", confidence=0.96),
            "area": Judgment(value="api", confidence=0.79),
            "priority": Judgment(value="high", confidence=0.84),
            "route": Judgment(value="backend", confidence=0.89),
        }
    )

    result = await async_triage(
        IssueSubject(title="Failure", repository="acme/shop"),
        profile,
        provider,
        existing_labels=["type: feature", "customer-visible"],
    )

    assert result.status == "review_required"
    assert result.needs_review is True
    assert result.labels_to_add == ["needs-human-review"]
    assert result.labels_to_remove == []


def test_sync_triage_uses_the_same_workflow_result() -> None:
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
    provider = StubProvider(
        {
            "type": Judgment(value="bug", confidence=0.96),
            "area": Judgment(value="api", confidence=0.91),
            "priority": Judgment(value="high", confidence=0.84),
            "route": Judgment(value="backend", confidence=0.89),
        }
    )

    result = triage(
        IssueSubject(title="Failure", repository="acme/shop"),
        profile,
        provider,
    )

    assert result.status == "observed"
    assert result.judgments["type"].value == "bug"


@pytest.mark.asyncio
async def test_batch_triage_preserves_order_and_isolates_failures() -> None:
    class SelectiveProvider(StubProvider):
        async def decide(
            self, *, state: Mapping[str, Any], questions: Mapping[str, Any], model: str
        ) -> DecisionResponse:
            if state["issue"]["title"] == "bad":
                raise RuntimeError("provider unavailable")
            return await super().decide(state=state, questions=questions, model=model)

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
    provider = SelectiveProvider(
        {
            "type": Judgment(value="bug", confidence=0.96),
            "area": Judgment(value="api", confidence=0.91),
            "priority": Judgment(value="high", confidence=0.84),
            "route": Judgment(value="backend", confidence=0.89),
        }
    )

    results = await async_triage_many(
        [
            IssueSubject(number=1, title="first", repository="acme/shop"),
            IssueSubject(number=2, title="bad", repository="acme/shop"),
            IssueSubject(number=3, title="third", repository="acme/shop"),
        ],
        profile,
        provider,
        concurrency=2,
    )

    assert [item.issue_number for item in results] == [1, 2, 3]
    assert [item.result is not None for item in results] == [True, False, True]
    assert results[1].error == "provider unavailable"


@pytest.mark.asyncio
async def test_invalid_provider_response_requires_review_instead_of_applying() -> None:
    profile = TriageProfile.model_validate(
        {
            "version": 1,
            "mode": "apply",
            "model": "jev-1.13.0",
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
    provider = StubProvider(
        {
            "type": Judgment(value="bug", confidence=0.96),
            "area": Judgment(value="invented", confidence=0.99),
            "priority": Judgment(value="high", confidence=0.84),
        }
    )

    result = await async_triage(
        IssueSubject(title="Failure", repository="acme/shop"),
        profile,
        provider,
        existing_labels=["type: feature"],
    )

    assert result.status == "review_required"
    assert result.needs_review is True
    assert result.labels_to_add == ["needs-human-review"]
    assert result.labels_to_remove == []
