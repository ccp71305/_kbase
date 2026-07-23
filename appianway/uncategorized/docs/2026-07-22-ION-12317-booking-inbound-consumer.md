# booking-inbound-consumer — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `com.inttra.mercury:booking-inbound-consumer:1.0` (sub-module of the standalone `watermill` reactor — **no parent** to the appianway root) · Main: `BookingInboundConsumerApplication` · Port 8085 · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only booking-inbound-consumer's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`) — verified booting clean against INT (DynamoDB offset read 35→36 + gRPC channel live at boot).
> **Scope:** the AWS-v1→v2 rebind + `shared`→`commons`/`cloud-sdk-api`/`cloud-sdk-aws`/`appianway-commons` migration only. The gRPC/protobuf consume layer (`Watermill` `consumeForever`, `BookingChangeEvent`→`BookingRequestContract` via `BookingTransformer` + ~41 type-maps, reconnect) is **not AWS** and is untouched. `watermill/consumer-commons` (the shared offset/S3/config-POJO library) **migrates alongside** and its rebind is fully specified here.

---

## Contents

---

## 1. Overview

`booking-inbound-consumer` is a **full pipeline-entry** gRPC consumer: it subscribes to one e2open Watermill topic (`INTTRA_INT-BOOKINGINBOUND`), parses proto `BookingChangeEvent` (filtering `BOOKING_STATE_REQUEST`/`AMEND`/`CANCEL`), transforms each `Booking.Transaction` to INTTRA's `BookingRequestContract` via `BookingTransformer` (+ ~41 type-map classes, from the `com.inttra.mercury:booking:2.1.1.M` model jar), archives the JSON to S3, hands a `MetaData` envelope to **one** SQS queue that feeds the booking workflow engine, and logs `START_WORKFLOW`/`CLOSE_WORKFLOW` events to SNS.

- **Current state:** DW5 baseline landed. AWS layer still on **AWS Java SDK v1 (1.12.720)** entirely through `shared` (`com.inttra.mercury.shared.*`) — pulled in transitively via `consumer-commons`, not declared directly in this module's own pom. DynamoDB rides the in-house `com.inttra.mercury:dynamo-client:1.0` (`DynamoDBCrudRepository`) on top of v1 `DynamoDBMapper`.
- **Target:** `1.0.27-SNAPSHOT` — `commons` (config command, `InttraServer` base) + `cloud-sdk-api`/`cloud-sdk-aws` (S3/SQS/SNS/SSM/DynamoDB v2 clients, `MetaData`/`Event`/`EventLogger` workflow model) + slim `appianway-commons` (residue: `AsyncDispatcher`/task base, `S3ConfigurationProvider`, gRPC-credential `ParameterSupplier` wrapper, config-transform glue). `shared` fully retired.
- **Headline change:** the **DynamoDB offset store** — `WatermillOffset` (`{env}_watermill_offset`, `inttra_int_watermill_offset` on INT) — moves from v1 `DynamoDBMapper`/`DynamoDBCrudRepository` (`dynamo-client`) to the cloud-sdk-aws **DynamoDB enhanced client** via `DatabaseRepository[WatermillOffset,String]`/`DynamoRepositoryFactory`, read at boot and flushed every 15 min by `OffsetUpdateScheduler`. This is the data-plane-safety-critical surface — offsets are consumed by other members of the shared Watermill topic, so table/attribute-shape preservation is non-negotiable (§10).
- Secondary: S3 write (`inttra-int-workspace`, metadata-free — **S-G2 not exercised**), SQS send (1 queue, `inttra_int_sqs_bk_inbound`), SNS publish (`inttra_int_sns_event`, START/CLOSE_WORKFLOW **Events** — depends on **W-G9**), SSM gRPC credentials. `consumer-commons` migrates in lockstep (§7).

---

## 2. Current vs Target architecture

