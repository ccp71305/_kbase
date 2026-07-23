# visibility-inbound-consumer — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `watermill/visibility-inbound-consumer` (parent = the `watermill` aggregator pom only — no appianway root parent) · Main: `VisibilityInboundConsumerApplication` · Port 8085 · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only visibility-inbound-consumer's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098) · >10 MB gRPC max message size (ION-15497, `maxInboundMessageSize(50*1024*1024)`) · component-name change (ION-13768) — all DONE. Verified booting clean against INT (richest consumer — 3x DynamoDB offset read + 3x gRPC channel init).
> **Scope:** AWS v1→v2 + drop-`shared` only. The gRPC/protobuf layer (`ConsumerManager`, `ConsumerInitUtil`, the three transformers, `AuthCredentials`) is **not AWS** and is untouched. `watermill/consumer-commons` co-migrates.

---

## Contents

---

## 1. Overview

**Purpose.** `visibility-inbound-consumer` is the **richest** of the four appianway Watermill gRPC consumers. It runs **three independent gRPC stream consumers in a single process**:

| Consumer class | gRPC topic (INT) | Transforms via | Sends to SQS |
|---|---|---|---|
| `VisibilityInboundConsumer` | `INTTRA_INT-INTTRACONTAINEREVENT` | `ContainerEventTransformer` → `mercury:visibility` model (`ContainerEventSubmission`) | `inttra_int_sqs_ce_wm_inbound` (Shippeo container events) |
| `CargoVisibilitySubscriptionConsumer` | `INTTRA_INT-INTTRACWSUBSCRIPTIONRESPONSE` | `CargoVisibilitySubscriptionTransformer` → local `CargoVisibilitySubscription` model | `inttra_int_sqs_ce_cw_subscription_inbound` |
| `CargoVisibilityEventConsumer` | `INTTRA_INT-INTTRACWCONTAINEREVENT` | `ContainerEventProtoMapper` → local `ContainerEvent` model | `inttra_int_sqs_ce_cw_event_inbound` |

Each consumer has its **own** `OffsetUtil` (in-memory cursor), its own `OffsetUpdateScheduler` (15-minute DynamoDB flush), and shares a single `ConsumerManager`-per-topic reconnect/backoff wrapper. All three archive both the transformed JSON and the raw proto (and, on batch error, the whole batch) to the shared **S3 workspace bucket**, and all three route a `MetaData` envelope onto their respective SQS queue for `mercury-services` `visibility`. `VisibilityInboundConsumer` additionally emits a workflow `Event` to **SNS** (`inttra_int_sns_event_ce`) via `EventLogger`.

**Current state.** AWS Java SDK v1 (`AmazonS3`, `AmazonSQS`, `AmazonSNS`, `AmazonDynamoDB`/`DynamoDBMapper`, SSM via `shared.parameterstore.ParameterStoreModule`) constructed directly in `ExternalServicesModule`/`WatermillConsumerModule`. Workflow model is `shared`'s `event.Event`/`event.EventLogger`/`task.MetaData`/`workspace.Annotations`. DynamoDB offset entity uses v1 datamodeling annotations mapped via a hand-rolled `DynamoDBMapper` + in-house `DynamoDBCrudRepository` (`dynamo-client` jar). gRPC/protobuf is **not AWS** and does not change.

