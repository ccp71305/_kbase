# watermill-publisher — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `watermill-publisher` · Main: `com.inttra.mercury.watermill.WatermillPubApplication` · Port 8081 · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only watermill-publisher's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`; `jaxb-runtime 4.0.4` added, `plexus-utils` removed). Boot-verified against INT (gRPC streams establish, SQS polls clean). **No ops health check exists** — verification is boot-evidence only.
> **Scope discipline:** the **gRPC/protobuf layer is NOT AWS and is explicitly out of scope** — `StatusEventGrpcClient`, `PublisherGrpc` stubs, `ResponseObserver`, `AuthCredentials`' gRPC `CallCredentials` contract, the XML→protobuf transform chain, and the `watermill.staging.e2open.com:443` channel are **unchanged**. Only the AWS-layer plumbing feeding that gRPC client (SQS consume/send/delete, SNS publish, S3 read, SSM-sourced gRPC credentials) is rebound.

---

## Contents

---

## 1. Overview

**Purpose:** watermill-publisher is the SE (Shipment-Status) **egress bridge** from the appianway ETL pipeline to the external Watermill/e2open gRPC service. It consumes `MetaData` envelopes off an SQS pickup queue, reads the referenced XML file from S3, transforms XML → protobuf (`ShipmentStatusChangeEvent`), and streams it to `watermill.staging.e2open.com:443` over a persistent gRPC channel authenticated with credentials sourced from SSM. A background `DeadLetterService` periodically redrives the queue's DLQ back onto the main queue.

