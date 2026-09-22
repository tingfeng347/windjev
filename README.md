# WindJev

WindJev is a confidence-aware decision foundation for developer workflows. Its MVP triages GitHub Issues with TypeSafe Jev and exposes the same behavior through a Python interface, a CLI, and a GitHub Action.

The MVP is intentionally narrow: it proves the foundation through Issue Triage without prematurely building a workflow DSL, plugin system, hosted service, or generic connector framework.

## What it decides

Each Issue produces four typed judgments:

- `type`: `bug`, `feature`, `question`, or `maintenance`
- `area`: a repository-defined product or code area
- `priority`: `low`, `medium`, `high`, or `critical`
- `route`: a repository-defined team

Each judgment includes confidence and option probabilities. WindJev derives `needs_review` from field-specific confidence gates and response validity; it does not ask the model whether its own answer should be trusted.

## Install

WindJev requires Python 3.11 or later.

```bash
pip install windjev
export TYPESAFE_API_KEY="..."
```

For local development:

```bash
uv sync --dev
uv run pytest
```

## Initialize a repository

```bash
windjev init
```

This creates `.windjev.yml` and `.github/workflows/windjev.yml` without overwriting existing files. Edit the generated `areas`, `routes`, and label mappings for the repository, then validate them:

```bash
windjev config validate
windjev config validate --json
```

New profiles start in `observe` mode with `jev-latest`. Observe Mode produces results but never changes labels.

## Run locally

```bash
windjev triage \
  --repository acme/shop \
  --title "POST /orders returns 500" \
  --body "The request fails after upgrading" \
  --json
```

To triage an existing GitHub Issue, also set `GITHUB_TOKEN`:

```bash
export GITHUB_TOKEN="..."
windjev triage --repository acme/shop --issue-number 42 --json
```

Machine output is one versioned JSON document on stdout. Diagnostics go to stderr. Stable exit codes are `0` for a completed judgment (including human review), `2` for invalid input or configuration, `3` for a provider failure, and `4` for a GitHub failure.

## GitHub Action

The generated workflow runs when an Issue is opened and supports manual retriage. Add `TYPESAFE_API_KEY` as a repository secret. The workflow checks out only the default branch before reading `.windjev.yml`; Issue content is never executed.

Observe Mode needs:

```yaml
permissions:
  contents: read
  issues: read
```

Before switching to Apply Mode, pin an immutable model such as `jev-1.13.0`, evaluate historical Issues, and change `issues: read` to `issues: write`. Apply Mode updates all four managed label dimensions together. If any judgment fails its gate, existing judgment labels remain unchanged and only `needs-human-review` is added.

WindJev never modifies unmanaged labels, assigns people, closes Issues, edits Issue text, or posts generated comments.

## Evaluate before applying

Create `.windjev/eval.yml`:

```yaml
version: 1
repository: acme/shop
cases:
  - issue: 42
    expected:
      type: bug
      area: api
      priority: high
      route: backend
```

Then run:

```bash
windjev eval --evaluation .windjev/eval.yml --json
```

The report includes per-field accuracy, automatic coverage, automatic error rate, human review rate, provider usage, and timing. Fewer than 30 cases produces a warning. WindJev does not tune gates or enable Apply Mode automatically.

## Python

```python
from windjev import IssueSubject, TriageProfile, TypeSafeJevProvider, triage

profile = TriageProfile.model_validate({
    "version": 1,
    "mode": "observe",
    "model": "jev-latest",
    "areas": {"api": "Public API and request handling"},
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
})

result = triage(
    IssueSubject(
        title="POST /orders returns 500",
        body="The request fails after upgrading",
        repository="acme/shop",
    ),
    profile,
    TypeSafeJevProvider(),
)
```

Async applications use `async_triage`. Batch evaluation uses `async_triage_many`, which limits concurrency, preserves input order, and isolates item failures.

## Data boundary

WindJev sends only the Issue title and body, repository name and description, and configured judgment criteria to TypeSafe. It does not send comments, attachments, author details, existing labels, repository source, or other Issues. Private Issue content still leaves GitHub and is sent to TypeSafe.

WindJev has no hosted service, database, or product telemetry. API keys are read from environment variables or GitHub Secrets and are not written to profiles or results.

## Project documents

- [MVP design](docs/mvp-design.md)
- [Domain language](CONTEXT.md)
- [Architecture decisions](docs/adr/)
