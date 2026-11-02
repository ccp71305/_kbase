# WI01124532 error-processor — AWS SDK 2.x (cloud-sdk) Upgrade

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

`error-processor` is the AppianWay error fan-in. It consumes failure `MetaData` from its pickup queue (`sqsPickupConfig`), archives the raw message body in the bucket named by the incoming `MetaData` (`metaData.bucket`) under `{rootWorkflowId}/{uuid}`, sends one `MetaData` per configured `errorEmailRecipient` to the email queue (`dropOffSQSConfig`, consumed by `email-sender`), and publishes a `CLOSE_WORKFLOW` event.

This change moves the module onto `shared` re-based on `commons` / `cloud-sdk-api` / `cloud-sdk-aws` **1.0.38-SNAPSHOT** (AWS SDK 2.x). The module keeps using the `shared` listener, task, error-handler, workspace, SQS sender and event-publisher contracts; `shared` now implements them over cloud-sdk (contract C1–C9 in the shared design). Archived objects, queue messages and events are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `error-processor` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 shared (mercury-shared) re-base on commons design |

### Functional Requirements

1. Consume failure `MetaData` from the existing pickup queue and archive the received body verbatim (bucket from the incoming `MetaData`, key `{rootWorkflowId}/{uuid}`, UTF-8, `text/plain`).
2. For each comma-separated `errorEmailRecipient`, send a new `MetaData` to the email queue exactly as today: new `workflowId`, `parentWorkflowId` = incoming `workflowId`, same `rootWorkflowId` and `bucket`, `fileName` = archive key, `RECIPIENT_EMAIL_ID` projection added only when the incoming projections exist and lack it, exit status `success`, no message attributes, no delay.
3. Publish the same `CLOSE_WORKFLOW` event with the `dropOffQueue` / `pickUpQueue` tokens.
4. Keep the existing failure flow through `ErrorProcessorErrorHandler` (`shared` `ErrorHandler`, no module error codes, default code `/exception/error-processor/system/messagePipeline/systemException`).

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in `error-processor` sources.
2. Byte-for-byte compatibility of archived objects, queue messages and events (see Backwards Compatible).
3. Same listener back-pressure model (workers = `maxNumberOfMessages`, default 10; long poll default 20 s) and the same retry profile per client, including zero SDK retries for S3 and SNS.

### Acceptance Criteria

1. `mvn -pl error-processor -am clean verify` is green.
2. Golden-fixture tests prove the email-queue `MetaData` body and the `CLOSE_WORKFLOW` event JSON are byte-identical to the v1 build.
3. Functional test asserts the archived object's bucket, key, body and `Content-Type` (`text/plain`).
4. Adapter-level test asserts the S3 and SNS clients are built with zero retries.
5. INT boot; one failure message produces the same archive object, email-queue messages and event as before.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard 5.0.2, Guice 7 (versions as managed by commons) |
| Build | Maven, Java 17 |
| AWS SDK | AWS SDK 2.x via `shared` adapters over `cloud-sdk-api` / `cloud-sdk-aws` 1.0.38-SNAPSHOT (was AWS SDK v1 1.12.720) |
| Messaging | SQS (receive, send, delete), SNS (publish) |
| Storage | S3 (put) |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | The archive `Content-Type` stays `text/plain`; `application/json` would be a behaviour change | Open Issue | Resolved | Keep `text/plain` |
| 3 | Today the S3 and SNS clients use `new ClientConfiguration().withMaxErrorRetry(0)` (`ExternalServicesModule.java:20`), i.e. zero retries with SDK v1 default timeouts (connect 10 s, socket 50 s, no execution timeout), not the shared profile | Open Issue | Resolved | Zero retries is expressible: cloud-sdk configs take a `RetryStrategy` (`BaseAwsConfig.retryStrategy`). The current values are kept: the module passes `shared` client-profile overrides for S3 and SNS (retries 0, connect 10 s, socket 50 s, no API-call timeout), each with a code comment naming the v1 setting it reproduces |
| 4 | `ErrorDetailsService` has no caller | Assumption | Resolved | Retyped onto the v2 workspace adapter only; no removal in this change |
| 5 | Non-recoverable failures are sent to `sqsErrorConfig`, which `error-processor.yaml` sets to the module's own pickup queue. A failure that repeats on every attempt re-enters the pickup queue as a new message indefinitely | Open Issue | Resolved | Kept as is: existing configuration, not changed by this program (see Risks) |
| 6 | With several recipients, the first recipient is written into the shared incoming projections map (`ErrorProcessorTask.java:96-99`), so every email-queue message carries the first recipient's address | Open Issue | Resolved | Kept as is: existing behaviour is not changed by this program; a disabled known-defect test covers it |
| 7 | `InboundSqsHealthCheck` relies on `VisibilityTimeout=0`, which cloud-sdk receive does not send | Open Issue | Resolved | Resolved in `shared` (open issue 11): the probe uses `MessagingClient.getQueueAttributes` |

---

## High Level Design

### Architectural Overview (ext)

