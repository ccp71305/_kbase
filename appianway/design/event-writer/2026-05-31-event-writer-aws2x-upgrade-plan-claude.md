# `event-writer` — AWS SDK v2 (cloud-sdk) Upgrade PLAN (claude)

> Module: `event-writer` (audit sink: consumes SNS-originated events from SQS, persists them as JSON to the workspace S3 bucket) · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard 5.0.1, AWS SDK v2 BOM 2.30.24, Jackson 2.21, Guice 7). Target = **Option B**.
> This plan **references** the MASTER docs and does not duplicate them: [shared PLAN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) (esp. §0, §10, §11) and [shared DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) (esp. §5, §6). Companion: [event-writer DESIGN](2026-05-31-event-writer-aws2x-upgrade-DESIGN-claude.md).

---

## 0. What this document changes vs. the Copilot plan (critical review)

Reviewed against [`2026-05-31-event-writer-aws2x-upgrade-plan-copilot.md`](2026-05-31-event-writer-aws2x-upgrade-plan-copilot.md) and [`...-DESIGN.md`](2026-05-31-event-writer-aws2x-upgrade-DESIGN.md). The Copilot inventory (ExternalServicesModule is the only AWS binding point; Task consumes only the listener DTO) is **accurate**. Corrections below align it with the master critical-review thesis (every cloud-sdk/commons change strictly additive; appianway keeps its own listener/dispatcher; the v1 `Message` becomes `QueueMessage<String>`, not an invented `MessageRef`).

| Copilot position | Evidence | This plan |
|---|---|---|
| Lists **G1 (concurrent SQS listener)** as a module cloud-sdk "gap" | `mercury-services` consumers never used cloud-sdk's `SqsListener`; appianway keeps its own `SQSListener`+`AsyncDispatcher` re-implemented on `MessagingClient<String>` (master §0, §11 O-G1) | **Not a cloud-sdk gap.** Listener stays appianway-local. O-G1 is optional upstream only. |
| Lists **G6 (config) / G7 (health checks)** as module gaps | G6 = compose public commons transforms in an appianway command (master §10); G7 = re-point indicators to injected cloud-sdk clients | **Not cloud-sdk changes.** Handled in appianway; no library delta. event-writer has no health indicators of its own beyond shared's. |
| **G2** framed loosely ("S3 putObject with metadata/content-type") | `S3StoringMessageHandler` writes via the **`String` `putObject` overload** ([S3StoringMessageHandler.java:45-47](../src/main/java/com/inttra/mercury/eventstore/services/S3StoringMessageHandler.java)), which hardcodes `text/plain`; the artifacts are `.json` | **Confirmed = master S-G2** (the single required additive change). event-writer is the clearest motivator: it wants `application/json` content-type. No **module-specific** change. |
| `Message` → **`MessageRef`** | No such type exists in cloud-sdk; ground-truth type is `QueueMessage<String>` | **`Message` → `QueueMessage<String>`** through the retained dispatcher/task chain. |
| Option A recommended in body (header says B) | stakeholder directive | **Option B**, consistent with master. |
| "Good first service to migrate" | low-risk single S3-write path, no SNS publish, no email | **Endorsed and strengthened: event-writer is the recommended FIRST consumer rollout** after shared + functional-testing. |

Net: event-writer is a **standard service-pattern consumer** with **no module-specific cloud-sdk change**; it consumes the existing public API plus shared's additive **S-G2** (the content-type it most wants).

---

## 1. Executive summary

`event-writer` is the program's lowest-risk module: a one-way **audit sink**. The `SQSListener` (in `shared`) long-polls the inbound queue; each message is dispatched to `SQSMessageWriterTask` → `S3StoringMessageHandler`, which parses the SNS/event envelope (`SQSMessageToEventConverter`) into `List<Event>` and writes each event as a JSON object to the workspace S3 bucket. There is **no SNS publish, no SQS fan-out, no email, no DynamoDB** here. AWS surface = **SQS consume + S3 write**, all via `shared` wrappers.

