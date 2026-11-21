# WI01124532 watermill itv-gps-consumer — AWS SDK 2.x (cloud-sdk) Upgrade

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

`itv-gps-consumer` reads the ITV GPS (`ITVShipmentStatusChangeEvent`) Watermill topic over a gRPC `consumeForever` stream. It writes each non-empty change event as protobuf JSON (`JsonFormat`, no insignificant whitespace) to the workspace bucket at `{YYYYMMdd}/{offset}.json`, updates the in-memory offset and flushes it to `${environment}_watermill_offset` every `offsetUpdateDelay` minutes and on shutdown (not on `onError`). The module publishes no SQS messages and no SNS events.

The module already uses the `consumer-commons` offset classes, `WatermillServiceConfig` and `S3PublishService`. It still has its own v1 `DynamoSupport`, a `create-table` command, unused `vo/DateToEpochSecond` and `vo/Expires`, an unused SNS binding, and v1 S3/SSM clients. This change replaces those with `cloud-sdk` 1.0.38-SNAPSHOT through the `shared` workspace adapter and the Tier-1 parameter store, on top of the migrated `consumer-commons` (Watermill platform page). Outputs are unchanged (shared contract C1–C9).


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `watermill/itv-gps-consumer` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` page; WI01124532 watermill consumer platform |

### Functional Requirements

1. Same topic, same S3 bucket, key (including the `YYYYMMdd` folder pattern) and JSON body.
2. Same offset semantics and offset row as today.
3. Keep the `create-table` CLI command.

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in module sources and no `dynamo-client`.
2. Wire compatibility per shared contract C1–C9.
3. Keep JUnit 4.

### Acceptance Criteria

1. `mvn -pl watermill/itv-gps-consumer -am clean verify` is green.
2. S3 test: key `{YYYYMMdd}/{offset}.json`, UTF-8 body, `text/plain`, bucket from `s3WorkspaceConfig.bucket`.
3. INT boot resumes from the row that the v1 build wrote.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard 5.0.2, Guice 7, gRPC / protobuf |
| Build | Maven, Java 17 |
| AWS SDK | AWS SDK 2.x via `cloud-sdk-api` / `cloud-sdk-aws` 1.0.38-SNAPSHOT (was AWS SDK v1 1.12.720) |
| Database | DynamoDB offset table (via `consumer-commons`) |
| Storage | S3 put |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | The platform modules (`consumer-commons`) migrate in the same release | Assumption | Resolved | Single release |
| 2 | An SNS client is bound in `ExternalServicesModule` but never used | Finding | Resolved | Binding removed; no SNS output today or after |
| 3 | `vo/DateToEpochSecond` and `vo/Expires` are referenced by nothing; the offset entity comes from `consumer-commons` | Finding | Resolved | Removed |
| 4 | The `YYYYMMdd` folder (commons `S3PublishService`) uses `Y` = week-based year with the JVM default locale's week rules, so the last days of December can get the next year's prefix. Kept for key parity | Finding | Resolved | Unchanged; the JVM default locale of the image must not change |
| 5 | Today's S3 client is the v1 default (`AmazonS3ClientBuilder.standard().build()`: connect 10 s, socket 50 s, 3 retries). The `shared` S3 profile would change this to connect 1 s, socket 5 s | Decision | Resolved | Keep the current values: the module passes a `shared` client-profile override for S3 (connect 10 s, socket 50 s, 3 retries, no API-call timeout), with a code comment naming the v1 default it reproduces |

---

## High Level Design

### Architectural Overview (ext)

```
 ITV GPS topic ──▶ ResponseConsumerObserver ── JsonFormat ──▶ consumer-commons S3PublishService
                              │                                -> shared WorkspaceService putObject(String)
                              │                                   (UTF-8, text/plain)
                              ▼
              consumer-commons OffsetUtil / OffsetUpdateScheduler ──▶ WatermillOffsetRepository
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Re-wire onto migrated `consumer-commons` and shared adapters | Minimal change | — | ✅ |
| 2 | Replace `create-table` with cloud-sdk `DynamoDbAdminCommand` | Tier 1 reuse | Command name is `dynamo-create`; CLI would change | ❌ |

