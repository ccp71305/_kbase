# WI01124532 event-writer — AWS SDK 2.x (cloud-sdk) Upgrade

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

`event-writer` is the AppianWay audit sink. It consumes workflow lifecycle events from its SQS pickup queue and stores each `Event` as JSON in the configured bucket (`s3Config.bucket`) under `{s3EventStorePath}/{yyyy-MM-dd of event timestamp}/{rootWorkflowId}/{component}-{type}-{eventId}.json`.

This change moves the module onto `shared` re-based on `commons` / `cloud-sdk-api` / `cloud-sdk-aws` **1.0.38-SNAPSHOT** (AWS SDK 2.x). The module keeps using the `shared` listener, task and workspace contracts; `shared` now implements them over cloud-sdk (see the shared design, contract C1–C9). Stored objects, keys, bodies and S3 headers are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `event-writer` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 shared (mercury-shared) re-base on commons design |

### Functional Requirements

1. Consume events from the existing pickup queue and write each event to S3 exactly as today (same bucket, key layout, body).
2. Accept both message shapes received today: a raw JSON array of `Event`, and an SNS notification envelope (`shared` `SNSNotification`) whose `Message` holds that array.
3. Keep the existing failure behaviour: a message whose events cannot be parsed or stored is logged and then deleted (the handler swallows the exception, `S3StoringMessageHandler.java:49`).

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in `event-writer` sources.
2. Byte-for-byte compatibility of stored objects (see Backwards Compatible).
3. Same listener back-pressure model: worker threads = `pickupSqsConfig.maxNumberOfMessages` (default 10), each receive asks for at most the idle-worker count, long poll `waitTimeSeconds` (default 20 s).

### Acceptance Criteria

1. `mvn -pl event-writer -am clean verify` is green.
2. Golden-fixture test proves the stored JSON for representative events (with and without annotations, tokens, null/empty fields) is byte-identical to the v1 build.
3. Functional test asserts the stored object's key, `Content-Type: text/plain` and UTF-8 body.
4. INT boot; an end-to-end event lands in the event store with the same key and body as before.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard 5.0.2, Guice 7 (versions as managed by commons) |
| Build | Maven, Java 17 |
| AWS SDK | AWS SDK 2.x via `shared` adapters over `cloud-sdk-api` / `cloud-sdk-aws` 1.0.38-SNAPSHOT (was AWS SDK v1 through `shared`) |
| Messaging | SQS (receive, delete) |
| Storage | S3 (put) |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | The stored `Content-Type` stays `text/plain`; switching to `application/json` would change behaviour for event-store readers | Open Issue | Resolved | Keep `text/plain` |
| 3 | The `messages-failed` meter is never marked: `@Metered` sits on the private `handleException` (`S3StoringMessageHandler.java:63`), which Guice AOP cannot intercept, and the error-rate health check reads a meter registered under `SQSMessageWriterTask` (`EventWriterApplication.java:65`). The `errorsPerSecondAverage` check therefore always reports healthy | Open Issue | Resolved | Kept as is: existing behaviour is not changed by this program; a disabled known-defect test covers it |
| 4 | A failed S3 write loses the event: the handler catches every exception, so `AbstractTask` deletes the message (no retry, no DLQ) | Open Issue | Resolved | Kept as is: existing behaviour is not changed by this program; a disabled known-defect test covers it |
| 5 | `InboundSqsHealthCheck` receives with `VisibilityTimeout=0`; cloud-sdk `MessagingClient.receiveMessages` never sends a visibility timeout, so a receive-based v2 probe would hide a real message for the queue default visibility timeout | Open Issue | Resolved | Owned by `shared` (open issue 11): the probe uses `MessagingClient.getQueueAttributes` until U5 is released (needs `sqs:GetQueueAttributes`) |

---

## High Level Design

### Architectural Overview (ext)

