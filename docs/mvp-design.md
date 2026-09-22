# WindJev MVP Design

## Objective

WindJev turns a GitHub Issue into typed, confidence-aware routing judgments and applies project labels only when every required judgment is sufficiently reliable. The MVP also establishes a small decision foundation that later workflows can reuse for message triage, content moderation, support routing, developer automation, and batch record decisions.

The MVP succeeds by completing one workflow end to end, not by shipping those future applications.

## Users

- Development teams use Issue Triage to reduce manual routing work.
- Python and agent developers configure, invoke, and extend WindJev.

## MVP outcomes

For a GitHub Issue, WindJev produces:

| Field | Primitive | Values |
| --- | --- | --- |
| `type` | Choice | `bug`, `feature`, `question`, `maintenance` |
| `area` | Choice | Project-defined candidates |
| `priority` | Score | `low`, `medium`, `high`, `critical` |
| `route` | Choice | Project-defined team candidates |
| `needs_review` | Policy result | Derived from validity and confidence gates |

`needs_review` is not a model question. WindJev derives it after validating the four judgments.

## Architecture

```text
GitHub Issue / local input
          |
          v
    Issue Triage
          |
          v
    Decision Core ----> TypeSafe Jev Provider
          |
          v
 Confidence Gates
          |
          v
   Triage Result
          |
          +----> CLI / JSON
          +----> Python caller
          +----> GitHub label effect
```

The implementation begins with five main modules:

- `decision.py`: questions, judgments, gates, and single/batch orchestration.
- `providers.py`: the Decision Provider interface and TypeSafe Jev adapter.
- `issue_triage.py`: Issue subject, profile, question construction, and outcome rules.
- `github.py`: GitHub Issue reads and label updates.
- `cli.py`: initialization, validation, triage, and evaluation commands.

The module names may change during implementation, but their responsibilities must not leak GitHub concepts into the Decision Core.

## Decision foundation

The public foundation owns provider-independent `Choice`, `Score`, `Noul`, question-set, judgment, usage, timing, and error types. A Decision Provider receives one state and a set of typed questions, then returns validated judgments.

Only the TypeSafe Jev provider ships in the MVP. It uses the official `typesafe-sdk`, reads `TYPESAFE_API_KEY`, and submits all four Issue Triage questions in one request.

The orchestration core is asynchronous. A synchronous convenience interface executes the same implementation for scripts and the CLI. Simple batch execution preserves input order, limits concurrency, isolates per-item failures, and supports asynchronous iteration; generic file and database connectors are outside the MVP.

New scenarios are code-defined Decision Workflows with two responsibilities:

1. Build typed questions from a domain Subject and profile.
2. Resolve returned judgments into a workflow result and Disposition.

Configuration supplies candidates, thresholds, and mappings. It is not a programming language.

## Triage state

The provider receives only:

- Issue title and body.
- Repository name and public description.
- Definitions of fixed Issue Type and Priority values.
- Project-defined Area and Route candidates with descriptions.

WindJev does not send comments, attachments, author details, existing labels, source code, or other Issues. Private Issue content still leaves GitHub and is sent to TypeSafe; documentation and Action setup must disclose this explicitly.

## Profile

Each repository owns a versioned `.windjev.yml` on its default branch. It defines:

- Schema version and operating mode.
- Model identifier.
- Area and Route candidates with descriptions.
- Per-field confidence gates.
- Judgment-to-label mappings.
- The `needs-human-review` label.
- Bounded timeout settings when defaults are unsuitable.

Unknown fields, duplicate label mappings, missing descriptions, invalid candidates, and incompatible mode/model combinations are configuration errors.

`windjev init` creates a conservative starter profile and GitHub workflow. It does not scan the repository or infer classifications. `windjev config validate` validates without invoking Jev or GitHub.

## Operating modes

### Observe Mode

Observe Mode produces the full result but changes no labels. It may use the moving `jev-latest` alias and is the default for new profiles.

### Apply Mode

Apply Mode requires an immutable model identifier such as `jev-1.13.0`. It may update labels only when all four judgments are valid and pass their individual gates.

Initial default gates are:

| Field | Confidence |
| --- | ---: |
| `type` | 0.80 |
| `area` | 0.80 |
| `priority` | 0.75 |
| `route` | 0.80 |

These are conservative starting values, not claims of calibrated accuracy. Each project should tune them using its Evaluation Set.

Triage is atomic:

- When every gate passes, WindJev replaces all four dimensions of Managed Labels together and removes `needs-human-review`.
- When any gate fails, WindJev leaves the four judgment dimensions unchanged and adds only `needs-human-review`.
- Observe Mode writes no labels, including `needs-human-review`.

WindJev never deletes labels outside the mappings currently declared by the profile. Removing a mapping also relinquishes ownership of the corresponding existing label.

## Invocation surfaces

### Python

