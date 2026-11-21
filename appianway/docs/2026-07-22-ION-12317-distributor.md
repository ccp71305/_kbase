# distributor — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `distributor` · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only distributor's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`). distributor boots clean on that stack today (still on AWS v1 + `shared`).

---

## Contents

---

## 1. Overview

**Purpose:** distributor is the ETL egress worker for outbound file delivery. It consumes a `MetaData` envelope off SQS, resolves delivery-attribute metadata (filename pattern, delivery/archive paths, zip flag) from the INTTRA integration-profile-format network service, renders the delivery filename via token resolvers, optionally zips the source object, then **copies the source object to two destinations with replaced S3 user-metadata** — the outbound delivery bucket and an archive path in the workspace bucket — before publishing a `CLOSE_WORKFLOW` event to SNS.

- **Current state:** DW5 baseline; still on **AWS Java SDK v1 1.12.720** end-to-end (`AmazonSQS`/`AmazonS3`/`AmazonSNS`) + `shared` (`ConfigProcessingServerCommand`, `SQSListener`/`AsyncDispatcher`, `WorkspaceService`/`S3WorkspaceService`, `MetaData`/`Event`/`EventLogger`, `networkservices.*`, `ErrorHandler`).
- **Target:** `commons` + `cloud-sdk-api` + `cloud-sdk-aws` (`1.0.27-SNAPSHOT`) for everything `shared` provided, **except** the appianway-only residue (`AsyncDispatcher`/`AbstractTask`, `ErrorHandler`/`RecoverableException`, health-indicator glue, config-transform glue) which moves to slim **`appianway-commons`**.
- **Headline change:** distributor is the **primary S-G2 copy-with-replaced-metadata consumer** — its `FileDeliveryService.processMessage(...)` calls `WorkspaceService.copyObjectWithMetaDate(...)` **twice per message** (delivery copy + archive copy), each carrying a workflow-lineage + projection-key metadata map. It most directly depends on S-G2's `copyObject(..., Map replacedMetadata, String contentType)` overload with S3 `MetadataDirective.REPLACE`.

---

## 2. Current vs Target architecture

```
BEFORE — AWS v1 + shared
  pickup SQS ─▶ shared SQSListener + AsyncDispatcher (AmazonSQS v1) ─▶ DistributorTask.process(Message,...)
       DistributorTask ─▶ FileDeliveryService
            FileDeliveryService ─▶ ZipCompression (com.amazonaws.util.IOUtils)
            FileDeliveryService ─▶ shared WorkspaceService/S3WorkspaceService (AmazonS3 v1, ObjectMetadata) ─▶ S3 v1 (inttra-int-workspace, inttra-int-outbound-delivery)
       DistributorTask ─▶ shared EventLogger/SNSEventPublisher ─▶ SNS v1 (inttra_int_sns_event)
       DistributorTask ─▶ DistributorErrorHandler (shared ErrorHandler) ─▶ SQS v1 (inttra_int_sqs_subscription_errors)
       ExternalServicesModule (shared AWSClientConfiguration, NetworkServiceConfig, AuthClient)

AFTER — commons + cloud-sdk (AWS v2)
  pickup SQS ─▶ appianway-commons AsyncDispatcher + Listener (MessagingClient[String]) ─▶ DistributorTask.process(QueueMessage[String],...)
       DistributorTask ─▶ FileDeliveryService
            FileDeliveryService ─▶ ZipCompression (JDK readAllBytes)
            FileDeliveryService ─▶ WorkspaceService (appianway-local facade over StorageClient) ─▶ cloud-sdk-api StorageClient (S-G2 overloads) ─▶ S3 v2 (same 2 buckets)
       DistributorTask ─▶ cloud-sdk-api EventLogger/EventPublisher ─▶ NotificationService ─▶ SNS v2 (inttra_int_sns_event)
       DistributorTask ─▶ DistributorErrorHandler (appianway-commons ErrorHandler) ─▶ SQS v2 (inttra_int_sqs_subscription_errors)
       ExternalServicesModule (cloud-sdk-aws client configs, commons networkservices.AuthClient)
```

### Class-level mapping — `shared`/v1 type → replacement