```
 event-writer pickup queue (SQS)
        │  receive(max = idle workers, wait = 20 s, attrs = [failedAttempts])
        ▼
 shared SQSListener (back-pressure, over MessagingClient<String>) ─▶ AsyncDispatcher (maxNumberOfMessages workers)
        │
        ▼
 SQSMessageWriterTask ─▶ S3StoringMessageHandler ─▶ SQSMessageToEventConverter (shared Json, SNSNotification)
        │
        ▼
 shared workspace adapter putObject(bucket, key, String)   (UTF-8, Content-Type text/plain)
        │
        ▼
 cloud-sdk StorageClient ─▶ event store bucket
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Call cloud-sdk `StorageClient.putObject(bucket,key,String)` from the module | No adapter | Sends `text/plain; charset=UTF-8`; bypasses the `shared` parity point (C1) | ❌ |
| 2 | Keep calling `shared` `WorkspaceService.putObject(String)`; its v2 adapter writes the UTF-8 bytes through `StorageClient.putObject(bucket, key, bytes, metadata, "text/plain")` | No module code change for the write; parity enforced in `shared` | Depends on the `shared` re-base | ✅ |
| 3 | Switch to `application/json` | Semantically nicer | Behaviour change for event-store readers | ❌ |

### Data Flow — Before vs After (ext)

**Before:** v1 `SQSListenerClient` receive → `shared` task on v1 `Message` → `shared` `Json` → `S3WorkspaceService.putObject(String)` (SDK v1 sets `text/plain`, UTF-8).

**After:** `shared` back-pressure listener over `MessagingClient<String>` → same task on `QueueMessage<String>` → `shared` `Json` (unchanged) → `shared` workspace adapter `putObject(String)` (UTF-8 bytes, `Content-Type: text/plain`) → `StorageClient`.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `ExternalServicesModule` | v1 `AmazonSQS` (listener, sender) and `AmazonS3` bindings removed; installs the `shared` v2 module, which builds one cloud-sdk client per role with the shared client profile. The `EventWriterApplication(Module)` constructor is kept so functional tests inject fakes |
| 2 | `EventWriterModule` | Binds the `shared` v2 `SQSListener`, `AsyncDispatcher` (`maxNumberOfMessages` workers) and the v2 workspace adapter as `WorkspaceService`; `ListenerManager` unchanged |
| 3 | `EventWriterApplication` | `initialize()` registers the commons-based config command instead of `ConfigProcessingServerCommand`, and the v2 S3 bootstrap source provider when `CONFIG_LOCATION=s3`; config files unchanged. Health checks: `InboundSqsHealthCheck`, `ErrorThresholdHealthCheck` (default + ops), `S3WriteHealthCheck` (ops only) — `shared` v2 versions on the injected clients, same names |
| 4 | `EventWriterConfiguration` | Unchanged (`errorRateThreshold`, `pickupSqsConfig`, `s3Config`, `s3EventStorePath`) |
| 5 | `SQSMessageHandler`, `SQSMessageWriterTask` | v1 `Message` → `QueueMessage<String>` (SDK-neutral `shared` task signature); only body and message id are used |
| 6 | `SQSMessageToEventConverter` | Unchanged logic: parse body as `List<Event>`, on failure parse as `shared` `SNSNotification` and then its `Message` |
| 7 | `S3StoringMessageHandler` | Same `WorkspaceService.putObject(bucket, key, String)` call and key composition; only the message type changes |

#### Client Profile (ext)

From the shared client profile (C3): listener connect 1 s, socket 30 s, no API-call timeout; sender (used only for delete) connect 1 s, socket 5 s, API-call timeout 10 s; S3 connect 1 s, socket 5 s, no API-call timeout. All: 50 max connections, 3 retries, exponential backoff 500 ms – 5 s, `AwsRetryCondition`; closed by the Dropwizard lifecycle.

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive, delete after the task; health probe (see Open Issue 5) | AWS SDK 2.x via `shared` / cloud-sdk |
| S3 | `PutObject` per event (`text/plain`, UTF-8, no user metadata); ops health check puts key `HEALTHCHECK` | AWS SDK 2.x via `shared` / cloud-sdk |

#### DynamoDB Changes (ext)

None.

### UI

N/A

### API Architecture

N/A — no API added or changed. Only the existing Dropwizard health/admin endpoints, unchanged.

---

## Configuration

### Component-Level Configuration

`EventWriterApplication.initialize()` registers the commons-based config command instead of the `shared` one; `conf/event-writer.yaml` keys and `.properties` files are unchanged. The only YAML edit is the logger entry in Auditing/Logging.

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

Module log messages and levels are unchanged. cloud-sdk logs every S3 put at INFO (`S3StorageClient`); with one put per event this would roughly double log volume, so `event-writer.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers`, as the shared design requires for every module.

### Event Publishing (ext)

None — `event-writer` stores events; it does not publish any.

---

## Metrics and Statistics

No change. `messages-processed` (`AbstractTask`) is unchanged; `messages-failed` keeps its existing defect (Open Issue 3).

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
| Other file migration | No | Stored objects unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change: same queue, same objects, same keys, same headers.

### Performance (ext)

One S3 put per event, sequential within a message; at most `maxNumberOfMessages` (default 10) puts in flight against a 50-connection pool, so no pool contention. The S3 client has no API-call timeout; a stalled put is bounded by the 5 s socket timeout per attempt.

### Deployment (ext)

Rolling restart as part of the single AppianWay release. No data migration. A single service can be rolled back to its previous build alone, because formats are unchanged.

---

## Resiliency

- S3 put failure: the client retries 3 times; the adapter then raises `RecoverableException` (C9), which the handler logs and swallows, so the message is deleted and the event is not stored — as today (Open Issue 4).
- Parse failure: logged and deleted, as today.
- Redelivery (delete failed or visibility expired): the event is rewritten to the same key, so writes are idempotent.
- Receive failure: logged by the listener; the poll loop continues.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files.

---

## Impact on Tools

None.

---

## Impact on Other Components

- Readers of the event store: None — objects are byte-identical, same keys and `Content-Type`.
- Event producers: None — input formats unchanged.
- `shared`: consumes the re-based workspace adapter, listener, health checks and commons config command.

---

## Backwards Compatible

**Yes.**

| Question | Answer |
|----------|--------|
| Stored object body | Identical — same `Event` model and field order, `shared` `Json`, UTF-8 |
| Stored object key | Identical |
| S3 `Content-Type` / metadata | Identical — `text/plain`, no user metadata |
| Input message formats | Identical — raw array and SNS envelope both accepted |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:mercury-shared` | 1.0 | 1.0 (re-based on commons) | Upgrade | Brings `commons`, `cloud-sdk-api`, `cloud-sdk-aws` 1.0.38-SNAPSHOT and AWS SDK 2.x transitively |

