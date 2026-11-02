# WI01124532 dispatcher — AWS SDK 2.x (cloud-sdk) Upgrade

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

`dispatcher` is the AppianWay inbound gate. It consumes S3 `ObjectCreated` notifications (SNS-wrapped) from its SQS pickup queue, derives the archive format type and MFT id from the key, filters the file against the Network Services integration profiles, copies the inbound object into the workspace bucket, builds the initial `MetaData` envelope and sends it to the queue mapped to the archive format type (`sqsRouteMappingConfig`). Zip files are expanded back into the inbound bucket instead, and filtered-out `300_IFTMBF` files that carry an `xlogid` are sent to the booking-bridge queue.

This change moves `dispatcher` off AWS SDK v1 onto `commons` + `cloud-sdk-api` + `cloud-sdk-aws` **1.0.38-SNAPSHOT** (AWS SDK 2.x) through `shared` re-based on commons: SQS, SNS and workspace S3 go through the `shared` Tier-2 adapters, SSM and client construction come from commons/cloud-sdk directly (Tier 1). Queue messages, events, stored objects, keys, user metadata and S3 headers are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `dispatcher` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` design |

### Functional Requirements

1. Parse the S3 notification exactly as today: first record only; bucket; key URL-decoded as UTF-8 (`+` becomes a space); size; event time printed as `yyyy-MM-dd HH:mm:ss.SS` in UTC for the `s3EventCreatedTime` projection. A body that cannot be parsed still fails the message before the error handler (message left on the queue), as today.
2. Read the inbound object's user metadata (HEAD) and copy the object to the workspace bucket under `{rootWorkflowId}/{uuid}` (plain copy, metadata directive COPY). A `rootworkflowid` user-metadata value, when present, is reused as the root workflow id.
3. Send the same `MetaData` JSON to the queue mapped to the archive format type (`default` otherwise). When the preprocessors abort and the type is `300_IFTMBF` with an `xlogid`, send it to the booking-bridge queue (no workspace copy), as today.
4. Expand `.zip` files into the inbound bucket under the zip's folder with the same keys, bytes and user metadata (zip metadata plus `rootworkflowid`), `Content-Type: application/octet-stream`; zero-length entries are still written.
5. Keep the archive-format/MFT-id filter (30-minute cache), event lineage, error codes and the retry/DLQ path unchanged.

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in module sources.
2. Byte-for-byte wire compatibility of queue messages, events and stored objects (shared contract C1–C4, C7–C9).
3. Same concurrency (`maxNumberOfMessages` worker threads), long-poll wait and back-pressure receive as today.

### Acceptance Criteria

1. `mvn -pl dispatcher -am clean verify` is green.
2. Golden-fixture tests prove the routed and booking-bridge `MetaData` JSON and the emitted `Event` JSON are byte-identical to the v1 build.
3. `S3EventParserTest` proves identical `S3Event` output (encoded keys, `+`, UTC event time, size) for recorded notifications.
4. Functional test asserts zip-entry objects (including a zero-length entry) carry the same keys, user metadata and `Content-Type` (`application/octet-stream`) as before.
5. Config golden test (program-level) passes for `dispatcher.yaml` with every environment's properties.
6. INT boot; an inbound file reaches the routed queue with the same envelope as before.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard 5.0.2, Guice 7 |
| Build | Maven, Java 17 |
| AWS SDK | AWS SDK 2.x via `cloud-sdk-api` / `cloud-sdk-aws` 1.0.38-SNAPSHOT (was AWS SDK v1 1.12.720) |
| Messaging | SQS (receive/send/delete), SNS (publish) |
| Storage | S3 (head/get/put/copy) |
| Parameters | SSM Parameter Store (Network Services client id/secret) |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | v1 `S3EventNotification` (joda `DateTime`, offset kept from the string) is replaced by cloud-sdk-api `storage.event.S3EventNotification` (`Instant`) | Open Issue | Resolved | Format the `Instant` with `Json.DEFAULT_DATE_TIME_PATTERN` at `ZoneOffset.UTC`; use `getUrlDecodedKey()` (same `URLDecoder`, UTF-8) |
| 3 | cloud-sdk `getMetadata` returns an unmodifiable map; `ZipPreprocessor` adds `rootworkflowid` to it | Open Issue | Resolved | Workspace adapter returns a mutable, case-insensitive copy (shared C2) |
| 4 | cloud-sdk `copyObject` returns `false` on 400/403/404 instead of throwing | Open Issue | Resolved | Workspace adapter raises `RecoverableException` on `false` (shared C2); v1 threw `SdkClientException`, wrapped the same way |
| 5 | cloud-sdk `StorageClient` rejects zero-length content; a zip can contain empty or directory entries | Open Issue | Resolved | The `shared` workspace adapter writes zero-length objects through the interface-only fallback (`shared` open issue 3, U2): same key, metadata and content type |
| 6 | Network Services clients stay in `shared` (Tier 3); the `commons` network-services package is not used | Assumption | Resolved | Unchanged by construction |

---

## High Level Design

### Architectural Overview (ext)

```
 inbound bucket ──(S3 notification)──▶ SNS ──▶ dispatcher pickup queue (SQS)
                                                     │
                                                     ▼
            shared back-pressure SQSListener ─▶ shared AsyncDispatcher (maxNumberOfMessages threads)
                                                     │
                                                     ▼
   DispatcherTask ─▶ S3EventParser (cloud-sdk-api S3EventNotification)
        │        ─▶ workspace adapter getMetaData (HEAD inbound object)
        │        ─▶ PreProcessors: IgnorePreprocessor (Network Services filter)
        │                          ZipPreprocessor  (get zip; put entries to inbound bucket)
        │        ─▶ workspace adapter copyObject (inbound → workspace bucket, COPY)
        │        ─▶ RouterManager ─▶ shared SQS sender (routed / booking-bridge queue)
        └────────▶ EventLogger ─▶ shared SNS EventPublisher (event topic)
                                                     │
               failure ─▶ DispatcherErrorHandler ─▶ retry (pickup queue) / _dlq / errors queue
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Keep a dispatcher-local copy of the v1 `S3EventNotification` model | No dependency on cloud-sdk event model | Duplicates a model cloud-sdk-api already provides | ❌ |
| 2 | cloud-sdk-api `S3EventNotification` + explicit UTC formatting in `S3EventParser` | Shared model; same `S3Event` output | Formatting must be pinned by tests | ✅ |
| 3 | Call cloud-sdk `StorageClient` / `MessagingClient` directly from tasks | Fewer layers | Bypasses the parity rules (copy result, mutable metadata, empty objects, exception mapping) | ❌ |
| 4 | `shared` Tier-2 workspace, SQS and SNS adapters | Wire parity enforced in one place; `WorkspaceService` contract kept | Adapter must reproduce v1 edge cases | ✅ |

