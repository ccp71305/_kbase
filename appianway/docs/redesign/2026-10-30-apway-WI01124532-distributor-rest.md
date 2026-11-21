# WI01124532 distributor-rest — AWS SDK 2.x (cloud-sdk) Upgrade

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

`distributor-rest` is the REST-delivery leg of the AppianWay distribution fan-out. It consumes `MetaData` from the REST-delivery queue. When the `MetaData` carries a subscription id, it reads the referenced payload from the workspace bucket (ISO-8859-1), resolves the subscription through Network Services, and POSTs the payload to the subscriber endpoint. The POST uses a bearer token from the subscriber's OAuth endpoint and is retried with guava-retrying. It then publishes a `CLOSE_WORKFLOW` event carrying the returned e2open transaction id.

This change moves the module from AWS SDK v1 and the `shared` v1 wrappers to `commons` + `cloud-sdk-api` + `cloud-sdk-aws` **1.0.38-SNAPSHOT** (AWS SDK 2.x), using `shared` re-based on commons. SQS, SNS and the workspace S3 read go through the `shared` Tier-2 adapters, and SSM uses `CloudParameterStore`. The outbound HTTP call, its payload, its retries and its authentication are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `distributor-rest` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` design (contract C1–C9) |

### Functional Requirements

1. Consume `MetaData` from the existing pickup queue with the same batch size (`maxNumberOfMessages`, default 5 = dispatcher threads) and long-poll wait.
2. Read the payload with the workspace adapter `getContent(bucket, fileName, ISO_8859_1)`: same charset and the same decoded string.
3. Keep subscription lookup (`SubscriptionService`, cached), `RequestBuilder`, the outbound POST (`application/json`, subscription headers, `Authorization: bearer`, Jersey connect/read timeouts from `restClientConfig`, 3-attempt retryer) and the module's OAuth `AuthClient` unchanged.
4. Publish the same `CLOSE_WORKFLOW` event with the `pickupQueue` and `E2openTransactionId` tokens (empty transaction id when there is no subscription id; the payload is then not read and nothing is posted).
5. Keep the failure flow unchanged (see Resiliency): failures from the S3 read, Network Services or the POST leave the message on the queue for SQS redelivery; only `NonRecoverableException` / `IOException` thrown directly by the task go through `ErrorHandler` (null sub-type → errors queue → delete).

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in module sources.
2. Byte-for-byte compatibility of the outbound POST body and of events (C1, C4).
3. Same SSM parameter names and decryption for the Network Services client credentials.

### Acceptance Criteria

1. `mvn -pl distributor-rest -am clean verify` is green.
2. Golden-fixture tests prove the `CLOSE_WORKFLOW` event JSON (with and without transaction id) is byte-identical to the v1 build.
3. Unit test asserts the S3 read uses ISO-8859-1 and the POST entity is the decoded string (`application/json`, encoded by Jersey as today).
4. A failing S3 read or POST leaves the message undeleted (no change of the visibility timeout).
5. INT boot; one REST-delivery message produces the same POST and the same event as before.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard 5.0.2, Guice 7, Jersey client, guava-retrying |
| Build | Maven, Java 17 |
| AWS SDK | AWS SDK 2.x via `cloud-sdk-api` / `cloud-sdk-aws` 1.0.38-SNAPSHOT (was AWS SDK v1 1.12.720) |
| Messaging | SQS (receive/send/delete), SNS (publish) via `shared` adapters |
| Storage | S3 workspace (read) via `shared` adapter |
| Parameters | SSM Parameter Store (Network Services credentials, decrypted) via `CloudParameterStore` |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | Network Services clients (incl. its own `AuthClient`) and `ParameterStoreModule` (pass-through mode included) stay in `shared` (Tier 3); SSM is backed by `CloudParameterStore` | Assumption | Resolved | Unchanged behaviour |
| 3 | The module's `distributorrest.auth.AuthClient` is a singleton that caches one bearer token (`token` field) for all subscriptions (`AuthClient.java:19,27-31`). A token obtained from one subscriber's OAuth endpoint is reused for other subscribers until a 401 response triggers a refresh | Assumption | Resolved | Existing behaviour, unchanged by this program |
| 4 | Redelivery timing depends on the queue's visibility timeout (not set by the code). One message can take about 3 x (60 s connect + 60 s read) of POST attempts plus token calls | Assumption | Open | Unchanged (no visibility timeout sent, C3). Confirm the queue visibility timeout exceeds the worst-case POST time, or duplicates can be posted while the first attempt is still running |

---

## High Level Design

### Architectural Overview (ext)

```
 REST-delivery queue (SQS)
          │  shared back-pressure SQSListener (idle permits, wait 20 s, attrs=[failedAttempts])
          ▼
 AsyncDispatcher (maxNumberOfMessages threads) ─▶ DistributorTask
   ├─▶ shared workspace adapter getContent(bucket, fileName, ISO_8859_1)
   ├─▶ SubscriptionService (Network Services, cached) ─▶ RequestBuilder
   ├─▶ RestServiceClient.post ─▶ subscriber endpoint (bearer from AuthClient; retryer x3)   (unchanged)
   └─▶ EventLogger ─▶ shared SNS event publisher (CLOSE_WORKFLOW, raw JSON array)
          │
          ├─ RecoverableException / runtime failure ─▶ not deleted ─▶ SQS redelivery ─▶ queue redrive
          └─ NonRecoverableException / IOException ─▶ ErrorHandler ─▶ errors queue ─▶ delete
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Migrate AWS access only (through the `shared` adapters); leave the HTTP/OAuth client untouched | Smallest change; outbound contract untouched | — | ✅ |
| 2 | Also move the REST client to a commons HTTP client | Fewer libraries | Changes outbound behaviour; out of scope | ❌ |
| 3 | Call cloud-sdk `StorageClient.getContent` / `NotificationService.publish` directly | Fewer layers | Breaks C1 (wire parity and exception mapping enforced in `shared`) | ❌ |

