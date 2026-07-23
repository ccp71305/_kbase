# distributor-rest — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `distributor-rest` · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only distributor-rest's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`). distributor-rest boots clean on that stack today (still on AWS v1 + `shared`); it **registers no health checks**, so AWS resolution is proven by boot evidence, not an ops probe.

---

## Contents

---

## 1. Overview

`distributor-rest` is the **REST-delivery leg of the distribution fan-out**: it consumes a `MetaData` envelope from the `inttra_int_sqs_rest_delivery` SQS queue, reads the referenced payload from S3 (`inttra-int-workspace`, read-only, **ISO-8859-1**), looks up the target `Subscription` via network-services, builds an HTTP request, and **POSTs** the payload to the subscriber's REST/webhook endpoint with an OAuth2 bearer token from a module-local `AuthClient`. On success it logs a close-run lineage event (SNS `inttra_int_sns_event`); on failure it routes through `ErrorHandler` (which can write to the error SQS `inttra_int_sqs_subscription_errors`).

- **Current state:** DW5/Jetty12/Java17 baseline (ION-16098, done); AWS Java SDK **v1** (`AmazonSQS`/`AmazonS3`/`AmazonSNS`) bound directly in `ExternalServicesModule`; appianway `shared` for config command, network-services, event/`MetaData` model, `SQSListener`/`AsyncDispatcher`, `ErrorHandler`.
- **Target state:** `commons` (config command, network-services `AuthClient`, health base — unused here) + `cloud-sdk-api`/`cloud-sdk-aws` (`MessagingClient[String]`, `StorageClient`, `NotificationService`) + slim `appianway-commons` (`AsyncDispatcher`/`AbstractTask`, `ErrorHandler`/`RecoverableException`).
- **Headline change:** the **lightest migration in the program — a pure client rebind**. Exactly **one** AWS binding point (`ExternalServicesModule`), S3 usage is **read-only** (S-G2 not exercised), and the entire HTTP/OAuth egress half (Jersey client, module-local `AuthClient`, `Retryer`, `RequestBuilder`, `e2net.*`) is **non-AWS and completely untouched**.
- **No health checks:** `DistributorApplication.run()` never calls `registerHealthChecks(...)`. `GET /admin/opsHealthcheck` → 404; `/admin/healthcheck` → 200 with only the default `deadlocks` check. Verification of the rebind is by **boot evidence** (SQSListener starts + polls with zero errors, `AuthClient`/SSM succeeds), not an ops endpoint.

---

## 2. Current vs Target architecture

```
BEFORE — shared + AWS SDK v1
  pickup SQS ─▶ shared SQSListener + AsyncDispatcher ─▶ DistributorTask (extends shared AbstractTask)
       DistributorTask ─▶ shared S3WorkspaceService.getContent (READ ONLY)          ─▶ AmazonS3 (v1)
       DistributorTask ─▶ shared networkservices SubscriptionService                 ─▶ shared AuthClient (SSM, INTTRA auth)
       DistributorTask ─▶ shared EventLogger.logCloseRunEvent                         ─▶ AmazonSNS (v1)
       DistributorTask ─▶ shared ErrorHandler (writeErrorsToS3 / sendToQueue)         ─▶ AmazonSQS x2 (v1) @listener/@sender
       DistributorTask ─▶ module-local RestServiceClient (Jersey, OAuth bearer)  [NON-AWS]
                              └─▶ module-local auth.AuthClient (OAuth2)           [NON-AWS]

AFTER — commons + cloud-sdk-api/aws (AWS v2)   [client rebind only, no behavior change]
  pickup SQS ─▶ appianway-commons AsyncDispatcher + SQSListener ─▶ DistributorTask (extends appianway-commons AbstractTask)
       DistributorTask ─▶ cloud-sdk-api StorageClient.getContent(bucket,key,charset) (READ ONLY — S-G2 NOT used) ─▶ cloud-sdk-aws S3StorageClient (v2)
       DistributorTask ─▶ commons networkservices SubscriptionService               ─▶ commons client.AuthClient (SSM, INTTRA auth)
       DistributorTask ─▶ cloud-sdk-api notification.workflow EventLogger/Event/MetaData ─▶ cloud-sdk-aws NotificationService (v2)
       DistributorTask ─▶ appianway-commons ErrorHandler (RecoverableException/ErrorHelper) ─▶ cloud-sdk-aws SQS MessagingClient x2 (v2)
       DistributorTask ─▶ module-local RestServiceClient  [UNCHANGED, NON-AWS]
                              └─▶ module-local auth.AuthClient  [UNCHANGED, NON-AWS]
```