| Current (`com.inttra.mercury.shared.*` / v1) | Replacement | Home | Distributor call site |
|---|---|---|---|
| `command.ConfigProcessingServerCommand` | `com.inttra.mercury.config.ConfigProcessingServerCommand` + composed appianway property-substitution transform | commons + appianway-commons | `DistributorApplication.initialize()` |
| `config.S3ConfigurationProvider` | keep appianway-local (unchanged behavior) | appianway-commons / module | `DistributorApplication.initialize()` |
| `config.BaseConfiguration`, `SQSConfig`, `SNSConfig`, `S3Config`, `NetworkServiceConfig`, `AWSClientConfiguration` | cloud-sdk config types (`AwsMessagingClientConfig`, `NotificationClientConfig`, `CloudStorageConfig`) + module POJOs (`DistributorConfiguration` keeps the same field names/paths) | cloud-sdk-aws / module | `DistributorConfiguration`, `ExternalServicesModule` |
| `com.amazonaws.services.sqs.AmazonSQS` (×2 named: `amazonSQSForListener`/`amazonSQSForSender`) | `cloud-sdk-api` `MessagingClient[String]` (listener + sender roles) | cloud-sdk-aws | `ExternalServicesModule.configure()` |
| `com.amazonaws.services.s3.AmazonS3` (`s3_read_put_copy`) | `cloud-sdk-api` `StorageClient` | cloud-sdk-aws | `ExternalServicesModule.configure()` |
| `com.amazonaws.services.sns.AmazonSNS` (`sns_publish`) | `cloud-sdk-api` `NotificationService` | cloud-sdk-aws | `ExternalServicesModule.configure()` |
| `listener.SQSListener` / `listener.support.ListenerManager` | `appianway-commons` (retained concurrency model, wired over `MessagingClient[String]`) | appianway-commons | `DistributorModule.getSQSListener/listenerManager` |
| `threaddispatcher.AsyncDispatcher`, `task.TaskFactory`, `task.AbstractTask` | `appianway-commons` (unchanged semantics) | appianway-commons | `DistributorModule.configure()`, `DistributorTask` |
| `com.amazonaws.services.sqs.model.Message` (`message.getBody()`) | `cloud-sdk-api` `QueueMessage[String]` (`.getPayload()`) | cloud-sdk-api | `DistributorTask.process(...)` |
| `workspace.WorkspaceService` / `S3WorkspaceService` (`copyObjectWithMetaDate`, `putObject`, `getS3InputStream`) | appianway-local `WorkspaceService` facade over `cloud-sdk-api` `StorageClient` (**S-G2**) | appianway-local (thin) over cloud-sdk-api | `FileDeliveryService.copyFile(...)`, `ZipCompression.process(...)` |
| `task.MetaData` | `cloud-sdk-api` `notification.workflow.MetaData` (field-identical; `Projection.REPROCESS` needs **W-G9.2**) | cloud-sdk-api | `FileDeliveryService`, `DistributorTask`, `FileDeliveryAttributesProvider` |
| `event.Event`, `EventLogger`, `SNSEventPublisher`, `event.EventPublisher` | `cloud-sdk-api` `notification.workflow.{Event,EventLogger,EventPublisher}` (`Event.Token.PICK_UP_QUEUE`, `S3_DELIVERY_FILE_NAME_TOKEN` unaffected by the W-G9 gap) | cloud-sdk-api | `DistributorTask.process(...)`, `DistributorModule.snsEventPublisher(...)` |
| `networkservices.auth.AuthClient`, `format.CacheFormatService`, `integrationprofileformat.CacheIntegrationProfileFormatByIdService`, `integrationprofile.CacheIntegrationProfileByIdService`, `parameterstore.ParameterStoreModule`, `networkservices.NetworkRetryerModule` | `commons` `com.inttra.mercury.networkservices.*` + `client.AuthClient` | commons | `ExternalServicesModule.configure()`, `FileDeliveryAttributesProvider` |
| `healthcheck.HealthCheckRegistrar`, `indicator.{InboundSqs,OutboundSqs,SnsPublish,HttpGet,ErrorThreshold}HealthCheck` | commons `health.*` base + appianway-commons indicator wrappers re-pointed to injected `MessagingClient`/`NotificationService` | commons + appianway-commons | `DistributorApplication.registerHealthChecks(...)` |
| `task.ErrorHandler`, `task.errorhandler.ErrorHelper`, `externalwrapper.exception.RecoverableException` | `appianway-commons` (appianway error taxonomy preserved) | appianway-commons | `DistributorErrorHandler`, `ErrorConstants` |
| `com.amazonaws.util.IOUtils.toByteArray(...)` | JDK `InputStream.readAllBytes()` (no library replacement) | module-local | `ZipCompression.process(...)` |
| `org.zapodot.hystrix.bundle.HystrixBundle` (already commented out) | **drop** (dead import + dependency) | n/a | `DistributorApplication` |