### Data Flow — Before vs After (ext)

**Before:** local v1 `DynamoSupport` builds the client and mapper for the `consumer-commons` DAO; v1 S3 default client; `shared` v1 `ParameterStoreModule`.

**After:** `consumer-commons` `WatermillOffsetRepository` on the cloud-sdk DynamoDB client; the shared v2 module supplies the S3 client behind the workspace adapter and `CloudParameterStore` behind `ParameterSupplier`.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `dynamodb/DynamoSupport`, `vo/DateToEpochSecond`, `vo/Expires` | Removed |
| 2 | `WatermillGpsConsumerApplication` | `initialize()` registers the commons-based config command instead of the shared one; S3 configuration source provider is the shared v2 one. Config files unchanged |
| 3 | `ExternalServicesModule` | Remove the v1 S3 and unused SNS bindings and the v1 `ParameterStoreModule`; install the shared v2 module. `ParameterSupplier` backed by `CloudParameterStore.getParameters(userIdKey, passwordKey)` (one call, decrypted, unknown name fails startup — C7). `NetworkRetryerModule` / Jersey client unchanged (unused) |
| 4 | `WatermillConsumerModule` | Drop the v1 DynamoDB client, mapper and table-name resolver; bind `WatermillOffsetRepository`. The `ConsumptionRequest` and `OffsetUtil` providers are unchanged |
| 5 | `WatermillConsumerConfiguration` | `DynamoDbConfig` → `WatermillDynamoDbConfig`. YAML unchanged. `watermillServiceConfig` stays without `@Valid` (the commons class has `@NotNull` topic keys this YAML does not set) |
| 6 | `grpc/AuthCredentials`, `util/ConsumerInitUtil` | No change. Channel: TLS, keep-alive 30 s / 20 s, idle 30 min, gRPC default 4 MiB inbound limit |
| 7 | `dynamodb/command/DynamoTableCommand` | Name `create-table` kept; extends the commons-based config command. Re-implemented on the cloud-sdk DynamoDB client: create `${environment}_watermill_offset` if absent with hash key `topicName` (S), provisioned 10/10, SSE enabled = `sseEnabled`, no GSIs, no stream (as the v1 `generateCreateTableRequest`), then wait until active |
| 8 | `grpc/ResponseConsumerObserver` | No source change (uses the commons `S3PublishService` API) |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| S3 | `PutObject` JSON (`text/plain`) | AWS SDK 2.x via cloud-sdk |
| SSM Parameter Store | `GetParameters` Watermill credentials, decrypted, at startup | AWS SDK 2.x via cloud-sdk |
| DynamoDB | Offset `GetItem` / `PutItem` (initialise) / `UpdateItem`; optional `CreateTable` | AWS SDK 2.x via cloud-sdk |

#### DynamoDB Changes (ext)

| Table | Partition Key | Sort Key | GSIs | Annotation Class |
|-------|--------------|----------|------|-----------------|
| `${environment}_watermill_offset` — **No change** | `topicName` (S) — No change | None | None | `consumer-commons` `WatermillOffset` |

Attributes unchanged: `offset` (N), `readDateTime` (N, epoch seconds). The v2 bean must map the key getter to `topicName` (platform page).

### UI

N/A

### API Architecture

N/A — no API added or changed.

---

## Configuration

### Component-Level Configuration