### Class/type mapping

| `shared` (`com.inttra.mercury.shared.*`) / v1 type | Replacement | Home | Notes |
|---|---|---|---|
| `command.ConfigProcessingServerCommand` | `com.inttra.mercury.config.ConfigProcessingServerCommand` + composed appianway property-substitution transform | commons + appianway-commons | §5 |
| `config.S3ConfigurationProvider` | kept as-is (guarded by `S3ConfigurationProvider.requiresS3Configuration()`) | appianway-commons | unchanged |
| `config.BaseConfiguration`, `SQSConfig`, `SNSConfig`, `S3Config`, `NetworkServiceConfig`, `AWSClientConfiguration` | cloud-sdk config types bound in `ExternalServicesModule`; `DistributorConfiguration` POJO keeps `healthCheckConfig`/`networkServiceConfig`/`restClientConfig` | cloud-sdk-aws / module | YAML keys unchanged |
| `messaging.SQSListenerClient`, `messaging.SQSClient` (v1 `AmazonSQS`) | `cloud-sdk-api` `MessagingClient[String]` (listener + sender) | cloud-sdk-api/aws | two `@Named` bindings retained |
| `listener.SQSListener`, `listener.support.ListenerManager` | kept — appianway concurrency, re-typed onto `MessagingClient[String]`/`QueueMessage[String]` | appianway-commons | cloud-sdk `Listener` (O-G1) not taken |
| `threaddispatcher.AsyncDispatcher`, `task.AbstractTask`, `task.TaskFactory` | same classes, moved | appianway-commons | no logic change |
| `event.EventPublisher`, `event.SNSEventPublisher` (v1 `AmazonSNS`) | `cloud-sdk-api` `NotificationService.publish` + `notification.workflow.EventPublisher`/`SnsEventPublisher` | cloud-sdk-api/aws | |
| `event.Event`, `event.EventLogger`, `event.RandomGenerator` | `cloud-sdk-api` `notification.workflow.{Event,EventLogger,EventGenerator}` | cloud-sdk-api | **W-G9 relevant** — §6 |
| `task.MetaData` | `cloud-sdk-api` `notification.workflow.MetaData` | cloud-sdk-api | `Projection.SUBSCRIPTION_ID` read here — one of the W-G9.2 constants, must exist to compile |
| `task.ErrorHandler`, `task.errorhandler.ErrorHelper`, `externalwrapper.exception.RecoverableException` | same classes, moved | appianway-commons | error SQS + S3 error path unchanged |
| `workspace.WorkspaceService`, `workspace.S3WorkspaceService` (v1 `AmazonS3`) | `cloud-sdk-api` `StorageClient` (only `getContent(bucket,key,Charset)`) | cloud-sdk-api/aws | **read-only — S-G2 not exercised** |
| `networkservices.*`, `parameterstore.ParameterStoreModule`, `networkservices.NetworkRetryerModule` | `commons` `com.inttra.mercury.networkservices.*` + `client.AuthClient` | commons | SSM-backed INTTRA auth — **not** the module-local REST `AuthClient` |
| `distributorrest.auth.AuthClient`, `task.RestServiceClient`, `task.RequestBuilder`, `task.Request`, `auth.OAuthRequest`, `e2net.*` | **unchanged, no home change** — Jersey/JAX-RS OAuth2 client to the subscriber webhook | module-local | **non-AWS; zero migration work** |
| `com.amazonaws.services.sqs.model.Message` | `cloud-sdk-api` `messaging.QueueMessage[String]` (`getPayload()` replaces `getBody()`) | cloud-sdk-api | drives `DistributorTask.process` re-typing |

---

## 3. AWS touchpoints

