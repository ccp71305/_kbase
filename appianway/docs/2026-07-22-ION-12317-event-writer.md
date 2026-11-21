# event-writer — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `event-writer` · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only event-writer's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`). event-writer boots clean on that stack today (still on AWS v1 + `shared`).

---

## Contents

---

## 1. Overview

**Purpose.** `event-writer` is the platform's audit sink: the **sole subscriber** of the platform SNS event topic (via its own SQS pickup queue), persisting every workflow `Event` it receives as a JSON object in the shared workspace S3 bucket at `{s3EventStorePath}/{date}/{rootWorkflowId}/{component}-{type}-{eventId}.json`. Strict one-way sink: consume → parse → write. No SNS publish, no SQS fan-out, no email, no DynamoDB, no network-services/SSM auth call (confirmed at INT: no `networkServiceConfig`, no `AuthClient` call on boot).

**Current state.** AWS Java SDK v1 (`AmazonSQS`, `AmazonS3`) constructed directly in `ExternalServicesModule`; the task chain (`SQSMessageWriterTask` → `SQSMessageHandler` → `S3StoringMessageHandler` → `SQSMessageToEventConverter`) is typed on v1 `Message`; the workflow model is `shared`'s `event.Event` + `event.SNSNotification`; S3 writes go through `shared` `WorkspaceService.putObject(bucket,key,String)`, which **hardcodes `text/plain`** even though every object written is `.json`.

**Target.** `commons` + `cloud-sdk-api` + `cloud-sdk-aws` (`1.0.27-SNAPSHOT`) + slim `appianway-commons`. The task chain re-types to `QueueMessage<String>`; the workflow model becomes cloud-sdk-api's `notification.workflow.Event` (+ `notification.annotation.Annotations`); S3 writes move to `StorageClient` using the **S-G2** content-type overload to stamp `Content-Type: application/json`; the appianway `SQSListener`/`AsyncDispatcher` concurrency model is retained via `appianway-commons`.

**Headline change.** event-writer is the **program's rollout pilot** and the **primary S-G2 consumer** — every object it writes is JSON and today gets `text/plain`. It is also where **W-G9 matters most**: it is the only module that **archives raw `Event` JSON verbatim** to durable storage, so if cloud-sdk-api's `Event` deserializes annotations differently from `shared`'s (it currently does — §6), the archive silently loses data. The W-G9 round-trip corpus test **gates this module's rollout**.

---

## 2. Current vs Target architecture

```
BEFORE — AWS v1 + shared
  inttra_int_sqs_event (SQS pickup)
        │
        ▼
  shared SQSListener + AsyncDispatcher ──────▶ v1 AmazonSQS (2 clients: listener + sender)
        │
        ▼
  SQSMessageWriterTask (extends shared AbstractTask; process(v1 Message, queueUrl))
        │
        ▼
  S3StoringMessageHandler (implements SQSMessageHandler; handle(v1 Message))
        │            │
        │            ▼
        │      SQSMessageToEventConverter  convert(v1 Message) → List of shared Event
        ▼
  shared S3WorkspaceService.putObject(bucket,key,String)  -- text/plain hardcoded
        │
        ▼
  v1 AmazonS3 ──▶ inttra-int-workspace/eventstore

AFTER — commons + cloud-sdk (AWS v2)
  inttra_int_sqs_event (SQS pickup, unchanged)
        │
        ▼
  appianway-commons SQSListener + AsyncDispatcher (retained) ──▶ cloud-sdk-api MessagingClient[String] (cloud-sdk-aws SQS impl)
        │
        ▼
  SQSMessageWriterTask (extends appianway-commons AbstractTask; process(QueueMessage[String], queueUrl))
        │
        ▼
  S3StoringMessageHandler  handle(QueueMessage[String])
        │            │
        │            ▼
        │      SQSMessageToEventConverter  convert(QueueMessage[String]) → List of cloud-sdk-api Event
        │                                   (kept local: raw-array + SNS-envelope parsing)
        ▼
  cloud-sdk-api StorageClient.putObject(bucket,key,bytes,metadata,"application/json")  -- S-G2
        │
        ▼
  cloud-sdk-aws S3StorageClient (AWS v2) ──▶ inttra-int-workspace/eventstore
```

### 2.1 Class-level mapping

