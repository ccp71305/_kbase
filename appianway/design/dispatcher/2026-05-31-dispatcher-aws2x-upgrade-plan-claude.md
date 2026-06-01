# `dispatcher` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.appian-way:dispatcher:1.0` · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard 5.0.1, AWS SDK v2 BOM 2.30.24), the line `mercury-services` already runs on.
> Master references (do not duplicate): [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6.

---

## 0. What this plan changes vs. the Copilot plan (critical review)

Reviewed against [`dispatcher` plan-copilot](2026-05-31-dispatcher-aws2x-upgrade-plan-copilot.md) / [DESIGN-copilot](2026-05-31-dispatcher-aws2x-upgrade-DESIGN.md), the actual source ([`S3EventParser.java`](../src/main/java/com/inttra/mercury/dispatcher/services/S3EventParser.java), [`DispatcherTask.java`](../src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java), [`ZipPreprocessor.java`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java), [`ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/dispatcher/modules/ExternalServicesModule.java)), and the master. The governing constraint (master §0): **zero impact to existing mercury-services apps** — every cloud-sdk/commons change must be **strictly additive and behavior-preserving**.

| Copilot position | Evidence | This plan |
|---|---|---|
| **G3** — add an S3 event-notification model + parser **to cloud-sdk** as a *mandatory* gap (dispatcher is the S3→SQS gate) | dispatcher already owns [`S3EventParser`](../src/main/java/com/inttra/mercury/dispatcher/services/S3EventParser.java) + [`S3Event`](../src/main/java/com/inttra/mercury/dispatcher/model/S3Event.java); parsing the S3 event is plain JSON deserialization with a URL-decoded key. Only dispatcher needs it. | **Not a cloud-sdk gap.** dispatcher keeps a **LOCAL** S3 event parser (a dispatcher-owned record + Jackson parser) replacing `S3EventNotification.parseJson`. Tracked as **O-G3** (master §11): *optional* additive upstream of a reusable `S3EventParser` to `cloud-sdk-api/aws` for cross-program reuse by `mft-s3-aqua-appia` only. appianway does **not** depend on O-G3. |
| **G2** — "S3 putObject with metadata" listed as a module gap | [`ZipPreprocessor`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java) calls `workspaceService.putObjectWithMetaData(...)`; that path needs `StorageClient` metadata overloads | **Inherited, not module-owned.** This is the master's single required additive change **S-G2** (master §11), owned by `shared`/cloud-sdk. dispatcher just consumes it. |
| **G1 (concurrent listener), G6 (config), G7 (health) framed as dispatcher gaps** | all are shared-platform concerns | **Not dispatcher gaps.** Inherited from `shared` (master §0/§11): appianway keeps its own `SQSListener`+`AsyncDispatcher`; config is composed (master §10); health indicators re-pointed. No dispatcher-specific cloud-sdk change. |
| `Message`→`MessageRef` (a new shared adapter) | shared adopts `cloud-sdk-api` `QueueMessage<String>` directly | The v1 `com.amazonaws.services.sqs.model.Message` is replaced by **`QueueMessage<String>`** flowing through the retained Task/ErrorHandler chain — not a bespoke `MessageRef`. |
| `ObjectMetadata` / `com.amazonaws.util.IOUtils` swap framed loosely | [`ZipPreprocessor`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java:3-5) imports both | `ObjectMetadata` is only used to set content-length before a `putObjectWithMetaData(bytes,...)` call → drop it entirely (length derived from the byte[]). `com.amazonaws.util.IOUtils.toByteArray` → `software.amazon.awssdk.utils.IoUtils` or `java.io`/Guava. Mechanical. |

**Net:** dispatcher is a **standard consumer migration plus one module-local concern** — replacing the v1 `S3EventNotification` parser with a dispatcher-owned parser. **No required cloud-sdk change originates in dispatcher**; it relies only on shared's **S-G2**.

---

## 1. Executive summary

`dispatcher` is the **S3→SQS routing gate**: it consumes S3 `ObjectCreated` notifications (raw S3→SQS or S3→SNS→SQS), copies the inbound object into the workspace bucket, resolves the archive-format type and MFT id from the key, optionally unzips, and routes a `MetaData` envelope to the correct splitter queue while emitting lineage events.

Per directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws` (`1.0.26-SNAPSHOT`) on Dropwizard 5** (§7), implemented so that:
1. dispatcher consumes cloud-sdk **as a client only**; the sole required library change is shared's additive **S-G2** (storage metadata overloads), used by [`ZipPreprocessor.putObjectWithMetaData`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java:102);
2. the v1 `S3EventNotification.parseJson` is replaced by a **dispatcher-local** record + Jackson parser (DESIGN §6) — no cloud-sdk dependency;
3. the v1 `Message` element becomes `QueueMessage<String>` through the retained Task/ErrorHandler chain inherited from `shared`;
4. all domain orchestration (preprocessors, router, lineage events, error codes) is preserved.

---

## 2. Current state — AWS v1 inventory (with file:line)

AWS Java SDK **v1** (`com.amazonaws.*`, `1.12.720`); Dropwizard `dropwizard-core` and `aws-java-sdk-sqs` declared in [`pom.xml`](../pom.xml:47-51).

### 2.1 Client construction (Guice)
- [`ExternalServicesModule.java:40-47`](../src/main/java/com/inttra/mercury/dispatcher/modules/ExternalServicesModule.java) binds via v1 builders:
  - `AmazonSQS @Named("amazonSQSForListener")` ← `AWSClientConfiguration.sqs_listener`
  - `AmazonSQS @Named("amazonSQSForSender")` ← `AWSClientConfiguration.sqs_sender`
  - `AmazonS3` ← `AWSClientConfiguration.s3_read_put_copy`
  - `AmazonSNS` ← `AWSClientConfiguration.sns_publish`
  - Imports: [`ExternalServicesModule.java:3-8`](../src/main/java/com/inttra/mercury/dispatcher/modules/ExternalServicesModule.java) (`AmazonS3(ClientBuilder)`, `AmazonSNS(ClientBuilder)`, `AmazonSQS(ClientBuilder)`).

### 2.2 S3-event parsing (module-unique)
- [`S3EventParser.java:3,20-30`](../src/main/java/com/inttra/mercury/dispatcher/services/S3EventParser.java): `com.amazonaws.services.s3.event.S3EventNotification.parseJson(json)` → first record → bucket name, **URL-decoded** key (`URLDecoder.decode(...,"UTF-8")`), `getSizeAsLong()`, formatted event time → [`S3Event`](../src/main/java/com/inttra/mercury/dispatcher/model/S3Event.java).
- The SNS envelope is unwrapped first in [`DispatcherTask.getS3EventFromSNSMessage`](../src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java:173-176): the SQS body is parsed as `SNSNotification`, then `.getMessage()` (the inner S3 event JSON) is handed to the parser. So both raw-S3→SQS and S3→SNS→SQS envelopes must be handled.

### 2.3 SQS DTO leak through the task chain
- [`DispatcherTask.java:3,73`](../src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java): `process(com.amazonaws.services.sqs.model.Message, String queueUrl)`; reads `message.getBody()` ([:174,:183](../src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java)). Extends shared [`AbstractTask`](../../shared/src/main/java/com/inttra/mercury/shared/task/AbstractTask.java:20) whose `process(Message,...)` and `deleteMessage` are v1-typed.
- [`DispatcherErrorHandler`](../src/main/java/com/inttra/mercury/dispatcher/errors/DispatcherErrorHandler.java) extends shared [`ErrorHandler`](../../shared/src/main/java/com/inttra/mercury/shared/task/ErrorHandler.java) whose `handleException(Message, ...)` is v1-typed (the `FAILED_ATTEMPTS` retry path reads message attributes via `ErrorHelper`).
- [`ZipPreprocessor.java:4,46`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java) and [`PreProcessor`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/PreProcessor.java) pass the v1 `Message` through.

### 2.4 S3 object I/O via shared
- Copy inbound→workspace: [`DispatcherTask.copyInitialFileToWorkspace`](../src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java:191-198) → `workspaceService.copyObject(srcBucket,srcKey,dstBucket,dstKey)` (plain copy — **no metadata** → existing `StorageClient.copyObject` suffices).
- Metadata read: [`DispatcherTask.java:92`](../src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java) `workspaceService.getMetaData(bucket,key)` → `Map<String,String>` (already non-v1 on the shared facade boundary).
- Zip path: [`ZipPreprocessor.java:59,102`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java) `getS3InputStream(...)` and `putObjectWithMetaData(bucket,key,bytes,Map)` → **the one S-G2 dependency** (write user metadata).

### 2.5 v1 utility leaks (zip path)
- [`ZipPreprocessor.java:3`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java) `com.amazonaws.services.s3.model.ObjectMetadata` — only used at [:72-73](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java) to set content-length, then **discarded** (the actual write uses `putObjectWithMetaData(bytes,...)`). Removable.
- [`ZipPreprocessor.java:5,75`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java) `com.amazonaws.util.IOUtils.toByteArray(is)` → `software.amazon.awssdk.utils.IoUtils.toByteArray` (or Guava `ByteStreams`).

### 2.6 Routing / domain (keep, no AWS)
- [`RouterManager`](../src/main/java/com/inttra/mercury/dispatcher/routers/RouterManager.java) maps `FILE_TYPE`→queue from `routeMappings`; [`DispatcherTask`](../src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java) sends via `SQSClient.sendMessage(url, body)` and logs lineage via `EventLogger`. No v1 types beyond the `Message` element.

### 2.7 Config
- [`conf/dispatcher.yaml`](../conf/dispatcher.yaml): `sqsPickupConfig` (wait=20s, max=10), `sqsRouteMappingConfig`, `sqsErrorConfig`, `snsEventConfig`, `s3WorkspaceConfig`, `s3InboundPickupConfig`, `bookingBridgeConfig`, `networkServiceConfig`, DW `server`/`logging`/`metrics` — all `${placeholder}` driven.

---

## 3. Findings

- dispatcher's only **module-unique** AWS surface is **S3 event-notification parsing** ([`S3EventParser`](../src/main/java/com/inttra/mercury/dispatcher/services/S3EventParser.java)). Everything else is the standard consumer pattern (rebind module, swap `Message`→`QueueMessage<String>`, route S3 I/O through the shared `WorkspaceService`).
- The parser is **plain JSON + URL-decode + first-record extraction**; AWS SDK v2 core has **no drop-in `S3EventNotification` model**. Pulling the external `software.amazon.awssdk:s3-event-notifications` artifact (Copilot option a) adds dependency surface for ~30 lines of parsing. A **dispatcher-local record + Jackson parser** is simpler, dependency-free, and keeps the URL-decode and SNS-unwrap behavior exactly.
- The zip-preprocessor write is the **only metadata-bearing S3 write** in dispatcher → it is the consumer of shared's **S-G2**. The copy in `copyInitialFileToWorkspace` is metadata-less → no new overload needed there.
- `getSizeAsLong()` from the v1 model maps to the `s3.object.size` field in the event JSON (a `long`). The local record must expose it for [`S3Event.isValid()`](../src/main/java/com/inttra/mercury/dispatcher/model/S3Event.java:14) (`size > 0`, the zero-byte guard).

---

## 4. Option A — keep `shared`/DW4, delegate wrappers to cloud-sdk

Rebind [`ExternalServicesModule`](../src/main/java/com/inttra/mercury/dispatcher/modules/ExternalServicesModule.java) to the cloud-sdk factories; swap the `Message` element to `QueueMessage<String>` through the retained chain; replace the v1 `S3EventNotification` parser with the dispatcher-local parser; drop `ObjectMetadata`/`IOUtils`. Stay on Dropwizard 4 / JUnit 4. Same cloud-sdk consumption and same single additive change (S-G2) as Option B.
- **Pros:** smallest blast radius; no framework jump; reversible. **Cons:** keeps appianway's bespoke DW4 base. **Effort:** Low–Medium (parser is the only extra). **Risk:** Low–Medium.

## 5. Option B — adopt `commons` + cloud-sdk on Dropwizard 5 (directed default)

As Option A, plus the platform move: bind via `MessagingClientFactory`/`StorageClientFactory`/`NotificationClientFactory` (mirroring `mercury-services` `BookingMessagingModule`), run on `commons` `InttraServer` (DW5) with the appianway composed config command (master §10), new tests in JUnit 5. dispatcher business logic (preprocessors, router, lineage, error codes) is unchanged.
- **Pros:** platform convergence; one AWS abstraction; shared CVE/Jackson cadence. **Cons:** inherits the DW4→5 cost from `shared`; functional-testing rework. **Effort:** Medium. **Risk:** Medium (mostly inherited from `shared`).

## 6. Comparison

| Criterion | Option A | Option B |
|---|---|---|
| Off AWS v1 | ✅ | ✅ |
| Required cloud-sdk change | S-G2 (additive, shared-owned) | S-G2 (additive, shared-owned) |
| dispatcher-originated cloud-sdk change | **none** (O-G3 optional) | **none** (O-G3 optional) |
| Impact on mercury-services | none | none |
| Framework churn | none | DW4→5 (inherited) |
| Effort / Risk | Low–Med / Low–Med | Med / Med |

## 7. Recommendation

**Option B** per directive. dispatcher is a clean consumer migration: rebind the module to cloud-sdk factories, swap the SQS element type to `QueueMessage<String>`, and replace the v1 S3-event parser with a **dispatcher-local** parser. The **only** library dependency is shared's additive **S-G2**; dispatcher introduces **no** cloud-sdk change of its own (O-G3 is optional and not depended on). This preserves the zero-impact guarantee for mercury-services.

## 8. Peer review

Self-reviewed against the dispatcher source (S3EventParser, DispatcherTask, ZipPreprocessor, ExternalServicesModule, S3Event), the master plan/DESIGN (§0/§10/§11 and §5/§6), and the Copilot drafts. Key corrections recorded in §0: S3-event parsing is **dispatcher-local (O-G3 optional)**, not a mandatory cloud-sdk gap (G3); the metadata-write need is the **inherited** S-G2, not a dispatcher gap; `Message`→`QueueMessage<String>`, not a bespoke `MessageRef`; `ObjectMetadata` is removable (length from the byte[]).

## 9. Open questions / sequencing

- Migrate **after** `shared` + `functional-testing`, and after the pilot (`event-writer`) so the standard pattern is proven before the S3-event nuance.
- Pin a **real captured S3 event** (both raw-S3→SQS and S3→SNS→SQS) as a test fixture to lock the local parser's behavior (URL-decoded key, `size`, event time).
- Confirm `software.amazon.awssdk.utils.IoUtils` stream-close semantics match `com.amazonaws.util.IOUtils` for the zip loop.
- Keep the `QueueMessage`/`StorageClient`/S3-event contract aligned with `mft-s3-aqua-appia` (separate workspace) if O-G3 is ever upstreamed.

## 10. Configuration

Reference master [§10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md). Module specifics from [`conf/dispatcher.yaml`](../conf/dispatcher.yaml): the long-poll `sqsPickupConfig` (`waitTimeSeconds:20`, `maxNumberOfMessages:10`) maps to `ReceiveMessageOptions`; `sqsRouteMappingConfig`/`bookingBridgeConfig` queue URLs and `s3WorkspaceConfig`/`s3InboundPickupConfig` buckets are placeholder-resolved unchanged; `${PROFILE}`/`${ENV}` resource naming and `${awsps:...}` SSM resolution unchanged. No placeholder change required. DW5 `server`/`logging` keys move to `io.dropwizard.core.*` packaging — verify the YAML server/connector block parses under DW5.

## 11. cloud-sdk gaps

Reference master [§11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md).
- **S-G2** (required, additive, **shared-owned**): `StorageClient` `putObject(...,Map metadata,String contentType)` overload — consumed by [`ZipPreprocessor.putObjectWithMetaData`](../src/main/java/com/inttra/mercury/dispatcher/preprocessor/ZipPreprocessor.java:102). dispatcher relies on it; it does not own it.
- **O-G3** (optional, additive, **local in dispatcher**): a reusable `S3EventRecord` + `S3EventParser` could be upstreamed to `cloud-sdk-api/aws` for `mft-s3-aqua-appia` reuse. appianway **does not depend on it** — dispatcher ships its own local parser (DESIGN §6). This is the explicit correction vs Copilot's mandatory-G3 framing.
- No dispatcher-originated S-Gn. G1/G6/G7 are inherited shared/platform concerns, not dispatcher gaps.
