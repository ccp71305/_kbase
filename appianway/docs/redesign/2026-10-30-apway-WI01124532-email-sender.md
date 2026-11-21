# WI01124532 email-sender — AWS SDK 2.x (cloud-sdk) Upgrade

## Contents

<!-- info macro + TOC macro -->

---

## Contributors

| Role | Name |
|------|------|
| Author | @Arijit Kundu |
| Implementation | @Arijit Kundu |
| Jira Assignee | @Arijit Kundu |
| Product Owner | @Mahendran Pandian |

---

## Summary

`email-sender` consumes `MetaData` from the email queue (`sqsPickupConfig`, fed by `error-processor`). For each message it reads the archived failure `MetaData` at the message's `bucket` / `fileName`, then the error `Annotations` at that `MetaData`'s `bucket` / `fileName`, renders the subject and body with Thymeleaf TEXT templates, sends one plain-text email through SES when the rate limiter allows it, and publishes a `CLOSE` event carrying the SES message id (or `messageDropped=true` when rate-limited).

This change moves the module onto `shared` re-based on `commons` / `cloud-sdk-api` / `cloud-sdk-aws` **1.0.38-SNAPSHOT** (AWS SDK 2.x). SQS, SNS and workspace S3 go through the `shared` adapters (contract C1–C9 in the shared design); SES moves to the commons `EmailService` (SESv2 API). Email content, sender, recipient, reply-to and events are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `email-sender` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 shared (mercury-shared) re-base on commons design |

### Functional Requirements

1. Consume from the existing email queue with the same concurrency (`maxNumberOfMessages` default 1, so one worker) and long poll (default 20 s).
2. Read both workspace objects with `WorkspaceService.getContent(bucket, key)` and parse them with `shared` `Json`.
3. Render subject and body with the same Thymeleaf templates in TEXT mode.
4. Send via SES with the same From (`mailConfig.senderEmailAddress`, display-name form allowed), To (the `RECIPIENT_EMAIL_ID` projection), Reply-To (`mailConfig.replyToEmailAddress`), subject and text body; no HTML part, no attachments, no charset set (as today).
5. Keep the rate limiter (one email per `rateLimitInSeconds`, default 120 s, per instance; drop when limited) and the `CLOSE` event with null sub-type and the `messageId` / `messageDropped` token.
6. Keep the failure flow (`EmailSenderErrorHandler` → `shared` `ErrorHandler`) and the three error codes.

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in `email-sender` sources.
2. Byte-for-byte compatibility of events and email content (see Backwards Compatible).
3. SES client: zero SDK retries and the region from the environment, as today (v1 `withMaxErrorRetry(0)`, default region chain).

### Acceptance Criteria

1. `mvn -pl email-sender -am clean verify` is green.
2. Golden-fixture tests prove the `CLOSE` event JSON (sent and dropped variants) is byte-identical to the v1 build.
3. Unit test asserts the SES request: From, To, Reply-To, subject, text body, no HTML part; message id returned.
4. Test asserts the SES client is built with zero retries.
5. INT boot; one email-queue message produces the same email and the same event as before.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard 5.0.2, Guice 7 (versions as managed by commons) |
| Build | Maven, Java 17 |
| AWS SDK | AWS SDK 2.x via `shared` adapters and commons `EmailService` (`cloud-sdk-api` / `cloud-sdk-aws` 1.0.38-SNAPSHOT); was AWS SDK v1 1.12.720 |
| Messaging | SQS (receive, send, delete), SNS (publish) |
| Storage | S3 (read) |
| Email | SES (SESv2 API), Thymeleaf templates |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | cloud-sdk `EmailService.sendEmail` returns `void` (`SesEmailServiceImpl` discards the response); the `CLOSE` event needs the SES message id | Open Issue | Open | U8: additive commons change returning the message id (`EmailSendResult` already exists in `cloud-sdk-api`). No interface-only fallback (a module-local SES client is not allowed, `shared` open issue 14), so U8 must be in a commons release before this release |
| 3 | cloud-sdk `EmailClientFactory` does not apply a retry strategy (SDK standard retries, 3 attempts) and sets a 10 s API-call and attempt timeout by default; `createDefaultSesClient` fixes the region to us-east-1 | Open Issue | Open | U9: additive commons change to honour a configured `RetryStrategy`. Region taken from the environment via `createSesClient(config)`. Must be in a commons release before this release, with item 2 |
| 4 | Exception mapping: v1 wrapped every SES `SdkClientException` (service errors included) in `RecoverableException`. cloud-sdk wraps send errors in `SendEmailException`, but throws `IllegalArgumentException` before the call for a blank From or subject or an empty To list | Assumption | Resolved | `MailingService` maps both to `RecoverableException`, matching v1, where SES rejected those requests as service errors |
| 5 | `EmailNotSendException` is mapped to an error code but never thrown | Assumption | Resolved | Unchanged |
| 6 | `InboundSqsHealthCheck` relies on `VisibilityTimeout=0`, which cloud-sdk receive does not send | Open Issue | Resolved | Resolved in `shared` (open issue 11): the probe uses `MessagingClient.getQueueAttributes` |

