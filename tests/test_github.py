import httpx
import pytest
import respx

from windjev import GitHubClient


@pytest.mark.asyncio
@respx.mock
async def test_github_applies_the_label_plan_in_one_atomic_update() -> None:
    route = respx.patch("https://api.github.com/repos/acme/shop/issues/42").mock(
        return_value=httpx.Response(200, json={"number": 42})
    )
    async with httpx.AsyncClient() as http_client:
        github = GitHubClient(token="secret", http_client=http_client)

        await github.apply_labels(
            repository="acme/shop",
            issue_number=42,
            existing_labels=["type: feature", "customer-visible"],
            labels_to_add=["type: bug", "priority: high"],
            labels_to_remove=["type: feature"],
        )

    assert route.call_count == 1
    assert route.calls[0].request.headers["authorization"] == "Bearer secret"
    assert route.calls[0].request.content == (
        b'{"labels":["customer-visible","type: bug","priority: high"]}'
    )


@pytest.mark.asyncio
@respx.mock
async def test_github_fetches_only_the_issue_triage_subject_and_labels() -> None:
    respx.get("https://api.github.com/repos/acme/shop/issues/42").mock(
        return_value=httpx.Response(
            200,
            json={
                "number": 42,
                "title": "Checkout fails",
                "body": None,
                "labels": [{"name": "customer-visible"}],
                "user": {"login": "untrusted-author"},
                "comments": 3,
            },
        )
    )
    respx.get("https://api.github.com/repos/acme/shop").mock(
        return_value=httpx.Response(
            200,
            json={"full_name": "acme/shop", "description": "Storefront API"},
        )
    )
    async with httpx.AsyncClient() as http_client:
        github = GitHubClient(token="secret", http_client=http_client)

        issue, labels = await github.fetch_issue("acme/shop", 42)

    assert issue.model_dump() == {
        "number": 42,
        "title": "Checkout fails",
        "body": "",
        "repository": "acme/shop",
        "repository_description": "Storefront API",
    }
    assert labels == ["customer-visible"]