- **Current state:** AWS v1 (`aws-java-sdk-sqs` + transitive v1 S3/SNS/SSM), entirely mediated by `shared` (`SQSListener`, `SQSClient`/`SQSListenerClient`, `S3WorkspaceService`, `SNSClient`/`SNSEventPublisher`, `ParameterStoreModule`/`SsmParameterSupplier`). Local concurrency (`AsyncDispatcher`/`Task`/`ListenerManager`) is appianway-owned but layered on `shared`'s v1-typed `SQSListener`.
- **Target:** `shared` retired. AWS layer rebinds onto `1.0.27-SNAPSHOT` — `cloud-sdk-api` (`MessagingClient[String]`/`QueueMessage[String]`, `StorageClient`, `NotificationService`, `CloudParameterStore`) + `cloud-sdk-aws` (v2 impls) + slim `appianway-commons` (the module's local `AsyncDispatcher`/`Task`/`ListenerManager`/`DeadLetterService` concurrency model plus a thin `SqsClient`/`SqsListener` facade over `MessagingClient[String]`).
- **Headline change:** the AWS surface is small and entirely mediated through `shared` today (no direct v1 SDK calls in production outside `ExternalServicesModule`), so the rebind is mechanical — element type `com.amazonaws...Message` → `QueueMessage[String]` everywhere in the local task/dispatcher chain, `getBody()`→`getPayload()`, and the SSM gRPC-credential fetch is re-decided (§5.2). **No cloud-sdk gap is required** — no S3 metadata write (no S-G2), no `Event`/`Annotations` publish/consume (no W-G9); it only round-trips `MetaData`, which is source- and wire-identical.

---

## 2. Current vs Target architecture

```
BEFORE — shared + AWS v1
  WatermillPubApplication (io.dropwizard.core)
   ExternalServicesModule: binds v1 AmazonSQS x2 / AmazonS3 / AmazonSNS via shared AWSClientConfiguration;
        installs shared ParameterStoreModule (v1 AWSSimpleSystemsManagement, eager fetch) + NetworkRetryerModule
   WatermillPubModule: binds shared S3WorkspaceService, SNSEventPublisher/SNSClient, WatermillServiceConfig, gRPC channel+stubs
   ListenerManager ─▶ AsyncDispatcher x listenerThreads(2) (appianway-local, on shared Dispatcher) ─▶ WatermillPubTask
   ListenerManager ─▶ DeadLetterService (direct v1 ReceiveMessageRequest)
   WatermillPubTask ─▶ shared S3WorkspaceService (AmazonS3, read only)
   WatermillPubTask ─▶ shared SQSClient/SQSListenerClient (AmazonSQS v1: Message)
   WatermillPubTask ─▶ StatusEventGrpcClient (NON-AWS) ─▶ AuthCredentials ─▶ SSM v1 (eager)
   WatermillPubModule ─▶ shared SNSEventPublisher/SNSClient (AmazonSNS v1)

AFTER — cloud-sdk-api/aws + appianway-commons (gRPC layer UNCHANGED)
  WatermillPubApplication (commons ConfigProcessingServerCommand, composed transforms)
   ExternalServicesModule: binds cloud-sdk-aws SQS/S3/SNS clients (region/creds via v2 default chain);
        NO ParameterStoreModule needed if boot-time ${awsps:} chosen (§5.2)
   WatermillPubModule: binds appianway-commons SqsClient/SqsListener, cloud-sdk-api StorageClient (read),
        NotificationService, WatermillServiceConfig, gRPC channel+stubs (UNCHANGED)
   ListenerManager (appianway-commons) ─▶ AsyncDispatcher x2 (appianway-commons) ─▶ WatermillPubTask
   ListenerManager ─▶ DeadLetterService (appianway-commons, over MessagingClient)
   WatermillPubTask ─▶ StorageClient (cloud-sdk-api, read only)
   WatermillPubTask ─▶ appianway-commons SqsClient/SqsListener over MessagingClient[String] + QueueMessage[String]
   WatermillPubTask ─▶ StatusEventGrpcClient (NON-AWS, UNCHANGED) ─▶ AuthCredentials (reads resolved value from WatermillServiceConfig)
   WatermillPubModule ─▶ NotificationService (cloud-sdk-api)
```

### 2.1 Class/type mapping

| Current (`shared` / AWS v1) | Target | Home | Notes |
|---|---|---|---|
| `com.amazonaws.services.sqs.model.Message` (element type in `Task`, `AsyncDispatcher`, `WatermillPubTask`, `DeadLetterService`, `TaskFactory`) | `QueueMessage[String]` | cloud-sdk-api | `getBody()`→`getPayload()`; `getReceiptHandle()` unchanged; attributes `Map[String,String]` |
| `shared.messaging.SQSClient` / `SQSListenerClient` | appianway-commons `SqsClient` (thin facade over `MessagingClient[String]`: `sendMessage`, `deleteMessage`, `receiveMessages`, `getVisibilityTimeout` via `getQueueAttributes`) | appianway-commons (facade) + cloud-sdk-aws (impl) | `ResponseObserver.getVisibilityTimeout` and `WatermillPubTask.deleteMessage` both ride this facade |
| `shared.listener.SQSListener` | appianway-commons `SqsListener` (polls `MessagingClient[String].receiveMessages`, dispatches to the local `Dispatcher`) | appianway-commons | Same poll-loop shape (`waitTimeSeconds`, `maxNumberOfMessages`, `queueUrl`) — behavior-preserving |
| `shared.threaddispatcher.Dispatcher` / `AsyncDispatcher` (module-local impl) | `appianway-commons.concurrency.Dispatcher` / `AsyncDispatcher` | appianway-commons | Module's own semaphore/pool model retained as-is; only its `shared` interface dependency moves home |
| `shared.workspace.WorkspaceService` / `S3WorkspaceService` | `cloud-sdk-api StorageClient` (`getContent(bucket,key,charset)` — read only, no metadata) | cloud-sdk | **Never writes S3 in production** (only the deleted scratch `Test.java` wrote) — **S-G2 not exercised** |
| `shared.event.SNSEventPublisher` / `SNSClient` | `cloud-sdk-api NotificationService.publish(topicArn, message)` | cloud-sdk | Bound in `WatermillPubModule.snsEventPublisher(...)` |
| `shared.task.MetaData` + `shared.support.Json` | `cloud-sdk-api notification.workflow.MetaData` (+ its `Json`/parse helper) | cloud-sdk-api | Field-identical; `metaData.getBucket()`/`getFileName()`/`getWorkflowId()`/`getProjections().get("dxRoutes")` all preserved |
| `shared.parameterstore.ParameterStoreModule` / `SsmParameterSupplier` / v1 `AWSSimpleSystemsManagement` | **Decision (§5.2):** `cloud-sdk-api CloudParameterStore` (runtime) **or** commons `${awsps:/path}` boot-time substitution (**recommended**) | cloud-sdk-api / commons | Drives whether `AuthCredentials` still injects a supplier or just reads resolved config strings |
| `shared.config.BaseConfiguration`, `SQSConfig`, `SNSConfig`, `S3Config`, `AWSClientConfiguration` | Module's own `WatermillPublisherConfiguration extends io.dropwizard.core.Configuration` + cloud-sdk-aws config types (`AwsMessagingClientConfig`, `NotificationClientConfig`, `CloudStorageConfig`) | module + cloud-sdk-aws | §5 has the exact field table |
| `shared.command.ConfigProcessingServerCommand` | `commons ConfigProcessingServerCommand` + composed appianway property-substitution transform | commons + appianway-commons | §5.3 composition |
| `shared.networkservices.NetworkRetryerModule` | **Dropped** — no `networkServiceConfig` block, no `AuthClient`/network-services call | n/a | `HealthCheckConfig.networkServiceHealthCheckUrl` was already dead (no health checks registered) |
| `task/Test.java` (scratch `main`: v1 load-generator) | **Deleted** | n/a | The only S3-write and SQS-send-with-delay code in the module lives here — not production |
| gRPC: `StatusEventGrpcClient`, `PublisherGrpc` stubs, `ResponseObserver`, `AuthCredentials`, `XMLTransformer`, `StatusEventProtobufTransformer`, `*Map` enums | **Unchanged** | module | NON-AWS; already on `jaxb-runtime 4.0.4` post-ION-16098 |

---

## 3. AWS touchpoints (INT resource names — exact, unchanged)

| Touchpoint | Direction | INT resource | Current (v1/`shared`) | Target (cloud-sdk) |
|---|---|---|---|---|
| SQS pickup (inbound) | consume | `inttra_int_sqs_watermill_ce` | `shared.SQSListener` x `listenerThreads`(2) over `AmazonSQS` | appianway-commons `SqsListener` x2 over `MessagingClient[String]` |
| SQS pickup DLQ (redrive source) | receive+redrive | `inttra_int_sqs_watermill_ce_dlq` (derived: `{queueUrl}_dlq`) | `DeadLetterService` direct v1 `ReceiveMessageRequest` | appianway-commons `DeadLetterService` over `MessagingClient.receiveMessages` |
| SQS ack delete (same queue) | `deleteMessage` | same as pickup | `SQSClient.deleteMessage` (v1) | `SqsClient.deleteMessage` (`MessagingClient[String]`) |
| SQS error (config-resolved only) | n/a in code path | `inttra_int_sqs_subscription_errors` | `sqsErrorConfig.queueUrl` — declared, **never referenced** in production code | unchanged — config-resolved, kept for parity |
| SNS event | publish | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `SNSEventPublisher` over `shared.SNSClient` | `NotificationService.publish(topicArn, ...)` |
| S3 workspace | read only (`getContent`) | `inttra-int-workspace` (key = `metaData.getBucket()/getFileName()`) | `shared.S3WorkspaceService.getContent(bucket,key,ISO_8859_1)` over `AmazonS3` | `StorageClient.getContent(bucket,key,charset)` — **no metadata, no S-G2** |
| DynamoDB | n/a | none — the publisher has **no** offset table (that's the 4 consumers) | n/a | n/a |
| SES | n/a | none | n/a | n/a |
| SSM Parameter Store (gRPC creds) | fetch at boot/runtime | `/inttra/int/appianway/watermill-grpc/se/username`, `.../password` | `shared.SsmParameterSupplier` (eager-cached at Guice injector construction) via v1 `AWSSimpleSystemsManagement` | **§5.2 decision:** `CloudParameterStore` (runtime) **or** `${awsps:/path}` (boot-time, **recommended**) |
| gRPC (NON-AWS) | bidi stream publish | `watermill.staging.e2open.com:443` (tenant `INTTRA`) | `StatusEventGrpcClient` / `PublisherGrpc` | **unchanged** |

---

## 4. Sequences

### 4.1 Pickup consume → transform → gRPC publish (main path)

```
 1.  appianway-commons SqsListener (x2, listenerThreads) ─▶ MessagingClient[String].receiveMessages(queueUrl=inttra_int_sqs_watermill_ce, wait=20s, max=5)
 2.  ─▶ List of QueueMessage[String]
 3.  SqsListener ─▶ AsyncDispatcher.submit(messages, queueUrl) ─▶ WatermillPubTask.execute(List of QueueMessage[String], queueUrl)
 4.  handleStreamTermination() (recreate gRPC stream if previously reset)
 5.  for each QueueMessage:
        MetaData = parse(msg.getPayload())
        StorageClient.getContent(metaData.getBucket(), metaData.getFileName(), ISO_8859_1) ─▶ file content (S3 inttra-int-workspace, read)
        XMLTransformer.unconvert(xml) ─▶ ExportSEPartInt ─▶ StatusEventProtobufTransformer.transform(..., dxRoutes, metaData) ─▶ ShipmentStatusChangeEvent
        transform error   ─▶ MessagingClient.deleteMessage(queueUrl, msg.getReceiptHandle())
        transform ok      ─▶ StatusEventGrpcClient.invoke(shipmentStatusChangeEvent, msg.getReceiptHandle())
                             ResponseObserver.addMessageKeys(messageId, {receiptHandle, sentTime})
                             on gRPC PublisherAck.onNext(correlationId): ResponseObserver deletes the SQS message via SqsClient
```

Element-type / accessor changes (module-local): `Task.execute`, `AsyncDispatcher.submit`, `WatermillPubTask.execute`, `TaskFactory.getTask` all change their `List of Message` parameter to `List of QueueMessage[String]`; `message.getBody()` → `msg.getPayload()`; `getReceiptHandle()` unchanged. `ResponseObserver`'s injected `SQSClient` becomes the appianway-commons `SqsClient` facade (`deleteMessage`, `getVisibilityTimeout` — unchanged signatures).

### 4.2 DeadLetterService — DLQ redrive (unchanged cadence: every 30 min, 3-empty-poll-and-stop loop)

```
  ListenerManager scheduler (30 min) ─▶ DeadLetterService.run()
    loop retry under 3, until source empty:
        MessagingClient.receiveMessages(sourceQueue=inttra_int_sqs_watermill_ce_dlq, wait=20s, max=10) ─▶ List of QueueMessage[String]
        has messages:
           for each: MessagingClient.sendMessage(targetQueue=inttra_int_sqs_watermill_ce, msg.getPayload())
                     MessagingClient.deleteMessage(sourceQueue, msg.getReceiptHandle())
        empty ─▶ retry++
```

Redrive routing preserved exactly: source `{queueUrl}_dlq` → target `{queueUrl}` (both derived from `sqsPickupConfig.queueUrl`). No queue names change.

---

## 5. Configuration changes

### 5.1 Property-key table — exact INT values (unchanged names/values)

| Property key | INT value | Consumed by (yaml path) | Change? |
|---|---|---|---|
| `componentName` | `watermill-publisher` | `componentName` | none |
| `watermill-publisher.pickupSQSConfig.queueUrl` | `.../inttra_int_sqs_watermill_ce` | `sqsPickupConfig.queueUrl` | none |
| `watermill-publisher.pickupSQSConfig.waitTimeSeconds` | default `20` | `sqsPickupConfig.waitTimeSeconds:-20` | none |
| `watermill-publisher.pickupSQSConfig.maxNumberOfMessages` | default `5` | `sqsPickupConfig.maxNumberOfMessages:-5` | none |
| `watermill-publisher.snsEventConfig.topicArn` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `snsEventConfig.topicArn` | none |
| `watermill-publisher.sqsErrorSubscriptionConfig.queueUrl` | `.../inttra_int_sqs_subscription_errors` | `sqsErrorConfig.queueUrl` | none (config-resolved only; unreferenced in code today) |
| `watermill-publisher.s3WorkspaceConfig.bucket` | `inttra-int-workspace` | `s3WorkspaceConfig.bucket` | none |
| `watermill-publisher.listenerThreads` | default `2` | `listenerThreads:-2` | none — **2 preserved**, drives 2 `AsyncDispatcher`/`SqsListener` pairs |
| `watermill-publisher.healthCheckConfig.errorRateThreshold` | default `5.0` | `healthCheckConfig.errorRateThreshold:-5.0` | none (vestigial — no health checks registered) |
| `networkservices.healthCheckUrl` | from `network-services.properties` | `healthCheckConfig.networkServiceHealthCheckUrl` | none (vestigial) |
| `watermill-grpc.se.username.key` | `/inttra/int/appianway/watermill-grpc/se/username` | `watermillServiceConfig.userIdKey` | §5.2 — value gains `${awsps:...}` wrapper if boot-time chosen; **SSM path itself unchanged** |
| `watermill-grpc.se.password.key` | `/inttra/int/appianway/watermill-grpc/se/password` | `watermillServiceConfig.passwordKey` | same |
| `watermill-grpc.se.tenant` | `INTTRA` | `watermillServiceConfig.tenant:-INTTRA` | none |
| `watermill-grpc.se.host` | `watermill.staging.e2open.com` | `watermillServiceConfig.host` | none |
| `watermill-grpc.se.port` | `443` | `watermillServiceConfig.port:-443` | none |
| `server.connector.port` | default `8081` | `server.connector.port:-8081` | none |
| `metrics.frequency` | from properties, default 1s | `metrics.frequency` | none |

**No queue/topic/bucket/SSM-path renames anywhere.**

### 5.2 SSM parameter table — resolution mechanism decision (REQUIRED)

| SSM parameter | Consumed by | Today | Option A: runtime `CloudParameterStore` | Option B: boot-time `${awsps:/path}` | Decision |
|---|---|---|---|---|---|
| `/inttra/int/appianway/watermill-grpc/se/username` | `AuthCredentials` (gRPC `CallCredentials`, sets `username` metadata header) | `shared.SsmParameterSupplier`, eager-fetched once at Guice injector construction, cached for the JVM lifetime — functionally already a one-shot boot fetch | Replace `shared.ParameterStoreModule`/`SsmParameterSupplier` 1:1 with `CloudParameterStore` injected as a `ParameterSupplier`-shaped facade (appianway-commons); `AuthCredentials` keeps its current constructor shape | Wrap the property **value** in `${awsps:...}`: `watermill-grpc.se.username.key=${awsps:/inttra/int/appianway/watermill-grpc/se/username}`. Resolved by commons `ParameterStoreConfigTransform` **before** Dropwizard parses the YAML. `WatermillServiceConfig.userIdKey`/`passwordKey` then hold the **resolved secret value**; `AuthCredentials` reads them directly — no `ParameterSupplier`/`CloudParameterStore` injection at all. | **Option B (boot-time)** |
| `/inttra/int/appianway/watermill-grpc/se/password` | same | same | same | same | same |

**Rationale for Option B:** the current behavior is already an eager, one-shot, boot-time fetch with no re-fetch/rotation logic — moving to `${awsps:/path}` is behavior-preserving, eliminates the v1 `AWSSimpleSystemsManagement` client + `shared.ParameterStoreModule`/`SsmParameterSupplier`/`PassThroughParameterSupplier` from the dependency graph, and matches how commons handles auth secrets for the modules with a `networkServiceConfig` block — consistent mechanism across the program. **Java-local caveat:** `WatermillServiceConfig.userIdKey`/`passwordKey` field *names* would then hold the plaintext credential, not a "key" — recommend renaming the two Java fields to `userId`/`password` (a module-internal POJO rename, **not** an SSM-path/queue-name rename), or leave as-is to minimize diff (either is compile-safe). **`usePassThrough`:** never set by this module — N/A. **If Option A instead:** keep `AuthCredentials`'s constructor shape and swap only the supplier impl (lower diff), but retain an extra Guice-eager SSM round trip and port a `ParameterSupplier`-equivalent into `appianway-commons` — recorded as the fallback.

### 5.3 Config-command composition

```
classpath watermill-publisher.yaml (template)
    │
    ▼
[ appianway property subst ]  ${key} from watermill-publisher.properties + network-services.properties + datadog.properties + env
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]  ${awsps:/path} → SSM value at boot (resolves watermillServiceConfig.userIdKey/passwordKey under §5.2 Option B)
    │
    ▼
Dropwizard Configuration factory (WatermillPublisherConfiguration)
```

`WatermillPubApplication.initialize()` registers this composed command in place of `shared.command.ConfigProcessingServerCommand`. `S3ConfigurationProvider` (conditional on `CONFIG_LOCATION=s3`) stays appianway-local.

### 5.4 What is unchanged

- CLI arg shape: `run watermill-publisher.yaml conf/int/watermill-publisher.properties ../configuration/int/network-services.properties ../configuration/int/datadog.properties` (`network-services.properties` still passed for consistency even though there is no `networkServiceConfig` block and no `AuthClient` call).
- `CONFIG_REGION=US_EAST_1`; `datadog.properties`/`metrics.frequency`; port **8081**, single `simple` connector; `com.inttra.mercury` logger at DEBUG; `listenerThreads: 2`; DLQ redrive cadence (30 min, 3-empty-poll-and-stop).
- **No health checks registered** — no `registerHealthChecks` call today, none added. `/admin/opsHealthcheck` stays **404**; verification remains boot-evidence.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Assumed gap | Exercised by watermill-publisher? | Detail |
|---|---|---|
| **S-G2** (`StorageClient` metadata-write overloads) | **No** | Production S3 access is `getContent` (read) only; the only S3 *write* was in the deleted scratch `Test.java`. |
| **W-G9** (`Event`/`MetaData`/`Annotations` parity) | **Partially — `MetaData` only, already compatible** | Round-trips `MetaData` (SQS body → parse) but never touches `Event`/`Annotations`/`EventLogger`. `MetaData` fields/order/`@JsonInclude`/builder are identical. `metaData.getProjections().get("dxRoutes")` is a `Map` lookup by raw string key, unaffected by the `Projection` constant-set lag (W-G9.2). |
| **X-G7 / X-G8 / C-G6 / O-G1 / O-G3** | No | not an email/ES/config-widen/reusable-listener concern; module keeps its own concurrency model. |

**Consumes:** cloud-sdk-api `MessagingClient[String]`, `QueueMessage[String]`, `StorageClient` (read), `NotificationService`, `MetaData` (+ `CloudParameterStore` if Option A); cloud-sdk-aws v2 SQS/S3/SNS/SSM impls; commons `ConfigProcessingServerCommand` + transforms.
**Moves to `appianway-commons`:** `Task`/`TaskFactory` (element type → `QueueMessage[String]`), `AsyncDispatcher` (+ its `Dispatcher` interface), `ListenerManager`, `DeadLetterService`, and a new thin `SqsClient`/`SqsListener` facade over `MessagingClient[String]`. `WatermillPubTask`, `StatusEventGrpcClient`, `ResponseObserver`, `AuthCredentials`, `WatermillServiceConfig`, `HealthCheckConfig`, and the whole `se/transformer/*` package stay module-local.

---

## 7. Maven dependency changes

**Remove:** `com.inttra.mercury.shared:mercury-shared`; `com.amazonaws:aws-java-sdk-sqs` (transitively pulled the v1 SQS/S3/SNS/SSM clients). Confirm removal of the dead commented-out `org.zapodot.hystrix.bundle.HystrixBundle` import.

**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK **v2** arrives transitively via `cloud-sdk-aws`'s BOM — do not declare it directly.

**Retained unchanged (gRPC/protobuf/jaxb — all NON-AWS, DW5/Java-17-verified):** `com.google.protobuf:protobuf-java:4.33.1`, `io.grpc:grpc-netty-shaded`/`grpc-protobuf`/`grpc-stub` (via `grpc-bom 1.77.0`), `javax.annotation-api`, `protobuf-java-format:1.4`, `org.glassfish.jaxb:jaxb-runtime:4.0.4` (runtime), `protobuf-maven-plugin 0.6.1`, `jaxb2-maven-plugin 3.2.0` (xjc build), `maven-shade-plugin`, `commons-cli`, `lombok`.

**Verify:** `mvn -pl watermill-publisher -am clean verify` (shade needs `clean`). Fat-jar boot against INT — since there is no ops health-check endpoint, verification is **boot-evidence**: gRPC stream creation log lines, `SqsListener` starting on `inttra_int_sqs_watermill_ce` with zero post-boot errors, and (Option B) successful config-command boot (an unresolved `${awsps:}` fails fast, itself proving SSM resolution).

---

## 8. Tests

- **`DeadLetterServiceTest`:** re-point to the appianway-commons `SqsClient`/`MessagingClient[String]` facade; assert `{queueUrl}_dlq` → `{queueUrl}` redrive, `getPayload()` body, `getReceiptHandle()` delete, the 3-consecutive-empty-poll retry-and-stop loop. Replace v1 `Message` doubles with `QueueMessage[String]` doubles.
- **`WatermillPubTaskTest`:** feed `List of QueueMessage[String]`; assert `getPayload()` → `MetaData` parse, `StorageClient.getContent(bucket, fileName, ISO_8859_1)`, transform-exception path → `deleteMessage` + no gRPC invoke, success path → `grpcClient.invoke(event, receiptHandle)`. Assert `metaData.getProjections().get("dxRoutes")` still resolves via plain `Map` lookup.
- **`WatermillPubModuleTest`:** assert 2 (`listenerThreads`) `SqsListener`/`AsyncDispatcher` pairs wired, `DeadLetterService` gets `{queueUrl}_dlq`/`{queueUrl}` source/target, gRPC channel/stub providers untouched.
- **`ResponseObserverTest`:** re-point `SQSClient`→`SqsClient` facade mock; assert `getVisibilityTimeout(queueName)` and `deleteMessage(queueName, receiptHandle)` on ack.
- **`AuthCredentialsTest`:** if Option B adopted, construct `AuthCredentials` directly from `WatermillServiceConfig` (no `ParameterSupplier` mock) and assert the three gRPC metadata headers (`username`/`password`/`tenant`) come from the already-resolved config fields.
- **gRPC-only tests** (`StatusEventProtobufTransformerTest`, `XMLTransformer`-related, `*Map` enum tests): **unchanged** — NON-AWS.
- **`task/Test.java`:** delete (scratch load-generator, never wired in).
- **`functional-testing`** (test-scope): re-pointed to `cloud-sdk-api`-shaped SQS/S3/SNS fakes (`QueueMessage[String]`-based). New/updated tests on JUnit 5.

---

## 9. Rollout & verification

Per the program order, watermill-publisher sits **after** the core apps and **before** the 4 watermill consumers:

```
... ─▶ email-sender, transformer ─▶ watermill-publisher ─▶ booking-inbound-consumer, cargoscreen-consumer, itv-gps-consumer, visibility-inbound-consumer
```

1. Confirm `appianway-commons` (slim residue) and `functional-testing` fakes landed.
2. Swap the local `Task`/`AsyncDispatcher`/`TaskFactory`/`WatermillPubTask`/`DeadLetterService`/`ResponseObserver` element type `Message` → `QueueMessage[String]`; rename `getBody()`→`getPayload()` at each call site.
3. Delete `task/Test.java`.
4. Make the §5.2 SSM decision concrete (recommend Option B): update `WatermillServiceConfig`/`AuthCredentials`, the yaml `watermillServiceConfig.userIdKey`/`passwordKey` tokens (unchanged tokens; only the underlying property value gains `${awsps:...}`), and the properties file.
5. Rebind `ExternalServicesModule` (drop v1 `AmazonSQS`/`S3`/`SNS`/`AWSSimpleSystemsManagement`; install cloud-sdk-aws clients) and `WatermillPubModule` (bind appianway-commons `SqsClient`/`SqsListener`, `StorageClient`, `NotificationService`) — gRPC channel/stub providers untouched.
6. Update `WatermillPublisherConfiguration` to extend `io.dropwizard.core.Configuration` directly (drop `shared.BaseConfiguration`) and declare its own AWS config fields using cloud-sdk-aws config types.
7. `mvn -pl watermill-publisher -am clean verify`; run the DLQ redrive equivalence test end-to-end against a disposable/test queue pair if available, else the retry-loop unit test.
8. **INT boot verification** (reuse the exact command): confirm Jetty 12.1.9/Java 17 clean boot; `StatusEventGrpcClient` creates streams to `watermill.staging.e2open.com:443` (proves SSM creds resolved); `SqsListener` starts on `inttra_int_sqs_watermill_ce` with zero post-boot errors; `ListenerManager`/`DeadLetterService` start; **no ops health-check exists** — boot-evidence-only.
9. Roll out alongside/just before the 4 watermill consumer modules (they share the gRPC/DynamoDB-offset pattern but are a separate, no-parent-pom Maven tree).

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| SSM resolution mechanism change (§5.2) silently breaks gRPC auth (wrong tenant/user/password header) | Boot-time `${awsps:}` fails fast on an unresolved token (server refuses to start) — a clean boot is proof of correct resolution; confirmed indirectly by `StatusEventGrpcClient : Creating new streams....` with no immediate `UNAUTHENTICATED` gRPC error |
| DLQ redrive semantics change (`_dlq` → main) | Preserve source/target derivation exactly; keep the 3-retry-on-empty loop; add/keep an equivalence test |
| `QueueMessage[String]` loses body/receipt/attribute semantics vs. v1 `Message` | `getPayload()`/`getReceiptHandle()` + `Map[String,String]` attributes are 1:1; unit-test the accessor rename everywhere it appears |
| `MetaData` field drift after adopting the cloud-sdk-api type | Fields/order/date-pattern/builder identical; still assert a JSON round-trip using a real SQS body sample |
| Accidentally porting scratch `Test.java` behavior (S3 write + delayed SQS send) into production | Delete it outright; it is the only place this module ever wrote to S3 or set a message delay |
| `HealthCheckConfig`/`networkServiceHealthCheckUrl` fields are vestigial (no health checks, no `networkServiceConfig`) | Leave as-is for this migration; flag as a candidate cleanup for a future pass |
| `getVisibilityTimeout` on the `SqsClient` facade needs a `MessagingClient.getQueueAttributes` equivalent | Confirm the cloud-sdk-api `MessagingClient[String]` exposes queue-attribute lookup (used by `ResponseObserver` to size its ack-expiry window); if not directly exposed, wrap it once in the facade — small local addition, not a cloud-sdk change |
| Lockstep coupling with `appianway-commons`/`functional-testing` landing first | Sequence strictly after those two; gate behind `mvn -pl watermill-publisher -am verify` |
| gRPC/protobuf/jaxb layer regresses during an AWS-focused change | Out of scope by design — no gRPC/protobuf/`se/transformer/*` files are touched; the ION-16098 boot evidence (streams established on `jaxb-runtime 4.0.4`) remains the baseline proof |