**Unchanged (no library involvement):** `TokensProcessor` + all 8 `TokenResolver` implementations, `Handler`/`Handlers`/`ZipCompression`'s JDK `java.util.zip` core, `FileDeliveryAttributes`/`OutputFileProperties` model classes, `AttributeNotFoundException`/`MissingProjectionException`.

---

## 3. AWS touchpoints

| Type | Direction | INT resource | cloud-sdk client | Notes |
|---|---|---|---|---|
| SQS | inbound (pickup) | `inttra_int_sqs_file_delivery` | `MessagingClient[String]` (listener) | Consumed via `SQSListener`+`AsyncDispatcher` (appianway-commons), `waitTimeSeconds=20`, `maxNumberOfMessages=10` |
| SQS | outbound (error/DLQ) | `inttra_int_sqs_subscription_errors` | `MessagingClient[String]` (sender) | Written by `DistributorErrorHandler` on unrecoverable exceptions |
| SNS | publish | `inttra_int_sns_event` | `NotificationService` | `CLOSE_WORKFLOW` event per processed message, success or failure |
| S3 | read + copy-source | `inttra-int-workspace` | `StorageClient` | Source object for both copies; also target of the optional zip `putObject` |
| S3 | write (copy target 1 — delivery) | `inttra-int-outbound-delivery` | `StorageClient.copyObject` **(S-G2, `MetadataDirective.REPLACE`)** | `FileDeliveryService.copyFile(source, deliveryFileName, s3MetaData)` |
| S3 | write (copy target 2 — archive) | `inttra-int-workspace` (archive path, token-rendered) | `StorageClient.copyObject` **(S-G2, `MetadataDirective.REPLACE`)** | `FileDeliveryService.copyFile(source, archiveFileName, s3MetaData)` |
| S3 | write (zip, no metadata) | `inttra-int-workspace` | `StorageClient.putObject(bucket,key,byte[])` (existing metadata-less overload) | `ZipCompression.process(...)`, only when `zipCompression=true` |
| DynamoDB / SES / gRPC | — | none | — | not used by distributor |
| Param Store (SSM) | auth secrets | `/inttra/int/appianway/networkservices/authclientid`, `.../authclientsecret` | commons `networkservices.client.AuthClient` (runtime resolution, unchanged) | `usePassThrough=false` |
| Network-services (non-AWS, HTTP) | integration-profile-format lookup + health ping | `.../network/participant/integrationProfile/format`, `.../network/services/ping` | commons `CacheIntegrationProfileFormatByIdService` | `FileDeliveryAttributesProvider` resolves `fileNamePattern`/`fileNameSuffix`/`fileDeliveryPath`/`fileArchivePath`/`zipCompression` per message |

**Health-check shape (unchanged):** read = inbound SQS + network-service HTTP GET + error-rate; write = outbound (error) SQS + SNS publish. **No S3 health check exists today** — both S3 buckets are config-resolved only. This migration re-points the same 5 checks to the injected v2 clients without adding S3 coverage (out of scope; §10 flags it as a residual gap).

---

## 4. Sequence — consume → resolve attributes → optional zip → copy-with-metadata (delivery + archive) → event

