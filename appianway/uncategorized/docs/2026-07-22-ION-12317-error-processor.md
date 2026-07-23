# error-processor — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `error-processor` · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only error-processor's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`). error-processor boots clean on that stack today (still on AWS v1 + `shared`), 4 ops health checks green.

---

## Contents

---

## 1. Overview

**Purpose.** `error-processor` is the pipeline's **error fan-in / fan-out hub**. It consumes every failed-message `MetaData` envelope the platform produces (from `dispatcher`, `distributor`, `splitter`, `transformer`, …) off a single shared error queue, archives the original failure payload to S3, splits the configured recipient list, and re-emits one email-drop-off envelope per recipient — then closes the workflow with an SNS event. It has no REST surface and no SES/network-services dependency of its own; it is a pure SQS/S3/SNS worker.

- **Current state:** DW5 baseline; AWS access is 100% **AWS Java SDK v1** (`AmazonS3`, `AmazonSQS` ×2 named, `AmazonSNS`) wrapped by `shared` (`S3WorkspaceService`, `SQSClient`/`SQSListenerClient`/`SQSListener`, `SNSClient`/`SNSEventPublisher`, `MetaData`/`Event`/`EventLogger`, `AsyncDispatcher`/`AbstractTask`, `ErrorHandler`, `HealthCheckRegistrar` + 4 health indicators). Verified booting clean at INT: inbound SQS, outbound SQS, S3 read, SNS all green.
- **Target:** `shared` retired; AWS v1 types → **`cloud-sdk-api`** (`StorageClient`, `MessagingClient[String]`, `NotificationService`) backed by **`cloud-sdk-aws`** (AWS SDK v2). The workflow/event model → `cloud-sdk-api` `notification.*`. The appianway-only residue (`AsyncDispatcher`, `AbstractTask`, `ErrorHandler`, `RecoverableException`, health-indicator glue) → slim **`appianway-commons`**. Config command → **`commons`** composed with the appianway property-substitution transform.
- **Headline change:** (a) the archive-to-S3 write (`saveEventMetaData`) is a direct **S-G2** consumer — today it writes the raw failure JSON via the metadata-less `String` `putObject`; cloud-sdk-api's additive S-G2 overload lets it optionally set `contentType=application/json` (behavior-preserving; bytes unchanged). (b) error-processor is one of the **heaviest W-G9 consumers** — it *deserializes* an incoming `MetaData`, *constructs and re-serializes* N outbound `MetaData` envelopes (using `Projection.RECIPIENT_EMAIL_ID`, the cross-service contract with email-sender), and *publishes* a `closeWorkflow` `Event` carrying `Event.Token.DROP_OFF_QUEUE`/`PICK_UP_QUEUE`. Any wire-shape drift directly corrupts the email pipeline or the event-store archive.
- **No network-services, no SSM.** error-processor's yaml has no `networkServiceConfig` block (confirmed by source + INT boot evidence — no `AuthClient`/SSM call at startup). Zero SSM/network-services migration work.

---

## 2. Current vs Target architecture

```
BEFORE — AWS v1 + shared
  ErrorProcessorApplication ─▶ ErrorProcessorModule (Guice)
       ExternalServicesModule: AmazonS3 (no-retry), AmazonSQS x2 @Named(listener/sender), AmazonSNS (no-retry)
       shared SQSListener + AsyncDispatcher ─▶ ErrorProcessorTask (extends shared AbstractTask)
            ErrorProcessorTask ─▶ shared S3WorkspaceService (WorkspaceService) ─▶ AmazonS3 v1
            ErrorProcessorTask ─▶ shared SQSClient (fan-out sendMessage) ─▶ AmazonSQS v1
            ErrorProcessorTask ─▶ shared EventLogger ─▶ AmazonSNS v1
            ErrorProcessorTask ─▶ ErrorProcessorErrorHandler (extends shared ErrorHandler)
       shared HealthCheckRegistrar + 4 indicators probe v1 S3/SQS/SNS

AFTER — cloud-sdk (AWS v2) + appianway-commons
  ErrorProcessorApplication ─▶ ErrorProcessorModule (Guice)
       ExternalServicesModule: StorageClient, MessagingClient[String] x2 (listener/sender), NotificationService
       appianway-commons AsyncDispatcher + cloud-sdk-api Listener/QueueMessage ─▶ ErrorProcessorTask (extends appianway-commons AbstractTask)
            ErrorProcessorTask ─▶ cloud-sdk-api StorageClient (+S-G2 content-type) ─▶ cloud-sdk-aws (AWS SDK v2 BOM)
            ErrorProcessorTask ─▶ cloud-sdk-api MessagingClient[String] (fan-out sendMessage)
            ErrorProcessorTask ─▶ cloud-sdk-api EventLogger (notification.workflow)
            ErrorProcessorTask ─▶ ErrorProcessorErrorHandler (extends appianway-commons ErrorHandler)
       appianway-commons health-indicator wrappers over commons health base — 4 checks re-pointed to injected clients
```