```
BEFORE — DW5 baseline, AWS v1 (current develop)
  BookingInboundConsumerApplication
     ─▶ shared ConfigProcessingServerCommand + S3ConfigurationProvider
     ─▶ ExternalServicesModule: AmazonS3, AmazonSNS, AmazonSQS(@Named amazonSQSForSender), shared ParameterStoreModule (SSM gRPC creds)
     ─▶ WatermillConsumerModule: AmazonDynamoDB + DynamoDBMapper (dynamo-client DynamoDBCrudRepository)
  BookingInboundConsumer (StreamObserver)
     ─▶ BookingTransformer + 41 type-maps (NON-AWS, booking:2.1.1.M)
     ─▶ S3PublishService (consumer-commons) ─▶ AmazonS3.putObject(bucket,key,String)
     ─▶ shared SQSClient ─▶ AmazonSQS.sendMessage
     ─▶ shared EventLogger/SNSEventPublisher ─▶ AmazonSNS
     ─▶ OffsetUtil/WatermillOffsetService ─▶ WatermillOffsetDao ─▶ DynamoDBMapper
  AuthCredentials ─▶ shared ParameterSupplier ─▶ AWSSimpleSystemsManagement

AFTER — commons + cloud-sdk (AWS v2), appianway-commons residue
  BookingInboundConsumerApplication
     ─▶ commons ConfigProcessingServerCommand + appianway-commons transform composition + appianway-commons S3ConfigurationProvider
     ─▶ ExternalServicesModule: cloud-sdk-api CloudParameterStore (SSM gRPC creds, via appianway-commons wrapper)
     ─▶ WatermillConsumerModule: cloud-sdk-aws DynamoRepositoryFactory ─▶ DatabaseRepository[WatermillOffset,String] (enhanced client)
  BookingInboundConsumer (StreamObserver)
     ─▶ BookingTransformer + 41 type-maps (NON-AWS, unchanged)
     ─▶ S3PublishService (consumer-commons) ─▶ cloud-sdk-api StorageClient.putObject(bucket,key,bytes)
     ─▶ cloud-sdk-api MessagingClient[String].sendMessage
     ─▶ cloud-sdk-api notification.workflow.EventLogger ─▶ NotificationService (SNS)
     ─▶ OffsetUtil/WatermillOffsetService ─▶ WatermillOffsetDao ─▶ DatabaseRepository
  AuthCredentials ─▶ CloudParameterStore
```

### 2.1 Class/type-level mapping (this module + `consumer-commons`)