### Data Flow — Before vs After (ext)

**Before:** v1 `AmazonSQS` receive → `S3WorkspaceService.getContent(.., ISO_8859_1)` → Network Services + Jersey POST → `SNSEventPublisher` (v1).

**After:** `shared` back-pressure listener over `MessagingClient<String>` → `shared` workspace adapter `getContent(.., ISO_8859_1)` over `StorageClient` → Network Services + Jersey POST (unchanged) → `shared` SNS event publisher over `NotificationService`.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `ExternalServicesModule` | Drops the v1 SQS/S3/SNS builders; installs the `shared` v2 module (one client per role from the C3 profile, `ManagedCloudResource` lifecycle). `ParameterStoreModule` (shared) backed by `CloudParameterStore`. Jersey `RestClient` (connect/read timeout), `RestRetry` retryer and both `AuthClient` bindings unchanged |
| 2 | `DistributorModule` | Listener, dispatcher, task factory, `EventPublisher` and `WorkspaceService` from the `shared` v2 module |
| 3 | `DistributorApplication` | `initialize()` registers the commons-based config command instead of the shared one; config files unchanged. S3 config source via the `shared` bootstrap provider. No health checks are registered today, and none are added |
| 4 | `DistributorTask` | SQS message type → SDK-neutral queue message from `shared`; `MetaData` / `Event` / `EventLogger` unchanged; ISO-8859-1 read unchanged |
| 5 | `RestServiceClient`, `RequestBuilder`, `distributorrest.auth.AuthClient`, `RetryerBuilder` | Unchanged |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive, delete, send to errors queue (non-recoverable path) | AWS SDK 2.x via `shared` adapters |
| S3 | Read payload; put error annotations (non-recoverable path) | AWS SDK 2.x via `shared` workspace adapter |
| SNS | Publish close-run events | AWS SDK 2.x via `shared` event publisher |
| SSM Parameter Store | Read Network Services client credentials (decrypted) | AWS SDK 2.x via `CloudParameterStore` |