### Class/type mapping

| # | `shared` (`com.inttra.mercury.shared.*`) — v1 | Replacement | Home | Notes |
|---|---|---|---|---|
| 1 | `config.BaseConfiguration` | module `ErrorProcessorConfiguration` extends commons/cloud-sdk-aware base | module + commons | `errorEmailRecipient`, `dropOffSQSConfig` stay module-owned fields |
| 2 | `config.SQSConfig` (pickup + drop-off) | cloud-sdk-aws `AwsMessagingClientConfig` (or equivalent SQS config POJO) | cloud-sdk-aws | 2 instances: pickup, drop-off |
| 3 | `workspace.WorkspaceService`/`S3WorkspaceService` | `cloud-sdk-api` `StorageClient` (+ S-G2 `putObject(bucket,key,byte[]/String,Map,contentType)`) | cloud-sdk-api/aws | `ErrorDetailsService.getContent`, `ErrorProcessorTask.saveEventMetaData` |
| 4 | `messaging.SQSClient`/`SQSListenerClient` | `cloud-sdk-api` `MessagingClient[String]` (2 instances: listener, sender) | cloud-sdk-api/aws | `AWSClientConfiguration.sqs_listener`/`sqs_sender` retry profiles map to per-client config |
| 5 | `event.SNSEventPublisher`/`EventPublisher` | `cloud-sdk-api` `notification.workflow.EventPublisher` / `NotificationService.publish` | cloud-sdk-api | `snsEventPublisher` Guice provider |
| 6 | `task.MetaData` | `cloud-sdk-api` `notification.workflow.MetaData` (`Projection.RECIPIENT_EMAIL_ID`, `EXIT_STATUS_SUCCESS`) | cloud-sdk-api | **W-G9 relevant** — §6 |
| 7 | `event.Event`, `EventLogger`, `RandomGenerator` | `cloud-sdk-api` `notification.workflow.{Event,EventLogger}`; `RandomGenerator` → appianway-commons/cloud-sdk-api util | cloud-sdk-api (+ appianway-commons) | `Event.SubType.CLOSE_WORKFLOW`, `Event.Token.DROP_OFF_QUEUE`/`PICK_UP_QUEUE` — **W-G9 relevant** |
| 8 | `workspace.Annotations` | `cloud-sdk-api` `notification.annotation.Annotations` | cloud-sdk-api | used by `ErrorDetailsService` (currently unreferenced by `ErrorProcessorTask` — dead-code candidate, verify at migration) |
| 9 | `externalwrapper.exception.RecoverableException` | appianway-commons `RecoverableException` | appianway-commons | thrown by `ErrorProcessorTask.process` |
| 10 | `task.AbstractTask`, `threaddispatcher.{AsyncDispatcher,Dispatcher}`, `task.TaskFactory` | appianway-commons (unchanged concurrency model) | appianway-commons | `ErrorProcessorModule` binds `Dispatcher` → `AsyncDispatcher` |
| 11 | `task.ErrorHandler`, `task.errorhandler.ErrorHelper` | appianway-commons `ErrorHandler`/`ErrorHelper` | appianway-commons | `ErrorProcessorErrorHandler extends ErrorHandler` unchanged shape |
| 12 | `listener.SQSListener`, `listener.support.ListenerManager` | appianway-commons `SQSListener`/`ListenerManager` over `cloud-sdk-api` `MessagingClient`/`Listener` | appianway-commons + cloud-sdk-api | `ErrorProcessorModule.getSQSListener`/`listenerManager` |
| 13 | `healthcheck.HealthCheckRegistrar`, `indicator.{InboundSqs,OutboundSqs,S3Read,SnsPublish}HealthCheck` | commons health base + appianway-commons indicator wrappers re-pointed to injected clients | commons + appianway-commons | 4 checks |
| 14 | `config.S3ConfigurationProvider` | appianway-commons (kept, conditional on `CONFIG_LOCATION=s3`) | appianway-commons | unchanged; not exercised in local/INT runs |
| 15 | `command.ConfigProcessingServerCommand` | commons `ConfigProcessingServerCommand` + composed appianway property-substitution transform | commons + appianway-commons | foundation §4 |
| 16 | `com.amazonaws.services.sqs.model.Message` | `cloud-sdk-api` `messaging.QueueMessage[String]` | cloud-sdk-api | `process(Message,...)` → `process(QueueMessage[String],...)`; `getBody()`→`getPayload()` |
| 17 | `com.amazonaws.ClientConfiguration` (`withMaxErrorRetry(0)`) | cloud-sdk-aws `ClientOverrideConfiguration`/retry-policy equivalent (zero-retry) | cloud-sdk-aws | **preserve** the deliberate no-retry S3/SNS behavior — §6 |
| 18 | `org.zapodot.hystrix.bundle.HystrixBundle` (already commented out) | none — dead code, drop the import/dependency | — | Hystrix is dead everywhere |

