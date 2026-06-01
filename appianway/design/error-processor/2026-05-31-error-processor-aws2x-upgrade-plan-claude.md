# `error-processor` — AWS SDK v2 (cloud-sdk) Upgrade PLAN (claude)

> Module: `error-processor` (fan-in consumer of `sqs_subscription_errors`: archives the failed MetaData/payload to S3, then fans out to email by posting to the email-sender queue) · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard 5.0.1, AWS SDK v2 BOM 2.30.24, Jackson 2.21, Guice 7). Target = **Option B**.
> References the MASTER docs (no duplication): [shared PLAN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [shared DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6. Companion: [error-processor DESIGN](2026-05-31-error-processor-aws2x-upgrade-DESIGN-claude.md).

---

## 0. What this document changes vs. the Copilot plan (critical review)

Reviewed against [`2026-05-31-error-processor-aws2x-upgrade-plan-copilot.md`](2026-05-31-error-processor-aws2x-upgrade-plan-copilot.md) and [`...-DESIGN.md`](2026-05-31-error-processor-aws2x-upgrade-DESIGN.md). The Copilot inventory is **accurate** (single binding point; standard-consumer profile; the reviewer's note about avoiding an archive-write loop is correct and preserved). Corrections to align with the master critical-review thesis:

| Copilot position | Evidence | This plan |
|---|---|---|
| **G1 (concurrent SQS listener)** listed as a module gap | appianway keeps its own `SQSListener`+`AsyncDispatcher` on `MessagingClient<String>` (master §0, O-G1) | **Not a cloud-sdk gap.** Listener stays appianway-local. |
| **G6 (config) / G7 (health checks)** listed as module gaps | compose public commons transforms (master §10); re-point indicators to injected clients | **Not cloud-sdk changes.** Handled in appianway. |
| **G2** "S3 archive putObject with metadata" | `ErrorProcessorTask.saveEventMetaData` writes via the **`String` `putObject` overload** ([ErrorProcessorTask.java:76](../src/main/java/com/inttra/mercury/error/processor/task/ErrorProcessorTask.java)) — `message.getBody()` (a JSON MetaData string) | **Confirmed = master S-G2.** No module-specific change; if content-type/metadata is wanted on the archive object, the S-G2 overload covers it. |
| `Message` → **`MessageRef`** | no such type; ground-truth is `QueueMessage<String>` | **`Message` → `QueueMessage<String>`** through the retained chain. `FAILED_ATTEMPTS` round-trips as a `String` attribute (master §3). |
| "no direct SES here; email via the email-sender queue" | `sendMailMessageToSQS` posts JSON to the drop-off queue ([ErrorProcessorTask.java:86-89](../src/main/java/com/inttra/mercury/error/processor/task/ErrorProcessorTask.java)) | **Confirmed.** Fan-out = `MessagingClient.sendMessage` to the email-sender queue; no SES, no `NotificationService` publish for the fan-out. |
| Option A recommended in body (header says B) | stakeholder directive | **Option B.** |

Net: error-processor is a **standard service-pattern consumer** (fan-in → S3 archive → SQS fan-out to email) with **no module-specific cloud-sdk change** — it consumes the existing public API plus shared's additive **S-G2**.

---

## 1. Executive summary

`error-processor` is the program's **error sink**: the `shared` `SQSListener` long-polls `sqs_subscription_errors`; `ErrorProcessorTask` parses the `MetaData` envelope, **archives** the failed payload to S3 (`WorkspaceService.putObject`), then **fans out** one email request per configured recipient by `sendMessage`-ing a target `MetaData` to the email-sender drop-off queue. On failure it delegates to `ErrorProcessorErrorHandler` (a thin subclass of `shared` `ErrorHandler`). AWS surface = **SQS consume + SQS send + S3 write** (note: `ExternalServicesModule` also binds `AmazonSNS`, but the task itself performs no SNS publish — see §2). All AWS access is via `shared` wrappers.

Recommendation: **Option B** (master §5/§7). Keep `SQSListener`+`AsyncDispatcher`; re-type the chain to `QueueMessage<String>`; adopt commons `MetaData`/`Event`; the archive write uses shared's additive **S-G2**. Low-risk; good early rollout **after** `event-writer`.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

- **[`modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/error/processor/modules/ExternalServicesModule.java)** — the only AWS binding point:
  - `:20-21` `AmazonS3` with a **no-retries** `ClientConfiguration().withMaxErrorRetry(0)` (note: error-processor deliberately disables S3 SDK retries; preserve this when mapping to cloud-sdk-aws config).
  - `:22-23` `AmazonSQS` `@Named("amazonSQSForListener")` ← `AWSClientConfiguration.sqs_listener`
  - `:24-25` `AmazonSQS` `@Named("amazonSQSForSender")` ← `AWSClientConfiguration.sqs_sender`
  - `:26` `AmazonSNS` with the same no-retries config (**bound but not used by the task** — fan-out is via SQS; the bind exists for `shared`'s `EventLogger`/`SNSClient` lineage path).
- **[`task/ErrorProcessorTask.java`](../src/main/java/com/inttra/mercury/error/processor/task/ErrorProcessorTask.java)** `extends AbstractTask`:
  - `:3` imports v1 `com.amazonaws.services.sqs.model.Message`; `:56` `process(Message, String)`.
  - `:59` `Json.fromJsonString(message.getBody(), MetaData.class)`.
  - `:74-78` `saveEventMetaData`: `workspaceService.putObject(bucket, rootWorkflowId/uuid, message.getBody())` — **`String` `putObject` overload** (the **S-G2** site; archives the JSON MetaData).
  - `:86-89` `sendMailMessageToSQS`: `sqsClient.sendMessage(dropOffQueueUrl, Json.toJsonString(metaData))` — **email fan-out via SQS**.
  - `:109-120` `publishCloseRunEvent`: `eventLogger.logCloseRunEvent(..., message.getBody(), ...)` (lineage via `shared` `EventLogger`).
  - `:69-70` on failure: `errorHandler.handleException(message, ...)`.
- **[`task/ErrorProcessorErrorHandler.java`](../src/main/java/com/inttra/mercury/error/processor/task/ErrorProcessorErrorHandler.java)** — thin subclass of `shared` `ErrorHandler` (`:11`), composing `ErrorHelper`/`EventLogger`. No AWS types of its own; inherits the `FAILED_ATTEMPTS` retry/delete semantics from `shared`.
- **[`services/ErrorDetailsService.java`](../src/main/java/com/inttra/mercury/error/processor/services/ErrorDetailsService.java)** — no AWS types (domain helper).
- **pom.xml**: declares `aws-java-sdk-sqs` directly ([pom.xml:45-46](../pom.xml)); S3/SNS arrive transitively via `shared`.

---

## 3. Findings

1. **Single binding point + small chain.** `ExternalServicesModule` binds; `ErrorProcessorTask` is the only consumer of the v1 `Message`. Reads only `getBody()` (and `ErrorHelper` reads `getMessageAttributes().get(FAILED_ATTEMPTS)`, `getReceiptHandle()`, `getMessageId()` in `shared`) — all present on `QueueMessage<String>` (master §3). The `FAILED_ATTEMPTS` counter round-trips as a `String` attribute (master §3, confirmed compatible).
2. **Archive write = the S-G2 site.** `saveEventMetaData` uses the `text/plain` `String` overload to store a JSON MetaData blob. S-G2's content-type/metadata overload covers this if desired; functionally the archived bytes are identical.
3. **Fan-out is SQS, not SES/SNS.** Email is requested by posting a target `MetaData` to the email-sender drop-off queue via `MessagingClient.sendMessage`. No direct SES in this module. `AmazonSNS` is bound only for `shared`'s lineage/`EventLogger` path → maps to `NotificationService` in the migrated `shared`.
4. **No-retries config must be preserved.** `ExternalServicesModule` builds S3/SNS with `withMaxErrorRetry(0)`. When rebinding to cloud-sdk-aws, map this to a zero-retry `ClientOverrideConfiguration`/retry policy so the error sink's "fail fast, let the listener re-deliver" behavior is unchanged.
5. **Error-sink loop caution (Copilot reviewer note — preserved).** error-processor is itself the error sink; if the archive write fails, the existing `RecoverableException`/delete semantics in `shared` `ErrorHandler` must survive the wrapper swap unchanged (no new behavior). Covered by a failure-path test (§DESIGN §8).
6. **`MetaData`/`Event` are field-identical to commons** (master §2.8) ⇒ adopt as a package change.

---

## 4. Option A — keep `shared`/DW4, delegate wrappers

Rebind `ExternalServicesModule` to v2-backed `shared` wrappers (preserving no-retries); `Message`→`QueueMessage<String>`; DW4/JUnit4. Smallest blast radius, reversible. Same cloud-sdk consumption + same single additive change (S-G2) as Option B. **Effort: Low. Risk: Low.** Documented fallback (master §4).

## 5. Option B — adopt commons + cloud-sdk-* on Dropwizard 5 (directed default)

Module work atop migrated `shared`:
1. **Rebind `ExternalServicesModule`** — two `@Named` SQS clients → listener/sender `MessagingClient<String>`; `AmazonS3` → `StorageClient` (preserve `maxErrorRetry(0)`); `AmazonSNS` → `NotificationService` (for `shared` lineage). Factory-built, Guice-bound, consumed via `shared` wrappers.
2. **Re-type** `ErrorProcessorTask.process` and helpers `Message`→`QueueMessage<String>`.
3. **Adopt commons `MetaData`/`Event`** (field-identical package change).
4. **Archive write** uses S-G2 (optional content-type/metadata; bytes unchanged).
5. **App bootstrap** → commons `InttraServer` (DW5) + appianway config command (master §10), shared across modules.

**Effort: Low–Medium. Risk: Low.**

## 6. Comparison

Master §6 matrix applies. For error-processor both options are off-v1 with identical cloud-sdk contract and identical single additive change (S-G2). Option B's per-module delta over A is the bootstrap/config swap; the no-retries S3 config and the error-sink delete semantics are preserved in both.

## 7. Recommendation

**Option B** (per directive), consumed as a normal client with exactly one strictly-additive enhancement (S-G2). Justification per master §7. error-processor is a clean low-risk consumer; roll out **after `event-writer`** in the first wave.

## 8. Peer review (self-review)

- Confirmed single AWS binding point; only `ErrorProcessorTask` consumes `Message` (reads `getBody()`); `shared` `ErrorHelper` reads attributes/receipt/id — all on `QueueMessage<String>`. **`MessageRef` corrected to `QueueMessage<String>`.**
- Confirmed **fan-out is SQS** (`sendMessage` to drop-off queue), not SES/SNS; `AmazonSNS` bound only for lineage → `NotificationService`.
- Confirmed the **`withMaxErrorRetry(0)`** S3/SNS config must be preserved in the cloud-sdk-aws mapping.
- Confirmed the archive write is the `String` `putObject` overload ⇒ S-G2 site; bytes unchanged.
- **Error-sink loop note preserved:** verify `RecoverableException`/delete semantics survive the wrapper swap (failure-path test).
- G1/G6/G7 reclassified as non-cloud-sdk-changes per master.

## 9. Open questions / dependencies / sequencing

- Migrate **after** `shared` + `functional-testing`; roll out **after `event-writer`** (`mvn -pl error-processor -am verify`).
- Confirm cloud-sdk-aws zero-retry mapping for the S3/SNS clients (preserve `maxErrorRetry(0)`).
- Confirm the failure-path (archive-write failure → no delete → re-delivery) behaves identically post-swap.

## 10. Configuration changes

Per **master §10**. No module-specific config design beyond preserving the **no-retries** S3/SNS client config in the cloud-sdk-aws mapping. `conf/error-processor.yaml` + `.properties` + `${PROFILE}`/`${ENV}` + `${awsps:…}` flow through the appianway config command composing public commons transforms. Recipient list (`getErrorEmailRecipient`) and drop-off/pickup queue URLs are plain config, unchanged. Zero commons change.

## 11. cloud-sdk gaps

Reference **master §11 / shared DESIGN §6**. Only **S-G2** is relevant (archive `putObject` with optional content-type/metadata), owned and specced in `shared`. **No module-specific cloud-sdk change required:** error-processor consumes the existing public API (`MessagingClient.sendMessage`/`receiveMessages`/`deleteMessage`, `StorageClient.putObject`, `NotificationService`) plus shared's additive S-G2. G1/G3/G6/G7 do not apply.
</content>