`event-writer/pom.xml` declares no AWS SDK dependency directly; other versions come from the root pom aligned with commons.

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `S3StoringMessageHandlerTest` (extended) | Key composition; `putObject(String)` call; exception swallowed |
| 2 | `EventWireCompatibilityTest` | Golden fixtures: stored JSON byte-identical to v1 output |
| 3 | `SQSMessageToEventConverterTest` | Raw array and SNS envelope inputs |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Handler / task | `S3StoringMessageHandlerTest`, `SQSMessageWriterTaskTest` | Unit, mocked `WorkspaceService` |
| End-to-end | `EventWriterFuncTest` | `functional-testing` cloud-sdk fakes; asserts key, body, `Content-Type` |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT boot; publish one event | Object stored at the same key with the same body and `Content-Type` as the v1 build |

### Existing Test Impact (ext)

`S3StoringMessageHandlerTest`, `SQSMessageWriterTaskTest` and `EventWriterFuncTest` are retargeted from v1 `Message` and v1 fakes to `QueueMessage<String>` and cloud-sdk fakes; assertions on stored content are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: a failed S3 write leaves the message on the queue (not deleted); a failed write marks `messages-failed`, so the error-rate health check reports it.

---

## Risks

**Key Risks**

- JSON output drift — mitigated by `shared` `Json` and golden fixtures.
- S3 header drift — enforced in the `shared` workspace adapter and asserted in the functional test.
- Silent event loss on write failure and an error-rate health check that never trips (Open Issues 3, 4) — existing behaviour, made visible here; not changed by the migration.
- Health-check probe consuming real messages if implemented as a plain v2 receive — mitigated by the `shared` probe on `getQueueAttributes` (Open Issue 5).

---

## Dependencies

**Major Dependencies**

- `shared` re-base (workspace adapter, back-pressure listener, health checks, commons config command).
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
