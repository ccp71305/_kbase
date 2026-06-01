# `splitter` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.appian-way:splitter:1.0` · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard 5.0.1, AWS SDK v2 BOM 2.30.24).
> Master references (do not duplicate): [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6.

---

## 0. What this plan changes vs. the Copilot plan (critical review)

Reviewed against [`splitter` plan-copilot](2026-05-31-splitter-aws2x-upgrade-plan-copilot.md) / [DESIGN-copilot](2026-05-31-splitter-aws2x-upgrade-DESIGN.md), the actual source ([`ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/splitter/modules/ExternalServicesModule.java), [`SplitterTask.java`](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java), [`SplitErrorHandler.java`](../src/main/java/com/inttra/mercury/splitter/task/SplitErrorHandler.java)), and the master. Governing constraint (master §0): **zero impact to existing mercury-services apps** — every cloud-sdk/commons change must be **strictly additive and behavior-preserving**.

| Copilot position | Evidence | This plan |
|---|---|---|
| Module-specific gaps listed: **G1 (concurrent listener), G2 (S3 putObject metadata), G6 (config), G7 (health)** | none of these originate in splitter; G1/G6/G7 are platform concerns and splitter performs **no metadata-bearing S3 write** (it only `getContent` reads — [`SplitterTask.getFileContent`](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java:192) — and child writes go through `SplitTransactionProcessor`/shared) | **No module-specific cloud-sdk gap.** splitter relies **only** on shared's **S-G2** (and only if a child write path sets metadata; the container read does not). G1/G6/G7 are inherited from `shared`. |
| `Message` DTO → a new shared **`MessageRef`** adapter | shared adopts `cloud-sdk-api` `QueueMessage<String>` directly | The v1 `com.amazonaws.services.sqs.model.Message` ([`SplitterTask.java:3,95`](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java)) becomes **`QueueMessage<String>`** through the retained Task/ErrorHandler chain — not a bespoke `MessageRef`. |
| "`ClientConfiguration`→v2 override mapping … `shared` owns this translation" | correct, but framed vaguely | Confirmed: the per-role `AWSClientConfiguration.{sqs_listener,sqs_sender,s3_read_put_copy,sns_publish}` mapping is centralized in `shared`/cloud-sdk-aws factories; splitter just **rebinds** to those factories. |

**Net:** splitter is the **standard service pattern** — a pure consumer rebind. **No splitter-originated cloud-sdk change.** It inherits the `QueueMessage<String>` task chain from `shared` and, at most, shared's additive S-G2 if a child-write path carries metadata.

---

## 1. Executive summary

`splitter` consumes a `MetaData` message from the dispatcher's splitter queue, reads the container envelope from the workspace bucket, runs a **strategy-pattern parser** ([`MessageParserManager`](../src/main/java/com/inttra/mercury/splitter/config/MessageParserManager.java) → Gen2 EDIFACT/ANSI/XML/rates/cfast/desktop parsers) to split it into per-document child `Message`s, authenticates/enriches each against integration-profile services, and routes child `MetaData` envelopes to the next-stage queues while emitting lineage events.

Per directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws` (`1.0.26-SNAPSHOT`) on Dropwizard 5** (§7):
1. rebind [`ExternalServicesModule`](../src/main/java/com/inttra/mercury/splitter/modules/ExternalServicesModule.java) to the cloud-sdk factories (`MessagingClient<String>` listener+sender, `StorageClient`, `NotificationService`);
2. inherit the `QueueMessage<String>` dispatcher/task chain from `shared` (the v1 `Message` element swap);
3. **preserve** the split-strategy logic, `MetaData` child-message creation, and event lineage (`rootWorkflowId`/`workflowId`/`parentWorkflowId`).

No splitter-specific cloud-sdk change.

---

## 2. Current state — AWS v1 inventory (with file:line)

AWS Java SDK **v1** (`com.amazonaws.*`, `1.12.720`); `aws-java-sdk-sqs` in [`pom.xml`](../pom.xml:58-63).

### 2.1 Client construction (Guice)
- [`ExternalServicesModule.java:37-44`](../src/main/java/com/inttra/mercury/splitter/modules/ExternalServicesModule.java) binds via v1 builders (imports [:3-8](../src/main/java/com/inttra/mercury/splitter/modules/ExternalServicesModule.java)):
  - `AmazonSQS @Named("amazonSQSForListener")` ← `AWSClientConfiguration.sqs_listener`
  - `AmazonSQS @Named("amazonSQSForSender")` ← `AWSClientConfiguration.sqs_sender`
  - `AmazonS3` ← `AWSClientConfiguration.s3_read_put_copy`
  - `AmazonSNS` ← `AWSClientConfiguration.sns_publish`
  - All via `*ClientBuilder.standard().withClientConfiguration(...)`.

### 2.2 SQS DTO leak through the task chain
- [`SplitterTask.java:3,95`](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java): `process(com.amazonaws.services.sqs.model.Message, String queueUrl)`; reads `message.getBody()` ([:97,:335](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java)) to deserialize `MetaData`. Extends shared [`AbstractTask`](../../shared/src/main/java/com/inttra/mercury/shared/task/AbstractTask.java:20) (v1 `process`/`deleteMessage`).
- The v1 `Message` is threaded through `splitAndProcess`/`processAllTransactions`/`SplitTransactionProcessor` ([:124,:131,:155,:160](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java)) and into [`SplitErrorHandler.java:3,65`](../src/main/java/com/inttra/mercury/splitter/task/SplitErrorHandler.java) (`handleSplitException(Message,...)`, `isRecoverableAttemptsNotMaxed(message)`, `sendBackToPickupQueue(message,...)` — the `FAILED_ATTEMPTS` retry path).

### 2.3 S3 object I/O (read-only; via shared)
- Container read: [`SplitterTask.getFileContent`](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java:192) → `workspaceService.getContent(bucket, fileName, ISO_8859_1)`. **No metadata-bearing write** in `SplitterTask`. Child writes/error writes go through `SplitTransactionProcessor` and `ErrorHelper.writeErrorsToS3` (shared) — already behind the shared facade.

### 2.4 Domain (keep, no direct AWS)
- Strategy parsers under [`parser/`](../src/main/java/com/inttra/mercury/splitter/parser), [`RouterManager`/`FormatBasedSQSRouter`](../src/main/java/com/inttra/mercury/splitter/routers), `MessageBatch`/`MessageGroup`, `GroupingHelper`, `SplitTransactionProcessor`, integration-profile/format network services — none touch the AWS SDK directly; routing/sends go through `SQSClient`/`MessagingClient` and lineage through `EventLogger`.

### 2.5 Config
- [`conf/splitter.yaml`](../conf/splitter.yaml): `sqsPickupConfig` (wait=20s, max=10), `sqsRouterConfig`, `sqsErrorConfig`, `snsEventConfig`, `s3WorkspaceConfig`, `enabledParsers`, `routeMappings`, `routersOrder`, `networkServiceConfig`, DW `server`/`logging`/`metrics` — all `${placeholder}` driven.

---

## 3. Findings

- splitter has **no module-unique AWS surface** beyond the four bound clients. It is the canonical "standard consumer" — exactly the rebind shape of `dispatcher`/`event-writer`, minus dispatcher's S3-event parsing.
- All AWS I/O is already funneled through shared facades (`WorkspaceService.getContent`, `SQSClient.sendMessage`, `EventLogger`); the only v1 type leaking into splitter's own code is the SQS `Message` element, resolved by the inherited `QueueMessage<String>` swap.
- The `FAILED_ATTEMPTS` retry counter ([`SplitErrorHandler.isRecoverableAttemptsNotMaxed`](../src/main/java/com/inttra/mercury/splitter/task/SplitErrorHandler.java:81)) round-trips as a `String` attribute on `QueueMessage<String>` (master §3 — confirmed compatible).
- Child-message lineage (`rootWorkflowId`/`workflowId`/`parentWorkflowId`, `MetaData.Projection.*`) is built in [`SplitterTask.buildMetaData`](../src/main/java/com/inttra/mercury/splitter/task/SplitterTask.java:260) and `SplitTransactionProcessor` — purely domain, preserved unchanged.

---

## 4. Option A — keep `shared`/DW4, delegate wrappers to cloud-sdk

Rebind [`ExternalServicesModule`](../src/main/java/com/inttra/mercury/splitter/modules/ExternalServicesModule.java) to cloud-sdk factories; swap the `Message` element to `QueueMessage<String>` through the retained chain. No splitter business-logic change. Stay on Dropwizard 4 / JUnit 4.
- **Pros:** minimal, reversible, no framework jump. **Cons:** keeps bespoke DW4 base. **Effort:** Low. **Risk:** Low.

## 5. Option B — adopt `commons` + cloud-sdk on Dropwizard 5 (directed default)

As Option A, plus binding via the cloud-sdk factories on `commons` `InttraServer` (DW5) with the appianway composed config command (master §10), new tests in JUnit 5. Split-strategy logic unchanged.
- **Pros:** platform convergence; one AWS abstraction. **Cons:** inherits the DW4→5 cost from `shared`; functional-testing rework. **Effort:** Low–Medium. **Risk:** Medium (inherited from `shared`).

## 6. Comparison

| Criterion | Option A | Option B |
|---|---|---|
| Off AWS v1 | ✅ | ✅ |
| splitter-originated cloud-sdk change | **none** | **none** |
| Required library change | shared S-G2 (additive) at most | shared S-G2 (additive) at most |
| Impact on mercury-services | none | none |
| Framework churn | none | DW4→5 (inherited) |
| Effort / Risk | Low / Low | Low–Med / Med |

## 7. Recommendation

**Option B** per directive. splitter is the cleanest migration in the program: a pure consumer rebind to cloud-sdk factories plus the inherited `Message`→`QueueMessage<String>` element swap, with **no module-specific cloud-sdk change** and **no business-logic change**. The zero-impact-to-mercury-services guarantee holds trivially (splitter introduces no library change).

## 8. Peer review

Self-reviewed against the splitter source (ExternalServicesModule, SplitterTask, SplitErrorHandler, parser strategy, conf/splitter.yaml), the master plan/DESIGN (§0/§10/§11, §5/§6), and the Copilot drafts. Corrections in §0: splitter has **no module-specific cloud-sdk gap** (de-scoped Copilot's per-module G1/G2/G6/G7 framing — these are inherited platform concerns); `Message`→`QueueMessage<String>`, not a bespoke `MessageRef`; the container access is a metadata-less **read**, so even S-G2 is only relevant if a child-write path sets metadata.

## 9. Open questions / sequencing

- Migrate **after** `shared` + `functional-testing`; alongside the other hot-pipeline standard consumers (with `dispatcher`).
- Verify the per-role `AWSClientConfiguration` (`sqs_listener`/`sqs_sender`/`s3_read_put_copy`/`sns_publish`) → cloud-sdk-aws factory mapping in `shared` covers splitter's timeouts/retry.
- Keep the `QueueMessage`/`StorageClient` contract aligned with `mft-s3-aqua-appia` and the rest of appianway.

## 10. Configuration

Reference master [§10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md). Module specifics from [`conf/splitter.yaml`](../conf/splitter.yaml): `sqsPickupConfig` (`waitTimeSeconds:20`, `maxNumberOfMessages:10`) → `ReceiveMessageOptions`; `sqsRouterConfig`/`routeMappings`/`sqsErrorConfig`/`snsEventConfig`/`s3WorkspaceConfig`/`enabledParsers`/`networkServiceConfig` unchanged; `${PROFILE}`/`${ENV}`/`${awsps:...}` resolution unchanged. No placeholder change. DW5: verify `server`/`logging`/`metrics` under `io.dropwizard.core.*`.

## 11. cloud-sdk gaps

Reference master [§11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md). **No module-specific cloud-sdk change; splitter relies only on shared's S-G2** (and only if a child-write path carries user metadata — the container read does not). G1 (concurrent listener), G6 (config), G7 (health) are inherited shared/platform concerns, not splitter gaps. The split-strategy parsing stays appianway-local — no cloud-sdk gap.
