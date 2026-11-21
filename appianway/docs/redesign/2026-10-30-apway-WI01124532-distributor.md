# WI01124532 distributor — AWS SDK 2.x (cloud-sdk) Upgrade

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

`distributor` is the file-shape egress. It consumes the `MetaData` envelope from its SQS pickup queue, resolves the outbound file name, delivery path and archive path from Network Services attributes and tokens, optionally zips the workspace document, and copies it from the workspace bucket to the outbound bucket twice (delivery key, then archive key), replacing the object metadata with workflow user metadata. It then publishes a `CLOSE_WORKFLOW` event.

This change moves the module from AWS SDK v1 and the `shared` v1 wrappers to `commons` + `cloud-sdk-api` + `cloud-sdk-aws` **1.0.38-SNAPSHOT** (AWS SDK 2.x), using `shared` re-based on commons. All S3 calls (including the copy to the outbound bucket) are `WorkspaceService` operations and go through the `shared` workspace adapter; SQS and SNS go through the `shared` adapters; SSM uses `CloudParameterStore`. Delivered objects, keys, user metadata, S3 headers, queue messages and events are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `distributor` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` design (contract C1–C9) |

### Functional Requirements

1. Copy the source object (workspace bucket from `s3WorkspaceConfig`) to the outbound bucket (`s3OutboundConfig`) under the same delivery and archive keys, with metadata directive REPLACE and the same user metadata: `rootWorkflowId`, `parentWorkflowId`, `workflowId`, outbound integration profile format id, context code, outbound EDI id, plus pick-up time and reprocess flag when present.
2. Delivered objects keep `Content-Type: application/octet-stream`, as v1 sends today (see Open Issue 2).
3. When zipping is configured, write the zip (single entry named after the output file, ISO-8859-1 entry-name encoding) to the message's bucket under `{rootWorkflowId}/{uuid}.zip` as bytes (`application/octet-stream`), and deliver it as above with the file extension changed to `.zip`.
4. Keep the file-name token resolution, the `CLOSE_WORKFLOW` event, error codes and the retry/DLQ path unchanged.

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in module sources.
2. Byte-for-byte compatibility of delivered objects (body, key, user metadata, headers), queue messages and events (C1–C4).
3. Same listener concurrency (dispatcher threads = `maxNumberOfMessages`, default 10), long-poll wait and batch size as today.

### Acceptance Criteria

1. `mvn -pl distributor -am clean verify` is green.
2. Golden-fixture tests prove the `Event` and error `MetaData` JSON are byte-identical to the v1 build.
3. Adapter-level test asserts the copy request: REPLACE directive, `Content-Type: application/octet-stream`, user metadata keys/values trimmed, absent optional values handled as characterized from v1 (Open Issue 3).
4. A copy that cloud-sdk reports as failed (`copyObject` returns `false` for 400/403/404 or missing source) raises `RecoverableException` and follows the retry path.
5. INT boot and an end-to-end delivery (plain and zipped) produce outbound objects whose body, key, user metadata and `Content-Type` equal those of the v1 build.

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
| Messaging | SQS (receive/send/delete), SNS (publish) via `shared` adapters |
| Storage | S3 (get/put/copy with replaced metadata) via `shared` workspace adapter |
| Parameters | SSM Parameter Store (Network Services credentials) via `CloudParameterStore` |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | v1 `AmazonS3Client.invoke` adds `Content-Type: application/octet-stream` to every request that has none, so today's REPLACE copy stores `application/octet-stream` on delivered objects. A v2 REPLACE copy without a content type makes S3 store its default `binary/octet-stream` | Open Issue | Resolved | The adapter's copy-with-metadata passes `application/octet-stream` via `StorageClient.copyObject(src, key, dst, key, metadata, contentType)`, as specified in `shared` C2. Confirm on one v1-delivered INT object |
| 3 | Optional metadata values can be null (outbound IPF id, context code, outbound EDI id are put unconditionally). v1 adds `x-amz-meta-(key)` with a null value; the stored result (header dropped or empty value) is not known | Open Issue | Open | Characterize on INT with a v1-delivered object missing `outboundEdiId`; the `shared` adapter reproduces it (omit or empty) |
| 4 | cloud-sdk `copyObject` returns `false` on missing source or 400/403/404 instead of throwing | Assumption | Resolved | `shared` adapter throws `RecoverableException` on `false` (C2), matching v1 where `AmazonS3Exception` was wrapped |
| 5 | v1 trims user metadata keys and values (`populateRequestMetadata`); cloud-sdk does not | Assumption | Resolved | `shared` adapter trims as v1 (C2) |
| 6 | Network Services clients stay in `shared` (Tier 3) | Assumption | Resolved | Unchanged |

---

## High Level Design

### Architectural Overview (ext)

```
 distributor pickup queue (SQS)
           │  shared back-pressure SQSListener (idle permits, wait 20 s, attrs=[failedAttempts])
           ▼
 AsyncDispatcher (maxNumberOfMessages threads) ─▶ DistributorTask
      │  ─▶ FileDeliveryAttributesProvider (Network Services) ─▶ TokensProcessor (file name, paths)
      │  ─▶ ZipCompression (optional): getS3InputStream ─▶ zip in memory ─▶ putObject(byte[]) (workspace)
      │  ─▶ FileDeliveryService: copyObjectWithMetaDate x2 (delivery key, archive key)
      │         shared workspace adapter: REPLACE, user metadata, Content-Type application/octet-stream
      └──▶ EventLogger ─▶ shared SNS event publisher (CLOSE_WORKFLOW)
           │
 failure ─▶ DistributorErrorHandler ─▶ retry (failedAttempts + DelaySeconds) / (pickup)_dlq / errors queue
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Call `StorageClient.copyObject` directly from `FileDeliveryService` | Fewer layers | Breaks C1; `false` instead of exception; trim, null-value and content-type differences leak into delivery | ❌ |
| 2 | `shared` workspace adapter `copyObjectWithMetaDate` reproducing v1 (REPLACE, `application/octet-stream`, trim, null handling, throw on `false`) | Delivered objects identical; one place for parity | Adapter behaviour must be pinned by tests | ✅ |

