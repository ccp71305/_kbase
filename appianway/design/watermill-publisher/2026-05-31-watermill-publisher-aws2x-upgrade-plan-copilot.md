# `watermill-publisher` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** SNS/SQS publish via `NotificationService`/`MessagingClient` and (if it consumes) G1 concurrent listener; G6 (config). DynamoDB offset access is covered by `DatabaseRepository` (no gap); verify G4 only if an entity uses a version attribute.
> Sections below are retained as the Option-A fallback reference.

> Module: `watermill-publisher` (companion publisher to the watermill side-bus) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
- **SQS:** `WatermillPubTask` consumes `com.amazonaws.services.sqs.model.Message`; `DeadLetterService` uses `sqs.model.{ReceiveMessageRequest, ReceiveMessageResult}` (direct SQS receive for DLQ redrive).
- **S3:** `task/Test.java` builds `AmazonS3`/`AmazonSQS` directly via `*ClientBuilder` and uses `SendMessageRequest` — this is a **throwaway `main`/scratch class** (`Test.java`), not production wiring. Confirm and exclude/delete-candidate; do not model production behavior on it.
- The module has **its own copies** of `AsyncDispatcher`/`Task` (not the `shared` ones) per the codebase notes — verify whether it depends on `shared` at all.

## 2. Migration concerns specific to watermill-publisher
1. **`DeadLetterService` direct SQS receive** (`ReceiveMessageRequest`/`Result`) → `cloud-sdk-api` `MessagingClient.receiveMessages(ReceiveMessageOptions)` returning `List<QueueMessage<String>>`. Preserve DLQ source/target queue routing and redrive semantics.
2. **`WatermillPubTask` DTO** `Message` → `MessageRef` (or directly `QueueMessage<String>` if the module adopts `cloud-sdk-api` rather than the appianway `shared` adapter — decide based on whether it uses `shared`).
3. **`Test.java`** (`AmazonS3`/`AmazonSQS`/`SendMessageRequest`) — scratch class; recommend **excluding from the migration / deleting** rather than porting. Flag for the implementing team.
4. **Own dispatcher copies:** if `watermill-publisher` duplicates `shared`'s SQS loop, it migrates **independently**; align it with the same `MessagingClient`/`QueueMessage` model used by watermill consumers.

## 3. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8. **Option A recommended** — adopt `cloud-sdk-aws` `MessagingClient`/`StorageClient`; keep Dropwizard 4 / JUnit 4. Because it has its own dispatcher, it can adopt `cloud-sdk-api` types directly.

## 4. Maven impact
Remove `aws-java-sdk-{sqs,s3}`. Add `cloud-sdk-api` + `cloud-sdk-aws`. Versions from the watermill/aggregator `dependencyManagement` (v2 BOM 2.30.24).

## 5. Test impact
- `DeadLetterServiceTest`, `WatermillPubTaskTest`, `WatermillPubModuleTest`, `ResponseObserverTest` reference v1 SQS model types and SQS URLs → re-point to `MessagingClient`/`QueueMessage`.
- gRPC publisher tests unaffected. JUnit 4 retained.

## 6. Recommendation
**Option A.** Migrate alongside the watermill consumers (shared DynamoDB/messaging track). Delete/exclude `Test.java`. Effort: **Medium** (DeadLetterService receive rewrite + own dispatcher alignment).

## 7. Peer review outcome
Peer-reviewed (Explore subagent). Confirmed: `DeadLetterService` does a direct SQS receive (not via `shared`); `Test.java` is a scratch `main`. Reviewer notes incorporated: (a) treat `Test.java` as delete/exclude, not port; (b) preserve DLQ source→target redrive semantics exactly; (c) decide `MessageRef` vs direct `QueueMessage` based on whether the module uses appianway `shared` (likely its own dispatcher → use `QueueMessage` directly). Recommendation unchanged.

## 8. Sequencing
With the watermill track (independent of the hot pipeline if no `shared` dependency).

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| DLQ redrive semantics change | Preserve source/target routing; test redrive end-to-end |
| Porting scratch `Test.java` by mistake | Exclude/delete; flag to implementers |
| Own dispatcher drift vs consumers | Align on the same `MessagingClient`/`QueueMessage` model |