### Data Flow — Before vs After (ext)

**Before:** v1 `AmazonSQS` receive → v1 `S3EventNotification` → `shared` `S3WorkspaceService` (v1 `AmazonS3`) → `shared` `SQSClient` / `SNSEventPublisher` (v1) → `shared` `Json`.

**After:** `shared` back-pressure listener over `MessagingClient<String>` → cloud-sdk-api `S3EventNotification` → `shared` workspace adapter (`StorageClient`) → `shared` SQS sender / SNS `EventPublisher` (`MessagingClient<String>` / `NotificationService`) → `shared` `Json` (unchanged).

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `ExternalServicesModule` | v1 `AmazonSQS` (listener, sender), `AmazonS3`, `AmazonSNS` bindings replaced by the `shared` v2 module: one cloud-sdk client per role with the shared client profile (connect 1 s; socket 5 s for sender/S3/SNS, listener above the 20 s long poll; API-call timeout 10 s for SQS send and SNS, none for S3; 50 connections; 3 retries, SNS 2; backoff 500 ms..5 s; `AwsRetryCondition`), closed by the Dropwizard lifecycle. `ParameterStoreModule` (v1 SSM default client) replaced by the shared parameter binding over commons `CloudParameterStore` (same names, decryption on, eager load, unknown name fails startup). `RecoveryConfig` defaults (5 attempts, multiplier 10) unchanged |
| 2 | `DispatcherModule` | `SQSListener`, `AsyncDispatcher`, `WorkspaceService` and `EventPublisher` bound from the `shared` v2 module; `routeMappings` binding unchanged |
| 3 | `DispatcherApplication` | `initialize()` registers the commons-based config command instead of the shared one; S3 bootstrap source provider kept (CONFIG_LOCATION=s3); config files unchanged. Health checks (inbound SQS, S3 read, error threshold; outbound SQS errors queue, S3 write workspace, SNS publish) keep their names and reuse the injected clients; the inbound SQS probe uses `getQueueAttributes` (`shared` open issue 11) |
| 4 | `DispatcherConfiguration`, `BookingBridgeConfiguration` | Unchanged; YAML keys unchanged |
| 5 | `DispatcherTask`, `PreProcessors`, `PreProcessor`s | v1 `Message` → `shared` SDK-neutral queue message type; logic unchanged |
| 6 | `S3EventParser` | cloud-sdk-api `S3EventNotification.parseJson`; first record; `getUrlDecodedKey()`; size; event time formatted in UTC with the existing pattern |
| 7 | `ZipPreprocessor` | `com.amazonaws.util.IOUtils` / `ObjectMetadata` removed; reads the zip via workspace adapter `getS3InputStream`, writes each entry via `putObjectWithMetaData` (bytes, `application/octet-stream`, metadata copy plus `rootworkflowid`) |
| 8 | `FileFilterService`, `RouterManager` | Unchanged (Network Services types from `shared`) |
| 9 | `DispatcherErrorHandler` | Unchanged; extends the `shared` `ErrorHandler` (retry re-queues the original body with `failedAttempts` and `DelaySeconds` 20–320 s; `_dlq` after 5 attempts; non-recoverable → annotations to workspace + `MetaData` to the errors queue) |
| 10 | External-call wrapper (Hystrix) | Not used by this module (no `@ExternalCall`; Hystrix bundle registration is commented out); unchanged |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive (`failedAttempts` attribute, no visibility timeout sent); send to routed / booking-bridge / errors / pickup (retry) / `_dlq` queues; delete | AWS SDK 2.x via `shared` adapters |
| S3 | HEAD (user metadata), get (zip), put (zip entries), copy (inbound → workspace), put error annotations (`text/plain`, UTF-8) | AWS SDK 2.x via `shared` workspace adapter |
| SNS | Publish close-run events (raw JSON array) | AWS SDK 2.x via `shared` `EventPublisher` |
| SSM | Read Network Services client id/secret (decrypted) at startup | AWS SDK 2.x via commons `CloudParameterStore` |