#### DynamoDB Changes (ext)

None.

### UI

N/A

### API Architecture

No new or changed inbound API. `distributor-rest` is an outbound HTTP client; the call below is listed for completeness and is unchanged.

| Use Case | API | Body | Method<br/>(GET/POST/PUT/DELETE) | Query Parameter | Access Privilege<br/>(Admin/Non-Admin User) | Authorization — (Yes/No)<br/>*(If Yes, mention the approach)* | Authentication — (Yes/No)<br/>*(If Yes, mention the approach)* | Remarks |
|---|---|---|---|---|---|---|---|---|
| Deliver payload to subscriber (outbound) | Subscriber endpoint from the subscription | Workspace payload (unchanged) | POST | None | N/A (system) | N/A | Yes — OAuth bearer token from the subscriber's OAuth endpoint (Basic client credentials) (unchanged) | No change |

---

## Configuration

### Component-Level Configuration

Application `initialize()` registers the commons-based config command instead of the shared one; config files unchanged. `conf/distributor-rest.yaml` keys (including `restClientConfig.connectTimeout` / `readTimeout`) and `.properties` overrides are unchanged.

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change. Same queues, topic, bucket and SSM parameter names.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to application log messages or levels. `distributor-rest.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3/SNS calls at INFO), as the shared design requires.

### Event Publishing (ext)

Unchanged: `CLOSE_WORKFLOW` with `pickupQueue` and `E2openTransactionId` tokens on success. The non-recoverable failure event has a null sub-type. Same topic, raw JSON array body, no subject or message attributes.

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
| Other file migration | No | None |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change: same POST to subscribers, same events, same redelivery behaviour.

### Performance (ext)

No material change expected; latency is dominated by the subscriber call (up to 3 attempts with 60 s connect / 60 s read timeouts). Five dispatcher threads are well below the 50-connection AWS client pools. S3 payload reads buffer the whole object, as today; the S3 client sets no API-call timeout, matching v1, which did not bound body reads (`shared` client profile).

### Deployment (ext)

Rolling restart as part of the single AppianWay release. No data migration. A single service can be rolled back to its previous build alone, because formats are unchanged.

---

## Resiliency

Unchanged, as implemented today:

- `RestServiceClient.post` wraps every failure in `RecoverableException` (`RestServiceClient.java:70-71`). That includes non-`SUCCESS` responses, which first raise `NonRecoverableException` at `:67`. `DistributorTask` catches only `NonRecoverableException | IOException` (`DistributorTask.java:89`), so POST, S3 and Network Services failures escape `process()`. `AbstractTask.execute` then logs them and does not delete the message. SQS redelivers it after the queue visibility timeout, and the queue redrive policy moves it to the DLQ. The `failedAttempts` / `DelaySeconds` retry path is not used by this module.
- Inside one attempt: the Jersey retryer makes up to 3 attempts with exponential wait from 100 ms. It does not retry HTTP 400/404. A 401 triggers `AuthClient.newToken` before the retry, and the token call itself makes up to 2 attempts.
- The POST is not idempotent: a redelivery after a successful POST (for example, event publish or delete failed) posts again (Open Issue 4).
- With cloud-sdk, the `shared` adapters still raise `RecoverableException` (runtime) for S3/SNS/SQS failures (C9). Those keep escaping `process()` exactly as v1 `RecoverableException` did.
- Hystrix (`externalwrapper`) is not used by this module.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files.

---

## Impact on Tools

None.

---

## Impact on Other Components

- Subscriber endpoints: None — request body, headers and authentication unchanged.
- Event consumers (`event-writer`, `ingestor`): None — events unchanged.
- Upstream `transformer` (routes to this queue): None — input contract unchanged.

---

## Backwards Compatible

**Yes.**

| Question | Answer |
|----------|--------|
| Outbound POST body / headers / auth | Identical — payload decoded as ISO-8859-1 and sent as a Jersey `application/json` string entity, as today |
| Events | Identical — same `Event` JSON array and tokens (C1, C4) |
| Error codes / failure flow | Identical |
| SSM parameters | Same names, decrypted |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

Versions come from commons; the module declares no versions for commons-managed libraries. Jersey and guava-retrying are unchanged.

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:cloud-sdk-aws` (brings `cloud-sdk-api`) | — | 1.0.38-SNAPSHOT (via `shared`) | New | AWS SDK 2.x |
| `com.amazonaws:aws-java-sdk-sqs` | 1.12.720 | removed as direct dependency | Removal | Replaced by AWS SDK 2.x |

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `DispatcherTaskTest` (extended) | ISO-8859-1 read; POST entity equals the decoded content; tokens; no-subscription path (no S3 read, empty transaction id); `NonRecoverableException` → `ErrorHandler`; `RecoverableException` escapes and the message is not deleted |
| 2 | `DistributorWireCompatibilityTest` | Golden fixtures: `CLOSE_WORKFLOW` events (with and without transaction id) and the non-recoverable failure event byte-identical to v1 output |
| 3 | `ExternalServicesModuleTest` (updated) | `shared` v2 module, parameter store, `RestClient` timeouts and `RestRetry` bound |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Task | `DispatcherTaskTest` | Unit, mocked `shared` adapters |
| HTTP | `RestServiceClientTest`, `RequestBuilderTest`, `RetryerBuilderTest` | Unchanged |
| Wiring | `DistributorModuleTest`, `ExternalServicesModuleTest` | Guice injector |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT boot; post one REST-delivery message | Subscriber receives the same POST; same event as the v1 build |