```
 1.  appianway-commons Listener (MessagingClient[String]) ─▶ DistributorTask.process(QueueMessage[String] msg, pickupQueueUrl)
 2.  metaData = Json.fromJsonString(msg.getPayload(), MetaData.class)
 3.  FileDeliveryService.processMessage(metaData):
        FileDeliveryAttributesProvider.apply(metaData)  [needs Projection.OUTBOUND_INTEGRATION_PROFILE_FORMAT_ID]
            ─▶ commons networkservices.getIntegrationProfileFormat(ipFormatId)
            ─▶ fileNamePattern, fileNameSuffix, fileDeliveryPath, fileArchivePath, zipCompression
        TokensProcessor renders deliveryFileName / archiveFileName (token resolvers)
        if attributes.isZipCompression():
            ZipCompression.process(...): getS3InputStream(workspaceBucket, metaData.getFileName()) [StorageClient.getObject]
                ─▶ zip via JDK java.util.zip + readAllBytes()
                ─▶ putObject(workspaceBucket, zipKey, bytes)   [existing metadata-less overload]
        build s3MetaData{rootWorkflowId, parentWorkflowId, workflowId, OUTBOUND_INTEGRATION_PROFILE_FORMAT_ID,
                         CONTEXT_CODE, OUTBOUND_EDI_ID, +optional INFTPFILEPICKUPTIME, +optional REPROCESS}
        copyObjectWithMetaDate(workspaceBucket, source, outboundBucket,  deliveryFileName, s3MetaData)
            ─▶ StorageClient.copyObject(src,srcKey,dst,dstKey, replacedMetadata, contentType)   [S-G2, MetadataDirective.REPLACE]
        copyObjectWithMetaDate(workspaceBucket, source, workspaceBucket, archiveFileName,  s3MetaData)
            ─▶ StorageClient.copyObject(...)   [S-G2 again]
 4.  EventLogger.logCloseRunEvent(metaData, CLOSE_WORKFLOW, runId, msg.getPayload(), componentName, startDateTime, success=true,
                                  {S3_DELIVERY_FILE_NAME_TOKEN: deliveryFileName, PICK_UP_QUEUE: pickupQueueUrl})
        ─▶ NotificationService.publish(event JSON) ─▶ SNS
 5.  on exception during processMessage:
        DistributorErrorHandler.handleException(msg, CLOSE_WORKFLOW, metaData, runId, startDateTime, {PICK_UP_QUEUE}, ex)
            ─▶ logCloseRunEvent(success=false, error annotation)
            ─▶ send to inttra_int_sqs_subscription_errors (MessagingClient sender role)
 6.  on success: Listener.deleteMessage(pickupQueueUrl, receiptHandle)
```

> The two `copyObjectWithMetaDate` calls (delivery + archive), each carrying a 6–8 entry `Map[String,String]`, are the load-bearing S-G2 dependency for this module.

---

## 5. Configuration changes

### 5.1 Property-key table

| YAML path (`${key}`) | `conf/int/distributor.properties` value | Notes |
|---|---|---|
| `componentName` | `distributor` | unchanged |
| `healthCheckConfig.errorRateThreshold` | default `5.0` | `${distributor.healthCheckConfig.errorRateThreshold:-5.0}` — no INT override |
| `healthCheckConfig.networkServiceHealthCheckUrl` | `${networkservices.healthCheckUrl}` → `https://api-alpha.inttra.com/network/services/ping` | unchanged |
| `snsEventConfig.topicArn` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | unchanged — **do not rename** |
| `sqsErrorConfig.queueUrl` | `.../inttra_int_sqs_subscription_errors` | unchanged |
| `sqsPickupConfig.queueUrl` | `.../inttra_int_sqs_file_delivery` | unchanged |
| `sqsPickupConfig.waitTimeSeconds` / `.maxNumberOfMessages` | defaults `20` / `10` | no INT override |
| `s3WorkspaceConfig.bucket` | `inttra-int-workspace` | source + archive-copy target |
| `s3OutboundConfig.bucket` | `inttra-int-outbound-delivery` | delivery-copy target |
| `networkServiceConfig.networkBaseUrl` | `https://api-alpha.inttra.com/network` | unchanged |
| `networkServiceConfig.authEndpointUrl` | `https://api-alpha.inttra.com/auth` | unchanged |
| `networkServiceConfig.clientId` / `.clientSecret` | SSM paths (§5.2) | unchanged |
| `networkServiceConfig.usePassThrough` | `false` | unchanged |
| `networkServiceConfig.servicePaths.integrationProfileFormatServicePath` | `/participant/integrationProfile/format` | primary lookup for `FileDeliveryAttributesProvider` |
| `networkServiceConfig.servicePaths.integrationProfileServicePath` / `formatServicePath` | `/participant/integrationProfile` / `/message/format` | bound but not on distributor's main path |
| `server.connector.port` | default `8081` | matches run-config evidence |
| `metrics.frequency` | from `datadog.properties` | unchanged |

