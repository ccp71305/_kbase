# `watermill-publisher` — AWS SDK v2 (cloud-sdk) Upgrade PLAN (claude)

> Module: `com.inttra.mercury:watermill-publisher` (companion publisher to the watermill side-bus) · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**).
> References MASTER docs: [shared plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11, [shared DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §4/§5/§6. Companion: [watermill-publisher DESIGN](2026-05-31-watermill-publisher-aws2x-upgrade-DESIGN-claude.md).

---

## 0. What this document changes vs. the Copilot plan (critical review)

Reviewed against [`2026-05-31-watermill-publisher-aws2x-upgrade-plan-copilot.md`](2026-05-31-watermill-publisher-aws2x-upgrade-plan-copilot.md) and the actual source. Copilot's inventory is accurate; the corrections are about coupling and which `shared` types carry the migration.

| Copilot position | Evidence (this codebase) | This plan |
|---|---|---|
| "The module has its **own copies** of `AsyncDispatcher`/`Task` (not `shared`'s); verify whether it depends on `shared` at all… likely its own dispatcher → use `QueueMessage` directly." | It **does** have its own `task/AsyncDispatcher`/`Task`/`ListenerManager`, **but they are built on `shared`'s `SQSListener`/`SQSListenerClient`/`SQSClient`/`Dispatcher` and the v1 `com.amazonaws...Message` type** ([WatermillPubModule.java](../src/main/java/com/inttra/mercury/watermill/modules/WatermillPubModule.java) L91–105; [AsyncDispatcher.java](../src/main/java/com/inttra/mercury/watermill/task/AsyncDispatcher.java) L5/L26; [Task.java](../src/main/java/com/inttra/mercury/watermill/task/Task.java) L3/L9). | **Tightly coupled to `shared`.** It inherits the `Message`→`QueueMessage<String>` swap **from `shared`** (it does not adopt `cloud-sdk-api` directly). Migrate **after `shared`**, in lockstep with the element-type change. |
| "`WatermillPubTask` DTO `Message` → `MessageRef` or `QueueMessage` (decide on `shared` usage)." | `WatermillPubTask` uses `shared`'s `WorkspaceService`, `SQSClient`, `MetaData`, `Json`, and the v1 `Message` ([WatermillPubTask.java](../src/main/java/com/inttra/mercury/watermill/task/WatermillPubTask.java) L3, L46, L51–76). | Follow `shared`: the local `Task`/`AsyncDispatcher` element type becomes `QueueMessage<String>`; `MetaData` becomes the adopted commons type. No bespoke `MessageRef`. |
| "`DeadLetterService` direct SQS receive → `MessagingClient.receiveMessages(ReceiveMessageOptions)`." | Correct: [DeadLetterService.java](../src/main/java/com/inttra/mercury/watermill/task/DeadLetterService.java) L33–42 builds a v1 `ReceiveMessageRequest(sourceQueue)` (wait=20s, max=10) and redrives `dlq → main`. | Confirmed. Map to `shared`'s migrated `SQSListenerClient`/`SQSClient` (which wrap `MessagingClient<String>`) — `getBody()`→`getPayload()`, `getReceiptHandle()` preserved; redrive routing unchanged. |
| "`Test.java` is a scratch `main` → exclude/delete, don't port." | Confirmed: [Test.java](../src/main/java/com/inttra/mercury/watermill/task/Test.java) L16–65 is a `public static void main` load-generator with a hardcoded Windows path and queue URL; not wired into any module. | **Delete/exclude.** Not production; do not model behavior on it. (It is the only place this module touches S3 **write** and SQS **send-with-delay** directly; neither is production wiring.) |
| Copilot header: "SNS/SQS publish via `NotificationService`/`MessagingClient`; **G1 concurrent listener** if it consumes; reference **S-G2** if it writes S3 with metadata." | **SNS:** `SNSEventPublisher` over `shared`'s `SNSClient` ([WatermillPubModule.java](../src/main/java/com/inttra/mercury/watermill/modules/WatermillPubModule.java) L79–81). **S3:** production code only **reads** via `WorkspaceService.getContent(...)` ([WatermillPubTask.java](../src/main/java/com/inttra/mercury/watermill/task/WatermillPubTask.java) L55) — **no metadata write**. **Listener:** uses `shared`'s `SQSListener` (one per thread, master §11 O-G1 — appianway keeps its own). | **S-G2 is NOT needed** by watermill-publisher (no S3 metadata write in production). O-G1 stays optional (it reuses `shared`'s listener). **No module-specific cloud-sdk gap** beyond what `shared` already carries. |

Net: watermill-publisher is a **standard `shared`-based SQS consumer + SNS publisher + S3 reader**. It carries **no module-specific cloud-sdk gap**; it inherits the `Message`→`QueueMessage<String>` swap and the S3/SNS/SSM rebind from `shared`. (It references S-G2 in the master index only by family; in fact it does not exercise S-G2 because it never writes S3 metadata.)

---

## 1. Executive summary

watermill-publisher consumes a pickup SQS queue, reads the referenced file from S3, transforms it (XML→protobuf), invokes the watermill gRPC publisher, and runs a DLQ redrive. Its AWS surface is entirely **`shared`-mediated**:
- **SQS (consume + send + delete):** `shared` `SQSListener` (×N threads) → local `AsyncDispatcher` → local `WatermillPubTask`; `shared` `SQSClient`/`SQSListenerClient`; `DeadLetterService` does a direct receive+redrive.
- **S3 (read only):** `shared` `WorkspaceService.getContent(bucket,key,ISO_8859_1)`.
- **SNS (publish):** `SNSEventPublisher` over `shared` `SNSClient`.
- **SSM:** `shared` `ParameterStoreModule`.
- **gRPC** publisher client (`e2open.watermill.proto`) — **not AWS, out of scope.**

Per the program directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§7), implemented so that the module **inherits the `QueueMessage<String>` chain and S3/SNS/SSM rebind from `shared`** with no module-specific cloud-sdk change, and the scratch `Test.java` is deleted.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

AWS Java SDK **v1** (`1.12.720`). Module already on Dropwizard 5-era packaging (`io.dropwizard.core.*`).

### 2.1 SQS — consume / send / delete (via `shared`)
- [`task/Task.java`](../src/main/java/com/inttra/mercury/watermill/task/Task.java) L3, L9 — `execute(List<com.amazonaws.services.sqs.model.Message>, String queueUrl)`.
- [`task/AsyncDispatcher.java`](../src/main/java/com/inttra/mercury/watermill/task/AsyncDispatcher.java) L5, L26 — `implements shared Dispatcher`; `submit(List<Message>, queueUrl)` → `WatermillPubTask.execute`.
- [`task/WatermillPubTask.java`](../src/main/java/com/inttra/mercury/watermill/task/WatermillPubTask.java) L3, L46–76 — iterates `List<Message>`; `message.getBody()` → `MetaData` (L52); `message.getReceiptHandle()` for delete (L70) and gRPC invoke (L76); injects `shared` `SQSClient`, `WorkspaceService`, `MetaData`, `Json`.
- [`modules/WatermillPubModule.java`](../src/main/java/com/inttra/mercury/watermill/modules/WatermillPubModule.java) L91–105 — builds N `shared.SQSListener(sqsClient=SQSListenerClient, wait, max, queueUrl, new AsyncDispatcher(...))`.
- [`task/DeadLetterService.java`](../src/main/java/com/inttra/mercury/watermill/task/DeadLetterService.java) L3–42 — `shared` `SQSListenerClient.receiveMessage(new ReceiveMessageRequest(sourceQueue).setWaitTimeSeconds(20).setMaxNumberOfMessages(10)).getMessages()`; per message `sqsSender.sendMessage(targetQueue, body)` + `sqsSender.deleteMessage(sourceQueue, receiptHandle)`. Redrive: `queueUrl+"_dlq"` → `queueUrl` (WatermillPubModule L110–116).

### 2.2 S3 — read only (via `shared`)
- [`WatermillPubTask.java`](../src/main/java/com/inttra/mercury/watermill/task/WatermillPubTask.java) L55 — `workspaceService.getContent(metaData.getBucket(), metaData.getFileName(), StandardCharsets.ISO_8859_1)`. **No write, no metadata.** `WorkspaceService` bound to `shared` `S3WorkspaceService` (WatermillPubModule L49).

### 2.3 SNS — publish (via `shared`)
- [`WatermillPubModule.java`](../src/main/java/com/inttra/mercury/watermill/modules/WatermillPubModule.java) L79–81 — `EventPublisher = SNSEventPublisher(snsEventConfig.topicArn, shared.SNSClient)`.

### 2.4 Client construction / SSM
- [`modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/watermill/modules/ExternalServicesModule.java) L32–43 — binds v1 `AmazonSQS` (`@Named amazonSQSForListener`/`amazonSQSForSender`), `AmazonS3`, `AmazonSNS` via `shared` `AWSClientConfiguration`; installs `shared` `ParameterStoreModule` + `NetworkRetryerModule`.

### 2.5 Scratch class (DELETE)
- [`task/Test.java`](../src/main/java/com/inttra/mercury/watermill/task/Test.java) L16–65 — `main` load-generator: `AmazonSQSClientBuilder.defaultClient()`, `AmazonS3ClientBuilder`, `s3client.putObject(bucket,key,String)`, `SendMessageRequest...withDelaySeconds(5)`. Hardcoded local path + queue URL. **Not production; delete/exclude.**

### 2.6 gRPC (NON-AWS — out of scope)
`se/StatusEventGrpcClient`, `PublisherGrpc` stubs (WatermillPubModule L56–75), `ResponseObserver`, `StatusEventProtobufTransformer`/`XMLTransformer` and type-maps. No AWS dependency.

### 2.7 Maven & tests
- `watermill-publisher/pom.xml` depends on `mercury-shared`, declares `aws-java-sdk-sqs` (`1.12.720`), and depends on `functional-testing` (test). Tests mix `junit` (4) and `junit-jupiter` (5): `DeadLetterServiceTest`, `WatermillPubTaskTest`, `WatermillPubModuleTest`, `ResponseObserverTest`, `StatusEventProtobufTransformerTest`, `AuthCredentialsTest` — the SQS ones reference v1 `Message`/queue URLs.

---

## 3. Findings

1. **Standard `shared`-based consumer.** All AWS access is through `shared` (`SQSListener`/`SQSClient`/`SQSListenerClient`/`WorkspaceService`/`SNSClient`/`ParameterStore`). The module owns only a thin local `AsyncDispatcher`/`Task`/`ListenerManager` layered on top.
2. **It is NOT independent of `shared`** (correcting Copilot): the local dispatcher delegates to `shared`'s loop and consumes the v1 `Message` type. ⇒ migrate **after `shared`**, inheriting the `Message`→`QueueMessage<String>` swap.
3. **No S3 metadata write in production** ⇒ **S-G2 unused.** The only S3 access is `getContent` (read). The only S3 write anywhere is the scratch `Test.java` (delete).
4. **`DeadLetterService`** is the one place doing a **direct** SQS receive; it maps cleanly to the migrated `SQSListenerClient`/`SQSClient` (which wrap `MessagingClient<String>`) — redrive routing preserved.
5. **`MetaData`** flows from the SQS body (`Json.fromJsonString(body, MetaData.class)`); it adopts the field-identical commons `cloud-sdk-api` `MetaData` with `shared`.
6. **Concurrency** is `shared.SQSListener` ×`listenerThreads`, each with its own `AsyncDispatcher` (here `getIdleThreadCount` just returns `maxNumberOfMessages`). This is preserved on the migrated `shared` listener; **O-G1 stays optional**.

---

## 4. Option A — keep bootstrap; ride `shared`'s migrated wrappers (DW4 retained)
Keep the publisher's own bootstrap; once `shared` migrates, the local `Task`/`AsyncDispatcher`/`DeadLetterService` element type becomes `QueueMessage<String>`; S3 read via `StorageClient`, SNS via `NotificationService`, SSM via `CloudParameterStore` — all inherited. Delete `Test.java`.
- **Pros:** minimal, mechanical (element-type swap + accessor renames `getBody→getPayload`); no framework jump.
- **Cons:** keeps bespoke DW4 base; must move in lockstep with `shared`.
- **Effort:** Low–Medium. **Risk:** Low (only the DLQ redrive needs an equivalence test).

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)
As Option A, **plus** move the application onto `commons` `InttraServer` (DW5) with the composed appianway config command (master §10). Keep all gRPC/transform logic and the local dispatcher/DLQ.
- **Pros:** platform convergence; removes bespoke DW4 base.
- **Cons:** DW4→5; lockstep with `shared`/`functional-testing`.
- **Effort:** Medium. **Risk:** Low–Medium.

## 6. Comparison matrix

| Criterion | Option A (DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 | ✅ | ✅ |
| Required cloud-sdk change | **None** | **None** |
| Impact on mercury-services | None | None |
| Effort | Low–Medium | Medium |
| Risk | Low | Low–Medium |
| Framework churn | None | DW4→5 |
| Consistency w/ mercury-services | AWS layer only | Full |

## 7. Recommendation

**Adopt Option B** per directive. watermill-publisher is a thin consumer that **inherits everything from `shared`**: the `QueueMessage<String>` chain, S3 read via `StorageClient`, SNS via `NotificationService`, SSM via `CloudParameterStore`. **No module-specific cloud-sdk change** (S-G2 not exercised — no S3 metadata write). Delete the scratch `Test.java`. Migrate **after `shared` + `functional-testing`**, alongside the watermill consumer track.

> **Residual caution:** preserve the **DLQ redrive routing** (`{queueUrl}_dlq` → `{queueUrl}`) and the `FAILED_ATTEMPTS`-style attribute round-trip exactly through `QueueMessage<String>` (attributes are `Map<String,String>` — master plan §3).

## 8. Peer review note

Verified: (a) the module is **coupled to `shared`** (local dispatcher rides `shared.SQSListener`/`SQSClient`), correcting the "own dispatcher → independent" reading — it migrates **with** `shared`; (b) `Test.java` is a scratch `main` → delete; (c) DLQ redrive `_dlq`→main confirmed, preserve; (d) production S3 is **read-only** ⇒ **S-G2 not used**; (e) `MetaData` adopts the commons type with `shared`.

## 9. Open questions / dependencies / sequencing

- **Sequence after `shared` + `functional-testing`**, with the watermill consumer track. The element-type swap is driven by `shared`'s `Message`→`QueueMessage<String>` change.
- **Confirm `Test.java` removal** with the implementing team (delete from `src/main`).
- **DLQ redrive equivalence test** (`_dlq` → main) on the migrated `SQSListenerClient`/`SQSClient`.
- **`functional-testing` fakes** must expose the migrated `shared` SQS/S3/SNS surface for `DeadLetterServiceTest`/`WatermillPubTaskTest`/`WatermillPubModuleTest`.
- Mixed JUnit 4/5 in tests: new tests on Jupiter; existing JUnit 4 via vintage during transition.

## 10. Configuration changes

Per master plan §10. watermill-publisher rides `shared`'s config composition unchanged: SQS pickup/DLQ queue URLs, `listenerThreads`, `waitTimeSeconds`/`maxNumberOfMessages` (`SQSConfig`), `snsEventConfig.topicArn`, SSM `userIdKey`/`passwordKey`. Credentials/region env/IAM via v2 default providers; `AWSClientConfiguration` per-purpose tuning (`sqs_listener`/`sqs_sender`/`s3_read_put_copy`/`sns_publish`) maps to cloud-sdk-aws config → v2 `ClientOverrideConfiguration` with the `shared` migration. Under Option B, register the composed appianway `ServerCommand` on the `InttraServer` bootstrap.

## 11. cloud-sdk gaps — reference S-G2 only (and it is **not exercised** here)

watermill-publisher requires **no module-specific cloud-sdk change**. It consumes only what `shared` already provides:

| Need | Covered by |
|---|---|
| SQS consume/send/delete + long-poll + attributes | `MessagingClient<String>` / `QueueMessage<String>` (via migrated `shared` `SQSListener`/`SQSClient`/`SQSListenerClient`) |
| S3 **read** (`getContent`) | `StorageClient` existing read API |
| SNS publish | `NotificationService` (via `shared` `SNSClient`/`SNSEventPublisher`) |
| SSM | `CloudParameterStore` (via `shared` `ParameterStoreModule`) |
| Concurrent listening | `shared` `SQSListener` ×N (appianway-owned; master §11 O-G1 optional, not required) |

**S-G2** (StorageClient metadata write overloads, master plan §11 / DESIGN §6.1) is the program's single required additive change, owned by `shared`. **watermill-publisher does not exercise S-G2** — its only production S3 access is a metadata-free read; the sole S3 *write* is in the deleted scratch `Test.java`. It is listed here only to record the family reference per the master index.
