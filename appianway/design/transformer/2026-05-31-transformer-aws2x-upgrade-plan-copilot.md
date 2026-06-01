# `transformer` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata), **G4 (DynamoDB optimistic-lock/version attribute — `ControlNumberSequence` uses `@DynamoDBVersionAttribute` with CONSISTENT reads; adopt `DatabaseRepository`/`EnhancedDynamoRepository` and the version-attribute + atomic-counter additions in master DESIGN §1A.6 G4)**, G6 (config), G7 (health checks). Contivo XSLT/Java mapping stays appianway-local (the `com.contivo:commons` runtime is unrelated to `mercury-services-commons`).
> Sections below are retained as the Option-A fallback reference.

> Module: `transformer` (Contivo XSLT/Java mapping engine → canonical model) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
`transformer` is a **standard consumer** that **also uses DynamoDB** — the second-largest AWS surface after `watermill`. In [`modules/ExternalServicesModule`](../src/main/java/com/inttra/mercury/transformer/modules/ExternalServicesModule.java) it binds:
- `AmazonSQS` (`amazonSQSForListener` → `sqs_listener`; `amazonSQSForSender` → `sqs_sender`)
- `AmazonS3` (`s3_read_put_copy`)
- `AmazonSNS` (`sns_publish`)
- **`AmazonDynamoDB` + `DynamoDBMapper` + `DynamoDBMapperConfig`** (CONSISTENT reads) — for the control-number sequence store.

DynamoDB data-modeling files:
- [`controlnumbers/sequence/ControlNumberSequence`](../src/main/java/com/inttra/mercury/transformer/controlnumbers/sequence/ControlNumberSequence.java) — annotated VO: `@DynamoDBHashKey`, `@DynamoDBAttribute(keyId/id)`, **`@DynamoDBVersionAttribute`** (optimistic locking), `@DynamoDBIgnore`.
- [`controlnumbers/sequence/ControlNumberSequenceDao`](../src/main/java/com/inttra/mercury/transformer/controlnumbers/sequence/ControlNumberSequenceDao.java) — `DynamoDBMapper` + `DynamoDBMapperConfig` (load/save with optimistic-lock version checks).

> **Contivo note:** `transformer`'s `com.contivo:commons` is the **Contivo runtime** (in `lib/` + `contivo-lib/`), unrelated to `mercury-services-commons:commons`. **Do not touch** the Contivo mapping engine, its jars, or XSLT/Java mappings — they are non-AWS and out of scope.

## 2. Migration concerns specific to transformer
1. **DynamoDB `DynamoDBMapper` → v2 Enhanced Client** (same class of rewrite as `watermill`):
   - `ControlNumberSequence` v1 `datamodeling` annotations → v2 `@DynamoDbBean`/`@DynamoDbPartitionKey`/`@DynamoDbAttribute`, and **`@DynamoDBVersionAttribute` → `@DynamoDbVersionAttribute`** (v2 optimistic locking — must preserve concurrency semantics; control-number generation depends on it).
   - `@DynamoDBIgnore` → v2 `@DynamoDbIgnore`.
   - `ControlNumberSequenceDao` rewritten against `DynamoDbEnhancedClient` / `DynamoDbTable<ControlNumberSequence>`; CONSISTENT reads preserved (`builder().consistentRead(true)`).
   - Prefer routing through `cloud-sdk-aws` Dynamo support if it offers a suitable abstraction; otherwise use the v2 Enhanced Client directly. Adopt `dynamo-integration-test` for integration tests.
2. **Standard-consumer rebind** of SQS/S3/SNS → `cloud-sdk-aws` `MessagingClient`/`StorageClient`/`NotificationService` (canonical change; see [dispatcher DESIGN](../../dispatcher/docs/2026-05-31-dispatcher-aws2x-upgrade-DESIGN.md)).
3. **`Message` DTO → `MessageRef`** in the transform task.
4. **Contivo engine untouched.**

## 3. Dependencies on `shared`
**Hard dependency** for SQS/S3/SNS (after `shared` + `functional-testing`). The DynamoDB Enhanced-Client rewrite is transformer-local (mirrors the `watermill` approach) and should reuse the same v2 Dynamo patterns/`dynamo-integration-test` to stay consistent.

## 4. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8.
- **Option A (recommended):** rebind SQS/S3/SNS to `cloud-sdk-aws`; rewrite Dynamo to v2 Enhanced Client; keep Dropwizard 4 / JUnit 4; Contivo untouched.
- **Option B:** commons → Dropwizard 4→5; no transformer-specific benefit and higher risk near the Contivo runtime.

## 5. Maven impact
Remove `aws-java-sdk-{sqs,s3,sns,dynamodb}`. Add `cloud-sdk-api` + `cloud-sdk-aws` (+ `software.amazon.awssdk:dynamodb-enhanced` if used directly) and `dynamo-integration-test` (test). Versions from root `dependencyManagement` (v2 BOM 2.30.24). **Contivo jars unchanged.**

## 6. Test impact
- **DynamoDB:** rewrite `ControlNumberSequenceDao`/`ControlNumberSequence` tests against the Enhanced Client; add **optimistic-lock version** and **CONSISTENT-read** equivalence tests; adopt `dynamo-integration-test`.
- **Pipeline:** functional tests use `functional-testing` fakes re-pointed to `cloud-sdk-api`.
- **Contivo mapping tests** unaffected. JUnit 4 retained for unit tests (flag if `dynamo-integration-test` forces Jupiter for integration tests).

## 7. Recommendation
**Option A.** Effort: **Medium–High** — the `DynamoDBMapper`→Enhanced-Client rewrite of the control-number sequence (with version-attribute optimistic locking) is the main risk; the SQS/S3/SNS rebind is mechanical.

## 8. Peer review outcome
Peer-reviewed (Explore subagent). **Correction applied:** transformer was initially mis-classified as a DTO-only consumer; direct read shows it binds SQS/S3/SNS **and** `AmazonDynamoDB`/`DynamoDBMapper` and owns annotated `ControlNumberSequence`/`ControlNumberSequenceDao`. Reviewer flagged: (a) `@DynamoDBVersionAttribute` optimistic locking must map to v2 `@DynamoDbVersionAttribute` with identical concurrency behavior — control-number generation correctness depends on it; (b) CONSISTENT reads must be preserved; (c) keep the Contivo runtime strictly out of scope; (d) reuse `watermill`'s v2 Dynamo patterns + `dynamo-integration-test` for consistency. Recommendation: Option A.

## 9. Sequencing
SQS/S3/SNS rebind after `shared` + `functional-testing`. Schedule the DynamoDB rewrite with (or just after) the `watermill` Dynamo pilot to reuse the established v2 Enhanced-Client + `dynamo-integration-test` patterns.

## 10. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Optimistic-lock semantics change → duplicate/invalid control numbers | Map to v2 `@DynamoDbVersionAttribute`; concurrency + version equivalence tests; `dynamo-integration-test` |
| CONSISTENT read lost | Set `consistentRead(true)` in v2; assert |
| Annotation/converter gaps | Explicit v2 `@DynamoDbBean` mapping; round-trip tests |
| Accidental Contivo change | Keep Contivo jars/mappings out of scope |
| Override-config mapping gaps (SQS/S3/SNS) | Centralize in `shared`; functional-test assert |
| `Message`→`MessageRef` drift | Parity tests in `shared` |