| File (this module unless noted) | Current (`shared`/v1) | Target (`commons`/`cloud-sdk-*`/`appianway-commons`) |
|---|---|---|
| `BookingInboundConsumerApplication.initialize()` | `shared.command.ConfigProcessingServerCommand` | `commons ConfigProcessingServerCommand` **+ appianway-commons composed transform** (§5) |
| `BookingInboundConsumerApplication.initialize()` | `shared.config.S3ConfigurationProvider` | appianway-commons `S3ConfigurationProvider` (moved, behavior identical) |
| `BookingInboundConsumerApplication` | dead `org.zapodot.hystrix.bundle.HystrixBundle` import | **removed** |
| `ExternalServicesModule` | `AmazonS3`/`AmazonS3ClientBuilder` | `S3PublishService`'s injected `StorageClient` (cloud-sdk-api, bound in `consumer-commons`) |
| `ExternalServicesModule` | `AmazonSNS` (`AWSClientConfiguration.sns_publish`) | cloud-sdk-api `NotificationService` (cloud-sdk-aws SNS impl) |
| `ExternalServicesModule` | `AmazonSQS` `@Named("amazonSQSForSender")` (`sqs_sender`) | cloud-sdk-api `MessagingClient[String]` (cloud-sdk-aws SQS impl) |
| `ExternalServicesModule` | `shared.parameterstore.ParameterStoreModule(userIdKey, passwordKey)` | appianway-commons Guice module providing a `ParameterSupplier`-shaped wrapper over `CloudParameterStore` |
| `ExternalServicesModule` | `shared.networkservices.NetworkRetryerModule` | **dropped** — no `networkServiceConfig` block; dead code (no `AuthClient` call at boot) |
| `WatermillConsumerModule` | `AmazonDynamoDB` + `DynamoDBMapper` + `DynamoDBMapperConfig` (via `DynamoSupport`, `consumer-commons`) | cloud-sdk-aws `DynamoDbClientConfig` + `DynamoRepositoryFactory.createEnhancedRepository(...)` → bind `DatabaseRepository[WatermillOffset,String]` |
| `WatermillConsumerModule.snsEventPublisher()` | `shared.event.SNSEventPublisher(topicArn, SNSClient)` | cloud-sdk-api `notification.workflow.EventPublisher`/`SnsEventPublisher` over `NotificationService` |
| `BookingInboundConsumerConfiguration` | `com.inttra.mercury.dynamo.respository.module.DynamoDbConfig` (dynamo-client) | module-local/appianway-commons `DynamoDbConfig` POJO (same fields: `readCapacityUnits`, `writeCapacityUnits`, `environment`, `sseEnabled`) feeding cloud-sdk-aws `DynamoDbClientConfig`/`DynamoRepositoryConfig` |
| `BookingInboundConsumerConfiguration` | `shared.config.S3Config` | cloud-sdk-aws `CloudStorageConfig` (same `bucket` field) |
| `BookingInboundConsumerConfiguration` | `shared.config.SNSConfig` | cloud-sdk-aws `NotificationClientConfig` (same `topicArn` field) |
| `grpc/AuthCredentials` | `shared.parameterstore.ParameterSupplier` | `CloudParameterStore` via the appianway-commons wrapper — **same 2-call shape** (`getValue(userIdKey)`, `getValue(passwordKey)`) |
| `grpc/BookingInboundConsumer` | `shared.event.Event`, `EventLogger`, `RandomGenerator` | cloud-sdk-api `notification.workflow.Event`/`EventLogger` (W-G9-verified parity); `RandomGenerator` → appianway-commons thin wrapper (or inline `UUID.randomUUID()`) |
| `grpc/BookingInboundConsumer` | `shared.messaging.SQSClient` | cloud-sdk-api `MessagingClient[String]` |
| `grpc/BookingInboundConsumer` | `shared.support.Json` (`DATE_FORMATTER`) | cloud-sdk-api `util.DateConstants`/`JsonSupport` (identical `yyyy-MM-dd HH:mm:ss.SS` pattern) |
| `grpc/BookingInboundConsumer` | `shared.task.MetaData` (`Builder`, `Projection.*`, `EXIT_STATUS_*`) | cloud-sdk-api `notification.workflow.MetaData` (identical fields/builder; `ORIGINAL_FILENAME`/`INFTPFILEPICKUPTIME`/`CONTEXT_CODE` all in the 26-constant set already present, not among the W-G9.2 gaps) |
| `consumer-commons WatermillOffset` (vo) | `@DynamoDBTable`/`@DynamoDBHashKey`/`@DynamoDBAttribute`/`@DynamoDBTypeConverted(DateToEpochSecond)` (v1) | cloud-sdk-api `@Table("watermill_offset")` / `@DynamoDbPartitionKey @DynamoDbField("topicName")` / `@DynamoDbField(...)` + `LongEpochSecondAttributeConverter` — **attribute names + epoch-seconds shape preserved exactly** |
| `consumer-commons WatermillOffsetDao` | `extends DynamoDBCrudRepository[WatermillOffset, DynamoHashKey[String]]` | thin adapter over `DatabaseRepository[WatermillOffset,String]` (`findOne`/`save`/`update` shape retained so `WatermillOffsetService`/`OffsetUtil`/`OffsetUpdateScheduler` are byte-for-byte unchanged) |
| `consumer-commons DynamoSupport` | `newClient`/`newMapper`/`newDynamoDBMapperConfig` (v1) | folded into `DynamoRepositoryFactory.createEnhancedRepository(...)` — explicit `tableName = "{environment}_watermill_offset"` reproduces the v1 prefix resolver |
| `consumer-commons S3PublishService` | `AmazonS3.putObject(bucket, path, String)` | `StorageClient.putObject(bucket, key, bytes)` — **metadata-free, S-G2 not needed** |
| `consumer-commons DateToEpochSecond` | `DynamoDBTypeConverter[Long,Date]` (v1) | `LongEpochSecondAttributeConverter` (cloud-sdk-api) — identical `getTime()/1000` mapping |

**Unchanged (non-AWS):** `BookingInboundConsumer` (`StreamObserver[RawData]`), `WatermillConsumerTask`/`AsyncDispatcher` (moved home only — task base to appianway-commons, logic identical), `ConsumerInitUtil` (Netty gRPC channel), `BookingTransformer` + all type-map classes, `TransformationException`, `MessageKeys`, `booking:2.1.1.M` model jar dependency.

---

## 3. AWS touchpoints