### Existing Test Impact (ext)

Existing tests (JUnit 4) are retargeted from v1 types to `shared` v2 / cloud-sdk types; assertions on content are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: a POST attempt never outlives the queue visibility timeout.

---

## Risks

**Key Risks**

- Charset drift on the payload read — mitigated by keeping ISO-8859-1 and a test on the charset argument.
- JSON output drift if code bypasses `shared` `Json` — mitigated by C1 and golden-fixture tests.
- Exception classification drift that would make a failure suddenly hit `ErrorHandler` (errors queue) instead of redelivery, or the reverse. Mitigated by the `shared` mapping to runtime `RecoverableException` (C9) and test 1.
- Duplicate POSTs on redelivery or when visibility timeout is shorter than the worst-case POST time (existing; Open Issue 4).
- One cached bearer token shared across subscriptions in `AuthClient` (existing behaviour, unchanged; Open Issue 3).

---

## Dependencies

**Major Dependencies**

- `shared` re-based on commons, including Network Services clients and parameter store.
- `mercury-services-commons` 1.0.38-SNAPSHOT.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | N | No UI |
| 2 | Use of new services/ports | N | Same AWS services and resources; same subscriber endpoints; same ports |
| 3 | Authentication changes | N | AWS credentials from the default provider chain / task role, as today; subscriber OAuth unchanged (the existing single cached token is described in Open Issue 3) |
| 4 | New/changed encryption | N | No change; TLS to AWS and subscriber endpoints |
| 5 | Changes in the way data is transmitted | Y | AWS client library changes from SDK v1 to SDK 2.x. Endpoints, credentials and payloads unchanged; outbound HTTP unchanged |
| 6 | Changes in the way/location data is being stored | N | No data stored beyond error annotations, as today |
| 120 | New API implementation / change of existing APIs (Please fill the API arch table) | N | None; outbound call listed in the API table, unchanged |
| 124 | New / Change in existing file upload functionality | N | None |
| 125 | New / Change in integration within e2open or third-party apps | N | Subscriber integration unchanged |
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