#### DynamoDB Changes (ext)

None.

### UI

N/A

### API Architecture

N/A — no API added or changed. Only the existing Dropwizard health/admin endpoints, unchanged.

---

## Configuration

### Component-Level Configuration

No change. `dispatcher.yaml` keys (including `sqsRouteMappingConfig` and `bookingBridgeConfig`) and `.properties` files are unchanged; they are resolved by the commons config chain with the same result (config golden test).

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to `dispatcher` log messages or levels. `dispatcher.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3 calls at INFO), as the shared design requires. The `messages-failed` meter is unchanged.

### Event Publishing (ext)

Unchanged: one close-run event per routed or booking-bridge file (`START_WORKFLOW` sub-type, pick-up/drop-off queue tokens) and one per expanded zip entry (no sub-type, token `inboundS3ZipFileName`), with the same workflow ids, tokens and `success` flag, published as a raw JSON array to the same event topic.

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
| Other file migration | No | Objects and messages unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change: same queues, routing, objects, keys, user metadata, headers and events.

### Performance (ext)

No material change. Existing limits, kept as is: the whole zip and each entry are held in memory (`getS3InputStream` buffers the object; entries are copied into byte arrays) with up to `maxNumberOfMessages` (10) files in flight, so heap bounds the largest zip; each zip entry triggers one HEAD of the zip for its metadata. Connection pools (50) exceed worker threads (10).

### Deployment (ext)

Rolling restart as part of the single AppianWay release. No data migration. A single service can be rolled back to its previous build alone, because formats are unchanged.

---

## Resiliency

Unchanged: failures map to the same error codes. Recoverable failures re-queue the original notification to the pickup queue with `failedAttempts` and `DelaySeconds` (2^n × 10 s), then go to `_dlq`; non-recoverable failures write annotations to the workspace bucket and post the `MetaData` to the errors queue before the message is deleted. S3/SQS/SNS cloud-sdk failures (including `copyObject` returning `false`) are mapped to `RecoverableException` by exception type in the `shared` adapters, as v1 `SdkClientException` was (shared C9). Redelivery is at-least-once as today: a zip that fails part-way is re-expanded on retry, re-writing entries already written and so re-triggering their notifications.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files; zip entries are processed in memory as today.

---

## Impact on Tools

None.

---

## Impact on Other Components

- `splitter`, booking bridge and other routed consumers: None — `MetaData` JSON unchanged.
- Event consumers (`event-writer`, `ingestor`): None — events unchanged.
- Inbound bucket readers: None — zip-entry objects unchanged.
- `shared`: re-based on commons; `dispatcher` binds its v2 module.

---

## Backwards Compatible

**Yes.**

| Question | Answer |
|----------|--------|
| Routed / booking-bridge `MetaData` JSON | Identical — `shared` `MetaData` and `Json` |
| `s3EventCreatedTime` projection | Identical — same pattern, UTC |
| Events | Identical — same sub-types, tokens and lineage ids |
| Workspace copy | Identical — plain copy (COPY), source metadata and `Content-Type` retained |
| Zip-entry objects | Identical key, bytes, user metadata; `Content-Type` `application/octet-stream`; empty entries written (open issue 5) |
| Error annotations | Identical — UTF-8, `text/plain` |
| Retry / DLQ messages | Identical body, `failedAttempts` String attribute and `DelaySeconds` |
| SSM parameters | Same names, decrypted |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:commons`, `cloud-sdk-api`, `cloud-sdk-aws` | — | 1.0.38-SNAPSHOT (via `shared`) | New | AWS SDK 2.x platform |
| `com.inttra.mercury.shared:mercury-shared` | 1.0 | 1.0 (re-based on commons) | Upgrade | Tier-2 adapters, v2 Guice module |
| `com.amazonaws:aws-java-sdk-sqs` (direct) | 1.12.720 | removed | Removal | Replaced by AWS SDK 2.x; v1 stays transitive via `cloud-sdk-aws` until upstream removal |