| Surface | Direction | INT resource | Current (v1) | Target (v2) |
|---|---|---|---|---|
| **DynamoDB** (offset) | read (boot) + write (15-min flush + on-error) | `inttra_int_watermill_offset` (physical = `{environment}_watermill_offset`, `environment=inttra_int`) | `AmazonDynamoDB` + `DynamoDBMapper` (`dynamo-client`) | cloud-sdk-aws DynamoDB **enhanced client** → `DatabaseRepository[WatermillOffset,String]` via `DynamoRepositoryFactory` |
| **S3** | write only | `inttra-int-workspace` | `AmazonS3.putObject(bucket,key,String)` (no metadata) | `StorageClient.putObject(bucket,key,bytes)` — **metadata-free, S-G2 NOT exercised** |
| **SQS** | send only, 1 queue | `inttra_int_sqs_bk_inbound` | `AmazonSQS` (`@Named amazonSQSForSender`) via shared `SQSClient.sendMessage` | `MessagingClient[String].sendMessage(url, body)` |
| **SNS** | publish only | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `AmazonSNS` via shared `SNSEventPublisher`/`EventLogger` | `NotificationService` (via `notification.workflow.EventPublisher`/`EventLogger`) — **W-G9 applies** (this module does **not** set annotations on its `Event`s, so it is not exposed to the W-G9.1 defect, but still consumes the corrected jar) |
| **SSM** (Param Store) | read, gRPC creds only | `/inttra/int/appianway/watermill-grpc/se/username`, `.../password` | `AWSSimpleSystemsManagement` via shared `ParameterSupplier`/`ParameterStoreModule` | `CloudParameterStore` (via appianway-commons wrapper) |
| **gRPC** (non-AWS) | consume (stream) | `watermill.staging.e2open.com:443`, topic `INTTRA_INT-BOOKINGINBOUND` | `io.grpc` + `grpc-netty-shaded`, `ConsumerGrpc.ConsumerStub` | **unchanged** |
| Health checks | — | — | none registered | **unchanged** — verification is boot-evidence only, port **8085** (`/admin/opsHealthcheck` → 404) |

---

## 4. Sequences

### 4.1 Steady state — consume → transform → S3 + SQS + SNS → in-memory offset

```
  gRPC stream (INTTRA_INT-BOOKINGINBOUND) ─▶ RawData @ offset k (BookingChangeEvent: REQUEST/AMEND/CANCEL)
  BookingInboundConsumer:
     BookingTransformer.transform(BookingTransaction) ─▶ BookingRequestContract JSON   [NON-AWS]
     S3PublishService.uploadToS3(inttra-int-workspace, "{rootWorkflowId}/{uuid}", json) ─▶ StorageClient.putObject(bucket, key, bytes)   [metadata-free]
     build MetaData(rootWorkflowId, bucket, key, contextCode="requestBooking")
     MessagingClient[String].sendMessage(inttra_int_sqs_bk_inbound, metaData.toJsonString())
     EventLogger.logCloseRunEvent(START_WORKFLOW, success=true) ─▶ NotificationService
     OffsetUtil.updateOffset(k)   [in-memory only, not yet persisted]
```

### 4.2 Transformation failure path (poison message)

```
  BookingTransformer.transform(proto) ─▶ TransformationException
     EventLogger.logCloseRunEvent(CLOSE_WORKFLOW, success=false)   [no S3/SQS send]
     OffsetUtil.updateOffset(k)   [offset still advances — poison msg not retried indefinitely]
```

### 4.3 Boot offset-seed + periodic offset-flush (DynamoDB v2)

```
  WatermillConsumerModule ─▶ WatermillOffsetService.getOffset("INTTRA_INT-BOOKINGINBOUND")
     ─▶ WatermillOffsetDao.findOne(WatermillOffset{hashKey=topic}) ─▶ DatabaseRepository.findById(topic) ─▶ GetItem(PK topicName)
        present ─▶ offset=N (e.g. 35) ─▶ startOffset = N + 1 (36)
        absent  ─▶ initializeOffset(topic, -1L) ─▶ save() ─▶ PutItem ; startOffset = 0
  OffsetUpdateScheduler (every offsetUpdateDelay=15 min, and on Managed.stop()):
     WatermillOffsetService.updateOffset(topic, OffsetUtil.getOffset()) ─▶ Dao.update ─▶ DatabaseRepository.save ─▶ PutItem   [last-writer-wins, no optimistic lock]
```

**At-least-once semantics preserved:** cursor advances in-memory per message; the DynamoDB row is durable only on the 15-min tick, `Managed.stop()`, or the `onError` handler (which persists before reconnecting). A crash between flushes re-consumes from `persisted+1` — identical to the current v1 implementation.

---

## 5. Configuration changes

### 5.1 Property-key table (exact INT values, unchanged names)

Run command (unchanged — `../../configuration` is **two levels up**, no parent pom for the `watermill` reactor):

