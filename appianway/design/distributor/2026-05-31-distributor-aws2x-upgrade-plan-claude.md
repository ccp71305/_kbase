# `distributor` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.appian-way:distributor:1.0` (file-shape egress: renders filename, optional zip, writes to outbound-delivery S3) · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard 5.0.1, AWS SDK v2 BOM 2.30.24, Guice 7, Jackson 2.21). Target = **Option B**.
> **Master references (do not duplicate):** [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6. Governing constraint: **ZERO IMPACT to existing mercury-services apps** ⇒ every cloud-sdk/commons change strictly additive/behavior-preserving.

---

## 0. What this document changes vs. the Copilot plan (critical review)

Reviewed against [`2026-05-31-distributor-aws2x-upgrade-plan-copilot.md`](2026-05-31-distributor-aws2x-upgrade-plan-copilot.md) / [`-DESIGN.md`](2026-05-31-distributor-aws2x-upgrade-DESIGN.md) and the actual distributor source. The Copilot inventory is mostly right (standard S3/SQS/SNS consumer; `IOUtils` in the zip path; `putObject` return ignored). Corrections:

| Copilot position | Evidence | This plan |
|---|---|---|
| Lists module-specific **G1 (concurrent listener)** and **G7 (health)** as distributor cloud-sdk gaps | mercury-services hand-roll listeners; appianway already owns `SQSListener`+`AsyncDispatcher`; health indicators re-point to injected clients | **Not distributor gaps** (master plan §0). Inherit the retained `shared` chain. |
| Frames S3 metadata as a generic "G2 putObject-with-metadata" | distributor's egress path actually uses **`copyObjectWithMetaDate(...)`** with a metadata map ([`FileDeliveryService.java:97-108`](../src/main/java/com/inttra/mercury/distributor/services/FileDeliveryService.java)), and `putObject(byte[])` for the zip ([`ZipCompression.java:40`](../src/main/java/com/inttra/mercury/distributor/handlers/ZipCompression.java)) | **Reference master S-G2** precisely — distributor depends on S-G2's **copy-with-replaced-metadata** overload, plus the plain `putObject(byte[])` (no metadata) for the zip. No distributor-specific gap. |
| `IOUtils` → v2 `IoUtils` | `com.amazonaws.util.IOUtils.toByteArray` at [`ZipCompression.java:3,40`](../src/main/java/com/inttra/mercury/distributor/handlers/ZipCompression.java) | Keep — but prefer JDK `InputStream.readAllBytes()`/Guava to avoid pinning an AWS util dependency; trivial either way. |
| Recommend Option A | stakeholder directive | **Option B** (master §7). |

**Net for distributor: ZERO module-specific cloud-sdk gaps beyond master S-G2.** distributor is a standard-service rebind that consumes the S-G2 metadata-copy overload owned by `shared`.

---

## 1. Executive summary

`distributor` is a standard SQS+S3+SNS consumer that renders a delivery filename, optionally zips the payload, and copies the result to the outbound-delivery bucket **with S3 user metadata** (workflow lineage). It binds AWS v1 clients in [`modules/ExternalServicesModule`](../src/main/java/com/inttra/mercury/distributor/modules/ExternalServicesModule.java) and consumes the v1 `Message` DTO in [`task/DistributorTask`](../src/main/java/com/inttra/mercury/distributor/task/DistributorTask.java).

Under **Option B** (directed default) distributor:
1. rebinds `ExternalServicesModule` to cloud-sdk-aws factories (`MessagingClient<String>`, `StorageClient`, `NotificationService`);
2. inherits the retained `shared` `SQSListener`+`AsyncDispatcher` chain; `DistributorTask.process(Message,...)` becomes `process(QueueMessage<String>,...)`, reading `getPayload()` instead of `getBody()`;
3. depends on the `shared` `WorkspaceService.copyObjectWithMetaDate(...)`/`putObject(...)`, which are backed by master **S-G2** (`StorageClient` metadata overloads);
4. swaps `com.amazonaws.util.IOUtils` for JDK/Guava (or v2 `IoUtils`), keeping the streaming zip;
5. preserves `MetaData`/`EventLogger` event lineage and the `DistributorErrorHandler` chain.

**No distributor-specific cloud-sdk library change** beyond master S-G2.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

- [`modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/distributor/modules/ExternalServicesModule.java):
  - `AmazonSQS` `amazonSQSForListener` (`sqs_listener`) / `amazonSQSForSender` (`sqs_sender`) — lines 40–43.
  - `AmazonS3` (`s3_read_put_copy`) — lines 44–45.
  - `AmazonSNS` (`sns_publish`) — lines 46–47.
- [`task/DistributorTask.java`](../src/main/java/com/inttra/mercury/distributor/task/DistributorTask.java):
  - extends `shared` `AbstractTask` — line 22.
  - `process(com.amazonaws.services.sqs.model.Message message, String pickupQueueUrl)` — lines 3, 47.
  - reads `message.getBody()` for the `MetaData` envelope — lines 50, 64; error path line 70.
- [`services/FileDeliveryService.java`](../src/main/java/com/inttra/mercury/distributor/services/FileDeliveryService.java):
  - builds an S3 user-metadata map (rootWorkflowId/parentWorkflowId/workflowId + projection keys) — lines 48–63.
  - `workspaceService.copyObjectWithMetaDate(srcBucket, src, dstBucket, dst, metaDataMap)` for both the delivery and archive copies — lines 64–65, 97–108. **This is the S-G2 copy-with-replaced-metadata dependency.**
- [`handlers/ZipCompression.java`](../src/main/java/com/inttra/mercury/distributor/handlers/ZipCompression.java):
  - `com.amazonaws.util.IOUtils.toByteArray(zipInputStream)` — lines 3, 40.
  - `s3WorkspaceService.getS3InputStream(...)` then `putObject(bucket, source, byte[])` (no metadata) — lines 36, 40; zip via JDK `java.util.zip` — lines 60–75.
- [`pom.xml`](../pom.xml): declares `com.amazonaws:aws-java-sdk-sqs` only (lines 44–49); S3/SNS clients arrive transitively via `shared`. **JUnit 4** + `mockito-core` (lines 79–90).

---

## 3. Findings

- **distributor is the canonical "standard-service" rebind plus an S-G2 metadata-copy consumer.** Its only AWS surfaces are SQS/S3/SNS (all via `shared`) and the v1 `IOUtils` util. The zip logic itself is pure JDK `java.util.zip` ([ZipCompression:60-75](../src/main/java/com/inttra/mercury/distributor/handlers/ZipCompression.java)) and is unaffected.
- **It genuinely exercises S-G2's copy-with-metadata overload.** `copyObjectWithMetaDate` carries a 6–8 entry user-metadata map (workflow IDs + outbound projection keys). This maps to the master S-G2 `StorageClient.copyObject(src,srcKey,dst,dstKey,replacedMetadata,contentType)` overload with `MetadataDirective.REPLACE`. The plain zip `putObject(byte[])` carries no metadata and maps to the existing metadata-less overload.
- **`putObject` return is ignored.** [ZipCompression:40](../src/main/java/com/inttra/mercury/distributor/handlers/ZipCompression.java) discards the result — consistent with the `shared` change to `void`/`String eTag`.
- **Streaming preserved.** The zip path streams from `getS3InputStream` through a 1 KB buffer into a `ByteArrayOutputStream`; the `IOUtils.toByteArray` → `putObject(byte[])` step buffers the (zipped) payload in memory today. Behavior is preserved on v2; if large-file memory pressure is a concern, the streaming `putObject(InputStream,length)` overload can be adopted later (not required for parity).
- **`MetaData` is `shared` `task/MetaData`** (field-identical to commons `cloud-sdk-api` `notification/workflow/MetaData`, master §2.8) — adopt the commons type under Option B; event lineage via `EventLogger` preserved.
- **JUnit 4** today ([pom.xml:85-90](../pom.xml)); new tests in JUnit 5 with `junit-vintage-engine` bridging existing tests during transition (master §8).

---

## 4. Option A — keep `shared`/DW4, delegate in place

Rebind `ExternalServicesModule` to cloud-sdk-aws factories; `DistributorTask` consumes `QueueMessage<String>`; `IOUtils` swap; outbound copy/put via the S-G2-backed `WorkspaceService`. Keep DW4/JUnit4. **Pros:** minimal blast radius; mechanical. **Cons:** keeps bespoke DW4 base. Effort Low–Medium; Risk Low.

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A plus moving distributor's Dropwizard base/config onto `commons` (DW5) and the appianway composed config command (master §10), adopting the commons `MetaData`/`EventLogger`. AWS plumbing changes are identical. **Pros:** platform convergence. **Cons:** DW4→5 base migration; JUnit5 pull. Effort Medium; Risk Medium.

## 6. Comparison

| Criterion | Option A | Option B |
|---|---|---|
| Off AWS v1 | ✅ | ✅ |
| Required cloud-sdk change | S-G2 (program-wide; distributor consumes it) | S-G2 |
| Impact on mercury-services | none | none |
| Framework churn | none | DW4→5, JUnit4→5 |
| `Message`→`QueueMessage` | mechanical (one task) | mechanical |
| Effort / Risk | Low–Med / Low | Med / Med |

## 7. Recommendation

**Option B**, per the stakeholder directive and master §7. distributor carries **no module-specific cloud-sdk gap**: its outbound metadata copy rides on master **S-G2**, and the listener/health/config concerns are inherited from `shared`/composed commons transforms (no library change). Option A is the fallback with the identical AWS rebind.

## 8. Peer review (self-reviewed vs source + master)

| Item | Finding | Status |
|---|---|---|
| Copilot G1/G7 as distributor gaps | inherited from retained `shared` chain / re-pointed indicators | **De-scoped — not distributor gaps** |
| S3 metadata path | `copyObjectWithMetaDate` with metadata map → master S-G2 copy-with-replaced-metadata; zip `putObject(byte[])` → metadata-less overload | **Resolved — reference S-G2** |
| `putObject` void return | call site ignores it ([ZipCompression:40](../src/main/java/com/inttra/mercury/distributor/handlers/ZipCompression.java)) | **Resolved** |
| `Message`→`QueueMessage<String>` | `getBody()`→`getPayload()` in `DistributorTask` | **Resolved** |
| `IOUtils` | JDK `readAllBytes()`/Guava preferred over v2 `IoUtils` (avoid pinning an AWS util) | **Resolved** |
| Streaming/large file | parity preserved; optional `putObject(InputStream,length)` later | **Resolved (optional)** |

## 9. Open questions / dependencies / sequencing

- Confirm `getS3OutboundConfig()`/`getS3WorkspaceConfig()` bucket config maps cleanly to the cloud-sdk-aws `StorageClient` (region/endpoint).
- **Sequencing:** after `shared` (which lands S-G2 additively) + `functional-testing`; pairs naturally with `distributor-rest`. Gate with `mvn -pl distributor -am verify`. Keep `1.0.26-SNAPSHOT` aligned program-wide.

## 10. Configuration changes

Reference master plan **§10** (composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}`). distributor-specific: `conf/distributor.yaml` S3 (`s3_read_put_copy`) + SQS role config map to cloud-sdk-aws options via `shared`; outbound/workspace bucket names unchanged; credentials/region via v2 default providers.

## 11. cloud-sdk-api / cloud-sdk-aws / commons gaps (distributor)

- **S3 outbound metadata** — reference master **S-G2** only. distributor consumes:
  - `StorageClient.copyObject(src,srcKey,dst,dstKey,replacedMetadata,contentType)` (REPLACE directive) for `copyObjectWithMetaDate` ([FileDeliveryService:97-108](../src/main/java/com/inttra/mercury/distributor/services/FileDeliveryService.java));
  - the existing metadata-less `putObject(bucket,key,byte[])` for the zip ([ZipCompression:40](../src/main/java/com/inttra/mercury/distributor/handlers/ZipCompression.java)).
  Both are owned/specified by `shared`; **no distributor-specific cloud-sdk change.**
- **Listener / config / health** — inherited from `shared` and composed commons transforms; no distributor-specific cloud-sdk change (master plan §0/§10).

**Summary: distributor requires no module-specific cloud-sdk gap beyond master S-G2.**