Recommendation: **Option B** (master §5/§7) — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws` `1.0.26-SNAPSHOT` on Dropwizard 5; keep appianway's `SQSListener`+`AsyncDispatcher`; re-type the task chain from v1 `Message` to `QueueMessage<String>`; adopt commons `Event`/`MetaData` (field-identical). The only cloud-sdk dependency is shared's strictly-additive **S-G2** (`StorageClient.putObject` with content-type), which lets the JSON write declare `application/json`. **Recommended FIRST consumer rollout.**

---

## 2. Current state — AWS v1 inventory (verified, file:line)

AWS Java SDK v1 (`com.amazonaws.*`).

- **[`modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/eventstore/modules/ExternalServicesModule.java)** — the **only** AWS binding point:
  - `:15-16` `AmazonSQS` `@Named("amazonSQSForListener")` ← `AWSClientConfiguration.sqs_listener`
  - `:17-18` `AmazonSQS` `@Named("amazonSQSForSender")` ← `AWSClientConfiguration.sqs_sender`
  - `:19-20` `AmazonS3` ← `AWSClientConfiguration.s3_read_put_copy`
  - No `AmazonSNS` binding (no publish path).
- **[`task/SQSMessageWriterTask.java`](../src/main/java/com/inttra/mercury/eventstore/task/SQSMessageWriterTask.java)** `extends AbstractTask`; `:3` imports v1 `com.amazonaws.services.sqs.model.Message`; `:23` `process(Message, String)` → `handler.handle(message)`.
- **[`services/SQSMessageHandler.java`](../src/main/java/com/inttra/mercury/eventstore/services/SQSMessageHandler.java)** `:3,:6` interface method `handle(com.amazonaws.services.sqs.model.Message)`.
- **[`services/S3StoringMessageHandler.java`](../src/main/java/com/inttra/mercury/eventstore/services/S3StoringMessageHandler.java)**:
  - `:38-41` reads `message.getMessageId()`, `message.getReceiptHandle()`
  - `:43` `SQSMessageToEventConverter.convert(message)`
  - `:44-47` `workspaceService.putObject(bucket, composePath(event), Json.toJsonString(event))` — the **`String` `putObject` overload** (drives **S-G2**: artifacts are `.json` (`:26` `EXTENSION = ".json"`) but the v1 `String` write hardcodes `text/plain`).
- **[`services/SQSMessageToEventConverter.java`](../src/main/java/com/inttra/mercury/eventstore/services/SQSMessageToEventConverter.java)** `:3,:16` reads `sqsMessage.getBody()`; `:26-29` parses the SNS envelope via `shared` `SNSNotification` → `List<Event>` (`shared` `event/Event`).
- **pom.xml**: no direct `aws-java-sdk-*` dependency declared in this module (S3/SQS arrive transitively via `shared`). AWS clients are nonetheless **constructed** in `ExternalServicesModule` via v1 builders.

---

## 3. Findings

1. **Single binding point.** All AWS coupling is the 3 binds in `ExternalServicesModule`; everything else flows through `shared`. The module change is: (a) rebind those to factory-built cloud-sdk-aws clients (delegated to `shared` wrappers), and (b) change the DTO element type.
2. **`Message` is load-bearing across the small task chain** (`SQSMessageWriterTask` → `SQSMessageHandler` → `S3StoringMessageHandler` → `SQSMessageToEventConverter`). All four read only `getBody()`/`getMessageId()`/`getReceiptHandle()` — every accessor exists on `QueueMessage<String>` (`getPayload()`/`getMessageId()`/`getReceiptHandle()`; master §3). The swap is mechanical and compiler-driven.
3. **`SQSMessageToEventConverter` parses the SNS Event envelope** — `shared` `SNSNotification` + `Event`. Both are field-identical to commons `cloud-sdk-api` types (master §2.8), so this becomes a package change (adopt commons `Event`), not a rewrite.
4. **S3 write wants content-type.** The JSON write currently goes through the `text/plain` `String` overload; **S-G2** gives it `application/json`. This is behavior-improving but not behavior-breaking; even without S-G2 the bytes are identical (content-type metadata only).
5. **No SNS / no email / no Dynamo** ⇒ smallest possible blast radius ⇒ ideal first rollout.

---

## 4. Option A — keep `shared`/DW4, delegate wrappers to cloud-sdk-aws

Rebind `ExternalServicesModule` to the v2-backed `shared` wrappers; change the task chain element type `Message`→`QueueMessage<String>`; stay on Dropwizard 4 / JUnit 4. Smallest blast radius, fully reversible. Shares the **same** cloud-sdk consumption and the **same** single additive change (S-G2) as Option B. **Effort: Low. Risk: Low.** Documented fallback (master §4).