---

## 3. AWS touchpoints

| Direction | Resource | INT value | cloud-sdk client | Notes |
|---|---|---|---|---|
| SQS — inbound (pickup / fan-in) | `inttra_int_sqs_subscription_errors` | `.../inttra_int_sqs_subscription_errors` | `MessagingClient[String]` (`@Named` listener) | Long-poll; the **shared platform-wide error queue** — every module's failures land here |
| SQS — outbound (drop-off / fan-out) | `inttra_int_sqs_email_outbound` | `.../inttra_int_sqs_email_outbound` | `MessagingClient[String]` (`@Named` sender) | One `sendMessage` per recipient email (N messages per 1 inbound failure) |
| S3 — write (archive) | `inttra-int-workspace` | key `{rootWorkflowId}/{uuid}` | `StorageClient.putObject` (**S-G2** site — optional `contentType`/metadata) | Archives the raw failure-message body verbatim before fan-out |
| S3 — read | `inttra-int-workspace` | same bucket | `StorageClient.getContent` | Used by `ErrorDetailsService.getErrorDetails` (`Annotations` lookup) — verify still called; health-checked as S3-read |
| SNS — publish | `inttra_int_sns_event` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `NotificationService.publish` (via `EventLogger`/`EventPublisher`) | `closeWorkflow` `Event`, `SubType.CLOSE_WORKFLOW`, `isSuccess=true/false` |
| DynamoDB / gRPC | — | none | — | not used |
| SES | — | none | — | no direct email send — email is *requested* via the SQS drop-off queue; email-sender does the SES send |
| Param Store (SSM) | — | **none** | — | no `networkServiceConfig` in yaml; confirmed by INT boot evidence — no `AuthClient`/SSM call at startup |

---

## 4. Sequence — consume → archive → fan-out → close