None of these keys, queue names, topic ARNs, or bucket names are renamed by this migration.

### 5.2 SSM parameters

| Parameter | Path | Mechanism | Decision |
|---|---|---|---|
| `networkservices.clientId` | `/inttra/int/appianway/networkservices/authclientid` | **Keep runtime resolution** via commons `client.AuthClient` / `CloudParameterStore` (unchanged — `ParameterStoreModule` today, commons equivalent after) | No change to timing (resolved at app-start, not baked into the YAML) |
| `networkservices.clientSecret` | `/inttra/int/appianway/networkservices/authclientsecret` | same | same |
| `networkservices.usePassThrough=false` | n/a (literal) | `PassThroughParameterSupplier` bypass stays disabled — always resolve real secrets from SSM | unchanged |

Distributor needs **no** `${awsps:/path}` boot-time YAML substitution — its only secrets are the two network-services auth values, already runtime-resolved and staying that way.

### 5.3 Config-command composition

`appianway property-substitution transform` (multi-`.properties` + env) **→** commons `TrimConfigCommentsTransform` **→** commons `ParameterStoreConfigTransform` (`${awsps:...}` — unused by distributor today, composed for consistency). CLI shape unchanged:

```
run distributor.yaml conf/int/distributor.properties ../configuration/int/network-services.properties ../configuration/int/datadog.properties
```

### 5.4 What's unchanged

- CLI verb `run`, arg order/count, `-DCONFIG_REGION=US_EAST_1`.
- `datadog.properties` pass-through (metrics frequency only).
- `S3ConfigurationProvider` conditional install (`CONFIG_LOCATION=s3`) — stays appianway-local, no cloud-sdk involvement.
- **No** run profiles/variants (unlike ingestor/splitter/transformer `ce-`/`os-`) — single deployment, single `distributor.yaml`.
- Port 8081, single `simple` Dropwizard server (`/application` + `/admin` share the port).

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap | Relevance | Detail |
|---|---|---|
| **S-G2** | **Primary consumer** | `StorageClient.copyObject(srcBucket,srcKey,dstBucket,dstKey, Map replacedMetadata, String contentType)` (`MetadataDirective.REPLACE`) backs `WorkspaceService.copyObjectWithMetaDate(...)`, called **twice per message** (delivery + archive) in `FileDeliveryService`. The metadata-less `putObject(bucket,key,byte[])` overload (already present) backs the zip write in `ZipCompression` — no new overload needed there. **No distributor-specific cloud-sdk change** — it consumes the program-wide S-G2 spec exactly. |
| **W-G9** | **Directly exercised** | distributor's own metadata map uses `MetaData.Projection.REPROCESS` (`FileDeliveryService`), one of the **6 missing `Projection` constants** (foundation §5A). **distributor will not compile against cloud-sdk-api's current 26-key set until W-G9.2 lands the constant.** `Event.Token.PICK_UP_QUEUE`/`S3_DELIVERY_FILE_NAME_TOKEN` are **not** among the 8 missing `Event.Token` keys, so they're unaffected. distributor doesn't set `Annotations` on its `Event`, so W-G9.1 doesn't block its publish path, but its events flow through the shared event-writer archive, so the corpus round-trip test gates the whole program including this module. |
| **X-G7** / **X-G8** | Not applicable | no email; no OpenSearch/Jest. |
| **C-G6** | Optional | config composition works with commons' `getConfigTransformer` staying `private`. |