| Direction | Resource (INT) | cloud-sdk client | Notes |
|---|---|---|---|
| SQS in (pickup) | `inttra_int_sqs_rest_delivery` | `MessagingClient[String]` (listener) | `SQSListener` polls, `waitTimeSeconds=20`, `maxNumberOfMessages=5` |
| SQS out (error) | `inttra_int_sqs_subscription_errors` | `MessagingClient[String]` (sender) | used by `ErrorHandler`/`ErrorHelper` on non-recoverable failure |
| SNS (lineage) | `inttra_int_sns_event` | `NotificationService` | close-run event publish only, no domain payload |
| S3 read | `inttra-int-workspace` | `StorageClient.getContent(bucket, key, ISO_8859_1)` | **read-only** — payload referenced by `MetaData.getBucket()/getFileName()`; no write, no copy. (`s3OutboundConfig.bucket=inttra-int-outbound-delivery` is a **dead, unreferenced** property — carry forward, do not remove here) |
| DynamoDB / SES / gRPC | none | n/a | not used |
| Param Store (SSM) | `/inttra/int/appianway/networkservices/authclientid`, `.../authclientsecret` | commons `CloudParameterStore` (via `client.AuthClient`) | resolved at **runtime**, not boot-time `${awsps:}` — unchanged mechanism (§5) |
| HTTP egress (non-AWS) | subscriber webhook URL (per-`Subscription`) + subscriber OAuth token endpoint | n/a — Jersey/JAX-RS `Client`, module-local `AuthClient` | untouched by this migration |

---

## 4. Sequence — consume → S3 read → REST deliver → lineage

```
 1.  SQSListener ─▶ receiveMessages (wait=20s, max=5) ─▶ List of QueueMessage[String]
 2.  AsyncDispatcher ─▶ DistributorTask.process(QueueMessage[String], queueUrl)
 3.  MetaData = Json.fromJsonString(msg.getPayload());  subscriptionId = metaData.getProjections().get(SUBSCRIPTION_ID)
 4.  if subscriptionId present:
        StorageClient.getContent(metaData.getBucket(), metaData.getFileName(), ISO_8859_1) ─▶ fileContent
        SubscriptionService.findSubscriptions(subscriptionId) ─▶ Subscription
        RequestBuilder.build(subscription) ─▶ Request{url, headers, OAuthRequest}
        RestServiceClient.post(request, fileContent):
            auth.AuthClient.getToken(oAuthRequest) ─▶ bearer token (cached; refreshed on 401)
            POST fileContent, Authorization: bearer [token] ─▶ Subscriber webhook ─▶ 2xx {status, e2openTransactionId}
        EventLogger.logCloseRunEvent(CLOSE_WORKFLOW, success, {PICK_UP_QUEUE, E2OPEN_TRANSACTION_ID}) ─▶ NotificationService.publish ─▶ SNS
        deleteMessage (ack, via AbstractTask.execute)
 5.  else subscriptionId absent: log.error("No subscriptionId!!!") — no delivery, no error routed
 6.  on NonRecoverableException / IOException:
        ErrorHandler.handleException(message, metaData, runId, tokens, ex)
          ─▶ writeErrorsToS3 (if applicable) + buildErrorMetaData
          ─▶ sendToQueue (error SQS) / sendBackToPickupQueue (recoverable)
          ─▶ logCloseRunEvent (failure)
```

---

## 5. Configuration changes

### 5.1 Property-key table