| `shared` (v1) type | Replacement | Home | Notes |
|---|---|---|---|
| `com.amazonaws.services.sqs.model.Message` | `cloudsdk.messaging.api.QueueMessage<String>` | cloud-sdk-api | `getBody()`→`getPayload()`; `getMessageId()`/`getReceiptHandle()` unchanged. Compiler-driven across the 4 chain classes. |
| `shared` listener/dispatcher/task base | same appianway concurrency model, retained | appianway-commons | Re-pointed onto `MessagingClient<String>` instead of v1 `AmazonSQS`. |
| `shared.externalwrapper.exception.RecoverableException` | `RecoverableException` (same semantics) | appianway-commons | Thrown from `AbstractTask.process(...)`; unchanged signature. |
| `shared.event.Event` | `cloudsdk.notification.workflow.Event` | cloud-sdk-api | Field-identical except `Builder` currently has no `annotations`/`setAnnotations()` — **W-G9.1** (§6). |
| `shared.event.SNSNotification` | kept **local** to `SQSMessageToEventConverter` | module | Raw AWS SNS delivery envelope, not a workflow type. |
| `shared.workspace.WorkspaceService`/`S3WorkspaceService` | `cloudsdk.storage.api.StorageClient` (+ cloud-sdk-aws `S3StorageClient`) | cloud-sdk | Target uses the **S-G2** `putObject(bucket,key,byte[],Map metadata,String contentType)` overload. |
| `shared.command.ConfigProcessingServerCommand` | `commons` command + composed appianway transform | commons + appianway-commons | §5. |
| `shared.healthcheck.*` (`InboundSqs`, `ErrorThreshold`, `S3Write`) | commons `health.*` base + appianway-commons indicator wrappers | commons + appianway-commons | 3 checks unchanged in shape. |
| `shared.config.{SQSConfig,S3Config}` | cloud-sdk config types bound in `ExternalServicesModule`; `EventWriterConfiguration` POJO fields unchanged | cloud-sdk-aws / module | No YAML field renames. |
| `shared.support.Json` | cloud-sdk-api `Event.parseJson`/`toJsonString` for the workflow type; plain Jackson retained locally for raw-array/SNS-envelope shapes | cloud-sdk-api + module | |

---

## 3. AWS touchpoints

| Touchpoint | Direction | INT resource name | cloud-sdk client | Notes |
|---|---|---|---|---|
| SQS | inbound (consume) | `inttra_int_sqs_event` (`https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_event`) | `MessagingClient<String>` | Sole inbound path. Long-poll `receiveMessages`; delete-on-success `deleteMessage`. |
| SNS | — | none (terminal subscriber of `inttra_int_sns_event`; the SNS→SQS subscription lives on the pickup queue, outside this module) | n/a | No `NotificationService` binding needed. |
| S3 | write only | `inttra-int-workspace`, prefix `eventstore` | `StorageClient` (S-G2 `putObject`) | One JSON object per event at `eventstore/{yyyy-MM-dd}/{rootWorkflowId}/{component}-{type}-{eventId}.json`. No read, no copy. |
| DynamoDB | — | n/a | n/a | Not used. |
| SES | — | n/a | n/a | Not used. |
| Param Store (SSM) | — | none | n/a | No `networkServiceConfig`; no `AuthClient` call at boot. §5.2. |
| gRPC | — | n/a | n/a | Not used (appianway core module, not watermill). |

---

## 4. Sequence — consume → convert → S3 write

```
 1.  SQSListener (appianway-commons) ─▶ MessagingClient.receiveMessages(queueUrl, max, waitSeconds)
 2.  MessagingClient ──▶ returns List of QueueMessage[String]
 3.  SQSListener ─▶ AsyncDispatcher.submit(message, queueUrl)   [semaphore-bounded]
 4.  AsyncDispatcher ─▶ SQSMessageWriterTask.process(QueueMessage[String] m, queueUrl)
 5.  Task ─▶ S3StoringMessageHandler.handle(m)
 6.  Handler ─▶ SQSMessageToEventConverter.convert(m.getPayload())
        ├─ payload is a raw JSON array of Events   ─▶ List of Event (direct parse)
        └─ payload is an SNS-wrapped notification   ─▶ unwrap SNSNotification.getMessage() ─▶ List of Event
 7.  for each Event e:
        composePath(e) = "{s3EventStorePath}/{date}/{rootWorkflowId}/{component}-{type}-{eventId}.json"
        Handler ─▶ StorageClient.putObject(bucket, path, e.toJsonString().getBytes(), metadata, "application/json")  [S-G2]
        StorageClient ─▶ S3 PUT object (Content-Type: application/json)
 8.  Handler returns ok (or logs + increments messages-failed metric on Exception)
 9.  AbstractTask contract: on success ─▶ MessagingClient.deleteMessage(queueUrl, receiptHandle)
```