---

## High Level Design

### Architectural Overview (ext)

```
 email queue (SQS)
        │  receive(max = idle workers (1), wait = 20 s, attrs = [failedAttempts])
        ▼
 shared SQSListener (back-pressure, over MessagingClient<String>) ─▶ AsyncDispatcher
        │
        ▼
 EmailSenderTask
   ├─▶ ContentLoaderService ─▶ shared workspace adapter getContent(bucket, key)  x2 (MetaData, Annotations)
   ├─▶ RateLimiterService ── limited ─▶ CLOSE event (messageDropped=true)
   ├─▶ MailingService ─▶ MailTemplateResolver (Thymeleaf TEXT) ─▶ commons EmailService (SESv2 SendEmail)
   └─▶ EventLogger ─▶ shared v2 SNS EventPublisher ─▶ event topic ([Event] JSON)
        │ failure
        ▼
 EmailSenderErrorHandler ─▶ recoverable: back to pickup queue (failedAttempts, DelaySeconds) or {pickup}_dlq
                         └▶ non-recoverable: errors to s3WorkspaceConfig bucket, failure MetaData to sqsErrorConfig
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | commons `EmailService` as-is | No new code | No message id; SDK default retries can send duplicate emails | ❌ |
| 2 | commons `EmailService` after the additive changes in Open Issues 2–3 | Tier 1 SES from commons, as in mercury-services | Depends on a commons release | ✅ |
| 3 | Module-local SESv2 send with zero retries | No commons dependency | Second SES path to maintain; builds an SDK client directly, which the AWS SDK boundary forbids | ❌ |

### Data Flow — Before vs After (ext)

**Before:** v1 `SQSListenerClient` → `S3WorkspaceService.getContent` → Thymeleaf → v1 `AmazonSimpleEmailService.sendEmail` → `SNSEventPublisher`.

**After:** `shared` back-pressure listener over `MessagingClient<String>` → `shared` workspace adapter `getContent` (UTF-8, line-joining kept) → Thymeleaf (unchanged) → commons `EmailService` (SESv2 simple content, same fields) → `shared` v2 SNS event publisher.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `ExternalServicesModule` | v1 `AmazonSQS`, `AmazonS3`, `AmazonSNS` and `AmazonSimpleEmailService` bindings removed; installs the `shared` v2 module and binds the commons `EmailService` (zero retries, environment region). `Clock` binding kept |
| 2 | `EmailSenderModule` | Binds the `shared` v2 `SQSListener`, `AsyncDispatcher`, v2 workspace adapter and v2 `EventPublisher`; Thymeleaf engine and resolvers unchanged |
| 3 | `EmailSenderApplication` | `initialize()` registers the commons-based config command instead of `ConfigProcessingServerCommand`, and the v2 S3 bootstrap source provider; config files unchanged. Health checks unchanged: `InboundSqsHealthCheck` (default + ops), `SnsPublishHealthCheck` (ops only), on the injected clients |
| 4 | `EmailSenderConfiguration`, `MailConfig` | Unchanged |
| 5 | `ContentLoaderService` | Unchanged call `WorkspaceService.getContent(bucket, key)` |
| 6 | `MailingService` | Builds `MailContent` (subject, text body, reply-to) and calls `EmailService` with the same From and To; returns the message id; maps `SendEmailException` and `IllegalArgumentException` to `RecoverableException`. `MailDetails`, `PlaceholdersResolver` and `PropertyPlaceholdersResolver` stop using the v1 SES `Message` / `Content` / `Body` model types and carry plain subject and body strings |
| 7 | `EmailSenderTask` | v1 `Message` → `QueueMessage<String>`; rate limiter and tokens unchanged |
| 8 | `EmailSenderErrorHandler` | Extends the `shared` `ErrorHandler` (SDK-neutral signatures); codes unchanged |
| 9 | `MailTemplateResolver`, subject/body resolvers, `RateLimiterService` | Unchanged |

#### Client Profile (ext)

| Role | Profile |
|------|---------|
| SQS listener, SQS sender, S3, SNS | Shared profile (C3): connect 1 s; socket 30 s listener, 5 s others; API-call timeout 10 s for sender and SNS, none for S3 and listener; retries 3 (SNS 2); `AwsRetryCondition` |
| SES | Zero retries, environment region (Open Issue 3); 10 s API-call timeout (cloud-sdk default; v1 had none) |

All clients: one instance per role, closed by the Dropwizard lifecycle.

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive; retry send to pickup queue (`failedAttempts`, `DelaySeconds`); send to DLQ / errors queue; delete | AWS SDK 2.x via `shared` / cloud-sdk |
| S3 | `GetObject` x2 per message (small JSON documents); error annotations on failure | AWS SDK 2.x via `shared` / cloud-sdk |
| SES | `SendEmail` (SESv2 API, simple content) | AWS SDK 2.x via commons `EmailService` |
| SNS | Publish `CLOSE` events | AWS SDK 2.x via `shared` / cloud-sdk |

#### DynamoDB Changes (ext)

None.

### UI

N/A

### API Architecture

N/A — no API added or changed. Only the existing Dropwizard health/admin endpoints, unchanged.

---

## Configuration

### Component-Level Configuration

`EmailSenderApplication.initialize()` registers the commons-based config command instead of the `shared` one; `conf/email-sender.yaml` keys (including `mailConfig`) and `.properties` files are unchanged apart from the logger entry below.

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change. SESv2 `SendEmail` is authorised by the same `ses:SendEmail` IAM action on the same identity; confirmed on INT boot.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

Module log messages and levels are unchanged. `email-sender.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs S3 reads at INFO), as the shared design requires.