```
 error-processor pickup queue (SQS)
        │  receive(max = idle workers, wait = 20 s, attrs = [failedAttempts])
        ▼
 shared SQSListener (back-pressure, over MessagingClient<String>) ─▶ AsyncDispatcher
        │
        ▼
 ErrorProcessorTask
   ├─▶ shared workspace adapter putObject(metaData.bucket, rootWorkflowId/uuid, body)   (UTF-8, text/plain)
   ├─▶ shared SQS sender sendMessage(emailQueue, MetaData JSON)                          (one per recipient)
   └─▶ EventLogger ─▶ shared v2 SNS EventPublisher ─▶ event topic ([Event] JSON)
        │ failure
        ▼
 ErrorProcessorErrorHandler ─▶ recoverable: back to pickup queue (failedAttempts, DelaySeconds) or {pickup}_dlq
                            └▶ non-recoverable: errors to s3WorkspaceConfig bucket, failure MetaData to sqsErrorConfig
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Call cloud-sdk `StorageClient` / `MessagingClient` / `NotificationService` from the module | No adapter | Different S3 content type, JSON mapper risk, wire rules duplicated per module (violates C1) | ❌ |
| 2 | Keep calling the `shared` contracts, now backed by the v2 adapters | No change to module wire code; parity enforced in `shared` | Depends on the `shared` re-base | ✅ |

### Data Flow — Before vs After (ext)

**Before:** v1 `SQSListenerClient` → `shared` task on v1 `Message` → `shared` `Json` → `S3WorkspaceService.putObject(String)` / `SQSClient.sendMessage` / `SNSEventPublisher`.

**After:** `shared` back-pressure listener over `MessagingClient<String>` → same task on `QueueMessage<String>` → `shared` `Json` (unchanged) → `shared` workspace adapter `putObject(String)` (UTF-8, `text/plain`) / `shared` SQS sender / `shared` v2 SNS event publisher.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `ExternalServicesModule` | v1 `AmazonS3`, `AmazonSQS` (listener, sender) and `AmazonSNS` bindings removed; installs the `shared` v2 module with the S3 and SNS retry override (Open Issue 3). `Clock` binding kept |
| 2 | `ErrorProcessorModule` | Binds the `shared` v2 `SQSListener`, `AsyncDispatcher`, v2 workspace adapter as `WorkspaceService` and v2 `EventPublisher` on `snsEventConfig.topicArn` |
| 3 | `ErrorProcessorApplication` | `initialize()` registers the commons-based config command instead of `ConfigProcessingServerCommand`, and the v2 S3 bootstrap source provider; config files unchanged. Health checks unchanged in name and placement: `InboundSqsHealthCheck` and `S3ReadHealthCheck` (default + ops), `OutboundSqsHealthCheck` (email queue) and `SnsPublishHealthCheck` (ops only), now on the injected clients |
| 4 | `ErrorProcessorConfiguration` | Unchanged (`errorEmailRecipient`, `dropOffSQSConfig` + `BaseConfiguration`) |
| 5 | `ErrorProcessorTask` | v1 `Message` → `QueueMessage<String>`; workspace, SQS and event calls unchanged |
| 6 | `ErrorProcessorErrorHandler` | Extends the `shared` `ErrorHandler` (SDK-neutral signatures); no codes |
| 7 | `ErrorDetailsService` | Unchanged call `WorkspaceService.getContent(bucket, key)` |

#### Client Profile (ext)

| Role | Profile |
|------|---------|
| SQS listener | Shared profile: connect 1 s, socket 30 s, no API-call timeout, 3 retries, `AwsRetryCondition` |
| SQS sender | Shared profile: connect 1 s, socket 5 s, API-call timeout 10 s, 3 retries, `AwsRetryCondition` |
| S3, SNS | Override (Open Issue 3): zero retries, connect 10 s, socket 50 s, no API-call timeout — today's values |

All clients: 50 max connections, one instance per role, closed by the Dropwizard lifecycle.

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive; send to email queue (no attributes, no delay); retry send to pickup queue (`failedAttempts`, `DelaySeconds`); send to DLQ / errors queue; delete | AWS SDK 2.x via `shared` / cloud-sdk |
| S3 | `PutObject` archive (`text/plain`, UTF-8, no user metadata); error annotations on failure | AWS SDK 2.x via `shared` / cloud-sdk |
| SNS | Publish `CLOSE_WORKFLOW` events (raw JSON array, no subject or attributes) | AWS SDK 2.x via `shared` / cloud-sdk |

#### DynamoDB Changes (ext)

None.

### UI

N/A

### API Architecture

N/A — no API added or changed. Only the existing Dropwizard health/admin endpoints, unchanged.

---

## Configuration

### Component-Level Configuration

`ErrorProcessorApplication.initialize()` registers the commons-based config command instead of the `shared` one; `conf/error-processor.yaml` keys and `.properties` files are unchanged apart from the logger entry below.

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

Module log messages and levels are unchanged. `error-processor.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs each S3 put at INFO), as the shared design requires.

### Event Publishing (ext)

Unchanged: `CLOSE_WORKFLOW` on success and failure, same tokens, same topic, raw JSON array body via `shared` `Json`, no subject or message attributes. A publish failure is logged and swallowed by the publisher (`SNS_Failed_AFTER_RETRY`), as today.

