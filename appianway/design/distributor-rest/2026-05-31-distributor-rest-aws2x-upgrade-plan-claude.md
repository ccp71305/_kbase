# `distributor-rest` — AWS SDK v2 (cloud-sdk) Upgrade PLAN (claude)

> Module: `distributor-rest` (REST/HTTP egress: consumes SQS, reads the payload from S3, POSTs it to subscriber endpoints with an OAuth bearer token) · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard 5.0.1, AWS SDK v2 BOM 2.30.24, Jackson 2.21, Guice 7). Target = **Option B**.
> References the MASTER docs (no duplication): [shared PLAN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [shared DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6. Companion: [distributor-rest DESIGN](2026-05-31-distributor-rest-aws2x-upgrade-DESIGN-claude.md).

---

## 0. What this document changes vs. the Copilot plan (critical review)

Reviewed against [`2026-05-31-distributor-rest-aws2x-upgrade-plan-copilot.md`](2026-05-31-distributor-rest-aws2x-upgrade-plan-copilot.md) and [`...-DESIGN.md`](2026-05-31-distributor-rest-aws2x-upgrade-DESIGN.md). Copilot's key correction — distributor-rest is a **standard consumer** (binds SQS/S3/SNS in its own `ExternalServicesModule`), not DTO-only, and the HTTP/OAuth egress is non-AWS and out of scope — is **accurate and retained**. Corrections to align with the master critical-review thesis:

| Copilot position | Evidence | This plan |
|---|---|---|
| **G1 (concurrent SQS listener)** listed as a module gap | appianway keeps its own `SQSListener`+`AsyncDispatcher` on `MessagingClient<String>` (master §0, O-G1) | **Not a cloud-sdk gap.** Listener stays appianway-local. |
| **G2 (S3 putObject with metadata)** listed as a module gap | distributor-rest only **reads** S3 (`getContent(...ISO_8859_1)` — [DistributorTask.java:76](../src/main/java/com/inttra/mercury/distributorrest/task/DistributorTask.java)); it performs **no S3 write/copy** | **S-G2 does not even apply to this module.** It uses the existing `StorageClient.getContent(bucket,key,charset)` read API. |
| **G6 (config) / G7 (health checks)** listed as module gaps | compose public commons transforms (master §10); re-point indicators to injected clients | **Not cloud-sdk changes.** Handled in appianway. |
| `Message` → **`MessageRef`** | no such type; ground-truth is `QueueMessage<String>` | **`Message` → `QueueMessage<String>`** through the retained chain. |
| Option A recommended in body (header says B) | stakeholder directive | **Option B.** |

Net: distributor-rest is a **standard service-pattern consumer** that uses the AWS surface only for SQS consume + **S3 read** + SNS lineage; the OAuth/HTTP egress (Jersey/JAX-RS + retry) is local and untouched. **No module-specific cloud-sdk change, and even S-G2 is not exercised here** (read-only S3) — it relies on `shared` + the existing public cloud-sdk-api.

---

## 1. Executive summary

`distributor-rest` consumes a `MetaData` envelope from SQS (`shared` `SQSListener`), **reads** the referenced payload from S3 (`WorkspaceService.getContent` in ISO-8859-1), looks up the subscriber's `Subscription`, builds a `Request`, and **POSTs** the payload to the subscriber endpoint with an OAuth bearer token via a Jersey/JAX-RS `RestServiceClient` (with a `Retryer`). On success it logs a close-run lineage event; on `NonRecoverableException`/`IOException` it delegates to `shared` `ErrorHandler`. AWS surface = **SQS consume + S3 read + SNS lineage**, all via `shared`. The HTTP/OAuth egress is **not AWS** and is unchanged.

Recommendation: **Option B** (master §5/§7). Keep `SQSListener`+`AsyncDispatcher`; re-type the chain to `QueueMessage<String>`; adopt commons `MetaData`/`Event`. **No module-specific cloud-sdk change; S-G2 not exercised** (S3 read-only). Sequence with the hot egress group (alongside `distributor`), after the lower-risk `event-writer`/`error-processor`.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

- **[`modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/distributorrest/modules/ExternalServicesModule.java)** — the only AWS binding point:
  - `:45-46` `AmazonSQS` `@Named("amazonSQSForListener")` ← `AWSClientConfiguration.sqs_listener`
  - `:47-48` `AmazonSQS` `@Named("amazonSQSForSender")` ← `AWSClientConfiguration.sqs_sender`
  - `:49-50` `AmazonS3` ← `AWSClientConfiguration.s3_read_put_copy`
  - `:51-52` `AmazonSNS` ← `AWSClientConfiguration.sns_publish`
  - `:79-91` Jersey `Client` (`jerseyClient`/`jerseyRestClient` with connect/read timeouts) and `:71-73` a `@Named("RestRetry")` `Retryer` — **non-AWS HTTP egress wiring, unchanged**. `ParameterStoreModule` (`:68`) and `NetworkRetryerModule` (`:70`) installed.
- **[`task/DistributorTask.java`](../src/main/java/com/inttra/mercury/distributorrest/task/DistributorTask.java)** `extends AbstractTask`:
  - `:3` imports v1 `com.amazonaws.services.sqs.model.Message`; `:65` `process(Message, String)`.
  - `:68` `Json.fromJsonString(message.getBody(), MetaData.class)`.
  - `:76-77` `workspaceService.getContent(bucket, fileName, StandardCharsets.ISO_8859_1)` — **S3 READ only** (no write/copy; S-G2 not used).
  - `:78-81` `subscriptionService.findSubscriptions(...)` → `requestBuilder.build(...)` → `restServiceClient.post(request, fileContent)` — **OAuth/HTTP egress, unchanged**.
  - `:85-87`, `:95-106` `eventLogger.logCloseRunEvent(..., message.getBody(), ...)` (lineage via `shared` `EventLogger`).
  - `:89-92` on failure: `errorHandler.handleException(message, ...)`.
- **[`auth/AuthClient.java`](../src/main/java/com/inttra/mercury/distributorrest/auth/AuthClient.java)**, **[`task/RestServiceClient.java`](../src/main/java/com/inttra/mercury/distributorrest/task/RestServiceClient.java)**, `OAuthRequest`, `Request`, `RequestBuilder`, `e2net/*` — **OAuth/HTTP egress; non-AWS; untouched.**
- **pom.xml**: declares `aws-java-sdk-sqs` directly ([pom.xml:46-47](../pom.xml)); S3/SNS arrive transitively via `shared`.

---

## 3. Findings

1. **Single AWS binding point** (`ExternalServicesModule`); `DistributorTask` is the only consumer of v1 `Message`, reading only `getBody()` — present on `QueueMessage<String>` (`getPayload()`; master §3). `shared` `ErrorHelper` reads attributes/receipt/id (also on `QueueMessage<String>`).
2. **S3 is read-only here.** `getContent(bucket,key,charset)` already exists on the public `StorageClient`/`shared` `WorkspaceService` (master §3) ⇒ **S-G2 is not exercised** by distributor-rest.
3. **The whole egress half is non-AWS** — Jersey client, OAuth bearer (`AuthClient`), `Retryer`, subscriber endpoints. Keep the migration strictly at the AWS boundary; do not touch egress logic.
4. **`MetaData`/`Event` are field-identical to commons** (master §2.8) ⇒ adopt as a package change.
5. **ISO-8859-1 charset must be preserved** on the S3 read (binary-safe payload handling for the HTTP POST body); the cloud-sdk `getContent(bucket,key,Charset)` overload covers it.

---

## 4. Option A — keep `shared`/DW4, delegate wrappers

Rebind `ExternalServicesModule` AWS clients to v2-backed `shared` wrappers; `Message`→`QueueMessage<String>`; leave Jersey/OAuth egress untouched; DW4/JUnit4. Smallest blast radius; reversible. Same cloud-sdk consumption as B (and S-G2 not needed). **Effort: Low–Medium. Risk: Low–Medium** (only because it sits on the hot egress path). Documented fallback (master §4).

## 5. Option B — adopt commons + cloud-sdk-* on Dropwizard 5 (directed default)

Module work atop migrated `shared`:
1. **Rebind `ExternalServicesModule`** AWS binds — two `@Named` SQS → listener/sender `MessagingClient<String>`; `AmazonS3` → `StorageClient`; `AmazonSNS` → `NotificationService` (lineage). Jersey `Client`, `Retryer`, `ParameterStoreModule`, `NetworkRetryerModule` **unchanged**.
2. **Re-type** `DistributorTask.process` and helpers `Message`→`QueueMessage<String>`.
3. **Adopt commons `MetaData`/`Event`** (field-identical package change).
4. **S3 read** uses the existing `getContent(bucket,key,ISO_8859_1)` (no S-G2).
5. **App bootstrap** → commons `InttraServer` (DW5) + appianway config command (master §10), shared across modules.

**Effort: Low–Medium. Risk: Low–Medium (hot egress path).**

## 6. Comparison

Master §6 matrix applies. For distributor-rest both options are off-v1 with identical cloud-sdk consumption; **neither needs S-G2** (read-only S3). Risk is slightly elevated only because it sits on the live subscriber-delivery path, so it sequences after the lower-risk audit/error modules. The non-AWS egress is identical under both options.

## 7. Recommendation

**Option B** (per directive), consumed as a normal client; **no cloud-sdk change, S-G2 not exercised**. Justification per master §7. Migrate with the hot egress group (alongside `distributor`) **after** `event-writer`/`error-processor`. Strict AWS-boundary-only scope keeps the OAuth/HTTP delivery path safe.

## 8. Peer review (self-review)

- Confirmed the standard-consumer classification (binds SQS/S3/SNS in `ExternalServicesModule`); HTTP/OAuth egress is non-AWS and out of scope (retained from Copilot's correction).
- Confirmed **S3 is read-only** (`getContent`) ⇒ **S-G2 listed by Copilot does not apply** to this module.
- Confirmed `DistributorTask` reads only `getBody()`; **`MessageRef` corrected to `QueueMessage<String>`**.
- Confirmed the **ISO-8859-1** charset on the read must be preserved (binary-safe POST body).
- G1/G6/G7 reclassified as non-cloud-sdk-changes per master.

## 9. Open questions / dependencies / sequencing

- Migrate **after** `shared` + `functional-testing`; roll out **after** the low-risk `event-writer`/`error-processor`, with the hot egress group (alongside `distributor`) (`mvn -pl distributor-rest -am verify`).
- Confirm the ISO-8859-1 `getContent` overload mapping in the migrated `shared` `WorkspaceService`.
- Verify WireMock/JAX-RS egress tests stay green (no egress-logic change).

## 10. Configuration changes

Per **master §10**. No module-specific AWS config design. Subscriber-endpoint, OAuth (`AuthClient`/client-id/secret via `ParameterStoreModule`), and Jersey timeout config (`RestClientConfig`) are **non-AWS and unchanged**. `conf/distributor-rest.yaml` + `.properties` + `${PROFILE}`/`${ENV}` + `${awsps:…}` flow through the appianway config command composing public commons transforms. Zero commons change.

## 11. cloud-sdk gaps

Reference **master §11 / shared DESIGN §6**. **No module-specific cloud-sdk change required, and S-G2 is not exercised here** (S3 is read-only via the existing `getContent`). distributor-rest consumes the existing public cloud-sdk-api (`MessagingClient.receiveMessages`/`deleteMessage`, `StorageClient.getContent`, `NotificationService`) plus `shared`. The OAuth/HTTP egress is local and untouched. G1/G3/G6/G7 do not apply.
</content>