The package exposes asynchronous and synchronous triage entry points plus the public Decision Workflow and Decision Provider interfaces. Official SDK types do not appear in public signatures.

### CLI

The MVP commands are:

```text
windjev init
windjev config validate
windjev triage
windjev eval
```

Human-readable output is the default. With `--json`, stdout contains exactly one versioned JSON document; diagnostics go to stderr.

Exit codes are stable:

| Code | Meaning |
| ---: | --- |
| 0 | Successful execution, including `review_required` |
| 1 | Unclassified internal error |
| 2 | Invalid arguments, input, or profile |
| 3 | Decision Provider authentication, limit, timeout, or response failure |
| 4 | GitHub read or write failure |

The JSON result includes `schema_version`, `status`, `judgments`, `needs_review`, provider/model identity, usage, and timing. `status` is `observed`, `applied`, or `review_required`.

### GitHub Action

A Composite Action installs a fixed WindJev package version and invokes the same CLI. It runs automatically when an Issue is opened and supports manual workflow dispatch for retriage. It does not retriage on every edit in the MVP.

The Action writes a run Summary containing judgments, confidence, timing, and errors. It does not post comments, assign people, close Issues, or edit Issue content.

## Evaluation

An Evaluation Set is a versioned project file containing historical Issue numbers and expected judgments. `windjev eval` fetches the Issues, runs the current profile through the shared batch helper, and reports:

- Accuracy per judgment field.
- Fraction eligible for atomic automatic application.
- Error rate among automatically applicable cases.
- Fraction requiring human review.
- Provider latency and usage.

Fewer than 30 representative cases produces a prominent warning. WindJev does not invent a universal quality threshold, adjust gates automatically, or switch modes. Maintainers review the report and explicitly enable Apply Mode.

A model change returns the project to Observe Mode for reevaluation. Reports record the resolved immutable model identifier, not only an alias.

## Failure behavior

Provider requests use a 10-second attempt timeout, a 30-second overall deadline, and at most two retries with jittered exponential backoff for network failures, `429`, and `5xx` responses. Authentication, invalid requests, and invalid responses are not retried.

Failures are closed:

- Existing Managed Labels remain unchanged.
- `needs-human-review` is added when GitHub remains writable.
- The Action fails with a clear Summary.
- The CLI returns the documented nonzero code.
- The Python interface raises a WindJev-owned exception.

WindJev never silently switches providers or fabricates judgments with keyword rules.

## Security and privacy

The Action requests only `contents: read` and the Issue permission required by its mode. Observe Mode needs `issues: read`; Apply Mode needs `issues: write`.

The Triage Profile is read only from the default branch. Issue content is untrusted data: WindJev does not execute its code or commands, follow its URLs, or check out contributor branches. Secrets and authorization headers are redacted from logs and JSON.

The MVP is stateless. It has no database, hosted WindJev service, or product telemetry. Evaluation data is explicitly maintained by the project. API keys come only from environment variables or GitHub Secrets.

## Compatibility and release

- Python 3.11 or later.
- Apache-2.0 license.
- Semantic Versioning.
- Versioned `.windjev.yml`, Evaluation Set, and CLI JSON schemas begin at version 1.
- The Decision Workflow and Decision Provider interfaces are public; other implementation details are not compatibility commitments.
- PyPI and GitHub Action releases share a version. A moving `v1` Action tag accompanies immutable release tags.
- Release automation builds and tests artifacts; publishing requires protected credentials and human approval.

Runtime dependencies are limited to `typesafe-sdk`, Pydantic, PyYAML, Typer, and HTTPX. Tests use pytest, pytest-asyncio, and respx.

## Explicit exclusions

The MVP does not ship finished workflows for email, moderation, support tickets, code review, test selection, agent routing, CSV, JSONL, or databases. It also excludes a Web UI, hosted service, database, MCP server, GitLab/Jira/Slack/Gmail integrations, additional Decision Providers, local models, offline privacy mode, YAML workflow DSL, plugin registry, generic connector framework, generated replies, automatic assignment, Issue closure, automatic tuning, and automatic Apply Mode activation.

## Completion criteria

The MVP is complete when:

- Local input produces four judgments and a derived Review Requirement.
- Observe Mode generates a GitHub Summary without changing labels.
- Apply Mode atomically updates Managed Labels when every gate passes.
- A failed gate leaves judgment labels unchanged and adds `needs-human-review`.
- Provider and GitHub failures preserve existing labels and expose documented errors.
- `windjev eval` evaluates a historical Issue set and reports quality, coverage, usage, and timing.
- Synchronous and asynchronous Python entry points behave consistently.
- Configuration, JSON schema, and exit codes have contract tests.
- Default tests require no real API key; a separate optional Jev smoke test is available.
- The Composite Action passes an end-to-end test against a temporary repository or a faithful GitHub API test adapter.

Implementation must not add an excluded capability merely to satisfy a hypothetical future workflow.