No change. `conf/itv-gps-consumer.yaml` keys are unchanged (HTTP port `server.connector.port`, default 8085).

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to log messages or levels. `itv-gps-consumer.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3 calls at INFO, and `com.inttra.mercury` is at DEBUG in this file), as the shared design requires.

### Event Publishing (ext)

None — the module publishes no events.

---

## Metrics and Statistics

No change.

---

## Installer Changes

None.

---

## Impact on Current Application

### Migration Required

| Area | Needed? | Details |
|------|---------|---------|
| Database schema | No | Offset row unchanged |
| Property migration | No | Config keys unchanged |
| Other file migration | No | S3 objects unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change. S3 timeouts keep today's v1 default values through a client-profile override (open issue 5).

### Performance (ext)

Unchanged: one S3 put per change event, synchronously on the gRPC callback thread.

### Deployment (ext)

Restarted with the platform modules as part of the single AppianWay release. Rollback is safe.

---

## Resiliency

Behaviour is unchanged by this design; documented so that tests preserve it:

- Any exception while handling a record (for example an S3 failure) becomes `NonRetryableException`; `onError` reconnects after `retryDelay` s from stored offset + 1 with a new observer carrying the retry count. Non-retryable and connection-timeout errors stop the server after `maxRetry`; any error stops it after 100 consecutive retries. The counter resets after each successful record.
- `onError` does not flush the in-memory offset, so a reconnect replays up to `offsetUpdateDelay` minutes of records (also after a crash). Replays overwrite the same key on the same UTC day (offset-based key); duplicates appear only when a replay crosses midnight.
- If the offset read in `onError` fails, the exception escapes, nothing re-arms the stream and the process stays up without consuming (no health check covers the stream).
- cloud-sdk failures are wrapped in `RecoverableException` by the adapter (C9); here every exception becomes `NonRetryableException`, as today.

---

## Temporary object cleanup, temporary files cleanup

N/A

---

## Impact on Tools

None. `create-table` keeps its name and arguments.

---

## Impact on Other Components

- Readers of the ITV GPS workspace objects: None — identical objects.
- Other services: None.

---

## Backwards Compatible

**Yes.** Shared contract C1–C9 applies.

| Question | Answer |
|----------|--------|
| S3 key / body / `Content-Type` | Identical. UTF-8, `text/plain` (C2) |
| Offset row | Identical (C5) |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:cloud-sdk-api` / `cloud-sdk-aws` / `commons` | — | 1.0.38-SNAPSHOT | New | AWS SDK 2.x |
| `com.inttra.mercury:mercury-shared` | 1.0 | 1.0 | Upgrade | Re-based on commons |
| `com.inttra.mercury:dynamo-client` (via `consumer-commons`) | 1.0 | removed | Removal | v1 DynamoDB mapper repository |
| `com.amazonaws:aws-java-sdk-*` (via `consumer-commons` / `shared`) | 1.12.720 | removed | Removal | No longer direct or via `shared` (may remain transitive via `cloud-sdk-aws` until removed upstream) |

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `ResponseConsumerObserverTest` (extended) | Key `{YYYYMMdd}/{offset}.json`, body, `text/plain` via the workspace adapter, bucket from config |
| 2 | `DynamoTableCommandTest` (existing, retargeted) | Create-if-absent request: table name, key schema, throughput, SSE flag |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT: swap the v1 build for v2 | Resumes at stored offset + 1. Objects unchanged |

### Existing Test Impact (ext)

JUnit 4 tests are retargeted from v1 mocks to cloud-sdk mocks; `DynamoSupportTest` is removed with the class. Assertions are kept.

---

## Risks

**Key Risks**

- An offset regression — mitigated by the platform parity IT and an INT resume check.
- A drift in the S3 key date pattern — mitigated by keeping `YYYYMMdd` and asserting it in tests.
- Existing replay window on every reconnect (no offset flush in `onError`) and stall when the offset read fails — existing, unchanged by this design.

---

## Dependencies

**Major Dependencies**

- WI01124532 Watermill consumer platform (`consumer-commons`).
- `shared` re-based on commons; `mercury-services-commons` 1.0.38-SNAPSHOT.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | N | No UI |
| 2 | Use of new services/ports | N | Same AWS services and resources; same Watermill endpoint |
| 3 | Authentication changes | N | AWS credentials from the default provider chain / task role; Watermill credentials from Parameter Store, as today |
| 4 | New/changed encryption | N | No change; TLS to AWS endpoints |
| 5 | Changes in the way data is transmitted | Y | AWS client library changes from SDK v1 to SDK 2.x. Endpoints, credentials and payloads unchanged |
| 6 | Changes in the way/location data is being stored | N | Same bucket, keys, bodies and offset row |
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