```
java -DCONFIG_REGION=US_EAST_1 -jar target/booking-inbound-consumer-1.0.jar run booking-inbound-consumer.yaml conf/int/booking-inbound-consumer.properties ../../configuration/int/network-services.properties ../../configuration/int/datadog.properties
```

| YAML key (template) | INT value | Notes |
|---|---|---|
| `componentName` | `booking-inbound-watermill` | used as `MetaData`/`Event` `componentName` |
| `server.connector.port` | default `8085` | port **8085**, not 8081 |
| `watermillServiceConfig.userIdKey` | `/inttra/int/appianway/watermill-grpc/se/username` | SSM path, resolved via `CloudParameterStore` (§5.2) |
| `watermillServiceConfig.passwordKey` | `/inttra/int/appianway/watermill-grpc/se/password` | SSM path |
| `watermillServiceConfig.tenant` | `INTTRA_INT` | gRPC `CallCredentials` header |
| `watermillServiceConfig.host` | `watermill.staging.e2open.com` | gRPC endpoint (non-AWS) |
| `watermillServiceConfig.port` | `443` | gRPC endpoint |
| `watermillServiceConfig.topicName` | `INTTRA_INT-BOOKINGINBOUND` | offset-table hash-key AND gRPC subscription topic |
| `watermillServiceConfig.offsetUpdateDelay` | `15` (minutes) | `OffsetUpdateScheduler` cadence |
| `watermillServiceConfig.keepAliveTime`/`keepAliveTimeout`/`idleTimeout` | `30`s / `20`s / `30`min | gRPC channel, non-AWS |
| `dynamoDbConfig.environment` | `inttra_int` | table-name prefix → physical `inttra_int_watermill_offset` |
| `dynamoDbConfig.readCapacityUnits` / `writeCapacityUnits` | `25` / `25` (yaml) | create-table path only |
| `dynamoDbConfig.sseEnabled` | `false` (yaml) | create-table path (unused — table pre-exists) |
| `s3WorkspaceConfig.bucket` | `inttra-int-workspace` | `StorageClient.putObject` target |
| `snsEventConfig.topicArn` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `NotificationService` publish target |
| `bookingInboundQueueUrl` | `.../inttra_int_sqs_bk_inbound` | `MessagingClient[String].sendMessage` target |
| `healthCheckConfig.networkServiceHealthCheckUrl` | from `network-services.properties` | **config-resolved only — never wired into a registered health check** |

**Not renamed:** no topic/queue/bucket/SSM-path renames.

### 5.2 SSM parameter table

| Parameter | Path | Current resolution | Target resolution | Decision |
|---|---|---|---|---|
| gRPC username | `/inttra/int/appianway/watermill-grpc/se/username` | shared `ParameterSupplier.getValue(key)`, called once at `AuthCredentials` construction (Guice singleton, effectively boot-time) | `CloudParameterStore.getParameter(key)` via an appianway-commons `ParameterSupplier`-shaped wrapper, same call | **Keep runtime resolution** — the values are consumed **programmatically** in a constructor field (`AuthCredentials`), not bound through the Dropwizard `Configuration` YAML, so `ParameterStoreConfigTransform` boot-time substitution doesn't apply. Mirrors watermill-publisher's identical pattern. |
| gRPC password | `/inttra/int/appianway/watermill-grpc/se/password` | same | same | same |

`network-services.properties`'s `networkservices.clientId`/`clientSecret` SSM paths are passed on the CLI but **never referenced** by this module's yaml (no `networkServiceConfig` block) — no `AuthClient` call at boot. Unchanged.

### 5.3 Config-command composition