| YAML path | `${key}` | INT value | Notes |
|---|---|---|---|
| `componentName` | `${componentName:-distributor-rest}` | `distributor-rest` | |
| `healthCheckConfig.errorRateThreshold` | `${distributor.healthCheckConfig.errorRateThreshold:-5.0}` | `5.0` (default) | **unused** — `registerHealthChecks` never called |
| `healthCheckConfig.networkServiceHealthCheckUrl` | `${networkservices.healthCheckUrl}` | `https://api-alpha.inttra.com/network/services/ping` | unused (no health check consumes it) |
| `snsEventConfig.topicArn` | `${distributor.snsEventConfig.topicArn}` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | |
| `sqsErrorConfig.queueUrl` | `${distributor.sqsErrorSubscriptionConfig.queueUrl}` | `.../inttra_int_sqs_subscription_errors` | |
| `sqsPickupConfig.queueUrl` | `${distributor.pickupSQSConfig.queueUrl}` | `.../inttra_int_sqs_rest_delivery` | |
| `sqsPickupConfig.waitTimeSeconds` | `${distributor.pickupSQSConfig.waitTimeSeconds:-20}` | `20` | |
| `sqsPickupConfig.maxNumberOfMessages` | `${distributor.pickupSQSConfig.maxNumberOfMessages:-5}` | `5` | |
| `restClientConfig.connectTimeout` / `readTimeout` | literal `60000` | `60000` | **local, non-AWS**; unaffected |
| `s3WorkspaceConfig.bucket` | `${distributor.s3WorkspaceConfig.bucket}` | `inttra-int-workspace` | read-only |
| *(dead property, not in YAML)* | `distributor.s3OutboundConfig.bucket` | `inttra-int-outbound-delivery` | referenced by neither YAML nor code — carry forward unchanged |
| `networkServiceConfig.networkBaseUrl` | `${networkservices.networkBaseUrl}` | `https://api-alpha.inttra.com/network` | |
| `networkServiceConfig.authEndpointUrl` | `${networkservices.authEndpointUrl}` | `https://api-alpha.inttra.com/auth` | |
| `networkServiceConfig.clientId` / `clientSecret` | `${networkservices.clientId}` / `${...clientSecret}` | SSM paths (see §5.2) | |
| `networkServiceConfig.usePassThrough` | `${networkservices.usePassThrough}` | `false` | drives SSM vs. plain-text resolution |
| `networkServiceConfig.servicePaths.subscriptionSearchPath` | `${networkservices.subscriptionSearchPath}` | `/subscription/subscription` | **used** by `DistributorTask` → `SubscriptionService.findSubscriptions` |
| `server.connector.port` | `${server.connector.port:-8081}` | **8081** | single `simple` connector |
| `metrics.frequency` | `${metrics.frequency}` | (from `datadog.properties`) | unchanged |

### 5.2 SSM parameter table

| SSM path | Resolved by | Mechanism | Post-migration decision |
|---|---|---|---|
| `/inttra/int/appianway/networkservices/authclientid` | commons `client.AuthClient` (via `CloudParameterStore`) | **runtime**, at `AuthClient` construction (`asEagerSingleton()` — fail-fast on boot) | **Keep runtime resolution.** Do not move to boot-time `${awsps:/path}` — `usePassThrough=false` semantics preserved 1:1 by commons. |
| `/inttra/int/appianway/networkservices/authclientsecret` | same | same | same |

The module-local `auth.AuthClient` (OAuth2 bearer to the subscriber webhook) has **no SSM involvement** — its creds come from the `Subscription`'s `Action`/`ActionParameter` records (network-services data), not SSM.

### 5.3 Config-command composition

```
classpath distributor-rest.yaml
    │
    ▼
[ appianway property subst ]  ${key} from distributor-rest.properties + network-services.properties + datadog.properties + env
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]  (${awsps:/path} — no-op here, none declared)
    │
    ▼
DistributorConfiguration (Dropwizard factory)
```

`DistributorApplication.initialize(bootstrap)` still guards `S3ConfigurationProvider.requiresS3Configuration()` (`CONFIG_LOCATION=s3`) before installing the command — swap only the import from `shared`'s command to the commons equivalent (composed with the appianway transform). `CONFIG_REGION` and `datadog.properties` pass-through unchanged.

### 5.4 What's unchanged