**Consumed from commons:** `ConfigProcessingServerCommand` (+ appianway transform), `networkservices.*` (`AuthClient`, `CacheFormatService`, `CacheIntegrationProfileByIdService`, `CacheIntegrationProfileFormatByIdService`, `ParameterStoreModule`-equivalent, `NetworkRetryerModule`-equivalent), `health.*` base.
**Consumed from cloud-sdk-api:** `MessagingClient[String]`, `QueueMessage[String]`, `StorageClient` (incl. S-G2 overloads), `NotificationService`, `notification.workflow.{MetaData,Event,EventLogger,EventPublisher}`, `notification.annotation.ErrorHelper`.
**Moves to appianway-commons:** `AsyncDispatcher`/`AbstractTask`/`TaskFactory`/`Dispatcher` (retained concurrency model), `SQSListener`/`ListenerManager` wiring, `ErrorHandler`/`RecoverableException` base (`DistributorErrorHandler` extends it), health-indicator wrappers (`InboundSqs`, `OutboundSqs`, `SnsPublish`, `HttpGet`, `ErrorThreshold` re-pointed to injected clients), the appianway property-substitution config transform.
**appianway-local (thin, not in appianway-commons — few consumers):** the `WorkspaceService` facade interface + its `StorageClient`-backed implementation (kept in distributor or a small shared internal package alongside dispatcher/error-processor, since several modules use the same `copyObjectWithMetaDate`/`putObject`/`getS3InputStream` shape — evaluate promoting to `appianway-commons` if ≥2 modules need the identical facade, per foundation §3).

---

## 7. Maven dependency changes

**Remove:** `com.inttra.mercury.shared:mercury-shared`; `com.amazonaws:aws-java-sdk-sqs` (the only direct v1 dep; S3/SNS v1 came in transitively via `shared`); `javax.xml.bind:jaxb-api:2.3.1` — **verify** still needed; drop if nothing in the migrated stack requires JAXB (DW5/Jetty12 already assumes Jakarta namespaces).
**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK v2 arrives transitively via `cloud-sdk-aws` (BOM) — do not declare v1 or v2 directly.
**Align (already done by ION-16098):** `dropwizard-core` (DW5), `metrics-annotation`, Jetty 12.1.9/Jackson 2.21.4 via parent dependency management.
**Unchanged / module-specific:** `guice`, `metrics-guice`, `guava` — no AWS coupling; `functional-testing` (test) re-pointed to cloud-sdk-api in lockstep; `mockito-core`, `junit` (JUnit 4 today), `assertj-core` — add `dropwizard-testing` + JUnit 5 for new tests, keep `junit-vintage-engine` during transition; `lombok` (provided); shade plugin (main class `com.inttra.mercury.distributor.DistributorApplication`) — run with `clean verify`.
**Verify:** `mvn -pl distributor -am clean verify` green; fat-jar boot + `/admin/opsHealthcheck` green against INT (5 checks: inbound SQS `inttra_int_sqs_file_delivery`, network-service ping, error-rate, outbound error SQS `inttra_int_sqs_subscription_errors`, SNS publish `inttra_int_sns_event`).

---

## 8. Tests

- **Direction:** new tests in JUnit 5 via `dropwizard-testing`; existing JUnit 4 bridges via `junit-vintage-engine`.
- **`functional-testing` fakes** re-pointed to cloud-sdk-api interfaces (`StorageClient`, `MessagingClient[String]`, `NotificationService`) in lockstep with the program rollout — distributor's tests depend on this module migrating first.
- **What to assert:**
  - `Message`→`QueueMessage[String]` parity: `DistributorTask` reads `getPayload()` instead of `getBody()`; add a test double producing `QueueMessage[String]` with the same `MetaData` JSON body.
  - **Metadata round-trip on both `copyObjectWithMetaDate` calls (delivery + archive)** — assert via a fake `StorageClient` that the destination object's `replacedMetadata` map contains `rootWorkflowId`, `parentWorkflowId`, `workflowId`, `OUTBOUND_INTEGRATION_PROFILE_FORMAT_ID`, `CONTEXT_CODE`, `OUTBOUND_EDI_ID`, and (when present) `INFTPFILEPICKUPTIME` and `REPROCESS`. This is the primary S-G2 regression guard for this module.
  - `REPROCESS` projection constant compiles and round-trips through cloud-sdk-api's `MetaData.Projection` once W-G9.2 lands — assert it resolves and is carried into the copy-metadata map when set on the inbound envelope.
  - `putObject(bucket,key,byte[])` (zip path) — return value still ignored; assert only the byte content written.
  - Filename rendering (`TokensProcessor` + all 8 resolvers) — unaffected; keep existing coverage green as a regression check.
  - Optional-zip on/off branching — unaffected logic; verify it still gates correctly with the new `WorkspaceService` facade.
  - `DistributorErrorHandler` error-code map (`AttributeNotFoundException`, `MissingProjectionException`) — unaffected; keep as regression coverage.
  - JSON round-trip corpus test (foundation §5A gate) — distributor's production `MetaData`/`Event` (incl. `REPROCESS` + the two workflow-token keys) should be represented in the corpus.

