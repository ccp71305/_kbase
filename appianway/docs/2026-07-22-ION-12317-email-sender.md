# email-sender — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `email-sender` · Main: `com.inttra.mercury.email.EmailSenderApplication` · Port 8081 · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only email-sender's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`). email-sender boots clean on that stack today (still on AWS v1 + `shared`), 2 ops health checks green, and — verified — makes **no** `AuthClient`/SSM call at boot.

---

## Contents

---

## 1. Overview

`email-sender` is the **terminal notification leaf** of the pipeline: it drains `inttra_int_sqs_email_outbound`, performs **two S3 reads** (the original workflow event, then that event's `Annotations` error document), renders subject + body **locally with Thymeleaf** (`TemplateMode.TEXT`), applies a **local Guava rate limiter**, and sends the message through **Amazon SES**. It is a pure queue worker — no REST resources, no `networkServiceConfig` block, no SSM-backed auth call at boot.

- **Current state (DW5 baseline):** AWS Java SDK **v1 (1.12.720)** + `shared` (`AmazonSimpleEmailService`, `AmazonSQS` x2, `AmazonS3`, `AmazonSNS`, shared `SQSListener`/`AsyncDispatcher`/`ErrorHandler`/`MailContext`/`MetaData`/`Event`/`EventLogger`). Boots clean on INT.
- **Target:** `commons` + `cloud-sdk-api` + `cloud-sdk-aws` (`1.0.27-SNAPSHOT`) — SES v2, SQS v2, S3 v2, SNS v2 — + slim `appianway-commons` for the concurrency/error/health residue. Thymeleaf and the rate limiter stay **exactly as they are today**.
- **Headline change (X-G7):** every email this module sends carries a **reply-to address** (`mailConfig.replyToEmailAddress`, INT value `no-reply@appianway-alpha.inttra.com`) via v1 `SendEmailRequest.withReplyToAddresses(...)`. cloud-sdk-api's `MailContent`/`EmailService` today expose **no reply-to field** — the one module-specific cloud-sdk dependency email-sender needs. Everything else is a normal-client rebind.
- **Secondary theme (G5, de-scoped):** template rendering (Thymeleaf, `TemplateMode.TEXT`) stays **entirely local** — adding Thymeleaf to a library every mercury-services app depends on would violate the zero-transitive-impact constraint. cloud-sdk-api has a Handlebars `TemplateService`, but email-sender does **not** adopt it — it sends pre-rendered text.

---

## 2. Current vs Target architecture

```
BEFORE — email-sender on shared + AWS v1
  inttra_int_sqs_email_outbound ─▶ shared SQSListener ─▶ shared AsyncDispatcher
       ─▶ EmailSenderTask (shared AbstractTask)
              ─▶ ContentLoaderService ─▶ shared S3WorkspaceService ─▶ S3 v1 (inttra-int-workspace, read x2)
              ─▶ RateLimiterService (LOCAL, Guava, unchanged)
              ─▶ MailingService ─▶ Thymeleaf TemplateEngine (LOCAL, TEXT)
                                 ─▶ AmazonSimpleEmailService v1
                                      SendEmailRequest/Destination/Message + withReplyToAddresses, maxErrorRetry(0)
                                      ─▶ AWS SES classic
              ─▶ shared EventLogger/SNSEventPublisher ─▶ inttra_int_sns_event
       (non-recoverable) ─▶ shared ErrorHandler ─▶ inttra_int_sqs_subscription_errors

AFTER — email-sender on commons + cloud-sdk (AWS v2)
  inttra_int_sqs_email_outbound ─▶ appianway-commons AsyncDispatcher (+ cloud-sdk MessagingClient[String])
       ─▶ EmailSenderTask (appianway-commons AbstractTask)
              ─▶ ContentLoaderService ─▶ cloud-sdk-api StorageClient.getContent ─▶ S3 v2 (read x2)
              ─▶ RateLimiterService (LOCAL, Guava, UNCHANGED)
              ─▶ MailingService ─▶ Thymeleaf TemplateEngine (LOCAL, TEXT, UNCHANGED)
                                 ─▶ cloud-sdk-api EmailService (+ X-G7 replyTo)
                                      ─▶ cloud-sdk-aws SesEmailServiceImpl (SesV2Client, retry=none)
                                      ─▶ AWS SES v2
              ─▶ cloud-sdk-api EventLogger/EventPublisher (NotificationService) ─▶ inttra_int_sns_event
       (non-recoverable) ─▶ appianway-commons ErrorHandler ─▶ inttra_int_sqs_subscription_errors
```

### 2.1 Class/type-level mapping

| Today (`shared` / AWS v1) | Target | Home |
|---|---|---|
| `com.amazonaws.services.simpleemail.AmazonSimpleEmailService` | `cloud-sdk-api` `email.EmailService` backed by `cloud-sdk-aws` `SesEmailServiceImpl` (`SesV2Client`) — SES classic → SES v2 | cloud-sdk |
| `SendEmailRequest`/`Destination`/`simpleemail.model.{Message,Body,Content}`/`SendEmailResult` | `email.MailContent` (subject + text body **+ replyTo, X-G7**) built by `MailingService`; `EmailService.sendEmail(from, List to, MailContent)` returns message-id | cloud-sdk-api |
| `new ClientConfiguration().withMaxErrorRetry(0)` | `cloud-sdk-aws` SES client, `ClientOverrideConfiguration` retry policy = **none** (must preserve) | cloud-sdk-aws |
| `AmazonSQS` x2 (`amazonSQSForListener`/`amazonSQSForSender`) + `com.amazonaws.services.sqs.model.Message` | `cloud-sdk-api` `messaging.MessagingClient[String]` / `QueueMessage[String]`; `Message.getBody()` → `QueueMessage[String].getPayload()` | cloud-sdk |
| `AmazonS3`, `shared.workspace.{WorkspaceService,S3WorkspaceService}` | `cloud-sdk-api` `storage.StorageClient` (`getContent` only — **read-only**, no S-G2) | cloud-sdk |
| `AmazonSNS`, `shared.event.SNSEventPublisher`/`SNSClient` | `cloud-sdk-api` `notification.NotificationService` (`publish`) + `notification.workflow.EventPublisher` (topic ARN unchanged) | cloud-sdk-api |
| `shared.listener.SQSListener`, `shared.threaddispatcher.{AsyncDispatcher,Dispatcher}`, `shared.task.{AbstractTask,TaskFactory}` | **`appianway-commons`** `AsyncDispatcher`/`AbstractTask`/task lifecycle (same semaphore-bounded worker-pool model) | appianway-commons |
| `shared.mail.MailContext` (+ `Builder`) | `cloud-sdk-api` `email.MailContent` (send side) **+** a small local value object carrying `MetaData`/recipient/contents for template placeholders (rendering side stays appianway-local) | cloud-sdk-api (send) + module (render) |
| `MailDetails` (holds v1 `simpleemail.model.Message`) | refactor to hold the **rendered subject/body strings** (drops the v1 `Message` field) | module |
| `PropertyPlaceholdersResolver` (returns v1 `simpleemail.model.Message`) | same Thymeleaf call, **returns rendered subject + body `String`s** (or a local `RenderedMail` DTO) | module (Thymeleaf untouched, return type changed) |
| `shared.event.{Event,EventLogger,EventGenerator,RandomGenerator}`, `shared.task.MetaData`, `shared.workspace.Annotations` | `cloud-sdk-api` `notification.workflow.{Event,EventLogger,EventGenerator,MetaData,WorkflowAware}`, `notification.annotation.{Annotations,Annotation}` | cloud-sdk-api (**W-G9** applies) |
| `shared.task.{ErrorHandler,errorhandler.ErrorHelper}`, `shared.externalwrapper.exception.RecoverableException` | **`appianway-commons`** `ErrorHandler`/`RecoverableException`/error codes (`EmailSenderErrorHandler`'s 3-entry error-code map is unchanged app logic) | appianway-commons |
| `shared.healthcheck.{HealthCheckRegistrar, InboundSqsHealthCheck, SnsPublishHealthCheck}` | `commons` health base + **appianway-commons** indicator wrappers re-pointed at the injected `MessagingClient`/`NotificationService` (only 2 checks registered) | commons + appianway-commons |
| `shared.command.ConfigProcessingServerCommand`, `shared.config.S3ConfigurationProvider` | `commons` `ConfigProcessingServerCommand` + composed appianway transform; `S3ConfigurationProvider` kept appianway-local (unused at INT) | commons (+ appianway-commons) |
| `org.thymeleaf.TemplateEngine`/`StringTemplateResolver` (`TemplateMode.TEXT`) | **unchanged, local** — G5 de-scoped | module |
| `com.google.common.util.concurrent.RateLimiter` (`RateLimiterService`) | **unchanged, local** — no cloud-sdk equivalent needed | module |

---

## 3. AWS touchpoints

| Touchpoint | Direction | INT resource | cloud-sdk client | Health-probed today? |
|---|---|---|---|---|
| SQS pickup | in | `inttra_int_sqs_email_outbound` | `MessagingClient[String]` (listener) | Yes — `InboundSqsHealthCheck` (default + ops) |
| SQS error | out (non-recoverable only) | `inttra_int_sqs_subscription_errors` | `MessagingClient[String]` (sender, via appianway-commons `ErrorHandler`) | No — config-resolved only |
| SNS publish | out | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `NotificationService` | Yes — `SnsPublishHealthCheck` (ops) |
| S3 read | in (2 GETs per message: original event, then `Annotations`) | `inttra-int-workspace` | `StorageClient.getContent(bucket, fileName)` | No — config-resolved only |
| S3 write | — | none | — | n/a — email-sender never writes S3 (S-G2 not applicable) |
| DynamoDB | — | none | — | n/a |
| SES send | out | AWS SES (no INT-specific config-set in code); sender `mailConfig.senderEmailAddress`, reply-to `mailConfig.replyToEmailAddress` | `EmailService` (SES v2, `SesEmailServiceImpl`) | No — a real send needs a real inbound message |
| Param Store (SSM) | — | **none** | — | **No `networkServiceConfig` block** → no `AuthClient`/SSM call at boot. AWS creds for SQS/S3/SNS/SES come from the default credential chain only. |
| gRPC | — | none | — | n/a |

> **W-G9 call-out:** email-sender is both a **consumer** (original-event `MetaData`, `Annotations`) and a **producer** (close-run `Event` via `EventLogger`) of the workflow model. It reads `MetaData.Projection.RECIPIENT_EMAIL_ID` — one of the projection keys already present in cloud-sdk-api — so no additive-constant gap blocks this module specifically. The `Event.Builder` annotations round-trip defect (W-G9.1) does not affect email-sender's own close-run events (it does not set `Event` annotations), but the module still depends on the overall W-G9 fix landing first because it shares the wire model with every upstream producer (error-processor, validators) whose `MetaData`/`Annotations` it deserializes.

---

## 4. Sequence — consume → load S3 (2x) → render (local Thymeleaf) → SES send (+ reply-to) → publish

```
 1.  AsyncDispatcher (appianway-commons) ─▶ QueueMessage[String] (long-poll)
 2.  ─▶ EmailSenderTask.process(QueueMessage[String])
 3.  MetaData.parseJson(message.getPayload())
 4.  ContentLoaderService.getOriginalEvent(metaData):
        StorageClient.getContent(metaData.bucket, metaData.fileName) ─▶ original-event JSON ─▶ eventMetaData : MetaData
 5.  ContentLoaderService.getContents(eventMetaData):
        StorageClient.getContent(eventMetaData.bucket, eventMetaData.fileName) ─▶ Annotations JSON ─▶ {"content" ─▶ Annotations}
 6.  RateLimiterService.filterByRate() (LOCAL Guava)
        permit available:
           MailingService.sendMail(renderContext):
              Thymeleaf process(subjectTemplate)/process(bodyTemplate) ─▶ rendered subject + body (TEXT, unchanged)
              build MailContent(subject, body, replyTo=mailConfig.replyToEmailAddress)   [X-G7]
              EmailService.sendEmail(mailConfig.senderEmailAddress, [recipientEmailId], MailContent)
                 ─▶ SesV2Client.sendEmail (Destination/Content, Reply-To header) — retry=none ─▶ messageId
           EventLogger.logCloseRunEvent(success, tokens={messageId})
        rate exceeded:
           EventLogger.logCloseRunEvent(success, tokens={messageDropped=true})
 7.  deleteMessage on any non-throwing path
 8.  exception thrown anywhere above:
        appianway-commons ErrorHandler.handleException(message, metaData, tokens={PICK_UP_QUEUE}, ex)
           recoverable, under retry budget ─▶ return to pickup queue
           recoverable, exhausted        ─▶ send to DLQ
           non-recoverable               ─▶ write failure Annotations (StorageClient, write) + publish to inttra_int_sqs_subscription_errors
        EventLogger.logCloseRunEvent (failure/retry)
```

---

## 5. Configuration changes

### 5.1 Property-key table (exact INT values)

All keys/values are **unchanged by this migration** — the substitution *mechanism* changes (§5.3), not the environment contract.

| YAML key | `${...}` placeholder | INT value |
|---|---|---|
| `componentName` | `${componentName:-email-sender}` | `email-sender` |
| `environment` | `${email-sender.environment}` | `int` |
| `sqsPickupConfig.queueUrl` | `${email-sender.pickupSQSConfig.queueUrl}` | `.../inttra_int_sqs_email_outbound` |
| `sqsPickupConfig.waitTimeSeconds` | `${...:-20}` | **20** (default) |
| `sqsPickupConfig.maxNumberOfMessages` | `${...:-1}` | **1** (default) |
| `snsEventConfig.topicArn` | `${email-sender.snsEventConfig.topicArn}` | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` |
| `s3WorkspaceConfig.bucket` | `${email-sender.s3WorkspaceConfig.bucket}` | `inttra-int-workspace` |
| `sqsErrorConfig.queueUrl` | `${email-sender.sqsErrorConfig.queueUrl}` | `.../inttra_int_sqs_subscription_errors` |
| `mailConfig.senderEmailAddress` | `${email-sender.mailConfig.senderEmailAddress}` | `"INTTRA" no-reply@appianway-alpha.inttra.com` |
| `mailConfig.replyToEmailAddress` | `${email-sender.mailConfig.replyToEmailAddress}` | `no-reply@appianway-alpha.inttra.com` |
| `mailConfig.rateLimitInSeconds` | `${...:-120}` | **120** (default) |
| `server.connector.port` | `${server.connector.port:-8081}` | **8081** (default) |
| `logging.level` | `${email-sender.logging.level:-INFO}` | **INFO** (default) |
| `metrics.frequency` | `${metrics.frequency}` | from `datadog.properties` |

**No queue/topic/bucket names are renamed** — a client-rebind only.

### 5.2 SSM parameters — NONE

email-sender's yaml has **no `networkServiceConfig` block**, so it makes **no runtime SSM call** and needs **no `${awsps:/path}` boot-time substitution**. `network-services.properties` is still passed on the CLI (matching the shared convention), but nothing in `email-sender.yaml` references its keys. **Zero SSM/`CloudParameterStore` wiring.** AWS creds resolve purely through the default credential chain (SSO profile locally; task/instance role in deployed environments).

### 5.3 Config-command composition

```
classpath email-sender.yaml (template)
    │
    ▼
[ appianway property subst ]  ${key} from email-sender.properties + network-services.properties (unused) + datadog.properties + env
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]  (no-op — no ${awsps:} tokens in email-sender.yaml)
    │
    ▼
Dropwizard Configuration factory (EmailSenderConfiguration)
```

`ParameterStoreConfigTransform` is composed **for consistency** with the other 13 modules (single shared `ConfigProcessingServerCommand` wiring in `appianway-commons`), even though it is a pass-through no-op here — email-sender's yaml carries zero `${awsps:...}` placeholders, and none should be introduced.

### 5.4 Run profiles

**Single profile — no ce-/os- variants.** CLI shape unchanged:

```
run  email-sender.yaml  conf/int/email-sender.properties  ../configuration/int/network-services.properties  ../configuration/int/datadog.properties
```

`-DCONFIG_REGION=US_EAST_1` unchanged. `CONFIG_LOCATION=s3` (→ `S3ConfigurationProvider`) is supported in code but **not set at INT**.

### 5.5 What is unchanged

CLI arg shape and order; `CONFIG_REGION`; `datadog.properties`; `S3ConfigurationProvider` conditional install (kept appianway-local, dead-if-unused); all `${key:-default}` fallback values; port **8081**; no `networkServiceConfig`.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap ID | Applies? | Detail |
|---|---|---|
| **X-G7 (headline)** | **YES — the module's one required cloud-sdk dependency** | `MailingService.sendMail` sets `replyToAddresses` on every outbound email today from `mailConfig.replyToEmailAddress`. cloud-sdk-api's `MailContent`/`EmailService.sendEmail` expose **subject/html/text/attachments only — no reply-to field**. **Assumed done:** an additive `replyTo` field + builder setter on `MailContent`, mapped by `SesEmailServiceImpl` to SES v2 `replyToAddresses`. **Fallback if not delivered:** compose the Reply-To header locally against the underlying `SesV2Client` that `cloud-sdk-aws` already builds, rather than blocking the whole module migration. Contingency only — the additive `MailContent.replyTo` path is preferred and is what §2 assumes. |
| **G5 (Thymeleaf/TemplateService) — explicitly NOT adopted** | De-scoped | cloud-sdk-api has a Handlebars `TemplateService`, but email-sender **does not use it**. Forcing Thymeleaf into cloud-sdk-aws would push a heavy transitive dependency onto **every** mercury-services consumer of `EmailService` — a violation of the additive/zero-impact contract. Thymeleaf (`TemplateMode.TEXT`) stays **local, unchanged**; only the pre-rendered subject/body strings cross into `MailContent`. |
| **S-G2** | Not applicable | email-sender's only S3 verb is `getContent` (read) — no put/copy, so the metadata/content-type overloads are irrelevant. |
| **W-G9** | Applies indirectly | consumes `MetaData` (`RECIPIENT_EMAIL_ID` projection) + `Annotations` produced upstream, and produces its own close-run `Event`s. Doesn't hit the `Event.Builder` annotations defect directly (doesn't round-trip `Event.annotations`), but shares the wire model with every upstream producer — gate this module's migration behind the W-G9 JSON round-trip corpus test passing for the whole program. |
| **X-G8 / C-G6 / O-G1 / O-G3** | Not applicable | ingestor-only (X-G8, Jest signing) and program-wide optional conveniences — email-sender needs none; it keeps `AsyncDispatcher`/`AbstractTask` (appianway-commons) and composes config transforms the standard way. |

**Moves to `appianway-commons`:** `AsyncDispatcher`, `AbstractTask`/`TaskFactory` lifecycle (single-listener, semaphore-bounded worker model — `maxNumberOfMessages` still doubles as thread-pool width); `ErrorHandler`/`RecoverableException`/`EmailSenderErrorHandler`'s error-code map pattern; the `InboundSqsHealthCheck`/`SnsPublishHealthCheck` wrappers re-pointed to the injected `MessagingClient`/`NotificationService`; the appianway property-substitution transform.

**Stays fully local (neither commons nor cloud-sdk):** Thymeleaf `TemplateEngine`, `RateLimiterService` (Guava `RateLimiter`), `ContentLoaderService`'s hard-coded `Annotations.class`/`"content"` mapping, `MailTemplateResolver`/`ErrorSubjectResolver`/`ErrorBodyResolver` strategy chain, `MailConfig`/`EmailSenderConfiguration` POJOs.

---

## 7. Maven dependency changes

**Remove:** `com.inttra.mercury.shared:mercury-shared`; `com.amazonaws:aws-java-sdk-sqs`; `com.amazonaws:aws-java-sdk-ses` (no `-s3`/`-sns` declared directly in this pom — those came transitively via `shared` and disappear with it).

**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK **v2** (`sesv2`, `sqs`, `s3`, `sns`) arrives transitively via `cloud-sdk-aws`'s BOM — do **not** declare v2 artifacts directly.

**Keep unchanged:** `org.thymeleaf:thymeleaf` (3.0.7.RELEASE), plus `dropwizard-core`, `metrics-annotation`, `guice`, `metrics-guice`, `guava`, `lombok` — all DW5-aligned by the ION-16098 baseline.

**Test scope:** keep `functional-testing` (test) — but it must land its cloud-sdk-api-backed `EmailService` fake first (replacing the v1 `AmazonSESAdaptor`) before email-sender's functional tests re-point. Add `dropwizard-testing` for JUnit 5; keep `junit-vintage-engine` during transition. Keep `mockito-core`, `junit`, `assertj-core`.

**Shade/verify:** `maven-shade-plugin` output must show zero leftover `com.amazonaws.*`/v1 classes and no `META-INF/services` clashes against `software.amazon.awssdk:*`/`apache-client`. Run `mvn -pl email-sender -am clean verify` (clean is required — stale shaded fat jars otherwise).

---

## 8. Tests

- **New tests in JUnit 5.** Existing JUnit 4 runs via `junit-vintage-engine` until rewritten.
- **Re-point `MailingServiceTest`** from the v1 SES model (`SendEmailRequest`/`Destination`/`Message`) to `EmailService`/`MailContent`; assert the field mapping from/to/subject/text-body/**reply-to**/message-id.
- **X-G7 contract test:** a field-mapping test that fails loudly if `MailContent` has no reply-to accessor — the canary for the assumed cloud-sdk change; keep it red until X-G7 lands, then green with no other code change.
- **Preserve Thymeleaf tests unchanged in intent:** `PropertyPlaceholdersResolverTest` keeps asserting local `TemplateMode.TEXT` rendering; only the return type changes (rendered `String`s instead of a v1 `simpleemail.model.Message`).
- **Retry=none test:** assert the cloud-sdk-aws SES client is built with `ClientOverrideConfiguration` retry policy = none (preserves `maxErrorRetry(0)`).
- **SQS DTO tests:** `EmailSenderTaskTest` re-pointed from `com.amazonaws.services.sqs.model.Message` to `QueueMessage[String]`.
- **Rate-limiter test** retained unchanged — local Guava `RateLimiter`, no cloud-sdk involvement.
- **`functional-testing` SES fake — hard prerequisite:** the existing `AmazonSESAdaptor` (implements v1 `AmazonSimpleEmailService`) must be reworked to back the **cloud-sdk-api `EmailService`** fake, including a reply-to assertion hook once X-G7 lands; SQS/S3/SNS fakes re-pointed in the same functional-testing wave.
- **W-G9 round-trip coverage:** contribute a representative `MetaData` + `Annotations` JSON fixture (as consumed from `getOriginalEvent`/`getContents`) to the program-wide W-G9 corpus test to confirm no silent field loss on the read side.

---

## 9. Rollout & verification

Per the program order, email-sender is in **wave 4** — after the S-G2 write/copy consumers (dispatcher, distributor, error-processor) and before transformer:

```
appianway-commons ─▶ functional-testing (incl. EmailService fake)
   ─▶ event-writer ─▶ distributor-rest, splitter, ingestor
   ─▶ dispatcher, distributor, error-processor
   ─▶ email-sender (X-G7 reply-to)   [this module]
   ─▶ transformer ─▶ watermill-publisher + 4 watermill consumers
```

Sequencing rationale: email-sender sits **downstream of error-processor** (which feeds its pickup queue) — migrating error-processor's `MetaData`/`Annotations` production first, and confirming W-G9 wire-compat, de-risks what email-sender reads.

**Gates:**
1. `mvn -pl email-sender -am clean verify` green.
2. INT boot (same CLI shape as §5.4): clean boot, Jetty 12.1.9 / Java 17, **no `AuthClient`/SSM call**; `GET /admin/opsHealthcheck` → **200** with exactly the same **2 checks** — inbound SQS (`inttra_int_sqs_email_outbound`) + SNS publish (`inttra_int_sns_event`), now resolved through the injected cloud-sdk `MessagingClient`/`NotificationService`. Confirm the still-not-probed set is unchanged (error SQS, S3 read, SES send remain config-resolved only).
3. A dev/INT smoke send: push one message through `inttra_int_sqs_email_outbound` and confirm (a) delivery, (b) rendered subject/body unchanged, (c) the **Reply-To header is present** on the received message (X-G7 proof), (d) no SDK-level retry on a simulated transient SES error.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **X-G7 (reply-to) not delivered / delivered with a different shape than assumed** | Contract test (§8) stays red until the field lands; documented fallback is to compose the Reply-To header locally against the underlying SES v2 client rather than blocking the module's migration indefinitely. This is customer-facing (trading-partner support replies) — do not silently drop it. |
| **`maxErrorRetry(0)` regression** — SDK-level retries silently re-enabled | Explicit retry=none test (§8); the app's own rate limiter + workflow-level retry (via `ErrorHandler`) is the only retry path that should exist. |
| **Accidentally pulling Thymeleaf into cloud-sdk (G5)** | Explicitly forbidden per §6 — Thymeleaf stays local; PR review should reject any `ThymeleafTemplateService` addition to cloud-sdk-aws. |
| **`functional-testing` SES fake not ready** | Gate the email-sender wave behind the fake landing (§9); do not hand-roll a throwaway fake in email-sender. |
| **Two-step S3 read (`getOriginalEvent` then `getContents`) breaks on cloud-sdk `StorageClient` error semantics** | `ContentLoaderService` is unchanged in shape; verify `StorageClient.getContent` throws an equivalent-enough exception type that the existing `catch (Exception ex)` in `EmailSenderTask.process` still routes to `ErrorHandler` correctly. |
| **W-G9 wire drift on `MetaData`/`Annotations` read side** | Gate behind the program-wide W-G9 round-trip corpus test; email-sender contributes a fixture from its own S3 reads. |
| **Do not accidentally introduce an SSM/AuthClient dependency this module never had** | §5.2 documents zero SSM usage; any PR that adds a `networkServiceConfig` block or `${awsps:...}` token to `email-sender.yaml` is a scope change, not routine. |
| **Rate limiter is per-process** (pre-existing, unrelated to this migration) | Unchanged — `RateLimiterService` stays local; horizontal scaling still multiplies effective throughput by replica count. Not introduced or worsened here. |
| **`MailDetails`/`MailContext` refactor ripples into template-resolver tests** | `PropertyPlaceholdersResolverTest`/`MailTemplateResolver` tests unaffected in intent — only the carrier type at the SES boundary changes, not the Thymeleaf contract. |