Other dependency versions come from commons (root pom realigned in the same release); the module pom declares no versions for libraries commons manages.

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `DispatcherWireCompatibilityTest` | Golden fixtures: routed and booking-bridge `MetaData`, close-run `Event` JSON byte-identical to v1 output |
| 2 | `S3EventParserTest` (extended) | Encoded keys, `+` in keys, UTC event time, size, first record only |
| 3 | `ZipPreprocessorTest` (extended) | Mutable metadata copy; `rootworkflowid` added; entry key, bytes, content type; zero-length entry |
| 4 | `DispatcherTaskTest` (extended) | Copy returning `false` → `RecoverableException` → retry path with `failedAttempts`/`DelaySeconds`; zero-byte notification → `emptyFile` error |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Parser | `S3EventParserTest` | Unit, recorded notifications |
| Task | `DispatcherTaskTest`, `ZipPreprocessorTest` | Unit, mocked `shared` adapters |
| End-to-end | `DispatcherFuncTest` | `functional-testing` cloud-sdk fakes |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT boot; drop one EDI file | Same workspace copy and routed envelope as the v1 build |
| 2 | INT; drop one zip | Entries written to the inbound bucket with the same keys, user metadata and content type as the v1 build |

### Existing Test Impact (ext)

Existing tests are retargeted from v1 types and fakes to the `shared` SDK-neutral types and cloud-sdk fakes; assertions on messages, events and stored content are kept.

---

## Risks

**Key Risks**

- `s3EventCreatedTime` drift (time zone or pattern) — mitigated by explicit UTC formatting and parser tests.
- v1 edge cases lost in the storage layer (immutable metadata map, copy returning `false`, empty-object rejection) — mitigated by the `shared` workspace adapter, fakes that copy cloud-sdk behaviour, and targeted tests.
- Retry counter loss if the receive does not request `failedAttempts` — mitigated by the `shared` listener and a retry-path test.
- Large zips are fully buffered in memory (existing behaviour, unchanged); heap sizing stays as today.

---

## Dependencies

**Major Dependencies**

- `shared` re-based on commons, including empty-object writes (`shared` open issue 3).
- `mercury-services-commons` 1.0.38-SNAPSHOT.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | N | No UI |
| 2 | Use of new services/ports | N | Same AWS services and resources; same ports |
| 3 | Authentication changes | N | AWS credentials from the default provider chain / task role, as today. Network Services credentials read from SSM as today |
| 4 | New/changed encryption | N | No change; TLS to AWS endpoints; SSM decryption unchanged |
| 5 | Changes in the way data is transmitted | Y | AWS client library changes from SDK v1 to SDK 2.x. Endpoints, credentials and payloads unchanged |
| 6 | Changes in the way/location data is being stored | N | Same buckets, keys, bodies, user metadata and headers |
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