Behavior preserved (only client/type swapped): `handle(...)` catches all `Exception`s per message and logs + `@Metered` bumps `messages-failed` rather than rethrowing (a single malformed event doesn't stall the queue); `composePath` truncates the timestamp to `yyyy-MM-dd`; the two parse branches (raw array first, then SNS-envelope unwrap) stay module-local (no cloud-sdk/commons equivalent).

---

## 5. Configuration changes

### 5.1 Property-key table (INT values — unchanged names/values, verified live 2026-07-22)

| YAML key | `.properties` source | INT value | Notes |
|---|---|---|---|
| `errorRateThreshold` | `event-writer.errorRateThreshold` | *(unset → default 5.0)* | `${event-writer.errorRateThreshold:-5.0}` |
| `pickupSqsConfig.queueUrl` | `event-writer.pickupSqsConfig.queueUrl` | `https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_event` | The only inbound source. |
| `pickupSqsConfig.waitTimeSeconds` | `event-writer.pickupSqsConfig.waitTimeSeconds` | *(unset → default 20)* | Long-poll seconds. |
| `pickupSqsConfig.maxNumberOfMessages` | `event-writer.pickupSqsConfig.maxNumberOfMessages` | *(unset → default 10)* | Also sizes the `AsyncDispatcher` semaphore. |
| `s3Config.bucket` | `event-writer.s3Config.bucket` | `inttra-int-workspace` | |
| `s3EventStorePath` | `event-writer.s3EventStorePath` | `eventstore` | Path prefix, not a bucket. |
| `server.connector.port` | `server.connector.port` | *(unset → default 8081)* | Single simple server; `/application` + `/admin` share the port. |
| `metrics.frequency` | *(from datadog.properties)* | *(required, no default)* | Fed by the datadog properties file. |
| `componentName` | *(properties-only)* | `event-writer` | Cross-cutting logging/metrics naming. |

**No renames.** Client/library migration, not a config migration. The network-services and datadog properties files continue to be passed on the CLI (Dockerfile/`run.sh`/VSCode launch configs unchanged) even though the network-services auth vars are not referenced by this module (no `networkServiceConfig`) — kept only for CLI-shape consistency with the other 13 modules.

### 5.2 SSM parameter table

**None for this module.** event-writer has no `networkServiceConfig` block, so it never calls `AuthClient`/`CloudParameterStore` at boot (confirmed live at INT). Unchanged after migration: no `${awsps:/path}` placeholders introduced, because nothing here resolves from SSM today. (Contrast splitter/transformer/ingestor, which do call `AuthClient` and resolve `networkservices.clientId`/`clientSecret` from SSM.)

### 5.3 Config-command wiring

```
classpath event-writer.yaml
    │
    ▼
[ appianway property subst ]  ${key} from event-writer.properties + env  (appianway-commons transform)
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]  (no-op here — no ${awsps:...} tokens in this module's yaml)
    │
    ▼
Dropwizard Configuration factory (EventWriterConfiguration)
```

The `ParameterStoreConfigTransform` stage is present for consistency with the other 13 modules (and in case a future `${awsps:...}` is added) but is a structural no-op for event-writer today. `EventWriterApplication.initialize(...)` swaps the `shared` `ConfigProcessingServerCommand` for the commons one wrapped by the appianway composition, exactly as every other module does.

### 5.4 Run profiles

event-writer has **no** ce-/os- variant — one artifact, one YAML, one properties file, one queue. Simplest of the 14 modules on this axis.

### 5.5 What's unchanged

- CLI arg shape: `run event-writer.yaml conf/int/event-writer.properties <network-services.properties> <datadog.properties>`.
- `-DCONFIG_REGION=US_EAST_1` VM arg.
- `S3ConfigurationProvider` conditional install (`CONFIG_LOCATION=s3`) — not exercised at INT (filesystem config), retained (moves to appianway-commons).
- Queue name (`inttra_int_sqs_event`), bucket (`inttra-int-workspace`), path prefix (`eventstore`) — none renamed.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap | Relevant? | How event-writer exercises it |
|---|---|---|
| **S-G2** | **Yes — primary consumer.** | Every S3 write is a `.json` audit object; today's `putObject(bucket,key,String)` effectively defaults to `text/plain`. S-G2 adds `putObject(bucket,key,byte[],Map metadata,String contentType)`; `S3StoringMessageHandler` calls it with `contentType="application/json"`. Bytes unchanged — header-only, strictly additive. Confirmed: the current `StorageClient` interface has only `putObject(bucket,key,byte[]/InputStream/File/String)`, so the S-G2 overload must land upstream before end-to-end completion (interim fallback: ship on the 4-arg `putObject(bucket,key,byte[])`, defer the content-type stamp — §10 R1). |
| **W-G9** | **Yes — critical, gates rollout.** | event-writer is the only module that archives raw `Event` JSON to durable storage, so a workflow-model wire defect means silent, permanent audit-trail data loss. Source-verified: `Event.Builder` has no `annotations`/`setAnnotations`, and the copy-constructor doesn't copy annotations; since `Event.parseJson` deserializes via the builder, any `Event` JSON with an `"annotations"` block is silently dropped (`ignoreUnknown=true`). The class is write-only for annotations. **Do not roll out consumption of annotation-bearing events until W-G9.1 lands.** W-G9.2 (constant-set parity) is not event-writer-specific but ships in the same release. |
| **X-G7** | No. | No email. |
| **X-G8** | No. | No OpenSearch/Jest. |
| **C-G6** | Optional. | §5.3 composition works without commons widening `getConfigTransformer` visibility. |

**Moves to `appianway-commons`:** `AsyncDispatcher`/`AbstractTask`/`TaskFactory`; `SQSListener`/`ListenerManager`/`SQSListenerClient` (re-pointed to `MessagingClient<String>`); `RecoverableException`; the 3 health-check indicator wrappers; the appianway property-substitution config transform.
**Stays module-local (single consumer):** `SQSMessageToEventConverter`'s two-branch parsing + SNS-envelope shape knowledge; `composePath(event)` S3 key-naming.

---

## 7. Maven dependency changes

**Remove:** `com.inttra.mercury.shared:mercury-shared` (retired program-wide). v1 SQS/S3 arrive transitively through `mercury-shared`, so removing it removes them — nothing orphaned to clean up here.
**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK v2 arrives transitively via `cloud-sdk-aws` (BOM-managed) — do not declare v1 or v2 directly.
**Align (already done by ION-16098):** Dropwizard 5.0.2 / Jetty 12.1.9 / Jackson 2.21.4 / Java 17 inherited from the `appian-way` parent pom; reconcile with the mercury-services-commons BOM if patch versions differ (not expected). event-writer **has** a parent — no special no-parent handling (unlike the watermill consumers).
**Unaffected:** `guice`, `lombok`, `dropwizard-core`, metrics, `guava`, `slf4j`/`logback` — no changes. `functional-testing` test-scope dep stays (its fakes migrate lockstep). JUnit 4 currently declared — add `junit-jupiter`/`dropwizard-testing` during transition, do not hard-cut. Shade plugin config unchanged (note it's on the old 2.3 version; `clean verify` needed).
**Verify:** `mvn -pl event-writer -am clean verify` green; fat-jar boot + `curl http://localhost:8081/admin/opsHealthcheck` → 200, all 3 checks green.

---

## 8. Tests

**Direction:** JUnit 5 for new/changed tests; module currently uses JUnit 4 throughout. Migrate incrementally with `junit-vintage-engine` bridging — no big-bang rewrite (test bodies barely change; mock type swap only).

**Unit tests to update (mechanical):**
- `SQSMessageWriterTaskTest` — replace `new Message().setMessageId("MID")` with a `QueueMessage<String>` test double returning `"MID"`; assertion unchanged.
- `S3StoringMessageHandlerTest` — replace `Message` with a `QueueMessage<String>` stub whose `getPayload()` returns the fixture; replace the `WorkspaceService` mock with a `StorageClient` mock; **assert the S-G2 overload is called with `contentType="application/json"`**:
  `verify(storageClient).putObject(eq(bucket), eq(key), any(byte[].class), anyMap(), eq("application/json"));`
- **New: annotations round-trip (W-G9 guard).** Add a fixture Event JSON carrying an `Annotations` block; assert `Event.parseJson(...)` returns a non-null, field-correct `Annotations`, and re-serializing reproduces it. Written to fail against pre-W-G9 cloud-sdk-api and pass once W-G9.1 lands — do not merge while red.
- `SQSMessageToEventConverter` — add direct tests for both branches (raw `List<Event>` array; SNS-wrapped notification), both returning cloud-sdk-api `Event` instances.

**Functional tests:** `functional-testing` fakes (`FakeS3`, SQS fake) re-pointed to `StorageClient`/`MessagingClient<String>` as part of that module's own migration (before event-writer). event-writer's functional test needs only the mechanical `Message`→`QueueMessage<String>` / `Event` package swap; assert message consumed+deleted, JSON object at the same composed path, and (once S-G2 fakes support it) the stored content-type.

---

## 9. Rollout & verification

**Position:** the **second** program step — immediately after `appianway-commons` (slim residue) and `functional-testing` (fakes lockstep), and **before every other of the 13 modules**. "Low-risk S3 pilot, primary S-G2 consumer."

1. Confirm `appianway-commons` is published and consumable.
2. Confirm `functional-testing` fakes are re-pointed to `StorageClient`/`MessagingClient<String>`.
3. Confirm **S-G2** has landed (or accept the interim 4-arg `putObject` fallback — §10 R1).
4. Confirm **W-G9.1** has landed — **hard gate**. Run the round-trip corpus test using representative production `Event` JSON from event-writer's own S3 archives (it uniquely holds the historical corpus).
5. `mvn -pl event-writer -am clean verify` green.
6. Re-type the 4 task-chain classes to `QueueMessage<String>`/cloud-sdk-api `Event`; rebind `ExternalServicesModule` (`AmazonSQS`×2 + `AmazonS3` → `MessagingClient<String>`×2 + `StorageClient`); rebind the 3 health-check indicators.
7. Local INT boot verification:
   ```
   java -DCONFIG_REGION=US_EAST_1 -jar target/event-writer-1.0.jar run \
     event-writer.yaml conf/int/event-writer.properties \
     ../configuration/int/network-services.properties ../configuration/int/datadog.properties
   ```
   Expect: clean Jetty 12.1.9/EE10 boot, `SQSListener starting` on `inttra_int_sqs_event`, HTTP bound `0.0.0.0:8081`, `curl .../admin/opsHealthcheck` → 200 with all 3 checks (inbound SQS, S3 write, error-rate) green — now backed by cloud-sdk-aws v2 clients.
8. Drive one real message through `inttra_int_sqs_event` and confirm a JSON object lands at `inttra-int-workspace/eventstore/<date>/<rootWorkflowId>/...json` with `Content-Type: application/json` (via `aws s3api head-object`).
9. Only after this module is green does the program proceed to distributor-rest/structuralvalidator.

---

## 10. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **R1 — S-G2 not yet landed** | Loses the `application/json` content-type stamp (cosmetic; bytes unaffected) | Land S-G2 first in cloud-sdk; if blocked, ship interim on `putObject(bucket,key,byte[])` and fast-follow the content-type — additive either way. |
| **R2 — W-G9.1 not yet landed** | **Silent, permanent data loss** — annotation-bearing Events archived without annotations; the archive is the source of truth | **Hard gate** — do not roll consumption into production until the round-trip corpus test is green. Highest-severity risk in the program. |
| **R3 — `Message`→`QueueMessage<String>` misses a call site** | Compile failure, not silent | Compiler-driven across exactly 4 classes; `mvn verify` catches it. |
| **R4 — SNS-envelope / raw-array parse drift** | Malformed payload falls through the generic catch, bumping `messages-failed` without visibility | Preserve the two-branch try/fallback exactly (type swap only); add direct unit tests for both branches. |
| **R5 — Two-`MessagingClient` split (listener vs sender) not modeled 1:1** | `deleteMessage` issued against the wrong instance | Bind two configured `MessagingClient<String>` instances (mirroring today's `amazonSQSForListener`/`amazonSQSForSender`); confirm delete-path with a functional test. |
| **R6 — cloud-sdk/commons change breaks mercury-services** | Regression in the production consumer | Both changes strictly additive; verify via cloud-sdk CI + full mercury-services build green before/after. |
| **R7 — functional-testing fakes lag the module migration** | event-writer's functional test can't compile against cloud-sdk-api | Gate event-writer behind `functional-testing`'s migration completing first (program order). |