- CLI arg shape, port 8081, single `simple` server.
- `RestClientConfig` (connect/read timeout = 60000 ms) — local, non-AWS.
- The module-local OAuth2 `AuthClient`/`RequestBuilder`/`RestServiceClient`/`e2net.*` chain — zero change.
- **No** ce-/os- run-profile variants (single deployment, single properties file).
- Queue names, topic ARN, bucket name, SSM paths — **none renamed**.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap | Exercised? | Detail |
|---|---|---|
| **S-G2** | **No.** | `DistributorTask` calls only `workspaceService.getContent(bucket, fileName, ISO_8859_1)`; no `putObject`/`copyObject` anywhere. `s3OutboundConfig.bucket` is dead. Needs only the existing `StorageClient.getContent(bucket,key,Charset)` read API. |
| **W-G9** | **Yes — consumes and produces on the wire.** | Deserializes `MetaData` off `inttra_int_sqs_rest_delivery` (reads `Projection.SUBSCRIPTION_ID` — a W-G9.2 constant) and calls `logCloseRunEvent(...)` with `CLOSE_WORKFLOW` + `Token.PICK_UP_QUEUE`/`E2OPEN_TRANSACTION_ID` (`E2OPEN_TRANSACTION_ID` must be in the W-G9.2 constant list, or added locally if distributor-rest-specific — **verify against the final W-G9.2 diff before cutover**). This module carries no `Annotations` on its events, so it is not a W-G9.1 producer, but as a consumer of the shared envelope it benefits from the fix landing program-wide. |
| **X-G7** / **X-G8** | No | no email; no Elasticsearch/Jest. |
| **C-G6** | Optional | §5.3 composition works without it. |

**Consumed from commons:** `config.ConfigProcessingServerCommand`, `networkservices.*` (Format/IntegrationProfile/Subscription services), `client.AuthClient`, `CloudParameterStore`/SSM auth.
**Consumed from cloud-sdk-api/aws:** `MessagingClient[String]` ×2 (listener + sender), `QueueMessage[String]`, `StorageClient` (read only), `NotificationService`, `notification.workflow.{MetaData, Event, EventLogger, EventGenerator}`.
**Moves to appianway-commons:** `AsyncDispatcher`, `AbstractTask`, `TaskFactory`, `Dispatcher`, `SQSListener`, `ListenerManager`, `ErrorHandler`, `ErrorHelper`, `RecoverableException`, `NonRecoverableException`.
**Stays module-local (non-AWS):** `auth.AuthClient`, `auth.OAuthRequest`, `task.RestServiceClient`, `task.RequestBuilder`, `task.Request`, `e2net.*`, `RetryerBuilder` — the entire OAuth2/Jersey egress half.

---

## 7. Maven dependency changes

