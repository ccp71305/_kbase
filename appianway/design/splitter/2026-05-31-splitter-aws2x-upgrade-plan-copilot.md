# `splitter` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata), G6 (config), G7 (health checks). The split-strategy parsing stays appianway-local (no cloud-sdk gap).
> Sections below are retained as the Option-A fallback reference.

> Module: `splitter` (strategy-pattern parser; splits envelope containers → per-document child messages) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
`splitter` is a **standard consumer** — it binds its own AWS clients in [`modules/ExternalServicesModule`](../src/main/java/com/inttra/mercury/splitter/modules/ExternalServicesModule.java):
- `AmazonSQS` (`amazonSQSForListener` → `AWSClientConfiguration.sqs_listener`; `amazonSQSForSender` → `sqs_sender`)
- `AmazonS3` (`AWSClientConfiguration.s3_read_put_copy`)
- `AmazonSNS` (`AWSClientConfiguration.sns_publish`)

All built via `*ClientBuilder.standard().withClientConfiguration(...)`. The SQS listener loop, S3 body access, and SNS event publishing flow through `shared` (`SQSListener`, `WorkspaceService`, `EventLogger`). Splitter's own code consumes the v1 `com.amazonaws.services.sqs.model.Message` DTO via `shared`'s task base, plus the per-document split logic (no direct AWS calls beyond the bound clients).

## 2. Migration concerns specific to splitter
1. **Guice rebind:** rebind `ExternalServicesModule` from v1 `Amazon{SQS,S3,SNS}` to `cloud-sdk-aws` `MessagingClient`/`StorageClient`/`NotificationService` (mirrors `shared`'s [DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md) and the canonical standard-consumer change in [dispatcher](../../dispatcher/docs/2026-05-31-dispatcher-aws2x-upgrade-DESIGN.md)).
2. **`Message` DTO → `MessageRef`:** wherever splitter's tasks read the v1 SQS `Message`, switch to `shared`'s `MessageRef` adapter (`getBody`/`getReceiptHandle`/`getMessageAttributes`).
3. **`AWSClientConfiguration` mapping:** the per-role `ClientConfiguration` (`sqs_listener`/`sqs_sender`/`s3_read_put_copy`/`sns_publish`) must map to equivalent v2 `ClientOverrideConfiguration`/`ApacheHttpClient` settings exposed by `cloud-sdk-aws` factories — `shared` owns this translation.

## 3. Dependencies on `shared`
**Hard dependency.** Splitter must migrate **after** `shared` and `functional-testing`. Its bindings adopt whatever factory surface `shared`/`cloud-sdk-aws` expose.

## 4. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8.
- **Option A (recommended):** rebind to `cloud-sdk-aws`; keep Dropwizard 4 / JUnit 4. No splitter business-logic change.
- **Option B:** adopt commons → forces Dropwizard 4→5. No splitter-specific benefit.

## 5. Maven impact
Remove `aws-java-sdk-{sqs,s3,sns}`. Add `cloud-sdk-api` + `cloud-sdk-aws` (versions from root `dependencyManagement`, v2 BOM 2.30.24).

## 6. Test impact
Functional tests use the `functional-testing` fakes (in-memory S3/SQS/SNS) — re-pointed once that harness exposes `cloud-sdk-api` interfaces (see [functional-testing plan](../../functional-testing/docs/2026-05-31-functional-testing-aws2x-upgrade-plan-copilot.md)). Split-strategy unit tests unaffected. JUnit 4 retained.

## 7. Recommendation
**Option A.** Effort: **Low–Medium** (mechanical rebind + `Message`→`MessageRef` in tasks). No parsing-logic change.

## 8. Peer review outcome
Peer-reviewed (Explore subagent). **Correction applied:** splitter was initially mis-classified as a DTO-only consumer; it is in fact a standard consumer binding SQS/S3/SNS in its own `ExternalServicesModule` (confirmed by direct read). Reviewer confirmed the rebind mirrors dispatcher/event-writer exactly and that no split-strategy code touches AWS directly. Recommendation: Option A.

## 9. Sequencing
After `shared` + `functional-testing`; alongside the other hot-pipeline standard consumers.

## 10. Risks & mitigations
| Risk | Mitigation |
|---|---|
| `ClientConfiguration`→v2 override mapping gaps | Centralize in `shared`/`cloud-sdk-aws`; assert via functional tests |
| `Message`→`MessageRef` attribute drift | `MessageRef` parity unit tests in `shared` |
| Fakes not ready | Sequence after functional-testing |