```
 1.  appianway-commons SQSListener ─▶ receiveMessages(wait=20s, max=10) ─▶ List of QueueMessage[String]
 2.  AsyncDispatcher (semaphore-bounded) ─▶ ErrorProcessorTask.process(QueueMessage[String], pickupQueueUrl)
 3.  metaData = Json.fromJsonString(payload, MetaData.class)
 4.  StorageClient.putObject(bucket, rootWorkflowId/uuid, payload[, "application/json"])   [S-G2]  ─▶ archived (eventFileName)
 5.  for each emailId in errorEmailRecipient.split(","):
        buildMetaData(metaData, emailId, eventFileName)  [sets Projection.RECIPIENT_EMAIL_ID]
        MessagingClient.sendMessage(dropOffQueueUrl, Json.toJsonString(targetMetaData)) ─▶ inttra_int_sqs_email_outbound
 6.  EventLogger.logCloseRunEvent(metaData, CLOSE_WORKFLOW, runId, body, componentName, startDateTime, true, {DROP_OFF_QUEUE, PICK_UP_QUEUE})
        ─▶ NotificationService.publish(Event JSON) ─▶ SNS
 7.  success ─▶ message deleted
 8.  on any Exception during archive/fan-out/publish:
        ErrorProcessorErrorHandler.handleException(message, CLOSE_WORKFLOW, metaData, runId, startDateTime, {}, ex)
        ─▶ increments FAILED_ATTEMPTS / re-delivers or DLQs (unchanged semantics) — message NOT deleted
```

**Preserved failure semantics (do not change):** if the archive `putObject` throws, `process` catches it, calls `errorHandler.handleException(...)`, and the message is **not** deleted from `subscription_errors` — it is redelivered per the appianway-commons `ErrorHandler`/`FAILED_ATTEMPTS` model. Since error-processor is itself the error sink, a persistent archive-write failure must not silently swallow messages; this loop-avoidance behavior is unchanged and must be covered by an explicit test (§8).

---

## 5. Configuration changes

### 5.1 Property-key table (exact INT values, `conf/int/error-processor.properties`)

| Property key | INT value | Consumed by (yaml path) | Notes |
|---|---|---|---|
| `error-processor.pickupSQSConfig.queueUrl` | `.../inttra_int_sqs_subscription_errors` | `sqsPickupConfig.queueUrl`, `sqsErrorConfig.queueUrl` | inbound fan-in; referenced twice in yaml (`sqsPickupConfig` + a legacy `sqsErrorConfig` block resolving to the same URL — vestigial/duplicate, verify at migration whether still bound) |
| `error-processor.dropOffSQSConfig.queueUrl` | `.../inttra_int_sqs_email_outbound` | `dropOffSQSConfig.queueUrl` | outbound fan-out → feeds email-sender |
| `error-processor.snsEventConfig.topicArn` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `snsEventConfig.topicArn` | closeWorkflow event topic |
| `error-processor.s3WorkspaceConfig.bucket` | `inttra-int-workspace` | `s3WorkspaceConfig.bucket` | archive + `ErrorDetailsService` read bucket |
| `error-processor.errorEmailRecipient` | `appianway@inttra.com` | `errorEmailRecipient` (top-level) | **CSV list** — split on `,`; one outbound envelope per address |
| `componentName` | `error-processor` (default) | `componentName` | `MetaData.Builder` + `EventLogger` componentName |
| *(yaml default)* `server.connector.port` | **8081** (`${server.connector.port:-8081}`) | `server.connector.port` | single `simple` server; `/application` + `/admin` share the port |
| *(default)* `pickupSQSConfig.waitTimeSeconds` / `.maxNumberOfMessages` | `20` / `10` | `sqsPickupConfig.*` | long-poll; max also sizes the `AsyncDispatcher` semaphore |
| `metrics.frequency` | from `configuration/int/datadog.properties` | `metrics.frequency` | unchanged, not module-specific |

**Do not rename** `inttra_int_sqs_subscription_errors`, `inttra_int_sqs_email_outbound`, `inttra_int_sns_event`, `inttra-int-workspace`, or any property key — environment contracts shared with dispatcher/distributor/splitter/transformer (all fan into `subscription_errors`) and email-sender (consumes `email_outbound`).

### 5.2 SSM parameters

**None.** error-processor's yaml has **no `networkServiceConfig` block** — confirmed by source and by INT boot evidence (no `AuthClient`/SSM call logged at startup, matching the email-sender/event-writer pattern). `configuration/int/network-services.properties` is still passed on the CLI (to match the uniform run-script shape across all 14 modules) but **nothing in error-processor's yaml references its keys**. No `${awsps:/path}` boot-time SSM resolution is needed either — there is simply no secret to resolve.

### 5.3 Config-command composition

