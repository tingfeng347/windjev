# WindJev

WindJev provides reusable, confidence-aware decisions for developer workflows. It combines a general decision core with a focused workflow product and developer-facing integration surfaces.

## Language

**Decision Core**:
The reusable layer that evaluates typed questions and returns structured judgments with confidence information.
_Avoid_: SDK, AI wrapper, Jev client

**Workflow Application**:
The focused developer-workflow product built on the Decision Core for a complete user outcome.
_Avoid_: Demo, example app, use case

**Decision Workflow**:
A named composition of typed questions, confidence policies, and outcome rules that turns domain input into judgments and a bounded disposition. Issue Triage is the only Decision Workflow shipped by the MVP, while later workflows may address messages, moderation, support, developer tasks, or data records.
_Avoid_: Pipeline, recipe, template

**Subject**:
The domain item a Decision Workflow evaluates, such as an issue, message, document, developer task, or data record. Each workflow owns its concrete Subject type.
_Avoid_: Record, payload, item

**Issue Triage**:
The first Workflow Application, which turns a newly submitted development issue into routing judgments for a project team.
_Avoid_: Ticket bot, issue classifier

**Issue Type**:
The nature of the work represented by an issue: bug, feature, question, or maintenance.
_Avoid_: Kind, category

**Area**:
A project-defined part of the codebase or product affected by an issue.
_Avoid_: Component, module

**Priority**:
The issue's required attention level: critical, high, medium, or low.
_Avoid_: Severity, urgency

**Route**:
The project-defined team responsible for taking the next action on an issue.
_Avoid_: Assignee, owner

**Review Requirement**:
A result derived from confidence and validity policies indicating that automated triage is insufficient and a person must review the issue. It is not a model judgment.
_Avoid_: Fallback, uncertain

**Triage Profile**:
A project's allowed Areas and Routes together with the policies that translate triage judgments into project labels.
_Avoid_: Configuration, schema, settings

**Managed Label**:
A label whose lifecycle is owned by Issue Triage and which it may add, replace, or remove during retriage.
_Avoid_: Generated label, AI label

**Observe Mode**:
A triage mode that produces complete judgments and review requirements without changing any labels.
_Avoid_: Dry run, test mode

**Apply Mode**:
A triage mode that may update Managed Labels when every required judgment passes its Confidence Gate.
_Avoid_: Live mode, production mode

**Atomic Triage**:
The policy that applies all required judgment labels together or applies none of them when any judgment requires review.
_Avoid_: Partial triage, best effort

**Evaluation Set**:
A project-curated collection of historical issues and expected judgments used to measure triage quality and tune Confidence Gates.
_Avoid_: Test set, fixtures, benchmark

**Decision Provider**:
A service capable of evaluating the Decision Core's typed questions without defining WindJev's public domain types.
_Avoid_: Model, backend, SDK

**Disposition**:
The bounded operational outcome derived from a workflow's judgments, such as apply, review, reject, route, or defer. A Disposition is determined by workflow policy rather than generated prose.
_Avoid_: Action, status, decision

**Triage State**:
The minimum issue and project information evaluated during Issue Triage: issue title and body, repository identity and description, and the available judgment criteria.
_Avoid_: Prompt, context, payload

**Integration Surface**:
A supported way for developers or agents to invoke a Workflow Application or the Decision Core, such as the CLI, Python API, or agent tool.
_Avoid_: Frontend, adapter

**Confidence Gate**:
A policy that decides whether a judgment may trigger an automated action or must be deferred for human review.
_Avoid_: Confidence threshold, fallback

**Judgment**:
A typed decision result containing an answer and confidence information, rather than generated prose.
_Avoid_: Completion, response, prediction