### Data Flow — Before vs After (ext)

**Before:** v1 `AmazonSQS` receive → `shared S3WorkspaceService` (v1 `AmazonS3`, `CopyObjectRequest.withNewObjectMetadata` → REPLACE) → `shared SQSClient` / `SNSEventPublisher` (v1) → `shared Json`.

**After:** `shared` back-pressure listener over `MessagingClient<String>` → `shared` workspace adapter (`StorageClient.copyObject(.., metadata, "application/octet-stream")`, REPLACE) → `shared` SQS sender / SNS event publisher → `shared Json` (unchanged).

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `ExternalServicesModule` | Drops the v1 SQS/S3/SNS builders; installs the `shared` v2 module (one client per role from the C3 profile, `ManagedCloudResource` lifecycle). `ParameterStoreModule` (shared) backed by `CloudParameterStore` |
| 2 | `DistributorModule` | Listener, dispatcher, task factory, `EventPublisher` and `WorkspaceService` from the `shared` v2 module |
| 3 | `DistributorApplication` | `initialize()` registers the commons-based config command instead of the shared one; config files unchanged. S3 config source via the `shared` bootstrap provider. Health checks (`InboundSqs`, `HttpGet`, `ErrorThreshold`, `OutboundSqs` errors queue, `SnsPublish`) reuse the injected clients; the inbound SQS probe uses `getQueueAttributes` (`shared` open issue 11) |
| 4 | `DistributorTask`, `DistributorErrorHandler` | SQS message type → SDK-neutral queue message from `shared`; logic and error codes unchanged |
| 5 | `FileDeliveryService` | Unchanged; calls `WorkspaceService.copyObjectWithMetaDate` (same keys and metadata map) |
| 6 | `ZipCompression` | Injects the `WorkspaceService` interface instead of the concrete v1 `S3WorkspaceService` (`ZipCompression.java:22-25`); `com.amazonaws.util.IOUtils.toByteArray` → `InputStream.readAllBytes` |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive (`failedAttempts` attribute), send to errors / retry / `_dlq` queues, delete | AWS SDK 2.x via `shared` adapters |
| S3 | Get document (zip path), put zip, copy with replaced metadata (workspace → outbound, two keys), put error annotations | AWS SDK 2.x via `shared` workspace adapter |
| SNS | Publish close-run events | AWS SDK 2.x via `shared` event publisher |
| SSM | Read Network Services client credentials (with decryption) | AWS SDK 2.x via `CloudParameterStore` |

#### DynamoDB Changes (ext)

None.

### UI

N/A

### API Architecture

N/A — no API added or changed. Only the existing Dropwizard health/admin endpoints, unchanged.

---

## Configuration

### Component-Level Configuration

