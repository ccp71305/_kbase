# `event-writer` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata/content-type), G6 (config), G7 (health checks).
> Sections below are retained as the Option-A fallback reference.

> Module: `event-writer` (audit sink: persists SNS events as JSON to workspace S3) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
- **`modules/ExternalServicesModule`** binds: `AmazonSQS` (`@Named("amazonSQSForListener")` and `@Named("amazonSQSForSender")` via `AWSClientConfiguration.sqs_listener`/`sqs_sender`), `AmazonS3` (`AWSClientConfiguration.s3_read_put_copy`).
- **Task** (`EventStoreTask` / event writer task) consumes `com.amazonaws.services.sqs.model.Message` (the `shared` listener DTO) and writes payloads to S3 via the `shared` `WorkspaceService`.
- SQS send/receive, S3 put, SNS publish all flow through `shared` wrappers; this module only **binds** the underlying clients and **consumes** the listener DTO.

## 2. Dependencies on `shared`
`event-writer` depends on `shared` for `SQSListener`, `WorkspaceService`, `EventLogger`, `ErrorHandler`, `MetaData`. All of these are migrated in the `shared` deliverable. This module's own change is limited to (a) the Guice binding and (b) the listener-DTO type (`Message` → `MessageRef`).

## 3. Options (A vs B)
Both options are documented in full in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8.
- **Option A (recommended):** rebind the Guice module to provide `shared`'s v2-backed wrappers (or the `cloud-sdk-aws` `StorageClient`/`MessagingClient` the wrappers now require); switch the Task's DTO import from `com.amazonaws.services.sqs.model.Message` to the `shared` `MessageRef`. Stay on Dropwizard 4 / JUnit 4.
- **Option B:** additionally swap the Dropwizard `Application`/bootstrap to commons `InttraServer` and move to Dropwizard 5 — a much larger blast radius for no functional gain in this module.

## 4. Maven impact
Remove `com.amazonaws:aws-java-sdk-{sqs,s3}` (and `sns` if present); rely on `cloud-sdk-aws` transitive v2 deps via `shared`. No new direct deps if all AWS access stays behind `shared`; add `cloud-sdk-api` only if the Guice module needs to name the interface types directly.

## 5. Test impact
- Functional tests use the `functional-testing` fakes — they must be migrated first (see [`functional-testing` plan](../../functional-testing/docs/2026-05-31-functional-testing-aws2x-upgrade-plan-copilot.md)).
- Unit tests that build a v1 `Message` must build a `MessageRef` instead. Stay on JUnit 4.

## 6. Recommendation
**Option A.** Smallest change consistent with the program: rebind clients, swap DTO type, rebuild. Effort: **Low–Medium.**

## 7. Sequencing
After `shared` and `functional-testing`. Good **first service to migrate** (low risk, simple S3-write path) to validate the end-to-end pattern.

## 8. Peer review outcome
Peer-reviewed in the standard-consumer batch (Explore subagent). Confirmed: ExternalServicesModule is the only AWS-binding point; Task consumes the listener DTO only; no direct S3/SQS model usage beyond the DTO. Reviewer note added: verify the two `@Named` SQS clients map cleanly to the listener-vs-sender split in `cloud-sdk-aws` `MessagingClientFactory` (listener long-poll vs sender) — call out in the design. No correction to the recommendation.

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| `@Named` listener/sender split not 1:1 in cloud-sdk | Provide two configured `MessagingClient` instances in the Guice module |
| DTO swap misses a call site | Compiler-driven: `Message`→`MessageRef` is a type change, build flags every site |
| Functional fakes not ready | Gate this module behind `functional-testing` migration |
