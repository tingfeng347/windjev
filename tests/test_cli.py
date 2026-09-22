import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from typer.testing import CliRunner

from windjev import (
    DecisionResponse,
    GitHubError,
    IssueSubject,
    Judgment,
    ProviderError,
    load_profile,
)
from windjev.cli import Runtime, app

runner = CliRunner()

PROFILE_TEXT = """
version: 1
mode: observe
model: jev-latest
areas:
  api: Public API
routes:
  backend: Backend maintainers
labels:
  type:
    bug: "type: bug"
  area:
    api: "area: api"
  priority:
    high: "priority: high"
  route:
    backend: "route: backend"
  review: needs-human-review
""".lstrip()


@dataclass
class ExternalProvider:
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
            provider="external-test",
            model="jev-1.13.0",
        )


class ExternalGitHub:
    async def fetch_issue(
        self, repository: str, issue_number: int
    ) -> tuple[IssueSubject, list[str]]:
        return (
            IssueSubject(
                number=issue_number,
                title="Checkout fails",
                repository=repository,
            ),
            [],
        )

    async def apply_labels(self, **kwargs: Any) -> None:
        raise AssertionError("Observe Mode must not write labels")


class FailingProvider:
    async def decide(self, **kwargs: Any) -> DecisionResponse:
        raise ProviderError("provider unavailable")


class FailingGitHub(ExternalGitHub):
    async def fetch_issue(
        self, repository: str, issue_number: int
    ) -> tuple[IssueSubject, list[str]]:
        raise GitHubError("github unavailable")


def test_config_validate_json_is_a_single_machine_document(tmp_path) -> None:
    profile = tmp_path / ".windjev.yml"
    profile.write_text(
        """
version: 1
mode: observe
model: jev-latest
areas:
  api: Public API
routes:
  backend: Backend maintainers
labels:
  type:
    bug: "type: bug"
  area:
    api: "area: api"
  priority:
    high: "priority: high"
  route:
    backend: "route: backend"
  review: needs-human-review
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["config", "validate", "--config", str(profile), "--json"]
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "schema_version": 1,
        "status": "valid",
        "mode": "observe",
        "model": "jev-latest",
    }
    assert result.stdout.count("\n") == 1


def test_config_validate_reports_invalid_input_on_stderr(tmp_path) -> None:
    profile = tmp_path / ".windjev.yml"
    profile.write_text(
        "version: 1\nmode: apply\nmodel: jev-latest\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["config", "validate", "--config", str(profile), "--json"]
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Invalid WindJev profile" in result.stderr


def test_init_creates_an_observe_profile_and_github_workflow(tmp_path) -> None:
    result = runner.invoke(app, ["init", "--directory", str(tmp_path)])

    assert result.exit_code == 0
    profile = load_profile(tmp_path / ".windjev.yml")
    assert profile.mode == "observe"
    assert profile.model == "jev-latest"
    workflow = tmp_path / ".github" / "workflows" / "windjev.yml"
    assert workflow.is_file()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "issues: read" in workflow_text
    assert "uses: actions/checkout@v4" in workflow_text
    assert "uses: tingfeng347/windjev@v1" in workflow_text
    assert "ref: ${{ github.event.repository.default_branch }}" in workflow_text


def test_local_triage_json_runs_the_complete_decision_workflow(tmp_path) -> None:
    profile = tmp_path / ".windjev.yml"
    profile.write_text(
        """
version: 1
mode: observe
model: jev-latest
areas:
  api: Public API
routes:
  backend: Backend maintainers
labels:
  type:
    bug: "type: bug"
  area:
    api: "area: api"
  priority:
    high: "priority: high"
  route:
    backend: "route: backend"
  review: needs-human-review
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "triage",
            "--config",
            str(profile),
            "--repository",
            "acme/shop",
            "--title",
            "Checkout fails",
            "--body",
            "POST /orders returns 500",
            "--json",
        ],
        obj=Runtime(provider=ExternalProvider()),
    )

    assert result.exit_code == 0
    document = json.loads(result.stdout)
    assert document["schema_version"] == 1
    assert document["status"] == "observed"
    assert document["needs_review"] is False
    assert document["judgments"]["priority"]["value"] == "high"
    assert document["provider"] == {
        "name": "external-test",
        "model": "jev-1.13.0",
    }


def test_github_triage_json_uses_the_issue_number(tmp_path) -> None:
    profile = tmp_path / ".windjev.yml"
    profile.write_text(PROFILE_TEXT, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "triage",
            "--config",
            str(profile),
            "--repository",
            "acme/shop",
            "--issue-number",
            "42",
            "--json",
        ],
        obj=Runtime(provider=ExternalProvider(), github=ExternalGitHub()),
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "observed"


def test_eval_json_reports_historical_issue_quality(tmp_path) -> None:
    profile = tmp_path / ".windjev.yml"
    profile.write_text(PROFILE_TEXT, encoding="utf-8")
    evaluation = tmp_path / "eval.yml"
    evaluation.write_text(
        """
version: 1
repository: acme/shop
cases:
  - issue: 42
    expected:
      type: bug
      area: api
      priority: high
      route: backend
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "eval",
            "--config",
            str(profile),
            "--evaluation",
            str(evaluation),
            "--json",
        ],
        obj=Runtime(provider=ExternalProvider(), github=ExternalGitHub()),
    )

    assert result.exit_code == 0
    document = json.loads(result.stdout)
    assert document["case_count"] == 1
    assert document["accuracy"] == {
        "type": 1.0,
        "area": 1.0,
        "priority": 1.0,
        "route": 1.0,
    }
    assert document["warning"] == "Fewer than 30 representative cases"


def test_triage_uses_stable_external_failure_exit_codes(tmp_path) -> None:
    profile = tmp_path / ".windjev.yml"
    profile.write_text(PROFILE_TEXT, encoding="utf-8")

    provider_failure = runner.invoke(
        app,
        [
            "triage",
            "--config",
            str(profile),
            "--title",
            "Failure",
            "--json",
        ],
        obj=Runtime(provider=FailingProvider()),
    )
    github_failure = runner.invoke(
        app,
        [
            "triage",
            "--config",
            str(profile),
            "--repository",
            "acme/shop",
            "--issue-number",
            "42",
            "--json",
        ],
        obj=Runtime(provider=ExternalProvider(), github=FailingGitHub()),
    )

    assert provider_failure.exit_code == 3
    assert provider_failure.stdout == ""
    assert "provider unavailable" in provider_failure.stderr
    assert github_failure.exit_code == 4
    assert github_failure.stdout == ""
    assert "github unavailable" in github_failure.stderr
