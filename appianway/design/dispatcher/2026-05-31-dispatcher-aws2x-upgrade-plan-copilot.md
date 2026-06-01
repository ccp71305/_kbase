# `dispatcher` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata), **G3 (S3 event-notification parsing — dispatcher is the S3→SQS gate; see master DESIGN §1A.6 G3)**, G6 (config), G7 (health checks).
> Sections below are retained as the Option-A fallback reference.

> Module: `dispatcher` (S3→SQS routing gate: copies inbound to workspace, resolves archive type, routes to splitter) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
- **`modules/ExternalServicesModule`** ([src](../src/main/java/com/inttra/mercury/dispatcher/modules/ExternalServicesModule.java)) binds: `AmazonSQS` listener+sender (`AWSClientConfiguration.sqs_listener`/`sqs_sender`), `AmazonS3` (`s3_read_put_copy`), `AmazonSNS` (`sns_publish`).
- **Task** consumes `com.amazonaws.services.sqs.model.Message` (shared listener DTO).
- **S3-event-specific surface (module-unique):**
  - `com.amazonaws.services.s3.event.S3EventNotification` — parses the inbound S3 event payload to get bucket/key.
  - `com.amazonaws.services.s3.model.ObjectMetadata` — reads object metadata.
  - `com.amazonaws.util.IOUtils` — stream copy helpers.

## 2. Migration concerns specific to dispatcher
1. **`S3EventNotification`** has no direct equivalent in `cloud-sdk-api`. In AWS SDK v2 the event JSON is typically deserialized with a POJO/Jackson model (e.g. `software.amazon.awssdk.eventnotifications.s3.model.S3EventNotification` from the `s3-event-notifications` artifact, or a local record). **Decision needed:** either (a) add the v2 S3 event-notifications artifact, or (b) deserialize the event JSON into a small local record. Recommend (b) for minimal dependency surface unless `cloud-sdk-aws` already exposes a helper.
2. **`ObjectMetadata`** → v2 `HeadObjectResponse` / `GetObjectResponse` metadata, surfaced through the `shared` `StorageClient`/`StorageObject` (`getMetaData`). Route metadata reads through `shared` rather than a direct v2 call.
3. **`com.amazonaws.util.IOUtils`** → replace with `software.amazon.awssdk.utils.IoUtils` or `java.io`/Guava — a trivial utility swap.

## 3. Dependencies on `shared`
Copy-to-workspace and routing go through `shared` `WorkspaceService` + `SQSClient`/`SNSClient`. Those are migrated in the `shared` deliverable. Dispatcher's own changes: Guice rebind, DTO swap, S3-event parsing, metadata read via `shared`, IOUtils swap.

## 4. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8. **Option A recommended** — rebind, swap DTO/util, localize S3-event parsing; keep Dropwizard 4 / JUnit 4.

## 5. Maven impact
Remove `aws-java-sdk-{sqs,sns,s3}`; add `cloud-sdk-api` if the module names interface types or a v2 S3-event-notifications artifact if option (a) chosen. v2 runtime arrives transitively via `shared`.

## 6. Test impact
Functional tests via `functional-testing` fakes (migrate first). Add/keep tests for S3-event parsing using the new deserialization path and for archive-type resolution. JUnit 4 retained.

## 7. Recommendation
**Option A**, with S3-event parsing localized to a small record/Jackson model (no new heavy artifact unless `cloud-sdk-aws` provides one). Effort: **Medium** (S3-event + metadata are the extra work vs a plain consumer).

## 8. Peer review outcome
Peer-reviewed (Explore subagent). Confirmed the three module-unique surfaces (`S3EventNotification`, `ObjectMetadata`, `IOUtils`). Reviewer notes incorporated: (a) prefer routing metadata reads through `shared.StorageClient.getMetaData` rather than introducing a direct v2 `HeadObject` call in dispatcher; (b) verify whether `cloud-sdk-aws` already ships an S3-event-notification helper before adding the standalone v2 artifact — if it does, use it for consistency; (c) `IOUtils`→`software.amazon.awssdk.utils.IoUtils` keeps everything on one SDK. Recommendation unchanged.

## 9. Sequencing
After `shared` + `functional-testing`. Migrate after the pilot `event-writer` so the S3-event nuance is tackled once the basic pattern is proven.