- `BookingInboundConsumerApplication.initialize()` swaps `shared.command.ConfigProcessingServerCommand` → `commons ConfigProcessingServerCommand`, composed: appianway property-substitution transform (`${key}` from `.properties`+env) → commons `TrimConfigCommentsTransform` → commons `ParameterStoreConfigTransform` (`${awsps:/path}`, unused by this module's yaml today but available).
- The conditional `S3ConfigurationProvider.requiresS3Configuration()` check (`CONFIG_LOCATION=s3`) preserved, provider moved to appianway-commons.
- CLI arg shape, `-DCONFIG_REGION=US_EAST_1`, `datadog.properties` passthrough: **all unchanged**.

### 5.4 Run profile / path notes

- **No profiles** for this module (unlike splitter/transformer/ingestor's ce-/os- variants) — single yaml, single properties file, single topic.
- **`../../configuration` (two levels up)** — because `watermill/booking-inbound-consumer` sits two directories below the appianway root, unlike the 8081-port modules (one level, `../configuration`). Unchanged by the migration; called out because it's easy to get wrong when copying run configs.

### 5.5 Transform composition (BookingTransformer, non-AWS)

`BookingTransformer` + `CarriageTransformer`/`LocationTransformer`/`PartyTransformer`/`EquipmentTransformer`/`CommonTransformer`/`CargoTransformer` (+ ~35 `type.*TypeMap` classes) are pure Guice-injected POJOs with no AWS/config dependency — **entirely unaffected**. Recompiled only if the `booking:2.1.1.M` model jar version is bumped (a separate cross-workspace concern, §10).

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap ID | Exercised? | Detail |
|---|---|---|
| **S-G2** (metadata-aware `putObject`) | **No** | `S3PublishService.uploadToS3` is metadata-free (`StorageClient.putObject(bucket,key,bytes)`, no content-type/metadata overload needed). |
| **W-G9** (workflow-model parity) | **Yes, as a consumer of the corrected jar** | `MetaData`/`Event`/`EventLogger` come from `cloud-sdk-api notification.*`. This module does **not** set `Annotations` on its `Event`s, so it is not itself exposed to the W-G9.1 `Event.Builder` annotations-round-trip defect, but must still consume a cloud-sdk-api build with W-G9 landed (program-wide gate) since other Watermill/mercury-services apps in the same `Event`/SNS fan-out **do** carry annotations. `MetaData.Projection.ORIGINAL_FILENAME`/`INFTPFILEPICKUPTIME`/`CONTEXT_CODE` are confirmed present in the existing 26-constant set — **no blocking dependency on the constant-parity fix for this module specifically.** |
| X-G7 / X-G8 / C-G6 | Not applicable | no email, no OpenSearch/Jest; config composition works without widening `getConfigTransformer`. |
| DynamoDB v2 (de-scoped as a cloud-sdk change — native feature) | **Yes — primary consumer** | `DynamoRepositoryFactory.createEnhancedRepository(...)`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`. `@DynamoDbVersionAttribute` is available but **intentionally unused** — matches current last-writer-wins semantics. |

**Consumes from `commons`:** `ConfigProcessingServerCommand`, `TrimConfigCommentsTransform`/`ParameterStoreConfigTransform`, `InttraServer` base (no health-check registrar used).
**Consumes from `cloud-sdk-api`:** `StorageClient`, `MessagingClient[String]`, `NotificationService`, `CloudParameterStore`, `notification.workflow.{MetaData,Event,EventLogger,EventPublisher}`, `DatabaseRepository[T,ID]`.
**Consumes from `cloud-sdk-aws`:** S3/SQS/SNS/SSM v2 impls, DynamoDB enhanced client, `DynamoRepositoryFactory`, `DynamoDbClientConfig`, `LongEpochSecondAttributeConverter`, `DynamoDbAdminUtil`.
**Moves to `appianway-commons`:** `AsyncDispatcher`/task lifecycle base (this module's own `task.AsyncDispatcher`/`task.WatermillConsumerTask` retain their shape, just no longer duplicate a `shared` base class), `S3ConfigurationProvider`, the gRPC-credential `ParameterSupplier`-over-`CloudParameterStore` wrapper, the appianway property-substitution config transform.

---

## 7. Maven dependency changes

**No parent pom** for the `watermill` reactor root — `watermill/pom.xml` does not inherit the appianway root's `dependencyManagement`, so all BOM/version pins must be mirrored directly in `watermill/pom.xml` (already true for the ION-16098 Jetty/Jackson pins). This module's `booking-inbound-consumer/pom.xml` **does** have a `<parent>` (→ `watermill:1.0`).

### 7.1 `watermill/pom.xml` (aggregator — add BOM pins, retire the v1 property)

Add to `<properties>`: `mercury.commons.version=1.0.27-SNAPSHOT`, `appianway.commons.version=1.0-SNAPSHOT`; remove `aws-java-sdk.version` (1.12.720) once **all 5 sub-modules** (`consumer-commons` + 4 consumers) stop referencing v1 — coordinate across the 4 consumer docs before deleting. Add to `<dependencyManagement>`: `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `${mercury.commons.version}`) alongside the existing jetty/jackson/httpcore pins.

### 7.2 `booking-inbound-consumer/pom.xml`

**Remove:** `com.inttra.mercury:dynamo-client:1.0` (+ its 6 exclusions) — replaced entirely by the cloud-sdk-aws DynamoDB enhanced client, consumed transitively via `consumer-commons`. (Transitively, once `consumer-commons` migrates §7.3) `mercury-shared`, `com.amazonaws:aws-java-sdk-{sqs,dynamodb}`.
**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (`${mercury.commons.version}`), `appianway-commons` (`${appianway.commons.version}`).
**Keep unchanged:** `com.inttra.mercury:consumer-commons:1.0` (its own pom migrates per §7.3); `com.inttra.mercury:booking:2.1.1.M` (+ its existing exclusions — the jar already excludes v1 AWS SDK jars; version alignment with a cloud-sdk-aligned `booking` release is a **separate, tracked cross-workspace concern**, §10); `jackson-datatype-jsr310`, `slf4j-api`, JUnit 5/Mockito/AssertJ, `lombok`; `protobuf-maven-plugin`/`maven-shade-plugin`/compiler/surefire (gRPC/protobuf toolchain — non-AWS, untouched). Remove the dead `HystrixBundle` import.

### 7.3 `consumer-commons/pom.xml` (migrates alongside — load-bearing for this module)

**Remove:** `mercury-shared`, `com.amazonaws:aws-java-sdk-sqs`, `com.amazonaws:aws-java-sdk-dynamodb`, `com.inttra.mercury:dynamo-client:1.0` (+ exclusion).
**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `${mercury.commons.version}`), `appianway-commons`.
**Code moves (rebind, not new dependency):** `WatermillOffset` re-annotated to cloud-sdk-api DynamoDB annotations; `WatermillOffsetDao` rewritten as a `DatabaseRepository` adapter; `DynamoSupport` retired (folded into `DynamoRepositoryFactory` usage in each consumer's Guice module); `S3PublishService` rebinds `AmazonS3` → `StorageClient`; `DateToEpochSecond` retired in favor of `LongEpochSecondAttributeConverter`. `WatermillOffsetService`/`OffsetUtil`/`OffsetUpdateScheduler`/`WatermillServiceConfig`/`HealthCheckConfig` are plain POJOs — unchanged.

**Verify:** `mvn -pl watermill/booking-inbound-consumer -am clean verify` (`-am` pulls in `consumer-commons`); then `mvn -pl watermill -amd verify` once all 5 sub-modules migrate. `clean` required — shade fat jars go stale otherwise.

---

## 8. Tests

- **Offset persistence (highest priority):** `WatermillOffsetDaoTest`/`WatermillOffsetServiceTest` move to a DynamoDB-Local integration test (`dynamo-integration-test`); assert write→read round-trip with the **exact** attribute names (`topicName`/`offset`/`readDateTime`/`writeDateTime`) and epoch-**seconds** value shape.
- **Backward-compat fixture (gate, non-negotiable):** seed a DynamoDB-Local table with an item shaped exactly like a real `inttra_int_watermill_offset` row (string PK `INTTRA_INT-BOOKINGINBOUND`, numeric epoch-seconds dates) and assert the migrated `WatermillOffset` entity deserializes it and the `+1`-resume logic behaves identically.
- **S3 write:** re-point `S3PublishService`'s injected client to a `StorageClient` fake; assert `putObject(bucket, "{rootWorkflowId}/{uuid}", bytes)` called once per successful transform.
- **SQS send:** re-point `SQSClient`/`MessagingClient[String]` to a fake; assert `sendMessage("inttra_int_sqs_bk_inbound", metaData.toJsonString())` on the success path and **no send** on the `TransformationException` path.
- **SNS/EventLogger:** assert `logCloseRunEvent` fires `START_WORKFLOW` (success=true) vs `CLOSE_WORKFLOW` (success=false) against a `NotificationService` fake, targeting `snsEventConfig.topicArn`.
- **SSM/AuthCredentials:** unit-test the `CloudParameterStore`-backed `ParameterSupplier` wrapper returns the same value shape; gRPC `applyRequestMetadata` behavior unchanged and untested here (non-AWS).
- **Transformers:** unchanged unit tests; only recompile if the `booking` jar version is bumped — add a proto→`BookingRequestContract` JSON-shape assertion as a contract check (tracked separately, §10).
- **gRPC consumer/reconnect (`BookingInboundConsumer.onError`, `ConsumerInitUtil`):** unchanged, non-AWS — keep green (its `onError` calls `watermillOffsetService.updateOffset(...)`, now backed by `DatabaseRepository`, before reconnecting). Module is already JUnit 5.

---

## 9. Rollout & verification

Per the program order, this module is in the **last** wave (position 11 of 14, immediately after `watermill-publisher`, alongside the other 3 Watermill consumers):

1. `appianway-commons` lands first (slim residue: `AsyncDispatcher`/task base, `S3ConfigurationProvider`, `ParameterSupplier`-over-`CloudParameterStore` wrapper, config-transform composition) — shared by all 4 consumers.
2. `functional-testing` fakes re-pointed to `cloud-sdk-api`.
3. **`consumer-commons` DynamoDB pilot** (§7.3) — `mvn -pl watermill/consumer-commons -am verify`, gated on the backward-compat offset fixture (§8) seeded from a real `inttra_int_watermill_offset`-shaped item.
4. This module: rebind `ExternalServicesModule`/`WatermillConsumerModule`, config command, `AuthCredentials` — `mvn -pl watermill/booking-inbound-consumer -am clean verify`.
5. **INT boot evidence** (no ops health check — port **8085**): confirm in logs the enhanced-client offset-found (or absent→initialize) line for topic `INTTRA_INT-BOOKINGINBOUND`; gRPC `Channel initialized` + `Polling from offset N+1`; **zero** exceptions; `/admin/healthcheck` → 200 (deadlocks only); `/admin/opsHealthcheck` → 404 (expected). **Data-plane caveat:** running against INT briefly joins the live shared topic; confirm the run consumes **no** messages (offset unchanged) to avoid disrupting the shared consumer, or coordinate a maintenance window.
6. Aggregator `mvn -pl watermill -amd verify` once the other 3 consumers land alongside.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Offset-table data-shape incompatibility** — wrong physical table name or a renamed attribute ⇒ `inttra_int_watermill_offset` read fails or silently returns nothing → re-consumption from offset 0 → duplicate `START_WORKFLOW` events into the booking workflow engine | **Highest priority.** Preserve the explicit physical table name (`{environment}_watermill_offset` = `inttra_int_watermill_offset`) passed to `DynamoRepositoryFactory`; preserve `topicName`/`offset`/`readDateTime`/`writeDateTime` attribute names via `@DynamoDbField`; keep epoch-**seconds** via `LongEpochSecondAttributeConverter`. Gate cutover on the backward-compat fixture (§8) seeded from a real production-shaped item — **do not cut over without it.** |
| **`booking` model jar drift** — if the `com.inttra.mercury:booking` version is bumped near this migration and `BookingRequestContract`'s JSON shape moved, the SQS body the workflow engine consumes changes silently | Track jar-version alignment as a **separate, explicit decision** from the AWS-v2 rebind; diff produced JSON against a captured production sample before cutover; do not bump the `booking` version in the same PR unless both are individually verified. |
| **W-G9 program dependency** — this module consumes `cloud-sdk-api notification.workflow.*` types shared with every other Watermill/mercury-services app in the SNS fan-out | Sequence cutover **after** the W-G9 fix is confirmed in the pinned `1.0.27-SNAPSHOT` build (JSON round-trip corpus test green). This module doesn't set annotations, so it is not blocked on W-G9 for its own correctness, but the shared jar version must include the fix for program-wide safety. |
| **SSM gRPC-credential resolution regression** — if `CloudParameterStore` resolves differently than the old `AWSSimpleSystemsManagement`-backed `ParameterSupplier`, `AuthCredentials` construction fails or carries stale/blank creds → `UNAUTHENTICATED` gRPC handshake | Unit-test the wrapper against present-and-absent parameter cases; verify with an actual INT boot (gRPC `Channel initialized` + successful stream = creds resolved). |
| **Duplicate booking workflow on poison-message offset advance** — `TransformationException` path still advances the offset (existing, intentional) | Confirm preserved exactly (§4.2); keep the `catch (TransformationException)` → `logCloseRunEvent(CLOSE_WORKFLOW)` → offset-still-advances flow unchanged. |
| **Enhanced-client default extensions altering writes** (e.g. auto-versioning) | `@DynamoDbVersionAttribute` deliberately **not** added to `WatermillOffset`; confirm plain last-writer-wins `PutItem` in the integration test. |
| **`consumer-commons` shared-migration blast radius** — affects all 4 consumers | Land and verify `consumer-commons` (§7.3, §9 step 3) as its own gated step **before** touching this module's Guice modules. |
| **No health-check endpoint to prove AWS resolution post-deploy** (port 8085) | Rely on boot-log evidence (offset-found line + gRPC channel-initialized line + zero exceptions); consider adding a minimal health check as a follow-up (out of scope). |