---

## 9. Rollout & verification

**Position (program order):** the **"S-G2 write/copy consumers"** wave — after `appianway-commons`, `functional-testing`, event-writer (pilot), the light consumers (distributor-rest/splitter/ingestor), migrated with `dispatcher` and `error-processor`.

1. Prerequisite: `appianway-commons` published, `functional-testing` fakes re-pointed, event-writer pilot green (proves S-G2 end-to-end), cloud-sdk `1.0.27-SNAPSHOT` with W-G9 landed (distributor needs `Projection.REPROCESS` to compile).
2. Migrate: rebind `ExternalServicesModule` to cloud-sdk-aws client configs + commons `networkservices`/`AuthClient`; `DistributorTask.process(Message,...)` → `process(QueueMessage[String],...)`; swap `com.amazonaws.util.IOUtils` for JDK `readAllBytes()`; drop `aws-java-sdk-sqs` + `mercury-shared`; add the 4 new artifacts.
3. `mvn -pl distributor -am clean verify` (pairs with `dispatcher`/`error-processor` — same rollout step).
4. INT boot + health evidence: `java -DCONFIG_REGION=US_EAST_1 -jar target/distributor-1.0.jar run distributor.yaml conf/int/distributor.properties ../configuration/int/network-services.properties ../configuration/int/datadog.properties`; confirm clean boot (`AuthClient` GET `/auth` succeeds, `SQSListener starting`, connector bound `0.0.0.0:8081`), `GET /admin/opsHealthcheck` → 200 with the same 5 checks.
5. Smoke test beyond boot (no S3 probe exists): deliver one document **with** zip enabled and one **without**, and confirm both the outbound-delivery object and the workspace-archive object carry the expected user-metadata keys and correct filenames.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `Projection.REPROCESS` missing from cloud-sdk-api until W-G9.2 lands | Gate distributor's migration behind cloud-sdk `1.0.27-SNAPSHOT` actually containing W-G9; don't compile against an older snapshot |
| S-G2 metadata not applied on copy (`REPLACE` directive dropped or defaulted to `COPY`) | Functional test asserting the destination object's replaced-metadata map via fake `StorageClient`, for **both** the delivery and archive copies independently (different target buckets/keys) |
| Two sequential `copyObjectWithMetaDate` calls per message — partial failure leaves one copy done, one not | Preserve existing behavior (no transactionality today); document as a pre-existing condition, not a regression |
| No S3 health check exists — a broken `StorageClient` binding could pass ops health while quietly failing the copy path | Out of scope (pre-existing gap); flag as a candidate follow-up to add `S3ReadHealthCheck`/`S3WriteHealthCheck` from commons' health base once available |
| `Message`→`QueueMessage[String]` drift (`getBody()` vs `getPayload()`) | Parity test on `DistributorTask.process(...)`; same JSON envelope semantics, same `Json.fromJsonString` |
| `com.amazonaws.util.IOUtils` behavior diff after JDK `readAllBytes()` swap | Unit test the zip helper for identical output bytes |
| In-memory buffering of large zipped payloads (`readAllBytes()`) | Parity preserved as-is; optional streaming `putObject(InputStream,long)` could be adopted later if memory pressure arises — not required now |
| Any cloud-sdk/commons change breaking mercury-services production | S-G2/W-G9 are strictly additive; no existing signature changes |
| `jaxb-api:2.3.1` removal breaking an undiscovered runtime dependency | Verify via `mvn verify` + full boot before removing; keep if any transitive consumer still needs `javax.xml.bind` |
