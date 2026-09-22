from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import httpx
import typer
import yaml
from pydantic import ValidationError

from .decision import DecisionProvider
from .errors import GitHubError, ProviderError
from .evaluation import EvaluationReport, async_evaluate, load_evaluation_set
from .github import GitHubClient
from .issue_triage import IssueSubject, TriageProfile, TriageResult, async_triage
from .profile import load_profile
from .providers import TypeSafeJevProvider
from .workflows import GitHubIssuePort, async_triage_github_issue

app = typer.Typer(help="Confidence-aware decisions for developer workflows.")
config_app = typer.Typer(help="Validate and inspect WindJev configuration.")
app.add_typer(config_app, name="config")


@dataclass
class Runtime:
    provider: DecisionProvider
    github: GitHubIssuePort | None = None


def _runtime(context: typer.Context) -> Runtime:
    if isinstance(context.obj, Runtime):
        return context.obj
    return Runtime(provider=TypeSafeJevProvider())


async def _triage_from_cli(
    *,
    runtime: Runtime,
    profile: TriageProfile,
    repository: str,
    title: str,
    body: str,
    issue_number: int | None,
) -> TriageResult:
    if issue_number is None:
        return await async_triage(
            IssueSubject(title=title, body=body, repository=repository),
            profile,
            runtime.provider,
        )
    if runtime.github is not None:
        return await async_triage_github_issue(
            repository=repository,
            issue_number=issue_number,
            profile=profile,
            provider=runtime.provider,
            github=runtime.github,
        )
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN is required with --issue-number")
    async with httpx.AsyncClient() as http_client:
        github = GitHubClient(token=token, http_client=http_client)
        return await async_triage_github_issue(
            repository=repository,
            issue_number=issue_number,
            profile=profile,
            provider=runtime.provider,
            github=github,
        )


PROFILE_TEMPLATE = """\
version: 1
mode: observe
model: jev-latest
areas:
  general: General project work
routes:
  maintainers: Project maintainers
confidence:
  type: 0.80
  area: 0.80
  priority: 0.75
  route: 0.80
labels:
  type:
    bug: "type: bug"
    feature: "type: feature"
    question: "type: question"
    maintenance: "type: maintenance"
  area:
    general: "area: general"
  priority:
    low: "priority: low"
    medium: "priority: medium"
    high: "priority: high"
    critical: "priority: critical"
  route:
    maintainers: "route: maintainers"
  review: needs-human-review
"""

WORKFLOW_TEMPLATE = """\
name: WindJev Issue Triage

on:
  issues:
    types: [opened]
  workflow_dispatch:
    inputs:
      issue_number:
        description: Issue number to retriage
        required: true
        type: number

permissions:
  contents: read
  issues: read

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.repository.default_branch }}
      - uses: tingfeng347/windjev@v1
        with:
          issue-number: ${{ github.event.issue.number || inputs.issue_number }}
        env:
          TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}
          GITHUB_TOKEN: ${{ github.token }}
"""


@app.command("init")
def initialize(
    directory: Annotated[
        Path,
        typer.Option("--directory", file_okay=False),
    ] = Path("."),
) -> None:
    profile_path = directory / ".windjev.yml"
    workflow_path = directory / ".github" / "workflows" / "windjev.yml"
    existing = [path for path in (profile_path, workflow_path) if path.exists()]
    if existing:
        typer.echo(f"Refusing to overwrite {existing[0]}", err=True)
        raise typer.Exit(code=2)
    directory.mkdir(parents=True, exist_ok=True)
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(PROFILE_TEMPLATE, encoding="utf-8")
    workflow_path.write_text(WORKFLOW_TEMPLATE, encoding="utf-8")
    typer.echo(f"Created {profile_path} and {workflow_path}")


@app.command("triage")
def triage_command(
    context: typer.Context,
    config: Annotated[
        Path,
        typer.Option("--config", exists=True, dir_okay=False, readable=True),
    ] = Path(".windjev.yml"),
    repository: Annotated[str, typer.Option("--repository")] = "local/input",
    title: Annotated[str, typer.Option("--title")] = "",
    body: Annotated[str, typer.Option("--body")] = "",
    issue_number: Annotated[int | None, typer.Option("--issue-number")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        profile = load_profile(config)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as error:
        typer.echo(f"Invalid WindJev profile: {error}", err=True)
        raise typer.Exit(code=2) from error
    try:
        result = asyncio.run(
            _triage_from_cli(
                runtime=_runtime(context),
                profile=profile,
                repository=repository,
                title=title,
                body=body,
                issue_number=issue_number,
            )
        )
    except ProviderError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    except GitHubError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=4) from error
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    if as_json:
        typer.echo(json.dumps(result.model_dump(mode="json"), separators=(",", ":")))
    else:
        typer.echo(
            "\n".join(
                f"{name}: {judgment.value} ({judgment.confidence:.2f})"
                for name, judgment in result.judgments.items()
            )
        )


async def _evaluate_from_cli(
    *,
    runtime: Runtime,
    evaluation_path: Path,
    profile: TriageProfile,
) -> EvaluationReport:
    evaluation = load_evaluation_set(evaluation_path)
    if runtime.github is not None:
        return await async_evaluate(
            evaluation,
            profile,
            runtime.provider,
            runtime.github,
        )
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN is required for evaluation")
    async with httpx.AsyncClient() as http_client:
        github = GitHubClient(token=token, http_client=http_client)
        return await async_evaluate(
            evaluation,
            profile,
            runtime.provider,
            github,
        )


@app.command("eval")
def evaluate_command(
    context: typer.Context,
    config: Annotated[
        Path,
        typer.Option("--config", exists=True, dir_okay=False, readable=True),
    ] = Path(".windjev.yml"),
    evaluation: Annotated[
        Path,
        typer.Option("--evaluation", exists=True, dir_okay=False, readable=True),
    ] = Path(".windjev/eval.yml"),
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        profile = load_profile(config)
        report = asyncio.run(
            _evaluate_from_cli(
                runtime=_runtime(context),
                evaluation_path=evaluation,
                profile=profile,
            )
        )
    except (OSError, yaml.YAMLError, ValidationError, TypeError, ValueError) as error:
        typer.echo(f"Evaluation failed: {error}", err=True)
        raise typer.Exit(code=2) from error
    if as_json:
        typer.echo(json.dumps(report.model_dump(mode="json"), separators=(",", ":")))
    else:
        typer.echo(
            f"Cases: {report.case_count}; automatic coverage: "
            f"{report.automatic_coverage:.1%}; review: {report.review_rate:.1%}"
        )
        if report.warning:
            typer.echo(f"Warning: {report.warning}", err=True)


@config_app.command("validate")
def validate_config(
    config: Annotated[
        Path,
        typer.Option("--config", exists=True, dir_okay=False, readable=True),
    ] = Path(".windjev.yml"),
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        profile = load_profile(config)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as error:
        typer.echo(f"Invalid WindJev profile: {error}", err=True)
        raise typer.Exit(code=2) from error
    result = {
        "schema_version": 1,
        "status": "valid",
        "mode": profile.mode,
        "model": profile.model,
    }
    if as_json:
        typer.echo(json.dumps(result, separators=(",", ":")))
    else:
        typer.echo(f"Valid WindJev profile ({profile.mode}, {profile.model})")


def main() -> None:
    app()
