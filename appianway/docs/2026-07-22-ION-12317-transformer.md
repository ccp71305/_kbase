# transformer — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `transformer` · Main: `com.inttra.mercury.transformer.TransformerApplication` · Port 8081 · Three profiles (`transformer` / `ce-transformer` / `os-transformer`) · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only transformer's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`). All 3 profiles boot clean on that stack today (still on AWS v1 + `shared`), 10 ops health checks green per profile.

---

## Contents

---

## 1. Overview

**Purpose.** transformer is the **ETL hub** of appianway: it consumes canonical XML (containers, schedules, bookings) off SQS, runs it through the **Contivo** XSLT/Java mapping engine to produce carrier/customer-format output, allocates EDI **control numbers** from a DynamoDB sequence, structurally validates the output (via `structuralvalidator`), writes the transformed file to S3, republishes an `Event` to SNS, and routes the enriched `MetaData` envelope onward via SQS per a configurable `routing` map. One jar runs as **three** independent profiles that differ only by pickup queue (and ce's SNS topic); routing is shared across all three.

- **Current state (DW5 baseline):** AWS SDK v1 (`aws-java-sdk-sqs`, `-dynamodb`, `-cloudwatchmetrics`; S3/SNS transitively via `shared`) + the appianway `shared` module. `DynamoDBMapper` (v1 datamodeling) backs the control-number sequence with `@DynamoDBVersionAttribute` optimistic locking. `AwsSdkMetrics.enableDefaultMetrics()` (v1 CloudWatch SDK metrics) runs at boot. All 3 profiles verified green against INT.
- **Target:** `commons` (config command, network-services, health base) + `cloud-sdk-api`/`cloud-sdk-aws` (SQS/SNS/S3 clients, workflow model) + slim `appianway-commons` (`AsyncDispatcher`/`AbstractTask`, `ErrorHandler`/`RecoverableException`, health-indicator glue). AWS SDK v1 removed entirely; DynamoDB moves to the **native v2 enhanced client**.

**Headline changes (this is the most complex of the 14 modules):**
1. **DynamoDB control-number sequence** (`ControlNumberSequence`/`ControlNumberSequenceDao`/`ControlNumberSequenceProvider`) rewritten onto the **AWS SDK v2 DynamoDB Enhanced Client**, keeping optimistic locking via the **native** `software.amazon.awssdk.enhanced.dynamodb.extensions.annotations.@DynamoDbVersionAttribute` (the default `VersionedRecordExtension` applies automatically — **NOT a cloud-sdk change**, de-scopes G4). `DynamoTableCommand` (the `create-table` CLI verb) is rewritten onto the v2 `DynamoDbClient`.
2. **Contivo XSLT/Java runtime** is a large, self-contained vendor classpath (`com.contivo:*`, Scala/Akka/RocksDB/MapDB/Saxon/BCEL/ANTLR/...) that must be pre-flight-verified to coexist with the AWS SDK v2 + DW5/Jetty12 shaded fat jar — a §10 risk, not a code change.
3. **`AwsSdkMetrics.enableDefaultMetrics()`** (v1-only API) has no v2 drop-in — replaced by an explicit `CloudWatchMetricPublisher` wiring (or dropped), called out as a named config/observability decision (§5.6).
4. **Three profiles, one jar** — pickup queue and, for `ce-transformer`, the SNS topic differ; the `routing` map (10 dynamically-derived outbound health checks) and all other AWS touchpoints are identical across profiles.

---

## 2. Current vs Target architecture

```
BEFORE — transformer on shared + AWS v1
  inbound SQS (v1 AmazonSQS) ─▶ shared SQSListener + AsyncDispatcher
       ─▶ TransformerTask.process(Message)
              ─▶ TransformationParamsProvider + networkservices AuthClient/FormatService (shared, SSM via shared.parameterstore)
              ─▶ TransformerPreprocessors (LOCAL, unchanged)
              ─▶ StructuralValidationFAProcessor (structuralvalidator jar, unchanged)
              ─▶ TransformationProcessor ─▶ Contivo Transformer (com.contivo.*) UNCHANGED vendor runtime
              ─▶ ControlNumberGenerators ─▶ ControlNumberSequenceProvider
                     ─▶ ControlNumberSequenceDao (DynamoDBMapper v1 datamodeling, @DynamoDBVersionAttribute)
                     ─▶ DynamoDB v1 (inttra_int_controlnumber_sequence)
              ─▶ shared WorkspaceService/S3WorkspaceService (v1 AmazonS3) ─▶ S3 (inttra-int-workspace)
              ─▶ shared EventLogger/SNSEventPublisher (v1 AmazonSNS) ─▶ SNS (sns_event / sns_event_ce)
              ─▶ shared SQSClient.sendMessage (v1) ─▶ routing.outbound queues
  TransformerApplication.run() ─▶ AwsSdkMetrics.enableDefaultMetrics() (v1 CloudWatch metrics publisher)

AFTER — transformer on commons + cloud-sdk (AWS v2) + appianway-commons
  inbound SQS (v2 SqsClient) ─▶ appianway-commons AsyncDispatcher + cloud-sdk-aws MessagingClient[String] listener
       ─▶ TransformerTask.process(QueueMessage[String])
              ─▶ TransformationParamsProvider + commons networkservices AuthClient/FormatService (SSM via cloud-sdk CloudParameterStore)
              ─▶ TransformerPreprocessors — UNCHANGED
              ─▶ StructuralValidationFAProcessor — UNCHANGED
              ─▶ TransformationProcessor ─▶ Contivo Transformer — UNCHANGED (classpath/shade pre-flight, §10)
              ─▶ ControlNumberGenerators ─▶ ControlNumberSequenceProvider — retained
                     ─▶ ControlNumberSequenceDao (cloud-sdk-aws DynamoDB Enhanced Client, NATIVE v2 @DynamoDbVersionAttribute)
                     ─▶ DynamoDB v2 (inttra_int_controlnumber_sequence)
              ─▶ cloud-sdk-api StorageClient (cloud-sdk-aws S3 impl) ─▶ S3 (inttra-int-workspace)
              ─▶ cloud-sdk-api EventLogger ─▶ NotificationService (SNS v2) ─▶ SNS (sns_event / sns_event_ce)
              ─▶ cloud-sdk-api MessagingClient.sendMessage (v2) ─▶ routing.outbound queues
  TransformerApplication.run() ─▶ CloudWatchMetricPublisher (v2) or dropped — §5.6/§10
```

### 2.1 Class/type-level mapping (verified against current source)

| Current (`shared.*` / AWS v1) | Replacement | Home |
|---|---|---|
| `shared.command.ConfigProcessingServerCommand` (`TransformerApplication.initialize`, `DynamoTableCommand`) | `com.inttra.mercury.config.ConfigProcessingServerCommand` + composed appianway property-substitution transform | commons + appianway-commons |
| `shared.config.S3ConfigurationProvider` | kept appianway-local (conditional on `CONFIG_LOCATION=s3`) | appianway-commons/module |
| `shared.config.NetworkServiceConfig`, `shared.config.BaseConfiguration` | commons/cloud-sdk equivalents (`NetworkServiceConfig` from commons networkservices, module `BaseConfiguration` residue) | commons |
| `shared.config.AWSClientConfiguration` (`sqs_listener`, `sqs_sender`, `s3_read_put_copy`, `sns_publish` v1 `ClientConfiguration`s) | cloud-sdk-aws client config types (`AwsMessagingClientConfig`, `CloudStorageConfig`, `NotificationClientConfig`) | cloud-sdk-aws |
| `shared.threaddispatcher.AsyncDispatcher`, `Dispatcher`, `TaskFactory` | **appianway-commons** `AsyncDispatcher`/`AbstractTask`/task lifecycle (unchanged semantics) | appianway-commons |
| `shared.listener.SQSListener`, `shared.listener.support.ListenerManager` | cloud-sdk-api `messaging.Listener`/`SqsListener` **or** retained `AsyncDispatcher` wiring | cloud-sdk-api + appianway-commons |
| `shared.messaging.SQSListenerClient`, `shared.messaging.SQSClient` (`TransformerTask.sqsClient.sendMessage`) | cloud-sdk-api `MessagingClient[String]` (`QueueMessage[String]` envelope) | cloud-sdk-api / cloud-sdk-aws |
| `shared.messaging.SNSClient`, `shared.event.SNSEventPublisher` | cloud-sdk-api `NotificationService` / `notification.workflow.EventPublisher` | cloud-sdk-api |
| `shared.workspace.WorkspaceService`, `S3WorkspaceService` (`TransformerTask.workspaceService.putObject`) | cloud-sdk-api `StorageClient` (`putObject(bucket,key,bytes)` — plain 3-arg, no metadata today) | cloud-sdk-api / cloud-sdk-aws |
| `shared.task.MetaData`, `shared.event.{EventGenerator,EventLogger,RandomGenerator}` | cloud-sdk-api `notification.workflow.{MetaData,EventGenerator,EventLogger,RandomGenerator}` | cloud-sdk-api (**W-G9** applies) |
| `shared.externalwrapper.exception.RecoverableException` | **appianway-commons** `RecoverableException` | appianway-commons |
| `shared.networkservices.auth.AuthClient`, `.format.CacheFormatService`/`FormatService`, `.integrationprofile*.*` | `commons` `com.inttra.mercury.networkservices.*` + `client.AuthClient` | commons |
| `shared.parameterstore.ParameterStoreModule` | commons/cloud-sdk `CloudParameterStore`/`ParameterStoreLookup` wiring | commons / cloud-sdk-aws |
| `shared.healthcheck.HealthCheckRegistrar` + indicators (`InboundSqs`, `OutboundSqs`, `S3Write`, `SnsPublish`, `HttpGet`, `ErrorThreshold`) | commons `health.*` base + **appianway-commons** indicator wrappers re-pointed to injected cloud-sdk clients | commons + appianway-commons |
| `com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapper`/`DynamoDBMapperConfig` | cloud-sdk-aws **DynamoDB Enhanced Client** (`DynamoDbEnhancedClient` + `DynamoDbTable[ControlNumberSequence]`) via `DynamoRepositoryConfig`/`DynamoRepositoryFactory` | cloud-sdk-aws |
| `@DynamoDBHashKey`, `@DynamoDBAttribute`, `@DynamoDBIgnore`, `@DynamoDBVersionAttribute` (v1, `ControlNumberSequence`) | v2 enhanced-client bean annotations `@DynamoDbPartitionKey`, `@DynamoDbAttribute`, `@DynamoDbIgnore` + **native** `@DynamoDbVersionAttribute` | AWS SDK v2 (native, no cloud-sdk change) |
| `com.amazonaws.services.dynamodbv2.model.ConditionalCheckFailedException` (`ControlNumberSequenceProvider.nextLowerBound` catch) | v2 `software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException` | AWS SDK v2 |
| `AmazonDynamoDB`/`AmazonDynamoDBClientBuilder` (`DynamoTableCommand`) | v2 `DynamoDbClient`/`DynamoDbClientBuilder` (+ `DynamoDbEnhancedClient` wrapping it) | AWS SDK v2 |
| `com.amazonaws.services.dynamodbv2.util.TableUtils.waitUntilActive` | v2 `DynamoDbWaiter.waitUntilTableExists(...)` | AWS SDK v2 |
| `com.amazonaws.metrics.AwsSdkMetrics` (`TransformerApplication.run`) | v2 `CloudWatchMetricPublisher` (per-client `MetricPublisher`) **or dropped** — §5.6/§10 | AWS SDK v2 |
| `com.contivo.mixedruntime.runtime.wrapper.Transformer`, `TransformerResults`, `TransformSpecification` | **UNCHANGED** — vendor Contivo runtime, not part of this program | module (Contivo jars) |
| `structuralvalidator` jar (`StructuralValidationFAProcessor`) | **UNCHANGED** — separate module, own doc | module dependency |

---

## 3. AWS touchpoints

| Touchpoint | Direction | INT resource | Profile variance | Current | Target |
|---|---|---|---|---|---|
| SQS pickup | consume | `inttra_int_sqs_transformer_inbound` / `inttra_int_sqs_transformer_ce` / `inttra_int_sqs_transformer_os_inbound` | **per-profile** | v1 `AmazonSQS` via `shared.SQSListener` | `MessagingClient[String]` listener (`QueueMessage[String]`) |
| SQS routing (10 dynamic outbound checks) | produce/route | see §5.2 (`ce_validate`, `os_inbound`, `bk_inbound`, `subscription_errors`, `file_delivery`, `rest_delivery`) | common | v1 `AmazonSQS` via `shared.SQSClient.sendMessage` | `MessagingClient[String].sendMessage` |
| SNS event publish | produce | `arn:aws:sns:...:inttra_int_sns_event` (transformer, os-) / `inttra_int_sns_event_ce` (ce-) | **per-profile (ce only)** | v1 `AmazonSNS` via `shared.SNSEventPublisher` | `NotificationService` |
| S3 workspace write | write | `inttra-int-workspace` (transformed output) | common | v1 `AmazonS3` via `shared.S3WorkspaceService` | `StorageClient.putObject(bucket,key,bytes)` — plain, no metadata (S-G2 available if needed, not currently exercised) |
| DynamoDB control-number sequence | read+write (optimistic lock) | `inttra_int_controlnumber_sequence` | common | v1 `DynamoDBMapper` | cloud-sdk-aws DynamoDB Enhanced Client, native `@DynamoDbVersionAttribute` |
| SES | — | none | — | — | — |
| Param Store (SSM) | boot-time auth | `/inttra/int/appianway/networkservices/{authclientid,authclientsecret}` (`usePassThrough=false`) | common | commons/`shared` `AuthClient` resolves at runtime | commons `client.AuthClient` + `CloudParameterStore` (unchanged resolution mechanism) |
| gRPC | — | none (transformer has no watermill dependency) | — | — | — |
| network-services HTTP | auth + format/integration-profile lookups | `https://api-alpha.inttra.com/{auth,network/...}` | common | `shared.networkservices.*` | commons `com.inttra.mercury.networkservices.*` |

---

## 4. Sequence — consume → transform (Contivo) → sequence (DynamoDB) → route

```
 1.  inbound SQS (v2) ─▶ AsyncDispatcher (appianway-commons) ─▶ poll QueueMessage[String]
 2.  TransformerTask.process(message)
 3.  MetaData.fromJson(message.getPayload())
 4.  paramsProvider.get(metaData) (integrationProfile/format lookups; SSM-resolved auth via commons networkservices)
        ─▶ TransformationParams (contextConfig, transformName, ...)
 5.  TransformerPreprocessors.execute(params, configuration) ─▶ sanitized params
 6.  StructuralValidationFAProcessor.structuralValidationAndFA(metaData, params)
        structural validation OK:
           TransformationProcessor.transformToBytes(transformName, sources)   [Contivo, UNCHANGED vendor runtime]
              ─▶ transformed bytes
           control-number generator invoked during transform:
              ControlNumberSequenceProvider.nextSequenceId()
                 ─▶ Dao.findAllWithReadConsistency() [if block exhausted] ─▶ GetItem/Scan (ConsistentRead=true)
                 ─▶ id += 1000, upperBound recomputed
                 ─▶ Dao.save(sequence) ─▶ PutItem (ConditionExpression version=v; native VersionedRecordExtension)
                       version matched      ─▶ OK
                       concurrent writer won ─▶ ConditionalCheckFailedException (v2) ─▶ retry (under MAX_RETRIES)
           StorageClient.putObject(bucket, outFileName, transformedBytes)
           updateMetaData (exitStatus=SUCCESS, projections)
           MessagingClient.sendMessage(targetSqsUrl, newMetaData.toJsonString())
              targetSqsUrl = routing.outbound[contextCode].successQueue, or .distributorRestQueue if MetaData.Projection.DISTRIBUTOR_REST
           eventLogger.logCloseRunEvent(metaData, ..., success=true)
        structural validation fails:
           transformerErrorHandler.handleException(...) ─▶ sendMessage(errorQueue, ...) ; logCloseRunEvent(..., success=false)
```

---

## 5. Configuration changes

### 5.1 Property keys referenced by `transformer.yaml` — INT values, all 3 profiles

| Property key | transformer | ce-transformer | os-transformer | Notes |
|---|---|---|---|---|
| `componentName` | `transformer` | `ce-transformer` | `os-transformer` | feeds `AwsSdkMetrics` namespace today (§5.6); unchanged key |
| `transformer.pickupSqsConfig.queueUrl` | `.../inttra_int_sqs_transformer_inbound` | `.../inttra_int_sqs_transformer_ce` | `.../inttra_int_sqs_transformer_os_inbound` | **differs per profile** — the only inbound-queue variance |
| `transformer.pickupSqsConfig.waitTimeSeconds` | `${...:-20}` | same | same | unchanged |
| `transformer.pickupSqsConfig.maxNumberOfMessages` | `1` | `10` | `1` | per-profile throughput tuning; unchanged |
| `transformer.snsEventConfig.topicArn` | `arn:aws:sns:...:inttra_int_sns_event` | `...:inttra_int_sns_event_ce` | `...:inttra_int_sns_event` | **ce differs**; transformer/os share the main topic |
| `transformer.sqsValidatorConfig.queueUrl` | `.../inttra_int_sqs_ce_validate` | same | same | routing `publishContainerEvent.successQueue` |
| `transformer.sqsErrorSubscriptionConfig.queueUrl` | `.../inttra_int_sqs_subscription_errors` | same | same | shared error queue across appianway |
| `transformer.fileDeliverySqsUrl` | `.../inttra_int_sqs_file_delivery` | same | same | routing.outbound successQueue for most contexts |
| `transformer.restDeliverySqsUrl` | `.../inttra_int_sqs_rest_delivery` | same | same | routing.outbound `distributorRestQueue` for `requestBooking`/`confirmBooking` — **NOT health-probed** (§5.2) |
| `transformer.s3WorkspaceConfig.bucket` | `inttra-int-workspace` | same | same | S3 write target |
| `transformer.dynamoDbSequenceTable` | `inttra_int_controlnumber_sequence` | same | same | **DynamoDB table name — headline change, §6** |
| `transformer.booking.inbound.queueUrl` | `.../inttra_int_sqs_bk_inbound` | same | same | routing `requestBooking`/`confirmBooking` success+error queue |
| `transformer.schedules.inbound.queueUrl` | `.../inttra_int_sqs_os_inbound` | same | same | routing `publishSchedule.successQueue` |
| `transformer.preprocessorConfig.enable` | `true` | same | same | unchanged |
| `transformer.preprocessorConfig.directionCode` | `outbound` | same | same | unchanged |
| `transformer.preprocessorConfig.envelopeCode` | `X12` | same | same | unchanged |
| `environment` | `int` | same | same | feeds `AwsSdkMetrics` namespace today (`AWSSDK_int_[componentName]`) |
| `server.connector.port` | `${server.connector.port:-8081}` | same | same | port **8081** for all 3 profiles |

> **`routing` block (yaml, identical across all 3 profiles):** `inbound.{publishContainerEvent, publishSchedule, requestBooking, confirmBooking}` and `outbound.{publishContainerEvent, publishSchedule, requestBooking, confirmBooking, messageFA}`, each with `successQueue`/`errorQueue` (+ `distributorRestQueue` on the two booking outbound entries). `TransformerApplication.registerHealthChecks` walks `routing.getInbound().values()` + `routing.getOutbound().values()` and adds a distinct `OutboundSqsHealthCheck` for every `successQueue`/`errorQueue` it finds — **10 distinct queues** across the union per the verified INT run (10 ops checks). This loop reads only the `successQueue`/`errorQueue` getters — it does **not** call `getDistributorRestQueue()`, so **`rest_delivery` is never health-probed**. The traversal logic is unchanged by the AWS v2 migration; only the underlying `MessagingClient`/health-check implementation changes.

### 5.2 Outbound-SQS health-check targets (dynamically derived from `routing`, all 3 profiles identical)

| Contributor | successQueue | errorQueue | Health-probed? |
|---|---|---|---|
| `inbound.publishContainerEvent` | `inttra_int_sqs_ce_validate` | `inttra_int_sqs_subscription_errors` | Yes — both |
| `inbound.publishSchedule` | `inttra_int_sqs_os_inbound` | `inttra_int_sqs_subscription_errors` | Yes — both |
| `inbound.requestBooking` / `confirmBooking` | `inttra_int_sqs_bk_inbound` | `inttra_int_sqs_bk_inbound` | Yes — same queue both roles |
| `outbound.publishContainerEvent` / `publishSchedule` / `messageFA` | `inttra_int_sqs_file_delivery` | `inttra_int_sqs_subscription_errors` | Yes — both |
| `outbound.requestBooking` / `confirmBooking` | `inttra_int_sqs_file_delivery` | `inttra_int_sqs_subscription_errors` | Yes — both (successQueue); **distributorRestQueue `inttra_int_sqs_rest_delivery` is a separate field, not probed** |

### 5.3 SSM parameters

| SSM path | Resolved by | Mechanism | Change? |
|---|---|---|---|
| `/inttra/int/appianway/networkservices/authclientid` | `networkServiceConfig.clientId` (`usePassThrough=false`) | runtime `AuthClient` call at boot (SSM via `CloudParameterStore`) | **kept as runtime resolution** (commons `client.AuthClient` + `CloudParameterStore`), not moved to boot-time `${awsps:/path}` — matches every other profile's proven INT behavior |
| `/inttra/int/appianway/networkservices/authclientsecret` | `networkServiceConfig.clientSecret` | same | same |

`networkservices.usePassThrough=false` in `configuration/int/network-services.properties` is unchanged; no `PassThroughParameterSupplier` behavior change.

### 5.4 Config-command composition

```
classpath transformer.yaml (template)
    │
    ▼
[ appianway property subst ]  ${key} from transformer/ce-/os-.properties + network-services.properties + datadog.properties + env
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]  (${awsps:/path} — not used by transformer)
    │
    ▼
Dropwizard Configuration factory (TransformerConfiguration)
```

`TransformerApplication.initialize` registers `ConfigProcessingServerCommand` (now the commons type, composed) as the `run` verb, and separately registers `DynamoTableCommand` — also rewritten to extend the commons `ConfigProcessingServerCommand` — as the `create-table` verb. `S3ConfigurationProvider.requiresS3Configuration()` gating is unchanged (appianway-commons residue).

### 5.5 Run profiles — CLI shape unchanged

```
run transformer.yaml conf/int/transformer.properties     ../configuration/int/network-services.properties ../configuration/int/datadog.properties
run transformer.yaml conf/int/ce-transformer.properties  ../configuration/int/network-services.properties ../configuration/int/datadog.properties
run transformer.yaml conf/int/os-transformer.properties  ../configuration/int/network-services.properties ../configuration/int/datadog.properties
```

Same jar/main class/yaml for all 3; only the first properties file swaps. `CONFIG_REGION`, `datadog.properties`, and the S3-config-provider opt-in are all unchanged.

### 5.6 `AwsSdkMetrics.enableDefaultMetrics()` — explicit config/observability change

Today `TransformerApplication.run()` calls the v1-only API `AwsSdkMetrics.enableDefaultMetrics()` + `setMetricNameSpace("AWSSDK_" + environment + "_" + componentName)`, starting a background CloudWatch metrics publisher (namespace `AWSSDK_int_transformer` / `AWSSDK_int_ce-transformer` / `AWSSDK_int_os-transformer`). AWS SDK v2 has **no equivalent global toggle** — v2 metrics are per-client, opted in via a `MetricPublisher` attached to each client's `overrideConfiguration().addMetricPublisher(...)`. Two options, both explicit — **pick one before cutover, do not silently drop observability**:
1. **Replace** — instantiate one `CloudWatchMetricPublisher` per profile (namespace derived the same way, `AWSSDK_[environment]_[componentName]`) and attach it to every v2 client built in `ExternalServicesModule` (SQS/SNS/S3/DynamoDB). Closest behavioral parity.
2. **Drop** — remove the call entirely if this metrics stream isn't consumed downstream (verify with the ops/observability owner first — it emits a real CloudWatch namespace today).

Either way this is a **named decision**, not silently absorbed into "AWS v2 client rebind" — see §10.

### 5.7 What is unchanged

CLI arg shape (`run [yaml] [props...]`), `CONFIG_REGION=US_EAST_1`, `datadog.properties`, `formatConfig`/`envelopeCodeRules`/`preprocessorConfig` yaml blocks, Contivo `lib/maps` runtime classpath (`-Dcontivo.runtime.classpath=lib/maps`), queue/topic/bucket/SSM-path names (no renames).

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| ID | Applies? | Detail |
|---|---|---|
| **S-G2** (`putObject(...,metadata,contentType)`) | **Referenced, not currently exercised** | `TransformerTask.transform()` calls `workspaceService.putObject(bucket, outFileName, transformed)` — a plain 3-arg put, no metadata/content-type today. Migrates to the plain cloud-sdk `StorageClient.putObject(bucket,key,bytes)` overload; S-G2 is available if a content-type/metadata need emerges later, not required for parity. |
| **W-G9** (workflow-model parity) | **REQUIRED — transformer is a heavy consumer** | `TransformerTask` reads/writes `MetaData.Projection.DISTRIBUTOR_REST`, `.ORIGINAL_IB_WORKSPACE_FILE`, `.CANONICAL_JSON`, `.UNSTREAMED_REQUESTED` and calls `eventLogger.logCloseRunEvent(...)` with `EventGenerator.{TIME_TAKEN_FOR_STRUCTURAL_VALIDATION, TIME_TAKEN_FOR_TRANSFORMATION, DROP_OFF_QUEUE, PICK_UP_QUEUE, TRANSFORMATION_SUPPLEMENT_TOKEN}` tokens — several of these are in the **missing `Projection`/`Token`** constant sets flagged in the program W-G9 audit (`DISTRIBUTOR_REST`, `ORIGINAL_IB_WORKSPACE_FILE` explicitly named). transformer will **not compile** against cloud-sdk-api until W-G9.2 constant parity lands. The `Event.Builder.setAnnotations` round-trip fix (W-G9.1) matters because transformer both consumes `MetaData`/`Event` from splitter and republishes an `Event` per run. |
| **X-G7 / X-G8** | Not applicable | transformer has no email or Elasticsearch/Jest touchpoint. |
| **C-G6** (`getConfigTransformer` visibility) | Optional | transformer composes the appianway property-substitution transform in front of the commons transforms; works whether or not C-G6 lands. |
| **DynamoDB optimistic lock (G4)** | **De-scoped — NOT a cloud-sdk change** | use the **native** v2 `@DynamoDbVersionAttribute` — the default enhanced-client `VersionedRecordExtension` already provides it. No `cloud-sdk-api`/`cloud-sdk-aws` addition required for this module's headline change. |

**Consumed from commons:** `ConfigProcessingServerCommand`, `com.inttra.mercury.networkservices.*` (+ `client.AuthClient`), health base classes, `InttraServer`.
**Consumed from cloud-sdk-api/cloud-sdk-aws:** `MessagingClient[String]` (SQS in/out), `NotificationService` (SNS), `StorageClient` (S3), `notification.workflow.{MetaData,Event,EventGenerator,EventLogger,EventPublisher,RandomGenerator}`, `notification.annotation.{Annotations,Annotation,ErrorHelper}`, DynamoDB Enhanced Client wiring (`DynamoRepositoryConfig`/`DynamoRepositoryFactory` if transformer adopts the cloud-sdk-aws convenience wrapper, or a raw `DynamoDbEnhancedClient` built directly — either is acceptable since the version-attribute behavior is native).
**Moves to appianway-commons:** `AsyncDispatcher`/`AbstractTask`/`TaskFactory`, `RecoverableException`/`TransformerErrorHandler`'s base plumbing, the 6 health-indicator wrappers (`InboundSqs`, `OutboundSqs`, `S3Write`, `SnsPublish`, `HttpGet`, `ErrorThreshold`) re-pointed to injected cloud-sdk clients.

---

## 7. Maven dependency changes

Pin `mercury-services-commons` line at **`1.0.27-SNAPSHOT`** (root `dependencyManagement`, inherited via the `appian-way` parent).

**Remove:** `com.inttra.mercury.shared:mercury-shared`; `com.amazonaws:aws-java-sdk-cloudwatchmetrics` (superseded by the v2 metrics decision, §5.6); `com.amazonaws:aws-java-sdk-sqs`; `com.amazonaws:aws-java-sdk-dynamodb`; the `com.amazonaws:aws-java-sdk-bom` import in `dependencyManagement` once nothing references v1 (transformer's own pom has no `-s3`/`-sns` — those arrived transitively via `shared`).

**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK v2 (`dynamodb-enhanced`, `sqs`, `s3`, `sns`, `ssm`) arrives transitively via `cloud-sdk-aws`'s BOM — do **not** declare v2 artifacts directly.

**Unchanged / module-specific, keep exactly as-is:** all `com.contivo:*` dependencies (`commons`, `Runtime`, `akka-actor`, `antlr-runtime`, `bcel`, `config`, `mapdb`, `scala-library`, `eclipse-collections*`, `elsa`, `lz4`, `Analyst`/`AnalystServices`/`AnalystUtil`/`Core`, `metrics-core`, `rocksdbjni`, `saxon-pe-9.2_noservice`, plus the `javax.xml.bind`/`jakarta.xml.bind`/`jaxb-core`/`jaxb-impl` pins) and the `contivo-dep` file repository (`contivo-lib/`). None interact with AWS SDK v1/v2 — verify only via the shade/classpath pre-flight (§10), not a dependency change. Also `structuralvalidator` (separate module, own doc), `functional-testing` (test scope, migrates alongside its own module), Dropwizard/Guice/Lombok/JUnit 5 Jupiter/Mockito/AssertJ/slf4j-logback (DW5-baseline). `maven-shade-plugin` main-class config and `maven-surefire-plugin`'s `-Dcontivo.runtime.classpath=lib/maps` argLine unchanged.

**Verify:** `mvn -pl transformer -am clean verify` green (shade needs `clean`); fat-jar boot for **all 3 profiles** + `GET /admin/opsHealthcheck` green against INT (10 checks per profile).

---

## 8. Tests

- **JUnit 5 (Jupiter)** — transformer's pom already uses the DW5 junit-bom (5.14.4); no Vintage bridge needed. Continue this convention.
- **DynamoDB control-number tests (new/rewritten):**
  - Optimistic-lock **version-conflict**: two concurrent writers on the same `keyId="SequenceId"` item; assert one throws v2 `ConditionalCheckFailedException` and `ControlNumberSequenceProvider.nextLowerBound()` retries (bounded by `MAX_RETRIES=10`) exactly as today.
  - **Consistent-read** equivalence for `findAllWithReadConsistency()` against the v2 enhanced client's read options.
  - Field round-trip: `keyId` (partition key) / `id` / `version` map correctly with the mixed native-`@DynamoDbVersionAttribute` + attribute annotations, mirroring the `mercury-services` booking `SequenceId` pattern.
  - Block-allocation boundary behavior of `ControlNumberSequenceProvider` (`INCREMENT_RANGE=1000`, `SEED_VALUE=100000000000`) unchanged.
  - `DynamoTableCommand`'s `create-table` verb against a local/test DynamoDB — assert v2 `CreateTableRequest`/`waitUntilTableExists` succeeds with the same key schema (`keyId` HASH, `S` type) and provisioned throughput (10 RCU/10 WCU).
- **Workflow-model round-trip (W-G9 gate):** representative production `MetaData`/`Event` JSON (transformer both consumes and republishes) run through `parseJson → toJsonString`, asserting byte-stability and that `Annotations`/the newly-required `Projection`/`Token` constants survive — gates transformer specifically because it reads `MetaData.Projection.DISTRIBUTOR_REST` off the wire and must not silently lose it.
- **Contivo transformation tests** — unaffected; `TransformationProcessor`/`TransformationsFlow` unit tests continue exercising the vendor `Transformer`/`TransformerResults` API directly.
- **`functional-testing` fakes** re-pointed to cloud-sdk-api interfaces (`MessagingClient`, `StorageClient`, `NotificationService`) in lockstep with the `functional-testing` module's own migration.
- **`TransformerTask` unit tests** — swap `com.amazonaws.services.sqs.model.Message` fixtures for `QueueMessage[String]`; assert routing decisions (`getSuccessQueue`/`getErrorQueue`, the `DISTRIBUTOR_REST` projection branch) and `RecoverableException` propagation unchanged.
- **Health-check tests** — assert `registerHealthChecks` still derives exactly the same 10-queue set from `routing.inbound`/`routing.outbound` after `OutboundSqsHealthCheck` is re-pointed to the cloud-sdk client, and that `distributorRestQueue` remains unprobed (documenting the existing gap, not introducing a new one).

---

## 9. Rollout & verification

Per the program order, transformer is positioned **last of the core (non-watermill) modules**, after `email-sender` and immediately before the watermill batch — reflecting its DynamoDB + Contivo complexity:

```
appianway-commons ─▶ functional-testing ─▶ event-writer ─▶ distributor-rest, splitter, ingestor
  ─▶ dispatcher, distributor, error-processor
  ─▶ email-sender ─▶ transformer   [this module]
  ─▶ watermill-publisher ─▶ 4 watermill consumers
```

1. Confirm `appianway-commons`, `commons`/`cloud-sdk-api`/`cloud-sdk-aws` at `1.0.27-SNAPSHOT`, and `functional-testing` fakes are already migrated.
2. Rebind `ExternalServicesModule`/`TransformerModule` to cloud-sdk clients; rewrite `ControlNumberSequence`/`ControlNumberSequenceDao`/`ControlNumberSequenceProvider` onto the v2 enhanced client; rewrite `DynamoTableCommand` onto `DynamoDbClient`; resolve the `AwsSdkMetrics` decision (§5.6).
3. `mvn -pl transformer -am clean verify` green.
4. Boot **all 3 profiles** against INT (reuse the pre-upgrade commands, swapping only the properties file), and confirm `GET /admin/opsHealthcheck` returns 200 with the same 10-check shape for each profile.
5. Spot-check DynamoDB: run `create-table` verb (or confirm table pre-exists), then drive one message through each profile's pickup queue and confirm the control-number sequence increments without `ConditionalCheckFailedException` exhaustion.
6. Confirm Contivo transformations still produce byte-identical output for a known-good sample per profile (regression check against the pre-upgrade fat jar's output), since the Contivo classpath now shares the fat jar with AWS SDK v2 instead of v1 (§10).

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Contivo classpath/shade conflict with AWS SDK v2 + DW5/Jetty12** — Contivo bundles its own Scala/Akka/Kotlin/RocksDB/MapDB/Saxon/BCEL/ANTLR/eclipse-collections runtime (30+ jars) alongside two jaxb generations already coexisting; adding the AWS SDK v2 BOM's transitive set (Netty/Apache HttpClient, Jackson 2.21.4, reactive-streams) into the same shaded fat jar risks `META-INF/services` clobbering, duplicate-class shading warnings, or classloader conflicts surfacing only at Contivo `Transformer` construction time | Pre-flight: `mvn -pl transformer -am clean package` and inspect shade output for overlapping-classes/duplicate `META-INF/services` warnings before relying on grep; smoke-test one transformation per profile and diff output bytes against the pre-upgrade jar; keep Contivo jars entirely untouched (no version bumps) so any regression is isolated to the AWS-layer change |
| **`AwsSdkMetrics.enableDefaultMetrics()` has no v1→v2 drop-in** — silently dropping it removes a live CloudWatch metrics stream with no compiler error | Explicit decision required before cutover (§5.6): either wire a v2 `CloudWatchMetricPublisher` per client with the same namespace convention, or confirm with the ops owner that the stream is unused and formally drop it — do not let it fall out silently during the `ExternalServicesModule` rebind |
| **DynamoDB optimistic-lock semantics drift** → duplicate/invalid control numbers if the native `@DynamoDbVersionAttribute` isn't recognized or the default extension list changes | Use the native v2 annotation (not a cloud-sdk-api one) exactly as `mercury-services` booking `SequenceId` does; version-conflict integration test (§8) against a real/local DynamoDB before cutover; re-point the `ConditionalCheckFailedException` catch in `ControlNumberSequenceProvider` to the v2 type |
| **W-G9 constant-set gap blocks compilation** — transformer references `MetaData.Projection.DISTRIBUTOR_REST`/`.ORIGINAL_IB_WORKSPACE_FILE` and multiple `EventGenerator` tokens not yet in cloud-sdk-api | Land W-G9 (constant parity + `Event.Builder.setAnnotations`) in cloud-sdk-api before or alongside transformer's migration; run the program-wide JSON round-trip corpus test using transformer's own production `MetaData`/`Event` traffic as part of the corpus |
| **3-profile regression risk** — a fix validated only against the default `transformer` profile could miss `ce-transformer`'s different SNS topic/queue or `os-transformer`'s different pickup queue | Boot and health-check **all 3** profiles every verification pass (§9 step 4); the `routing` block and health-check derivation are shared code, so a single logic bug surfaces identically — test once, verify thrice |
| **`rest_delivery` blind spot carries forward unchanged** — `distributorRestQueue` was never health-probed pre-upgrade and stays that way (health-check loop logic is unchanged) | Documented as a pre-existing gap, not introduced by this migration; closing it is a separate, explicitly-scoped change (add a probe for `getDistributorRestQueue()`), out of scope here |
| Any cloud-sdk/commons change breaking `mercury-services` production consumers | None proposed here beyond the program-wide W-G9 (additive) and optional S-G2 (additive, not currently exercised); DynamoDB version-attribute is native SDK v2 behavior, not a cloud-sdk change |