commons `ConfigProcessingServerCommand` runs `TrimConfigCommentsTransform.andThen(ParameterStoreConfigTransform)`; since this module resolves no `${awsps:...}` tokens, `ParameterStoreConfigTransform` is a no-op pass-through here. The **required** composition point is still the appianway property-substitution transform (from appianway-commons) prepended in front, so `${error-processor.pickupSQSConfig.queueUrl}` etc. resolve from `conf/int/error-processor.properties` + env before the commons transforms run:

```
classpath error-processor.yaml
    │
    ▼
[ appianway-commons property subst ]  ${key} from error-processor.properties + network-services.properties (unused) + datadog.properties + env
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]  (no ${awsps:...} tokens present — no-op for this module)
    │
    ▼
Dropwizard Configuration factory (ErrorProcessorConfiguration)
```

`ErrorProcessorApplication.initialize(bootstrap)` registers this composed command in place of `shared`'s, keeping the conditional `S3ConfigurationProvider` install (`CONFIG_LOCATION=s3`) unchanged (moves to appianway-commons per §2 row 14).

### 5.4 What is unchanged

- **CLI arg shape:** `run error-processor.yaml conf/int/error-processor.properties ../configuration/int/network-services.properties ../configuration/int/datadog.properties` — identical, all 4 args still passed even though the 2 network-services args are unreferenced by this module's yaml.
- **`CONFIG_REGION=US_EAST_1`** — unchanged.
- **Port 8081**, single `simple` Dropwizard server, `/application` + `/admin` sharing the connector — unchanged.
- **No run profiles / variants** (unlike ingestor/splitter/transformer `ce-`/`os-`) — exactly one deployment shape.
- **`datadog.properties`** → `metrics.frequency` — unchanged.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap | Relevant? | Detail |
|---|---|---|
| **S-G2** | **Yes — direct consumer.** | `ErrorProcessorTask.saveEventMetaData` archives `message.getBody()` (raw failure JSON) via the metadata-less `String putObject` today. Migrating to cloud-sdk-api's additive `StorageClient.putObject(bucket,key,byte[]/String,Map metadata,String contentType)` lets the archive object carry `contentType=application/json` (optional — behavior-preserving; bytes identical). No cloud-sdk change is module-specific; error-processor exercises the same S-G2 overload as event-writer/dispatcher/distributor. |
| **W-G9** | **Yes — primary/heaviest consumer alongside event-writer.** | It (1) **deserializes** `MetaData` produced by every upstream module off `subscription_errors`; (2) **constructs N new `MetaData` envelopes** setting `Projection.RECIPIENT_EMAIL_ID` (the exact cross-service contract email-sender depends on); (3) **publishes a `closeWorkflow` `Event`** with `Event.Token.DROP_OFF_QUEUE`/`PICK_UP_QUEUE`. Per foundation §5A the wire *data* is compatible, and the constants it uses (`RECIPIENT_EMAIL_ID`, `DROP_OFF_QUEUE`, `PICK_UP_QUEUE`) **are** present in the current cloud-sdk-api sets — so this module compiles today against the gap — but any annotation-carrying `Event` that transits its `logCloseRunEvent` is subject to the W-G9.1 round-trip defect downstream at event-writer. **Recommendation: land W-G9 before or in lockstep**, and run the foundation §5A round-trip corpus test using production `subscription_errors` payloads (the richest `MetaData`/`Event` samples in the platform — literally other modules' failure envelopes) as this module's own test gate. |
| **X-G7** / **X-G8** | No | no SES send (email requested via SQS, not sent directly); no OpenSearch/Jest. |
| **C-G6** | Optional | the appianway transform composes in front of commons' transforms without widening `getConfigTransformer`. |

**Consumes from commons:** `ConfigProcessingServerCommand` (composed), health base (`com.inttra.mercury.health.*`), `InttraServer` DW5 base if adopted at bootstrap.
**Moves to appianway-commons:** `AsyncDispatcher`/`AbstractTask`/`TaskFactory`/`Dispatcher`, `ErrorHandler`/`ErrorHelper`/`RecoverableException`, the 4 health-indicator wrappers (`InboundSqs`, `OutboundSqs`, `S3Read`, `SnsPublish` re-pointed to injected clients), `SQSListener`/`ListenerManager`, the conditional `S3ConfigurationProvider`.

---

## 7. Maven dependency changes

**Remove:** `com.inttra.mercury.shared:mercury-shared`; `com.amazonaws:aws-java-sdk-sqs` (the only direct v1 dep; transitive v1 S3/SNS disappear once `shared` is removed — no direct `aws-java-sdk-s3`/`-sns` in this pom); drop the dead commented-out `HystrixBundle` import/dependency. Verify with `mvn dependency:tree` that no v1 artifact remains.
**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK v2 arrives transitively via `cloud-sdk-aws` (BOM) — do not declare any `software.amazon.awssdk:*` directly.
**Align (already true from ION-16098):** `dropwizard-core`/`metrics-annotation`, Java 17 compiler, shade `ManifestResourceTransformer` mainClass (`com.inttra.mercury.error.processor.ErrorProcessorApplication`, unchanged), `ServicesResourceTransformer`.
**No other module-specific artifacts** (no schema-beans/gen2-parser/protobuf/Contivo/Jest — a plain JSON-`MetaData` consumer).
**Verify:** `mvn -pl error-processor -am clean verify` (`-am` also builds the new reactor modules; confirm the root `pom.xml` `<modules>` includes `appianway-commons`); fat-jar boot + `/admin/opsHealthcheck` green against INT (`clean` required — shade otherwise leaves stale fat jars).

---

## 8. Tests

- **JUnit 5** direction (existing tests are JUnit 4 — migrate or bridge via `junit-vintage-engine`).
- **Re-point mocks:** `AmazonSQS`/`AmazonS3`/`AmazonSNS` → `MessagingClient[String]` (2 instances)/`StorageClient`/`NotificationService`; `com.amazonaws.services.sqs.model.Message` → `QueueMessage[String]` (`getBody()`→`getPayload()`).
- **`ErrorProcessorTask` unit tests must assert:**
  1. `saveEventMetaData` calls `StorageClient.putObject` with key **exactly** `{rootWorkflowId}/{uuid}` and (post S-G2 adoption) `contentType=application/json` if that overload is used; bucket = `s3WorkspaceConfig.bucket`.
  2. **Fan-out count** — one `MessagingClient.sendMessage(dropOffQueueUrl, json)` **per** entry in `errorEmailRecipient.split(",")`, each with a **distinct** `workflowId` (via `randomGenerator.randomUUID()`) but the **same** `rootWorkflowId`/`eventFileName`.
  3. **`Projection.RECIPIENT_EMAIL_ID`** set on every outbound `MetaData` to the corresponding split email — the wire contract email-sender reads; a round-trip test (build → `toJsonString` → `fromJsonString` on the cloud-sdk-api `MetaData`) must show the projection key survives.
  4. **`closeWorkflow` Event** publish: `Event.SubType.CLOSE_WORKFLOW`, `isSuccess=true` on the happy path, tokens map contains exactly `Event.Token.DROP_OFF_QUEUE`→dropOffQueueUrl and `Event.Token.PICK_UP_QUEUE`→pickupQueueUrl.
  5. **Failure-path / loop-avoidance test (critical — this module is the error sink):** force `StorageClient.putObject` (or the fan-out `sendMessage`) to throw; assert `ErrorProcessorErrorHandler.handleException(...)` is invoked with `CLOSE_WORKFLOW`, and the inbound message is **not** deleted (`FAILED_ATTEMPTS`/redelivery preserved, not a silent drop). No new infinite-loop risk from the client swap.
- **W-G9 verification gate (foundation §5A):** include this module's own `subscription_errors` sample payloads (real upstream failure `MetaData`/`Event` JSON) in the shared round-trip corpus test — assert `parseJson → toJsonString` byte-stability, **including at least one sample that carries `Annotations`**, to guard the W-G9.1 builder defect from this module's consume-side.
- **`functional-testing` fakes** re-pointed to cloud-sdk-api (lockstep with the `appianway-commons`/functional-testing migration order) — no behavior change expected, just fake retargeting.
- Preserve **zero-retry** S3/SNS client behavior in test assertions (config mapping to cloud-sdk-aws `ClientOverrideConfiguration` retry policy) so `ErrorProcessorErrorHandler`'s fail-fast/redeliver expectations aren't silently changed by a default-retry v2 client.

---

## 9. Rollout & verification

**Position (program order):** the **"S-G2 write/copy consumers"** wave — after `appianway-commons`, `functional-testing`, event-writer (S-G2 pilot), the light consumers (distributor-rest/splitter/ingestor), migrated with `dispatcher` and `distributor`.

1. Confirm `appianway-commons` and the migrated `functional-testing` are available in the reactor.
2. Confirm **event-writer** landed first (primary S-G2 pilot) and cloud-sdk CI + a full mercury-services build are green (proof of zero blast-radius from S-G2/W-G9).
3. Migrate `ExternalServicesModule` (rebind 4 clients), re-type `ErrorProcessorTask`/`ErrorDetailsService`/`ErrorProcessorErrorHandler`, adopt cloud-sdk-api `MetaData`/`Event`/`EventLogger`, compose the config command (§5.3).
4. `mvn -pl error-processor -am clean verify` green.
5. Boot the fat jar against INT: `java -DCONFIG_REGION=US_EAST_1 -jar target/error-processor-1.0.jar run error-processor.yaml conf/int/error-processor.properties ../configuration/int/network-services.properties ../configuration/int/datadog.properties`.
6. Confirm all **4** `/admin/opsHealthcheck` checks green (inbound SQS `subscription_errors`, outbound SQS `email_outbound`, S3 read `inttra-int-workspace`, SNS publish `inttra_int_sns_event`) — matching the pre-migration baseline exactly.
7. If feasible, drive one real message through `subscription_errors` in INT (or a scratch queue) and confirm: the archive object lands at `{rootWorkflowId}/{uuid}` in `inttra-int-workspace`, N messages land in `email_outbound` (N = recipient count, currently 1), and a `closeWorkflow` event is observable on `inttra_int_sns_event`.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Archive-write failure creates a silent-drop or infinite-redelivery loop (error-processor is itself the error sink) | Explicit failure-path test (§8.5); preserve `RecoverableException`/no-delete semantics unchanged from `shared` |
| W-G9 `Event.Builder` annotations round-trip defect affects a `closeWorkflow` event carrying annotations published from here | Land W-G9 in cloud-sdk-api before/alongside this migration; run the round-trip corpus test with this module's own sample payloads (§8) |
| Losing the deliberate **zero-retry** S3/SNS client config (`withMaxErrorRetry(0)`) during the v1→v2 client rebind, silently changing fail-fast/redeliver timing | Map explicitly to a zero-retry `ClientOverrideConfiguration`/retry policy in `ExternalServicesModule`; assert in tests |
| `Message`→`QueueMessage[String]` misses a call site (`getBody()`, attribute reads in `ErrorHelper`) | Compiler-driven type change; `FAILED_ATTEMPTS` confirmed to round-trip as a `String` attribute |
| Two named `MessagingClient[String]` bindings (listener vs. sender) accidentally collapsed into one, changing retry/timeout per direction | Keep the two `@Named` bindings distinct in the migrated `ExternalServicesModule`, mirroring `AWSClientConfiguration.sqs_listener`/`sqs_sender` today |
| Vestigial `sqsErrorConfig` yaml block (duplicate of `sqsPickupConfig.queueUrl`) causes confusion or an unused binding during rebind | Verify whether `sqsErrorConfig` is bound anywhere in code; if truly dead, remove the yaml block (call out explicitly, don't silently drop if referenced) |
| `ErrorDetailsService`/`Annotations` path looks unreferenced by `ErrorProcessorTask` today — risk of migrating dead code or missing a live caller | Grep for `ErrorDetailsService` usage across the module before finalizing the class-mapping; migrate faithfully either way (keep if referenced, drop cleanly if confirmed dead) |
| Cloud-sdk-api/`commons` change breaking mercury-services production consumers | S-G2 and W-G9 are strictly additive (foundation §5/§5A); cloud-sdk CI + full mercury-services build green before/after |