---

## Metrics and Statistics

No change (`messages-processed`, `messages-failed`).

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
| Other file migration | No | Archived objects unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change: same queues, archive objects, email-queue messages and events.

### Performance (ext)

Per message: one S3 put, one SQS send per recipient, one SNS publish, all sequential; at most 10 workers against 50-connection pools. Zero SDK retries for S3/SNS means a transient error goes straight to the queue-level retry (delay `2^n × 10` s).

### Deployment (ext)

Rolling restart as part of the single AppianWay release. No data migration. A single service can be rolled back to its previous build alone, because formats are unchanged.

---

## Resiliency

- S3 or SQS send failure: adapter raises `RecoverableException` (C9) → message re-sent to the pickup queue with `failedAttempts` and `DelaySeconds = 2^n × 10`; after 5 attempts it goes to `{pickupQueue}_dlq` — as today.
- SNS failure: logged and swallowed; never triggers a retry — as today.
- Other failures: non-recoverable path to `sqsErrorConfig` (Open Issue 5).
- Body that is not valid `MetaData` JSON: thrown before the handler (`ErrorProcessorTask.java:59`), so the message is not deleted and is redelivered by the queue.
- Redelivery is not idempotent: each retry writes a new archive object (new UUID) and re-sends email-queue messages for recipients already sent. Existing behaviour; `email-sender`'s rate limiter limits the duplicate emails.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files. Archive objects are kept as today (bucket lifecycle unchanged).

---

## Impact on Tools

None.

---

## Impact on Other Components

- `email-sender`: None — email-queue messages and archive objects are byte-identical.
- Event consumers (`event-writer`): None — events unchanged.
- The ops write health checks send the literal `HEALTHCHECK` to the email queue and the event topic, which their consumers log as parse failures — existing behaviour, unchanged.

---

## Backwards Compatible

**Yes.**

| Question | Answer |
|----------|--------|
| Archive object body / key | Identical — received body stored verbatim, UTF-8, same bucket and key |
| Archive `Content-Type` / metadata | Identical — `text/plain`, no user metadata |
| Email-queue message | Identical — same `MetaData` via `shared` `Json`, no attributes, no delay |
| Events | Identical — same `Event` JSON array, same tokens |
| Failure flow / error code | Identical |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:mercury-shared` | 1.0 | 1.0 (re-based on commons) | Upgrade | Brings `commons`, `cloud-sdk-api`, `cloud-sdk-aws` 1.0.38-SNAPSHOT and AWS SDK 2.x transitively |
| `com.amazonaws:aws-java-sdk-sqs` (direct) | 1.12.720 | removed | Removal | No direct SDK use left in the module |

Other versions come from the root pom aligned with commons.

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `ErrorProcessorTaskTest` (extended) | Archive bucket/key and verbatim body; one message per recipient; workflow ids; `RECIPIENT_EMAIL_ID` behaviour as today |
| 2 | `ErrorProcessorWireCompatibilityTest` | Golden fixtures: email-queue `MetaData` and `CLOSE_WORKFLOW` event byte-identical to v1 output |
| 3 | `ErrorProcessorTaskTest` (failure) | Storage/queue failure → recoverable path; other failure → non-recoverable path with the default code |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Task | `ErrorProcessorTaskTest` | Unit, mocked `shared` contracts |
| End-to-end | `ErrorProcessorFuncTest` | `functional-testing` cloud-sdk fakes |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT boot; post one failure `MetaData` | Same archive object, email-queue messages and event as the v1 build |

### Existing Test Impact (ext)

`ErrorProcessorTaskTest` and `ErrorProcessorFuncTest` are retargeted from v1 `Message` and v1 fakes to `QueueMessage<String>` and cloud-sdk fakes; assertions on content are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: with several recipients each email-queue message carries its own recipient. The self-referencing `sqsErrorConfig` is configuration, not code, and is recorded in Risks only.

---

## Risks

**Key Risks**

- JSON output drift — mitigated by `shared` `Json` and golden fixtures.
- Retry drift: the shared profile would give S3 3 retries and SNS 2; the module needs the zero-retry override (Open Issue 3), asserted by test.
- Self-feeding error loop and duplicate side effects on redelivery (Open Issue 5, Resiliency) — existing behaviour, not changed by the migration.
- Wrong recipient with multiple recipients (Open Issue 6) — existing defect.

---

## Dependencies

**Major Dependencies**

- `shared` re-base (adapters, listener, health checks, commons config command, per-module retry override).
- `mercury-services-commons` 1.0.38-SNAPSHOT.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | N | No UI |
| 2 | Use of new services/ports | N | Same AWS services and resources; same ports |
| 3 | Authentication changes | N | AWS credentials from the default provider chain / task role, as today |
| 4 | New/changed encryption | N | No change; TLS to AWS endpoints |
| 5 | Changes in the way data is transmitted | Y | AWS client library changes from SDK v1 to SDK 2.x. Endpoints, credentials and payloads unchanged |
| 6 | Changes in the way/location data is being stored | N | Same bucket, keys, body and headers |
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