### Event Publishing (ext)

Unchanged: `CLOSE` event with null sub-type and `messageId=<SES id>` or `messageDropped=true`; same topic, raw JSON array body via `shared` `Json`, no subject or message attributes. A publish failure is logged and swallowed, as today.

---

## Metrics and Statistics

No change.

---

## Installer Changes

None. Same shaded jar, same start command.

---

## Impact on Current Application

### Migration Required

| Area | Needed? | Details |
|------|---------|---------|
| Database schema | No | No DynamoDB use |
| Property migration | No | Config keys unchanged |
| Other file migration | No | Templates unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change: same email content and headers, same rate limit, same events. Workspace reads now decode as UTF-8 explicitly; today `getContent(bucket, key)` uses the JVM default charset, so output differs only for non-ASCII content on a host whose default charset is not UTF-8.

### Performance (ext)

One worker; throughput is bounded by the rate limiter (one email per 120 s per instance by default). Both S3 reads happen before the rate check, so dropped messages still cost two reads.

### Deployment (ext)

Rolling restart as part of the single AppianWay release. No data migration. A single service can be rolled back to its previous build alone, because formats are unchanged.

---

## Resiliency

- SES, S3 read or SQS send failure → `RecoverableException` → re-sent to the pickup queue with `failedAttempts` and `DelaySeconds = 2^n × 10`; after 5 attempts to `{pickupQueue}_dlq` — as today. A missing workspace key is recoverable, as today.
- Template failures → existing non-recoverable codes; failure `MetaData` goes to `sqsErrorConfig` (configured as `error-processor`'s pickup queue), as today.
- SES keeps zero SDK retries so a timed-out but accepted send is not repeated by the SDK. A redelivery after a successful send (for example a failed delete) still sends the email again, as today.
- Rate-limited messages are dropped (deleted with `messageDropped=true`), as today.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files.

---

## Impact on Tools

None.

---

## Impact on Other Components

- `error-processor`: None — input contract unchanged.
- Event consumers (`event-writer`): None — events unchanged.
- Email recipients: None — same sender, reply-to, subject and body.

---

## Backwards Compatible

**Yes.**

| Question | Answer |
|----------|--------|
| Email From / To / Reply-To | Identical |
| Subject / body | Identical — same templates, text body only, no HTML part, no attachments |
| Events | Identical — same `Event` JSON array, null sub-type, same tokens |
| S3 reads | Same objects; `shared` `Json`; UTF-8 decoding (see Runtime Behavior) |
| Error codes / failure flow | Identical |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:mercury-shared` | 1.0 | 1.0 (re-based on commons) | Upgrade | Brings `commons`, `cloud-sdk-api`, `cloud-sdk-aws` 1.0.38-SNAPSHOT and AWS SDK 2.x (incl. SESv2) transitively |
| `com.amazonaws:aws-java-sdk-sqs`, `aws-java-sdk-ses` (direct) | 1.12.720 | removed | Removal | Replaced by `shared` adapters and commons `EmailService` |

Thymeleaf is unchanged; other versions come from the root pom aligned with commons.

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `MailingServiceTest` (extended) | `EmailService` call: From, To, Reply-To, subject, text body, no HTML; message id returned; `SendEmailException` / `IllegalArgumentException` → `RecoverableException` |
| 2 | `EmailSenderWireCompatibilityTest` | Golden fixtures: `CLOSE` event (sent and dropped) byte-identical to v1 output |
| 3 | `EmailSenderTaskTest` (extended) | Both workspace reads and parse; rate-limited drop; error codes |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Service | `MailingServiceTest`, `PropertyPlaceholdersResolverTest` | Unit, mocked `EmailService` |
| Task | `EmailSenderTaskTest` | Unit, rate limiter and error codes |
| End-to-end | `EmailSenderFuncTest` | `functional-testing` cloud-sdk fakes plus an `EmailService` fake |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT boot; post one email-queue message | Same email received; same event as the v1 build |

### Existing Test Impact (ext)

Existing tests are retargeted from v1 `Message`, v1 SES model types and v1 fakes to `QueueMessage<String>`, `MailContent` and cloud-sdk fakes; assertions on content are kept.

---

## Risks

**Key Risks**

- Loss of the SES message id token (cloud-sdk returns `void`) — Open Issue 2; no release without it.
- Duplicate emails from SDK default retries plus the 10 s attempt timeout — mitigated by the zero-retry SES client (Open Issue 3), asserted by test.
- Exception classification drift — mitigated by mapping `SendEmailException` and `IllegalArgumentException` to `RecoverableException`.
- JSON output drift — mitigated by `shared` `Json` and golden fixtures.

---

## Dependencies

**Major Dependencies**

- `shared` re-base (adapters, listener, health checks, commons config command).
- `mercury-services-commons` 1.0.38-SNAPSHOT, plus the SES changes U8–U9 (Open Issues 2–3), which must be in a commons release before this release.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | N | No UI |
| 2 | Use of new services/ports | N | Same AWS services and resources; same ports |
| 3 | Authentication changes | N | AWS credentials from the default provider chain / task role, as today |
| 4 | New/changed encryption | N | No change; TLS to AWS endpoints |
| 5 | Changes in the way data is transmitted | Y | AWS client library changes from SDK v1 to SDK 2.x; SES moves from the v1 SES API to the SESv2 API. Endpoints, credentials, sender identity and email content unchanged |
| 6 | Changes in the way/location data is being stored | N | No data stored |
| 120 | New API implementation / change of existing APIs (Please fill the API arch table) | N | None |
| 124 | New / Change in existing file upload functionality | N | None |
| 125 | New / Change in integration within e2open or third-party apps | N | None |
| 126 | New / Existing UI functionality support querying via either of them (VST, XML, java expressions, SQL or any other) | N | None |

---

## REQUIRED: Documentation Changes

| Question | Answer |
|----------|--------|
| Do end users interact with this feature? | No |
| Do project teams/SIs/BIT teams need to enable or configure this feature? | No |
| Does the feature require special migration from prior releases? | No |
| What guides or content sections need updating? | None |

---

## Blocking Issues and Actions from the Design Review

| # | Issue/Action | Owner | Status | Due Date | Resolution |
|---|-------------|-------|--------|----------|------------|
| 1 | | | Open | | |

---

## Design Document Review and Approval Matrix

> Add **"Approved"** or **"NA"** in the status column to approve the design document.
> **Approval Status Should have "Approved" or "NA" Only**

| Stage | Reviewer | Status | Notes | Ownership |
|-------|----------|--------|-------|-----------|
| Design | @Arijit Kundu | | | **Product Management** |
| Product Owner | @Mahendran Pandian | | | **Product Owner** |
| Pre Dev Security | @Kamalesh Bhol | | | **InfoSec** |
| Pre Dev Architecture | @Arijit Kundu | | | **Product Development** |
| Browser | NA | NA | | **Product Development** |
| UX | NA | NA | | **Product Development** |
| Post Dev Security | @Kamalesh Bhol | | | **InfoSec** |
| Post Dev Architecture | | | | **Product Development** |
| QA/Test Driven Development (TDD) | @Venkat Ganga | | | **Product Development/QA** |