**Remove:** `com.inttra.mercury.shared:mercury-shared`; `com.amazonaws:aws-java-sdk-sqs` (the module's only direct AWS dep — S3/SNS v1 arrive only transitively via `shared`, so they disappear when `shared` is removed).
**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK v2 arrives transitively via `cloud-sdk-aws` (BOM-managed) — do not declare v1 or v2 directly.
**Unchanged (module-specific, non-AWS):** Jersey stack (`jersey-common`/`-client`/`-hk2`/`-media-multipart`/`-server`/`-container-servlet-core` 3.1.11); `guava-retrying`-style `Retryer` (**verify it still resolves after `shared` removal; add an explicit dependency if it was only a transitive hitchhiker**); `metrics-guice`, `metrics-annotation`, `guava`, `guice`; `dropwizard-core` (DW5); `functional-testing` (test); `lombok`, `mockito-core`, `junit`, `assertj-core`.
**Align (already done by ION-16098):** Dropwizard 5.0.2 / Jetty 12.1.9 / Jackson 2.21.4 / Java 17.
**Verify:** `mvn -pl distributor-rest -am clean verify` (`clean` required — shade otherwise leaves stale v1 classes).

---

## 8. Tests

- **JUnit 5 direction;** existing JUnit 4 tests run under Vintage during transition.
- **Mock re-pointing:** `AmazonSQS`/`AmazonS3`/`AmazonSNS` → `MessagingClient[String]`/`StorageClient`/`NotificationService`; `com.amazonaws.services.sqs.model.Message` → `QueueMessage[String]` (`getBody()`→`getPayload()`).
- **`DistributorTask` unit tests must assert:**
  - `StorageClient.getContent(bucket, fileName, StandardCharsets.ISO_8859_1)` invoked with exactly that charset (regression guard).
  - `SubscriptionService.findSubscriptions(subscriptionId)` invoked with the value read from `MetaData.Projection.SUBSCRIPTION_ID`.
  - `RestServiceClient.post(request, fileContent)` invoked with the S3-read content (mock the egress boundary).
  - `EventLogger.logCloseRunEvent(..., CLOSE_WORKFLOW, success, {PICK_UP_QUEUE, E2OPEN_TRANSACTION_ID})` on success.
  - Missing-`subscriptionId` branch logs and does **not** call `restServiceClient`/`eventLogger`.
  - `NonRecoverableException`/`IOException` branch → `ErrorHandler.handleException(...)`.
- **W-G9 round-trip guard:** a `MetaData` JSON fixture carrying `Projection.SUBSCRIPTION_ID`, parsed through cloud-sdk-api, proving the constant-parity fix (W-G9.2) before `mvn verify` is trusted.
- **Egress tests unaffected:** WireMock/JAX-RS tests around `RestServiceClient`/module-local `AuthClient`/`RequestBuilder` should stay green with **zero** changes — the acceptance bar proving the AWS-boundary-only scope held.
- **`functional-testing` fakes** re-pointed to cloud-sdk-api in lockstep with the shared migration.

---

## 9. Rollout & verification

- **Position (program order):** after `appianway-commons` + `functional-testing` fakes + the `event-writer` pilot; the "light / read-only" tier — **before** the heavier `distributor`/`dispatcher`/`error-processor` S-G2 write consumers.
- **Build gate:** `mvn -pl distributor-rest -am clean verify` green.
- **INT boot + verification:**
  1. From `distributor-rest/`: `java -DCONFIG_REGION=US_EAST_1 -jar target/distributor-rest-1.0.jar run distributor-rest.yaml conf/int/distributor-rest.properties ../configuration/int/network-services.properties ../configuration/int/datadog.properties`.
  2. Confirm Jetty 12.1.9/Java 17 boot, commons `AuthClient` `GET /auth` succeeds (SSM resolved), `SQSListener starting` on `inttra_int_sqs_rest_delivery` with **zero** errors post-boot.
  3. **This module registers no health checks — do NOT rely on `/admin/opsHealthcheck`** (it 404s, same as baseline). Verify by boot-log evidence: SSM+auth success, clean SQSListener start, no exceptions in the polling loop.
  4. Optional deeper proof: drive one message through `inttra_int_sqs_rest_delivery` end-to-end and confirm S3-read + subscriber POST + `logCloseRunEvent` all succeed.
- **Regression bar:** WireMock/JAX-RS egress suite green with no changes — confirms the AWS-boundary-only scope held.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **No health checks to prove the rebind** — a broken client binding might only surface as a silent SQS-polling stall | Rely on boot-log evidence (SQSListener start + zero-error polling window); adding `registerHealthChecks` is a **follow-up, out of scope** for this AWS migration |
| Two distinct `AuthClient` classes with the same simple name (commons network-services vs. module-local OAuth2) causing confusion | Explicit in §2/§6; keep fully-qualified imports; do not let the commons migration touch the module-local class |
| ISO-8859-1 charset drift on the S3 read (binary-safe POST body) | Preserve `getContent(bucket, fileName, ISO_8859_1)` exactly; unit-test asserts the charset argument |
| `Message`→`QueueMessage[String]` re-typing misses a call site | Compiler-driven — will not compile until every site is updated; `AbstractTask`/`ErrorHelper` sites move with the appianway-commons library |
| `com.github.rholder.retry.Retryer` currently arrives transitively (possibly via `shared`) | Verify resolution after `shared` removal; add an explicit dependency if needed — **before** relying on a green `mvn verify` |
| W-G9.2 constant gap (`SUBSCRIPTION_ID`, `E2OPEN_TRANSACTION_ID`) blocks compilation | Gate behind the W-G9 cloud-sdk-api landing; confirm both constants exist before starting the rebind PR |
| S3 dead property (`s3OutboundConfig.bucket`) mistaken for an active write path | Called out in §3/§5.1 as unreferenced; do not add a write capability (scope creep beyond a pure rebind) |
| Regression on the live subscriber-delivery path | Strict AWS-boundary-only scope; WireMock/JAX-RS suite must stay green; sequence after the event-writer pilot |