**Target.** `commons` + `cloud-sdk-api` + `cloud-sdk-aws` (`1.0.27-SNAPSHOT`) + slim `appianway-commons`, with the DynamoDB offset store, `S3PublishService`, `SQSClient`-equivalent, `SNSEventPublisher`-equivalent, and `ParameterStore`-equivalent consolidated in **`watermill/consumer-commons`** (shared by all 4 gRPC consumers, migrated once, consumed here unchanged in call shape). No `appianway-commons` residue is needed beyond the composed config transform — the watermill consumers have no health-check glue and no `AsyncDispatcher`/task-lifecycle usage of the appianway-commons kind (this module's own local `AsyncDispatcher`/`task` package is a **different, gRPC-lifecycle-only** dispatcher, unrelated to the SQS-listener `AsyncDispatcher` in appianway-commons).

**Headline change.** This is the **widest AWS surface of the whole 14-module program on a single process**: 3x DynamoDB offset row + 3x SQS send target + 1x SNS publish + 1x S3 bucket, multiplied by the coordination hazard of **three concurrent gRPC streams sharing one Guice injector**. The correctness-critical piece is preserving the **exact physical table name and per-topic attribute values** in DynamoDB — three independent cursors coexist in one `{env}_watermill_offset` table keyed by topic name, and a silent remap of any one re-consumes a live tracking feed from offset 0. **S-G2** is not needed (every S3 write is metadata-free). **W-G9** **is** relevant — every SQS-bound `MetaData` and the SNS-bound `Event`/`Annotations` ride the cloud-sdk-api workflow model, so annotation round-trip parity matters on both the error-annotation path (`extractWatermillErrorTokens`/`extractTokens` populate `Annotations` on transform failure) and the `EventLogger.logCloseRunEvent(..., tokens, annotations)` SNS path.

---

## 2. Current vs Target architecture

```
BEFORE — AWS v1 + shared, per-topic gRPC x3
  gRPC INTTRACONTAINEREVENT          ─▶ VisibilityInboundConsumer (StreamObserver[RawData])       ─▶ ContainerEventTransformer ─▶ mercury:visibility model
  gRPC INTTRACWSUBSCRIPTIONRESPONSE  ─▶ CargoVisibilitySubscriptionConsumer                       ─▶ CargoVisibilitySubscriptionTransformer
  gRPC INTTRACWCONTAINEREVENT        ─▶ CargoVisibilityEventConsumer                              ─▶ ContainerEventProtoMapper
  all 3 ─▶ S3PublishService.uploadToS3 (consumer-commons, v1 AmazonS3, PutObjectResult ignored) ─▶ inttra-int-workspace
  all 3 ─▶ shared SQSClient.sendMessage (v1 AmazonSQS "amazonSQSForSender") ─▶ 3 SQS: ce_wm_inbound / ce_cw_subscription_inbound / ce_cw_event_inbound
  VisibilityInboundConsumer only ─▶ shared SNSEventPublisher (v1 AmazonSNS) ─▶ SNS inttra_int_sns_event_ce
  all 3 ─▶ OffsetUtil x3 (in-memory) ─▶ OffsetUpdateScheduler x3 (15 min) ─▶ WatermillOffsetDao (DynamoDBCrudRepository, v1 DynamoDBMapper) ─▶ DynamoDB {env}_watermill_offset (3 rows keyed by topicName)
  AuthCredentials (gRPC) ─▶ shared ParameterStoreModule (v1 AWSSimpleSystemsManagement)

AFTER — commons + cloud-sdk (AWS v2), gRPC layer UNCHANGED
  same 3 gRPC topics ─▶ same 3 consumer classes (unchanged) ─▶ same 3 transformers (unchanged, recompiled vs visibility jar)
  all 3 ─▶ S3PublishService.uploadToS3 (consumer-commons, over StorageClient) ─▶ inttra-int-workspace
  all 3 ─▶ SQSClient equivalent over cloud-sdk-api MessagingClient[String] ─▶ SAME 3 SQS queues
  VisibilityInboundConsumer only ─▶ SNSEventPublisher equivalent over cloud-sdk-api NotificationService ─▶ SAME SNS topic
  all 3 ─▶ OffsetUtil x3 (in-memory, unchanged) ─▶ OffsetUpdateScheduler x3 (unchanged shape) ─▶ WatermillOffsetDao adapter over DatabaseRepository[WatermillOffset,String] (cloud-sdk-aws DynamoRepositoryFactory) ─▶ DynamoDB {env}_watermill_offset (SAME 3 rows, SAME attribute names)
  AuthCredentials (gRPC, unchanged) ─▶ ParameterStore equivalent over cloud-sdk-api CloudParameterStore
```

### 2.1 Class-level mapping

| `shared`/v1 element (this module + `consumer-commons`) | Replacement | Home | Notes |
|---|---|---|---|
| `com.amazonaws.services.s3.AmazonS3` (+ builder) | `cloud-sdk-api StorageClient` | cloud-sdk-api/aws | `S3PublishService.uploadToS3(bucket, key, String payload)` → `StorageClient.putObject(bucket,key,bytes)`. **Metadata-free ⇒ S-G2 not used.** |
| `com.amazonaws.services.sqs.AmazonSQS` (`@Named("amazonSQSForSender")`, `sqs_sender`) | `cloud-sdk-api MessagingClient[String]` | cloud-sdk-api/aws | `shared.messaging.SQSClient.sendMessage(url, body)` → `MessagingClient[String].sendMessage(url, body)`. Producer-only here (no listener — this module never polls SQS). |
| `com.amazonaws.services.sns.AmazonSNS` (`sns_publish`) | `cloud-sdk-api NotificationService` | cloud-sdk-api/aws | `shared.event.SNSEventPublisher(topicArn, SNSClient)` → wraps `NotificationService.publish(topicArn, message)`. |
| `AmazonDynamoDB`/builder, `DynamoDBMapper`/`DynamoDBMapperConfig`, in-house `DynamoDBCrudRepository` (`dynamo-client` jar) | `DatabaseRepository[WatermillOffset,String]` via `DynamoRepositoryFactory` | cloud-sdk-api/aws | `WatermillOffsetDao` becomes a thin adapter (`findOne`/`save`/`update` signatures preserved so `WatermillOffsetService`/`OffsetUtil`/`OffsetUpdateScheduler` are **untouched**). |
| `@DynamoDBTable("watermill_offset")`, `@DynamoDBHashKey("topicName")`, `@DynamoDBAttribute offset/readDateTime/writeDateTime`, `@DynamoDBTypeConverted(DateToEpochSecond)`, `@DynamoDBStream(KEYS_ONLY)` | `@Table("watermill_offset")` + `@DynamoDbPartitionKey @DynamoDbField("topicName")` + `@DynamoDbField(...)` + `LongEpochSecondAttributeConverter` | cloud-sdk-api | **Exact attribute names + epoch-seconds shape preserved** — correctness-critical remap (§10 R1). |
| `DynamoSupport.newClient`/`newMapper`/`newDynamoDBMapperConfig` (`AwsClientBuilder.EndpointConfiguration`, table-name-prefix resolver) | `DynamoDbClientConfig.endpointOverride(...)` + `Region.of(signingRegion)`; `DynamoRepositoryFactory.createEnhancedRepository(..., tableName="{env}_watermill_offset")` (explicit prefix) | cloud-sdk-aws | Table-name prefix logic moves from a per-class resolver to an explicit `tableName` argument — same resulting physical name. |
| `shared.parameterstore.ParameterStoreModule` + `ParameterSupplier` (v1 `AWSSimpleSystemsManagement`) | `CloudParameterStore` | cloud-sdk-api/aws | `AuthCredentials` (gRPC call credentials, unchanged class) reads `userIdKey`/`passwordKey` via the migrated supplier — gRPC layer itself untouched. |
| `shared.event.{Event,EventLogger,RandomGenerator}` | cloud-sdk-api `notification.workflow.{Event,EventLogger,EventGenerator}` | cloud-sdk-api | `EventLogger.logCloseRunEvent(metaData, Event.SubType.CLOSE_WORKFLOW, rootWorkflowId, null, componentName, startDateTime, eventStatus, tokens, annotations)` — same 9-arg call shape; used on all 3 consumers' per-item and per-batch error paths. |
| `shared.task.MetaData` (`Builder`, `.getProjections()`, `.toJsonString()`) | cloud-sdk-api `notification.workflow.MetaData` | cloud-sdk-api | Field-identical; `Builder` 7-arg constructor and `Projection` map usage unchanged. |
| `shared.workspace.{Annotation,Annotations}` | cloud-sdk-api `notification.annotation.{Annotation,Annotations}` | cloud-sdk-api | Used on **every** transform-failure and batch-failure branch in all 3 consumers (`annotations.addAnnotations(ERROR, EXCEPTION, stackTrace)`). W-G9-relevant (§6). |
| `shared.command.ConfigProcessingServerCommand` + `shared.config.S3ConfigurationProvider` | `commons ConfigProcessingServerCommand` + composed appianway transform; `S3ConfigurationProvider` retained (appianway-local) if `CONFIG_LOCATION=s3` | commons + appianway-commons | §5. Not exercised at INT (filesystem config). |
| `com.inttra.mercury.dynamo.respository.module.DynamoDbConfig` (config POJO field) | cloud-sdk-aws `DynamoDbClientConfig`-compatible POJO (or retain the existing shape) | cloud-sdk-aws | Field names (`environment`, `readCapacityUnits`, `writeCapacityUnits`, `sseEnabled`) **unchanged** in the YAML. |
| `shared.config.{S3Config, SNSConfig}` (config fields) | cloud-sdk config equivalents (`CloudStorageConfig`, `NotificationClientConfig`) or retained shape | cloud-sdk-aws / module | `s3WorkspaceConfig.bucket`, `snsEventConfig.topicArn` field names unchanged. |
| gRPC/protobuf (`com.e2open.watermill.proto.*`, `ConsumerManager`, `ConsumerInitUtil`, `AuthCredentials`, three transformers, `WatermillServiceConfig`, `HealthCheckConfig`) | **UNCHANGED — not AWS** | module / consumer-commons | Including the >10 MB `maxInboundMessageSize` (ION-15497, done) and the reconnect/backoff logic in `ConsumerManager`. |
| `com.inttra.mercury:visibility:1.0.M` model jar | **same jar, retained as a domain dependency** — not part of the AWS migration | module (external) | `ContainerEventSubmission`, `Date`, `DateFormat`, `containerEvent.*` types. Model-jar version alignment is **out of scope** for this doc. |

---

## 3. AWS touchpoints

| Touchpoint | Direction | INT resource name | cloud-sdk client | Notes |
|---|---|---|---|---|
| gRPC (topic 1) | inbound (consume) | `INTTRA_INT-INTTRACONTAINEREVENT` @ `watermill.staging.e2open.com:443`, tenant `INTTRA_INT` | n/a (not AWS) | `VisibilityInboundConsumer`; Shippeo container events. |
| gRPC (topic 2) | inbound (consume) | `INTTRA_INT-INTTRACWSUBSCRIPTIONRESPONSE` (same host/tenant) | n/a | `CargoVisibilitySubscriptionConsumer`. |
| gRPC (topic 3) | inbound (consume) | `INTTRA_INT-INTTRACWCONTAINEREVENT` (same host/tenant) | n/a | `CargoVisibilityEventConsumer`. |
| DynamoDB (offset 1) | read+write | `{inttra_int}_watermill_offset`, hash key `topicName = INTTRA_INT-INTTRACONTAINEREVENT` | `DatabaseRepository[WatermillOffset,String]` (cloud-sdk-aws enhanced client) | Verified INT offset **35** at last check. |
| DynamoDB (offset 2) | read+write | same table, hash key `topicName = INTTRA_INT-INTTRACWSUBSCRIPTIONRESPONSE` | same | Verified INT offset **43**. |
| DynamoDB (offset 3) | read+write | same table, hash key `topicName = INTTRA_INT-INTTRACWCONTAINEREVENT` | same | Verified INT offset **79**. |
| S3 | write only (metadata-free) | `inttra-int-workspace` | `StorageClient.putObject(bucket,key,bytes)` | Shared by all 3 consumers: transformed-JSON object, raw-proto (`_proto` suffix) object, and on `batchSize>1 and error` the whole batch JSON. **S-G2 not needed.** |
| SNS | publish only | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event_ce` | `NotificationService` (via consumer-commons `SNSEventPublisher` equivalent) | Only `VisibilityInboundConsumer` publishes today; `EventLogger.logCloseRunEvent(...)` is the call site on all 3, but only the container-event path is wired to the publisher provider — confirm on migration whether the other two should also emit (§10 R5). |
| SQS (out 1) | producer | `inttra_int_sqs_ce_wm_inbound` (`shippeoInboundQueueUrl`) | `MessagingClient[String].sendMessage(url, MetaData.toJsonString())` | Consumed downstream by `mercury-services` `visibility` (Shippeo container events). |
| SQS (out 2) | producer | `inttra_int_sqs_ce_cw_subscription_inbound` (`cargoVisibilitySubscriptionQueueUrl`) | same | Consumed downstream by `visibility-wm-inbound-processor` (updates APPROVED/REJECTED subscription state). |
| SQS (out 3) | producer | `inttra_int_sqs_ce_cw_event_inbound` (`cargoVisibilityEventQueueUrl`) | same | Consumed downstream by `mercury-services` `visibility` (CargoWise container events). |
| SES | — | n/a | n/a | Not used. |
| Param Store (SSM) | resolved at gRPC-call time (not boot) | `/inttra/int/appianway/watermill-grpc/se/username`, `.../password` | `CloudParameterStore` (via `ParameterSupplier`) | One `username`/`password` key pair shared across all 3 topics; `AuthCredentials` reads them per-topic instance but from the same SSM paths. No `networkServiceConfig` block → no `AuthClient`/`/auth` HTTP call. |
| Port | n/a | `8085` | n/a | No parent pom; `../../configuration`. No health checks registered — `opsHealthcheck` → 404. |

---

## 4. Sequences

### 4.1 Startup — seed three consumption offsets + open three gRPC channels

```
  VisibilityInboundConsumerApplication ─▶ WatermillConsumerModule (Guice @Provides)
    for each of 3 topics (container / subscription / event):
       WatermillOffsetService.getOffset(topicName) ─▶ WatermillOffsetDao.findOne(hashKey=topicName) ─▶ DatabaseRepository.findById(topicName) ─▶ GetItem(PK topicName)
          offset present ─▶ offset=N ─▶ ConsumptionRequest.offsetStart = N+1
          absent         ─▶ initializeOffset(topic, -1L) ─▶ save() ─▶ offsetStart = 0
    register 3x OffsetUpdateScheduler (Managed lifecycle, 15-min cadence)
    3x ConsumerManager.setConsumer(this) + consumerStub.consumeForever(request, observer)
    3 independent gRPC channels to watermill.staging.e2open.com:443, maxInboundMessageSize 50MB (ION-15497)
```

### 4.2 Steady state — Shippeo container event: consume → transform → S3 + SQS + SNS → offset

```
  gRPC (INTTRACONTAINEREVENT) ─▶ VisibilityInboundConsumer: RawData @ offset k, batch of ContainerEvent upserts
    for each ContainerEvent in batch:
       ContainerEventTransformer.transform(containerEvent) ─▶ ContainerEventSubmission   [mercury:visibility model]
       S3PublishService.uploadToS3(bucket, workspaceFileName, rawJson) ─▶ StorageClient.putObject(bucket, key, bytes)   [metadata-free, no S-G2]
       metaData.getProjections().put("messageType","ShippeoContainerEvent")
       MessagingClient[String].sendMessage(shippeoInboundQueueUrl, metaData.toJsonString())
       S3PublishService.uploadToS3(bucket, workspaceFileName+"_proto", rawInputProtoJson)
       EventLogger.logCloseRunEvent(metaData, CLOSE_WORKFLOW, rootWorkflowId, ..., tokens, annotations) ─▶ publish Event via SNSEventPublisher(snsEventConfig.topicArn)
    OffsetUtil.updateOffset(k)   [in-memory; flushed by this topic's scheduler]
```

### 4.3 CW subscription response — consume → transform → SQS (subscription state return path)

```
  gRPC (INTTRACWSUBSCRIPTIONRESPONSE) ─▶ CargoVisibilitySubscriptionConsumer: RawData @ offset k (CargowiseSubscription upserts)
    for each subscription:
       CargoVisibilitySubscriptionTransformer.transform(subscription) ─▶ CargoVisibilitySubscription (local model)
       S3PublishService.uploadToS3(bucket, workspaceFileName, rawJson)
       metaData.getProjections().put("messageType","CargoVisibilitySubscription")
       MessagingClient[String].sendMessage(cargoVisibilitySubscriptionQueueUrl, body)
    OffsetUtil.updateOffset(k)
    (downstream: mercury-services visibility-wm-inbound-processor updates APPROVED/REJECTED)
```

### 4.4 Periodic offset flush + gRPC error/reconnect (per topic)

```
  OffsetUpdateScheduler (x3, one per topic; every offsetUpdateDelay=15 min):
     WatermillOffsetService.updateOffset(topic, offsetUtil.getOffset()) ─▶ DatabaseRepository.save/update(WatermillOffset{topicName,offset,readDateTime})   [last-writer-wins]
        ─▶ PutItem (enhanced client; default extensions inert, no @DynamoDbVersionAttribute)
  ConsumerManager (x3) on gRPC onError (per topic, independently):
     updateOffset(topic, offsetUtil.getOffset())   [persist before reconnect]
     determineIfShouldRetry (NonRetryableException ─▶ respect maxRetry, else always retry)
     sleep retryDelay seconds ─▶ reconnect(): new ManagedChannel + consumeForever(persisted+1, SAME observer)
```

**At-least-once preserved, per topic independently:** each of the 3 topics advances its own in-memory cursor and is flushed by its own `OffsetUpdateScheduler` (`Managed.stop()` also flushes on shutdown); on restart or reconnect each stream resumes at `persisted+1`. A crash between flushes re-consumes from the last persisted offset for **that topic only** — identical to today's v1 implementation.

---

## 5. Configuration changes

### 5.1 Property-key table (INT values — exact, unchanged names/values)

| YAML key | INT value | Notes |
|---|---|---|
| `componentName` | `visibility-inbound-consumer` | `${componentName:-visibility-inbound-consumer}` |
| `healthCheckConfig.errorRateThreshold` | default `5.0` | Config POJO field exists but **no health checks are registered** — config-resolved only. |
| `healthCheckConfig.networkServiceHealthCheckUrl` | from `network-services.properties` | Same — unused by any registered check. |
| `s3WorkspaceConfig.bucket` | `inttra-int-workspace` | |
| `server.connector.port` | default `8085` | **Not 8081** — watermill consumers default to 8085. |
| `watermillServiceConfig.userIdKey` | `/inttra/int/appianway/watermill-grpc/se/username` | SSM path, see §5.2. |
| `watermillServiceConfig.passwordKey` | `/inttra/int/appianway/watermill-grpc/se/password` | SSM path, see §5.2. |
| `watermillServiceConfig.tenant` | `INTTRA_INT` | gRPC call-credential metadata (`AuthCredentials`), not AWS. |
| `watermillServiceConfig.host` / `port` | `watermill.staging.e2open.com` / `443` | External e2open service, not AWS. |
| `watermillServiceConfig.topicName` | `INTTRA_INT-INTTRACONTAINEREVENT` | Topic 1 (Shippeo container events). |
| `watermillServiceConfig.subscriptionTopicName` | `INTTRA_INT-INTTRACWSUBSCRIPTIONRESPONSE` | Topic 2. |
| `watermillServiceConfig.eventTopicName` | `INTTRA_INT-INTTRACWCONTAINEREVENT` | Topic 3. |
| `watermillServiceConfig.retryDelay` | default `10` (s) | `ConsumerManager` backoff before reconnect. |
| `watermillServiceConfig.maxRetry` | default `3` | per `ConsumerManager` instance (per topic). |
| `watermillServiceConfig.offsetUpdateDelay` | `15` (min) | drives all 3 `OffsetUpdateScheduler`s. |
| `watermillServiceConfig.keepAliveTime`/`keepAliveTimeout`/`idleTimeout` | `30`s / `20`s / `30`min | gRPC channel, not AWS. |
| `dynamoDbConfig.readCapacityUnits` / `writeCapacityUnits` | `25` / `25` (yaml) | table-create-time only. |
| `dynamoDbConfig.environment` | `inttra_int` | table-name prefix → physical `inttra_int_watermill_offset`. |
| `dynamoDbConfig.sseEnabled` | `false` (yaml) | |
| `snsEventConfig.topicArn` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event_ce` | |
| `shippeoInboundQueueUrl` | `.../inttra_int_sqs_ce_wm_inbound` | |
| `cargoVisibilitySubscriptionQueueUrl` | `.../inttra_int_sqs_ce_cw_subscription_inbound` | |
| `cargoVisibilityEventQueueUrl` | `.../inttra_int_sqs_ce_cw_event_inbound` | |
| `logging.level` | default `INFO`; `com.inttra.mercury` hardcoded `DEBUG` in yaml | |

**gRPC max message size (ION-15497).** `ConsumerInitUtil.getChannel(...)` hardcodes `.maxInboundMessageSize(50 * 1024 * 1024)` on the `NettyChannelBuilder` (not a `${...}` property) — already >10 MB, already done, **not AWS**, unaffected. **No renames** — all property keys/values above are unchanged.

### 5.2 SSM parameter table

| Path | Resolution mechanism | Consumer |
|---|---|---|
| `/inttra/int/appianway/watermill-grpc/se/username` | Runtime, per gRPC channel — `ParameterSupplier.getValue(key)` → `CloudParameterStore` (v2 SSM `GetParameter`) at `AuthCredentials` construction | Shared by all 3 topics' `AuthCredentials` instances (same `userIdKey`) |
| `/inttra/int/appianway/watermill-grpc/se/password` | Same mechanism | Same |

**Not boot-time `${awsps:...}`.** These two paths are read **on gRPC call**, not at Dropwizard boot, and there is no `networkServiceConfig` block — keep the existing runtime-resolution model (`ParameterSupplier`/`CloudParameterStore`); converting to `${awsps:/path}` would require plumbing `AuthCredentials`' construction through the config-command chain instead of Guice, unnecessary churn for two values already resolved correctly. `usePassThrough` is not used by this module.

### 5.3 Config-command wiring

```
classpath visibility-inbound-consumer.yaml
    │
    ▼
[ appianway property subst ]  ${key} from visibility-inbound-consumer.properties + env (appianway-commons transform)
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]  (no-op here — no ${awsps:...} tokens in this yaml)
    │
    ▼
Dropwizard Configuration factory (VisibilityInboundConsumerConfiguration)
```

`T3` is present for consistency with the other 13 modules but is a **structural no-op** here — the two SSM paths are Guice/runtime-resolved, not yaml `${awsps:...}` tokens. `VisibilityInboundConsumerApplication.initialize(...)` swaps `shared.command.ConfigProcessingServerCommand` for the commons one wrapped by the appianway composition. `S3ConfigurationProvider.requiresS3Configuration()` conditional stays, unexercised at INT.

### 5.4 `../../configuration` note (no parent pom)

`watermill/pom.xml` has **no parent** (a standalone reactor root, mirroring the DW5/Jetty12/Jackson BOM pins locally) — so `visibility-inbound-consumer`, like its 3 siblings, resolves shared properties files **two** directory levels up: `../../configuration/int/network-services.properties` and `../../configuration/int/datadog.properties` (vs `../configuration/int/...` for the 10 non-watermill modules). This CLI shape is **unchanged**:

```
run visibility-inbound-consumer.yaml conf/int/visibility-inbound-consumer.properties ../../configuration/int/network-services.properties ../../configuration/int/datadog.properties
```

### 5.5 Transform composition (module-specific, non-AWS)

Each of the 3 consumers composes exactly one transformer per topic, unaffected by the AWS migration:
- `VisibilityInboundConsumer` → `new ContainerEventTransformer()` (instantiated inline) → `ContainerEventSubmission` (mercury:visibility jar).
- `CargoVisibilityEventConsumer` → injected `ContainerEventProtoMapper` → local `ContainerEvent`.
- `CargoVisibilitySubscriptionConsumer` → static `CargoVisibilitySubscriptionTransformer.transform(...)` → local `CargoVisibilitySubscription`.

These stay **exactly as-is**; only the S3/SQS/SNS/DynamoDB calls downstream change client.

### 5.6 What's unchanged

CLI arg shape and `-DCONFIG_REGION=US_EAST_1`; port **8085** default, no health checks, `opsHealthcheck` → 404; all 3 topic names, all 3 SQS queue URLs, the SNS topic ARN, the S3 bucket name, the DynamoDB `environment` prefix — **none renamed**; gRPC host/port/tenant, `maxInboundMessageSize` 50 MB, keep-alive/idle timeouts.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap ID | Relevant here? | How this module exercises it |
|---|---|---|
| **S-G2** | **No.** | Every S3 write (`S3PublishService.uploadToS3`) is metadata-free — `PutObjectResult` discarded, no `ObjectMetadata`/content-type set, none added. Maps to the plain `StorageClient.putObject(bucket,key,bytes)` overload. |
| **W-G9** | **Yes.** | This module both **produces** `MetaData` (onto 3 SQS queues, consumed by `mercury-services` `visibility`) and **emits** `Event`+`Annotations` (via `EventLogger.logCloseRunEvent`, SNS-bound). Every consumer's `catch (TransformationException / Exception e)` branch constructs an `Annotations` and calls `annotations.addAnnotations(ERROR, EXCEPTION, stackTrace)` — if cloud-sdk-api's `Event.Builder` drops annotations on parse (the confirmed W-G9.1 defect), any downstream re-hydration of this module's own archived `_proto`/batch JSON carrying annotations would silently lose them. The **direct SNS emission path is write-only** here (this module only *produces* `Event`s, never *consumes* them back), so W-G9.1 is lower-severity for this module than for event-writer, but the `extractWatermillErrorTokens`/`extractTokens` → `Annotation`/`Annotations` shape must match cloud-sdk-api's identically (confirmed identical). W-G9.2 (missing `Projection`/`Token` constants) does **not** block this module — it uses ad-hoc `Map` keys (`"messageType"`, `TOKENS_*` constants) rather than `MetaData.Projection.*`/`Event.Token.*` enums. |
| **X-G7 / X-G8** | No. | No email / OpenSearch. |
| **C-G6** | Optional, not required. | §5.3 composition works without widening `getConfigTransformer`. |

**Consolidates in `watermill/consumer-commons`** (shared by all 4 gRPC consumers, migrated once, consumed here unchanged in call shape): `WatermillOffset` (entity remap), `WatermillOffsetDao` (adapter over `DatabaseRepository`), `WatermillOffsetService`/`OffsetUtil`/`OffsetUpdateScheduler` (unchanged call shape), `S3PublishService` (`AmazonS3` → `StorageClient`), `DynamoSupport` (→ `DynamoDbClientConfig`/`DynamoRepositoryFactory`).

**Stays module-local:** the three `StreamObserver[RawData]` consumer classes, `ConsumerManager`, `ConsumerInitUtil`, `AuthCredentials`, `WatermillConsumerModule`/`ExternalServicesModule` (Guice wiring — rebinds AWS clients but stays module-local), the three transformers, and the local `AsyncDispatcher`/`task` package (a **gRPC-lifecycle task dispatcher local to this module**, distinct from the appianway-commons `AsyncDispatcher` used by the SQS-listener modules — this module has no SQS listener, only an SQS *sender*, so it needs no appianway-commons concurrency residue at all). `com.inttra.mercury:visibility` model jar — out of scope.

---

## 7. Maven dependency changes

**Current parent (unchanged):** `com.inttra.mercury:watermill:1.0`. This is **not** the appianway root pom — `watermill/pom.xml` is a standalone reactor root with **no parent of its own**; it already mirrors the DW5/Jetty12/Jackson-2.21.4/httpcore BOM pins locally (ION-16098). This migration adds the cloud-sdk/commons BOM mirror to that same `dependencyManagement` block, alongside the existing pins:

Add to `watermill/pom.xml` `<properties>`: `mercury.commons.version=1.0.27-SNAPSHOT`. Add to `<dependencyManagement>`: `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `${mercury.commons.version}`).

**`visibility-inbound-consumer/pom.xml` — remove:** transitively (via `consumer-commons` + `shared`) `com.amazonaws:aws-java-sdk-{s3,sqs,sns,ssm,dynamodb,core}`; the in-house `com.inttra.mercury:dynamo-client:1.0` local-repo jar (once `DynamoDBCrudRepository`/`DynamoSupport` usage is gone). `com.inttra.mercury:shared` is not a direct dependency (arrives via `consumer-commons`) — disappears once `consumer-commons` migrates.

**`visibility-inbound-consumer/pom.xml` — add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (versions managed by `watermill/pom.xml`); `consumer-commons` (already a direct dependency, version `1.0` — its internals migrate in place); AWS SDK v2 arrives transitively via `cloud-sdk-aws`. **No `appianway-commons` dependency is required** (no SQS-listener concurrency, no health-check glue to rebind). `com.inttra.mercury:visibility:1.0.M` (+ its local repo pointing at `lib/`) **retained unchanged** — model-jar version alignment is **out of scope** for this AWS-only doc.

**Align (unaffected, already done by ION-16098):** `io.dropwizard.version` 5.0.2, `jetty.version` 12.1.9, `jackson.bom.version` 2.21.4, httpcore5/httpcomponents4 pins, `google-guice` 7.0.0, Java 17 (in `watermill/pom.xml`, inherited via the `<parent>watermill</parent>`); `io.grpc:*` 1.77.0, `protoc-gen-grpc-java`, `com.google.protobuf:protoc:4.33.1` — unchanged, non-AWS; JUnit Jupiter 5.14.2 / Mockito 4.11.0 / AssertJ 3.24.2 (tests already JUnit 5, no vintage bridge needed).

**Verify:** `mvn -pl watermill/visibility-inbound-consumer -am clean verify` green (shade needs `clean`). Fat-jar boot from the module dir — expect the same 3x DynamoDB-offset-read + 3x gRPC-channel-init evidence, now backed by cloud-sdk-aws v2 clients.

---

## 8. Tests

**Direction:** already JUnit 5 (Jupiter) + Mockito throughout — **no JUnit 4→5 migration needed**.

**Offset persistence (per topic, in `consumer-commons`):**
- Move `WatermillOffsetDaoTest`/`WatermillOffsetServiceTest` to a `dynamo-integration-test` fixture (DynamoDB-Local). Assert write→read round-trip; attribute names `topicName`/`offset`/`readDateTime`/`writeDateTime` stored **exactly**; epoch-**seconds** date value via `LongEpochSecondAttributeConverter`; `findById(absent)` → empty → triggers `initializeOffset`.
- **Backward-compat fixture (critical — data-plane safety):** seed DynamoDB-Local with real-shaped `{env}_watermill_offset` items for **all three** topic keys (`INTTRA_INT-INTTRACONTAINEREVENT` offset 35, `INTTRA_INT-INTTRACWSUBSCRIPTIONRESPONSE` offset 43, `INTTRA_INT-INTTRACWCONTAINEREVENT` offset 79 — the exact INT values captured at last check) and assert the migrated entity deserializes them and each resumes at `persisted+1` **independently**.

**Unit tests to update (mechanical, client-swap driven):**
- `VisibilityInboundConsumerTest`, `CargoVisibilityEventConsumerTest`, `CargoVisibilitySubscriptionConsumerTest` — replace the `SQSClient` mock with a `MessagingClient[String]` mock (assert `sendMessage(queueUrl, metaData.toJsonString())` per queue); replace `S3PublishService`'s injected `AmazonS3` mock with a `StorageClient` mock (assert `putObject(bucket,key,bytes)`, no metadata/content-type since S-G2 is not used); replace `EventLogger`'s underlying `SNSEventPublisher`/`AmazonSNS` mock with a `NotificationService` mock.
- `ConsumerManagerTest` — unaffected by the AWS-client swap (depends on `WatermillOffsetService`, which keeps its call shape); re-verify `handleErrorAndReconnect`/`determineIfShouldRetry` still pass unchanged.
- `AuthCredentialsTest` — replace `ParameterSupplier` mock backing with the cloud-sdk-api-based implementation; assert the same 4 gRPC metadata headers (`username`/`password`/`tenant`/`topic`) are still applied.
- `WatermillConsumerModuleTest`/`ExternalServicesModuleTest` — update Guice binding assertions from v1 AWS client types to `StorageClient`/`MessagingClient[String]`/`NotificationService`/`DatabaseRepository`.
- **Annotations round-trip guard (W-G9, §6):** add a test asserting that an `Annotations` object built via `annotations.addAnnotations(ERROR, EXCEPTION, stackTrace)` and serialized into a `MetaData`/`Event` JSON, then re-parsed via cloud-sdk-api, reproduces the same annotation content — guards this module's error-path annotation usage against the W-G9.1 defect class even though this module doesn't directly consume `Event.parseJson(...)` output.

**Transformers (unchanged, non-AWS):** `ContainerEventTransformerTest`, `ContainerEventProtoMapperTest`, `CargoVisibilitySubscriptionTransformerTest` — no changes required.

**Create-table:** if a `DynamoTableCommand`-equivalent exists for this table, assert `DynamoDbAdminUtil`/`DynamoDbAdminCommand` creates `{env}_watermill_offset` with `readCapacityUnits=25`/`writeCapacityUnits=25`/`sseEnabled=false` and the `KEYS_ONLY` stream spec if still required.

---

## 9. Rollout & verification

**Position in program order:** last group — `watermill-publisher`, then the 4 watermill consumers. Within that group, sequence `consumer-commons` first (all 4 consumers depend on its offset-store remap), then this module (the widest surface, so it lands **last** among the 4 siblings to benefit from bugs already shaken out by booking-inbound/cargoscreen/itv-gps).

1. Confirm `watermill/pom.xml`'s `dependencyManagement` mirror (§7) includes the cloud-sdk/commons BOM alongside the existing Jetty/Jackson pins.
2. Migrate `watermill/consumer-commons` first — `WatermillOffset`/`WatermillOffsetDao`/`WatermillOffsetService`/`S3PublishService`/`DynamoSupport` → cloud-sdk-aws. `mvn -pl watermill/consumer-commons -am verify` green, including the `dynamo-integration-test` backward-compat fixture (§8) seeded with **all three** this-module topic keys.
3. Update `visibility-inbound-consumer/pom.xml` per §7; `mvn -pl watermill/visibility-inbound-consumer -am clean verify`.
4. Rebind `ExternalServicesModule` (v1 `AmazonS3`/`AmazonSNS`/`AmazonSQS` → `StorageClient`/`NotificationService`/`MessagingClient[String]`; `ParameterStoreModule` → `CloudParameterStore`-backed equivalent) and `WatermillConsumerModule` (v1 `AmazonDynamoDB`/`DynamoDBMapper` → cloud-sdk-aws `DynamoRepositoryFactory`/`DatabaseRepository`). **Do not touch** the three `StreamObserver` classes' gRPC logic, `ConsumerManager`, `ConsumerInitUtil`, or the transformers beyond their constructor-injected client types.
5. Local INT boot verification: expect clean Jetty 12.1.9/EE10 boot bound `0.0.0.0:8085`; **3x** offset-read log lines (`Offset found for topic <X> . Offset <N>`) matching the pre-migration values (35/43/79 at last check); **3x** `Channel initialized successfully` / observer-init lines; **3x** `OffsetUpdateScheduler` start messages; zero exceptions. `/admin/healthcheck` → 200 (default `deadlocks` only); `/admin/opsHealthcheck` → 404 (unchanged).
6. Drive at least one message through each of the 3 topics (or via a functional/integration harness against DynamoDB-Local + fake SQS/S3/SNS) and confirm: transformed JSON + raw-proto JSON land in `inttra-int-workspace`; the correct `MetaData` body lands on the corresponding one of the 3 SQS queues; the SNS `Event` publish succeeds; each topic's offset advances **independently** in DynamoDB.
7. Only after this module is green does the program's rollout sequence complete (this is the last of the 14).

---

## 10. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **R1 — Offset-table data-shape incompatibility, any one of 3 topics** | Wrong physical table name or a renamed attribute on **any** of the 3 rows ⇒ silent re-consumption from offset 0 on a **live tracking feed**, or duplicate/skipped delivery to `mercury-services` `visibility` | **Highest priority in this module.** Preserve the physical table name via an explicit `tableName` argument to `DynamoRepositoryFactory.createEnhancedRepository(...)` (not a resolver); keep exact attribute names via `@DynamoDbField`; keep epoch-seconds via `LongEpochSecondAttributeConverter`; gate cutover on the `dynamo-integration-test` fixture seeded with **all three** real topic keys/offsets before touching this module. |
| **R2 — Three concurrent gRPC streams sharing one Guice injector, one rebind pass** | A binding mistake (e.g. wiring the wrong `OffsetUtil`/`ConsumptionRequest` to the wrong topic) breaks all 3 consumers simultaneously | The `@Named(...)` bindings (`visibilityInboundConsumerOffsetUtil`/`cargoSubscriptionConsumerOffsetUtil`/`visibilityEventConsumerOffsetUtil` and their `ConsumptionRequest` counterparts) are **untouched** — only the AWS client types underneath `WatermillOffsetService`/`S3PublishService` change, not the Guice topology. Compile-time verification plus the 3-distinct-offset-log boot check catches a mis-wire immediately. |
| **R3 — SQS body / message size** | Large container-event payloads on any of the 3 queues | Payloads are archived to S3 first; only the `MetaData` (S3 ref, not the payload) goes on SQS, so all 3 queues stay well under 256 KB. gRPC `maxInboundMessageSize` (50 MB, ION-15497) is separately already-done and non-AWS. |
| **R4 — `Annotations`/`Event` wire parity (W-G9)** | If cloud-sdk-api's `Event.Builder` silently drops annotations on parse, any later re-hydration of this module's S3-archived batch-error JSON (or SNS-delivered `Event`) loses annotation data | Land W-G9.1 in cloud-sdk-api before this module's rollout completes; add the round-trip guard test (§8) using this module's own error-annotation construction pattern. Lower severity than event-writer (doesn't re-consume its own archive), but required for cross-module consistency. |
| **R5 — SNS publish scope ambiguity** | Only `VisibilityInboundConsumer` is wired to the `snsEventPublisher` provider today; confirm whether the other two consumers are intentionally silent on SNS or whether that's a pre-existing gap | Out of scope to *change* in this AWS-only migration — preserve exactly which consumers publish to SNS today; do not add or remove SNS call sites as a side effect. Flag to the module owner if intentional vs. accidental. |
| **R6 — `dynamo-client` local-repo jar removal** | The in-house `dynamo-client-1.0.jar` backs `DynamoDBCrudRepository`/`DynamoHashKey` — removing it without full `consumer-commons` migration first breaks the build | Sequence `consumer-commons`'s Dynamo remap **strictly before** this module's pom changes; do not remove the `dynamo-client` dependency until `WatermillOffsetDao` no longer extends `DynamoDBCrudRepository`. |
| **R7 — Enhanced-client default extensions altering offset writes** | Default extensions (versioning, atomic counters) could alter last-writer-wins semantics if accidentally enabled | Confirmed inert for this entity (no `@DynamoDbVersionAttribute`/`@DynamoDbAtomicCounter`); assert plain `PutItem` semantics in the `dynamo-integration-test` fixture. |
| **R8 — SSM credential resolution for gRPC `AuthCredentials`, shared across 3 topics** | If `CloudParameterStore` resolution behaves differently from the v1 `ParameterSupplier`, all 3 gRPC channels fail to authenticate simultaneously (single shared username/password) | Verify the two SSM paths resolve correctly in a dev/INT run before broad rollout — the 3x `Channel initialized successfully` boot evidence is the direct proof, since `AuthCredentials` construction happens at consumer-init time for all 3. |
| **R9 — Any cloud-sdk/commons change (W-G9) breaking mercury-services** | Regression in the production consumer of `cloud-sdk-api`/`cloud-sdk-aws` | W-G9 is strictly additive (new builder method + string constants); verify via cloud-sdk CI + full mercury-services build green before/after. |