## 5. Option B — adopt commons + cloud-sdk-* on Dropwizard 5 (directed default)

Module-level work (atop the migrated `shared`):
1. **Rebind `ExternalServicesModule`** — the two `@Named` SQS clients map to listener (long-poll) and sender configurations of `MessagingClient<String>`; `AmazonS3` → `StorageClient`. Built by `cloud-sdk-aws` factories, Guice-bound, consumed via `shared` wrappers (master §5.1). Resolves the Copilot reviewer's "listener/sender split" note: provide two configured `MessagingClient` instances.
2. **Re-type the task chain** `Message` → `QueueMessage<String>` across `SQSMessageWriterTask`, `SQSMessageHandler`, `S3StoringMessageHandler`, `SQSMessageToEventConverter`.
3. **Adopt commons `Event`** (and `SNSNotification` equivalent) in the converter (field-identical package change).
4. **S3 JSON write** uses S-G2 content-type (`application/json`) via the `shared` `WorkspaceService` `putObject` with content-type.
5. **App bootstrap** moves to commons `InttraServer` (DW5) with the appianway config command (master §10). This is the only "large" part and is shared across all modules.

**Effort: Low–Medium (for the module itself; the DW5 lift is in `shared`/bootstrap). Risk: Low.**

## 6. Comparison

Same matrix as master §6. For event-writer specifically: both options are off-v1 with the identical cloud-sdk contract and identical single additive change (S-G2). Option B adds the DW4→5 framework move (cost borne mostly in `shared`); the per-module delta over Option A is the bootstrap/config swap. Because event-writer is the lowest-risk consumer, it is the **safest place to first exercise the full Option-B stack** end-to-end.

## 7. Recommendation

**Option B** (per directive), consumed as a normal client with exactly one strictly-additive enhancement (S-G2). Justification mirrors master §7: directive + platform convergence; provable zero-impact on mercury-services (client-only + additive S-G2 that other apps need not adopt); domain semantics preserved (commons `Event`/`MetaData` field-identical); concurrency preserved (`AsyncDispatcher`). **event-writer is the recommended FIRST consumer rollout** to validate the full stack at minimum risk.

## 8. Peer review (self-review)

- Confirmed `ExternalServicesModule` is the sole AWS binding point and the task chain reads only `getBody()/getMessageId()/getReceiptHandle()` — all present on `QueueMessage<String>` (master §3). **No `MessageRef` exists; corrected to `QueueMessage<String>`.**
- Confirmed there is **no SNS publish** in this module (Copilot's mention of SNS lineage does not apply here; no `AmazonSNS` bind).
- Confirmed the JSON write uses the `text/plain` `String` overload ⇒ S-G2 is the right (and only) additive change; without it the payload bytes are unchanged.
- Confirmed `SQSMessageToEventConverter` envelope parsing maps to commons `Event` (field-identical) — package change only.
- G1/G6/G7 reclassified as non-cloud-sdk-changes per master.

## 9. Open questions / dependencies / sequencing

- Migrate **after** `shared` + `functional-testing` (fakes re-pointed to cloud-sdk-api). Then **event-writer is the FIRST consumer** to roll out (`mvn -pl event-writer -am verify`), validating the end-to-end Option-B pattern before higher-risk modules.
- Confirm the listener/sender `MessagingClient` split (two configured instances) — see DESIGN §2/§5.
- Dev-run parity check of credential/region (master §9) can piggy-back on this first rollout.

## 10. Configuration changes

Per **master §10** (config composition). event-writer adds nothing module-specific: its `conf/event-writer.yaml` + `.properties` + `${PROFILE}`/`${ENV}` flow through the appianway `ConfigProcessingServerCommand` composing the public commons transforms (`TrimConfigCommentsTransform`, `ParameterStoreConfigTransform` for `${awsps:…}`). `AWSClientConfiguration.{sqs_listener,sqs_sender,s3_read_put_copy}` map to cloud-sdk-aws client config. No commons change (no impact to mercury-services).

## 11. cloud-sdk gaps

Reference **master §11 / shared DESIGN §6**. The only relevant item is **S-G2** (`StorageClient.putObject` content-type/metadata overload), owned and specced in `shared`. event-writer is the primary motivator (JSON content-type for the audit objects) but requires **no module-specific cloud-sdk change**: it consumes the existing public API plus shared's additive S-G2. G1/G3/G6/G7 do not apply here.
</content>
</invoke>