Application `initialize()` registers the commons-based config command instead of the shared one; config files unchanged. `conf/distributor.yaml` keys (including `s3WorkspaceConfig`, `s3OutboundConfig`) and `.properties` overrides are unchanged.

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change. Same queues, topic, buckets and SSM parameter names.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to application log messages or levels. `distributor.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3/SNS calls at INFO), as the shared design requires.

### Event Publishing (ext)

Unchanged: one close-run event (`CLOSE_WORKFLOW` sub-type, `s3DeliveryFileName` and `pickupQueue` tokens) per delivery, with the same workflow ids and `success` flag, published as a raw JSON array to the same topic.

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
| Other file migration | No | Delivered objects unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change: same delivered objects, keys, user metadata, headers and events.

### Performance (ext)

- Copies are server-side and unchanged in number (two per message).
- Zip path keeps the whole document in heap about three times (source bytes, zip buffer, `toByteArray` copy), per dispatcher thread, as today. The adapter's `getS3InputStream` uses `StorageClient.getObject`, which issues a GET plus a HEAD, so each zipped delivery costs one extra HEAD request; accepted.
- The S3 client sets no API-call timeout (`shared` client profile), so large documents are not cut off by a whole-download cap; stalls are bounded by the 5 s socket timeout.

### Deployment (ext)

Rolling restart as part of the single AppianWay release. No data migration. A single service can be rolled back to its previous build alone, because formats are unchanged.

---

## Resiliency

- Unchanged error model: `RecoverableException` (S3/SQS/SNS client failures mapped by type per C9, and a copy reported as `false`) re-queues to the pickup queue with `failedAttempts` and `DelaySeconds`, then to `(pickup)_dlq`. Other exceptions write annotations to the workspace bucket and post the `MetaData` to the errors queue. The message is then deleted.
- Existing behaviour kept, not idempotent on retry: the delivery copy runs before the archive copy (`FileDeliveryService.java:64-65`). File names come from date and random tokens and the zip key from `UUID.randomUUID()`. If a later step fails recoverably after the delivery copy, the retry delivers a second file under a new name and leaves an orphan zip in the workspace bucket.
- Hystrix (`externalwrapper`) is not used by this module.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files; the zip is built in memory and stored in the workspace bucket as today.

---

## Impact on Tools

None.

---

## Impact on Other Components

- Outbound delivery (MFT egress) and downstream readers of the outbound bucket: None — objects, keys, user metadata and `Content-Type` unchanged (Open Issues 2 and 3).
- Event consumers (`event-writer`, `ingestor`): None — events unchanged.
- `shared`: copy-with-metadata passes `application/octet-stream` (C2, Open Issue 2).

---

## Backwards Compatible

**Yes**, once Open Issue 3 (absent optional metadata) is characterized on INT and pinned by a test.

| Question | Answer |
|----------|--------|
| Delivered objects | Identical body and keys; same user metadata keys/values (trimmed); `Content-Type` `application/octet-stream` |
| Zip object | Identical layout and key pattern; `Content-Type` `application/octet-stream` |
| Events / error `MetaData` JSON | Identical — `shared` `Json` (C1) |
| Retry / DLQ messages | Identical body, `failedAttempts` String attribute and `DelaySeconds` |
| SSM parameters | Same names, decrypted |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

Versions come from commons; the module declares no versions for commons-managed libraries.

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:cloud-sdk-aws` (brings `cloud-sdk-api`) | — | 1.0.38-SNAPSHOT (via `shared`) | New | AWS SDK 2.x |
| `com.amazonaws:aws-java-sdk-sqs` | 1.12.720 | removed as direct dependency | Removal | Replaced by AWS SDK 2.x |

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `DistributorWireCompatibilityTest` | Golden fixtures: `Event` and error `MetaData` JSON byte-identical to v1 output |
| 2 | `FileDeliveryServiceTest` (extended) | Metadata map incl. absent optional values and pick-up time / reprocess; delivery then archive copy |
| 3 | `ZipCompressionTest` (extended) | Zip key, entry name, bytes and byte put via the `WorkspaceService` interface |
| 4 | `shared` `CloudSdkWorkspaceServiceTest` (copy cases) | REPLACE, `application/octet-stream`, trim, null values, `false` → `RecoverableException` |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Service | `FileDeliveryServiceTest`, `ZipCompressionTest` | Unit, mocked `WorkspaceService` |
| Task | `DistributorTaskTest`, `ErrorHandlerTest` | Unit, mocked `shared` adapters |
| End-to-end | `DistributorFuncTest` | `functional-testing` cloud-sdk fakes |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT; deliver one plain and one zipped file, one with `outboundEdiId` absent | Outbound objects' body, keys, user metadata and `Content-Type` equal those of the v1 build |

### Existing Test Impact (ext)

Existing tests (JUnit 4) are retargeted from v1 types and fakes to cloud-sdk / `shared` v2 types and fakes; assertions on delivered objects, messages and events are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: a retried delivery reuses the same file name and zip key, so no second delivered file or orphan zip is created.

---

## Risks

**Key Risks**

- Delivered `Content-Type` changes from `application/octet-stream` to `binary/octet-stream` if the copy sends no content type. Mitigation: `shared` C2 passes `application/octet-stream` on REPLACE copies; adapter copy test.
- Absent optional metadata handled differently (missing vs empty value). Mitigation: Open Issue 3 characterization.
- Silent delivery loss if a copy that returns `false` is not turned into an exception. Mitigation: `shared` adapter throws `RecoverableException`.
- Large zipped documents exhaust heap at 10 threads. Mitigation: INT test with the largest outbound document; S3 timeouts follow the `shared` client profile (no whole-download cap).
- Duplicate delivery on retry after a partial copy (existing; unchanged).

---

## Dependencies

**Major Dependencies**

- `shared` re-based on commons, including the copy content type (C2).
- `mercury-services-commons` 1.0.38-SNAPSHOT.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | N | No UI |
| 2 | Use of new services/ports | N | Same AWS services and resources; same ports |
| 3 | Authentication changes | N | AWS credentials from the default provider chain / task role, as today. Network Services credentials read from SSM as today |
| 4 | New/changed encryption | N | No change; TLS to AWS endpoints; SSM decryption unchanged; no SSE/ACL set (bucket defaults), as today |
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
