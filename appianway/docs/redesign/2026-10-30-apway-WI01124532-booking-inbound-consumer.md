# WI01124532 watermill booking-inbound-consumer — AWS SDK 2.x (cloud-sdk) Upgrade

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

`booking-inbound-consumer` reads the booking Watermill topic over a gRPC `consumeForever` stream. For each upsert in a `BookingChangeEvent` whose state is request, amend or cancel it:

1. transforms the protobuf booking into a `BookingRequestContract` (`BookingTransformer`) and serialises it with the module-local `ObjectMapper`;
2. writes the contract JSON to the workspace bucket at `{rootWorkflowId}/{uuid}`;
3. sends a `MetaData` message (projections `originalFileName`, `source=watermill`, pickup time, `contextCode=requestBooking`) to the booking inbound queue;
4. publishes one `CLOSE_RUN` lineage event (sub-type `START_WORKFLOW`; the contract JSON is carried in the `TransformedPayload` token). A `TransformationException` produces a `CLOSE_WORKFLOW` failure event and no S3/SQS output.

After all upserts of a change event are handled, the offset is updated in memory and flushed to `${environment}_watermill_offset` every `offsetUpdateDelay` minutes, on `onError` and on shutdown.

This change replaces the module's AWS SDK v1 clients (S3, SQS, SNS, SSM, DynamoDB) with `cloud-sdk` 1.0.38-SNAPSHOT through the `shared` Tier-2 adapters (workspace, SQS sender, SNS `EventPublisher`) and the Tier-1 parameter store, and moves the booking model from `booking:2.1.1.M` to `booking:3.0.0.M`. Offset persistence and the S3 upload come from the migrated `consumer-commons` (Watermill platform page). Outputs are unchanged (shared contract C1–C9).


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `watermill/booking-inbound-consumer` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` page; WI01124532 watermill consumer platform |

### Functional Requirements

1. Same topic, transformation, S3 object (key, body, `Content-Type`), SQS message and lineage events as today.
2. Same offset semantics as described on the platform page.

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in module sources and no `dynamo-client`.
2. The booking model moves to `booking:3.0.0.M` (AWS SDK 2.x model, Java 17 class files, POM with no dependencies).
3. Wire compatibility per shared contract C1–C9; the contract JSON stays byte-identical (open issue 3).
4. Keep JUnit 5.

### Acceptance Criteria

1. `mvn -pl watermill/booking-inbound-consumer -am clean verify` is green.
2. Golden-fixture test: `BookingTransformer` output for the four test fixtures (`request_proto.json`, `max_request.json`, `request_min.json`, `cancel_proto.json`), serialised by the module mapper with `booking:3.0.0.M`, is byte-identical to the 2.1.1.M output; `MetaData` and `Event` JSON identical.
3. No `com.amazonaws` imports in module sources and no `dynamo-client` in `mvn dependency:tree`.
4. INT boot resumes from the stored offset, and one booking flows end to end as before.

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
| Messaging | SQS send, SNS publish |
| Storage | S3 put |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | The platform modules (`consumer-commons`) migrate in the same release | Assumption | Resolved | Single release |
| 2 | `booking:2.1.1.M` carries AWS SDK v1 / `dynamo-client` types (`BookingDetail` implements `DynamoHashAndSortKey`, `DateToEpochSecond` implements the v1 `DynamoDBTypeConverter`); once v1 is removed those classes cannot load. `booking:3.0.0.M` removes them. Verified: all 68 model classes imported by the module exist in 3.0.0.M; the transformer runs against 3.0.0.M without any AWS SDK on the path | Decision | Resolved | Move to `booking:3.0.0.M`; the long exclusion list on the dependency is dropped |
| 3 | Contract JSON with 3.0.0.M. Verified by running `BookingTransformer` on the four test fixtures with both jars and the module mapper (effective inclusion `NON_NULL` — the second `setSerializationInclusion` call overrides `NON_EMPTY` — and `WRITE_EMPTY_JSON_ARRAYS=false`): the only difference is three added keys `"cargoRoRoIndicator":false`, `"cargoBreakBulkIndicator":false`, `"viaExternalLink":false`; with them removed the output is byte-identical, key order included. New `String` fields (`DangerousGoods.variantDescription/applicableReg/variant`, `DGSDetails.variantCode/variation/applicableReg`) are null and omitted. The new `Contract` default `isReinstated()` is not serialised | Open Issue | Resolved | Mix-in `@JsonIgnoreProperties({"cargoRoRoIndicator","cargoBreakBulkIndicator","viaExternalLink"})` on `BookingRequestContract`, registered on the module mapper. Not "omit `false`" globally: existing primitive booleans such as `cargoHazardousIndicator:false` are in today's output and must stay. Ignoring is identical in every case because 2.1.1.M has no such properties and the transformer never sets them. The same string feeds the `TransformedPayload` event token, so the event is covered too |
| 4 | `booking:3.0.0.M` is not resolvable from the corporate Maven repository (local resolution attempts failed); it exists only in mercury-services module `lib/` file repositories. 2.1.1.M is vendored today in this module's `lib/` repository | Open Issue | Resolved | Vendor 3.0.0.M into this module's `lib/` file repository, as 2.1.1.M is today |
| 5 | Today's S3 client is the v1 default (`AmazonS3ClientBuilder.standard().build()`: connect 10 s, socket 50 s, 3 retries), not the shared S3 profile. The `shared` S3 profile would change this to connect 1 s, socket 5 s | Decision | Resolved | Keep the current values: the module passes a `shared` client-profile override for S3 (connect 10 s, socket 50 s, 3 retries, no API-call timeout), with a code comment naming the v1 default it reproduces |
| 6 | `retryCount` is an instance field and each reconnect creates a new `BookingInboundConsumer` with `retryCount = 1` (`BookingInboundConsumer.java:55,223`), so `maxRetry` is never reached for `NonRetryableException` | Finding | Resolved | Kept as is: existing behaviour is not changed by this program; a disabled known-defect test covers it |

---

## High Level Design

### Architectural Overview (ext)

```
 booking topic ──▶ BookingInboundConsumer.onNext ──▶ BookingTransformer ──▶ contract JSON (module mapper + mix-in)
                                    │
          ┌─────────────────────────┼────────────────────────────────┐
          ▼                         ▼                                ▼
  S3 {rootWorkflowId}/{uuid}   SQS booking inbound queue        SNS lineage CLOSE_RUN
  consumer-commons             shared SQS sender                shared EventLogger ->
  S3PublishService ->          (raw MetaData JSON,              shared SNS EventPublisher
  shared WorkspaceService      no attributes)                   (raw JSON array)
  putObject(String)
                                    │ after the whole change event
                                    ▼
             OffsetUtil (memory) ──▶ OffsetUpdateScheduler / onError / stop ──▶ WatermillOffsetRepository
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Keep `booking:2.1.1.M` | No model change | v1-typed classes on the path; fail to load once v1 is gone | ❌ |
| 2 | `booking:3.0.0.M` + `@JsonIgnoreProperties` mix-in for the three new properties | No v1 types; aligned with upgraded booking; JSON identical (verified) | Mix-in to maintain | ✅ |
| 3 | `booking:3.0.0.M` + mapper-wide "omit false booleans" | Generic | Drops `false` booleans present today (for example `cargoHazardousIndicator`) — wire change | ❌ |
| 4 | Copy the model POJOs into AppianWay | Removes the cross-repo dependency | Large copy; drift risk | ❌ |

### Data Flow — Before vs After (ext)

**Before:** v1 `AmazonS3` (defaults), `AmazonSQS` (`sqs_sender`), `AmazonSNS` (`sns_publish`), SSM default client and v1 DynamoDB client/mapper bound in `ExternalServicesModule` / `WatermillConsumerModule`. `shared` `SQSClient`, `SNSEventPublisher`, `EventLogger`, `ParameterSupplier`.

**After:** the `shared` v2 Guice module supplies the cloud-sdk clients (one per role, C3 profile, `ManagedCloudResource`) behind the Tier-2 adapters; SSM via `CloudParameterStore`; the offset via the platform `WatermillOffsetRepository`. `MetaData`, `Event`, `EventLogger`, `Json`, the transformer and the module mapper settings are unchanged.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `BookingInboundConsumerApplication` | `initialize()` registers the commons-based config command instead of the shared one; the S3 configuration source provider is the shared v2 one. Config files unchanged |
| 2 | `ExternalServicesModule` | Remove the v1 `AmazonSNS`/`AmazonS3`/`AmazonSQS` bindings and the v1 `ParameterStoreModule`; install the shared v2 module. `ParameterSupplier` (same interface) is backed by `CloudParameterStore.getParameters(userIdKey, passwordKey)`: one `GetParameters` call, `WithDecryption=true`, unknown name fails startup (C7). `NetworkRetryerModule` and the Jersey client binding are unchanged (not used by the consumer) |
| 3 | `WatermillConsumerModule` | Drop the v1 DynamoDB client, mapper and the module-local table-name resolver. Bind `WatermillOffsetRepository` on `environment + "_watermill_offset"` (platform page). `EventPublisher` is the shared v2 SNS publisher on the same topic (shared `Json`, log-and-continue on failure as today). `ConsumptionRequest` and `OffsetUtil` providers unchanged |
| 4 | `BookingInboundConsumerConfiguration` | `DynamoDbConfig` → `WatermillDynamoDbConfig`. YAML unchanged |
| 5 | `BookingInboundConsumer` | `SQSClient` → shared SQS sender adapter `sendMessage(queueUrl, metaData.toJsonString())` (raw body, no attributes, no delay). S3 via `S3PublishService.uploadToS3(bucket, key, json)` → shared workspace adapter `putObject(String)` (UTF-8, `text/plain`). The mapper registers the mix-in (open issue 3); other settings unchanged |
| 6 | `grpc/AuthCredentials`, `util/ConsumerInitUtil` | No change. Channel: TLS to the configured host/port, keep-alive 30 s / timeout 20 s, idle 30 min; no `maxInboundMessageSize` override (gRPC default 4 MiB, as today) |
| 7 | `pom.xml` | Remove `dynamo-client`; `booking` 2.1.1.M → 3.0.0.M (no exclusions needed); add the 3.0.0.M jar to the module `lib/` repository (open issue 4); library versions from commons (C6) |
| 8 | Transformers and type maps | No source change (compile against 3.0.0.M; `DangerousGoods` is built with the no-arg constructor and setters) |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| S3 | `PutObject` contract JSON (workspace adapter, `text/plain`) | AWS SDK 2.x via cloud-sdk |
| SQS | `SendMessage` `MetaData` | AWS SDK 2.x via cloud-sdk |
| SNS | `Publish` lineage events | AWS SDK 2.x via cloud-sdk |
| SSM Parameter Store | `GetParameters` Watermill credentials, decrypted, at startup | AWS SDK 2.x via cloud-sdk |
| DynamoDB | Offset `GetItem` / `PutItem` (initialise) / `UpdateItem` | AWS SDK 2.x via cloud-sdk |

#### DynamoDB Changes (ext)

| Table | Partition Key | Sort Key | GSIs | Annotation Class |
|-------|--------------|----------|------|-----------------|
| `${environment}_watermill_offset` — **No change** | `topicName` (S) — No change | None | None | `consumer-commons` `WatermillOffset` |

One row, keyed by the configured `topicName`. Attributes unchanged: `offset` (N), `readDateTime` (N, epoch seconds). The v2 bean must map the key getter to `topicName` (platform page).

### UI

N/A

### API Architecture

N/A — no API added or changed.

---

## Configuration

### Component-Level Configuration

No change. `conf/booking-inbound-consumer.yaml` keys are unchanged (HTTP port `server.connector.port`, default 8085).

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to log messages or levels. `booking-inbound-consumer.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3 calls at INFO, and `com.inttra.mercury` is at DEBUG in this file), as the shared design requires.

### Event Publishing (ext)

Same `CLOSE_RUN` events (sub-type `START_WORKFLOW` on success, `CLOSE_WORKFLOW` on transformation failure) on the same topic: raw JSON array, no subject, no attributes (C1, C4).

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
| Other file migration | No | Outputs unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change. S3 timeouts keep today's v1 default values through a client-profile override (open issue 5).

### Performance (ext)

Unchanged: each booking costs one S3 put, one SQS send and one SNS publish, synchronously on the gRPC callback thread, so throughput is bound by their latency. Clients are singletons (no per-call client creation).

### Deployment (ext)

Restarted with the platform modules as part of the single AppianWay release. Rollback is safe (v1 and v2 read each other's offset row).

---

## Resiliency

Behaviour is unchanged by this design; documented so that tests preserve it:

- S3 or SQS failure (after SDK retries): `onNext` throws `NonRetryableException`, the stream is cancelled and `onError` flushes the in-memory offset (last fully processed change event), waits `retryDelay` s and reconnects from stored offset + 1. The failed change event is reprocessed: upserts before the failure are sent again with new random `rootWorkflowId`s (downstream duplicates), and an S3 object written before a failed SQS send stays orphaned.
- Because of open issue 6 a poison record is retried forever every `retryDelay` s.
- SNS failure is logged and swallowed by the publisher; the booking still flows.
- If the offset write in `onError` fails, the exception escapes `onError`, no reconnect happens and the process stays up without consuming (no health check covers the stream).
- Crash or kill: up to `offsetUpdateDelay` minutes of change events are replayed (new workflow ids, not idempotent). On graceful stop the scheduler flushes but the stream is not cancelled first, so records processed after the flush are replayed.
- cloud-sdk failures are wrapped in `RecoverableException` by the adapters (C9); here every exception becomes `NonRetryableException`, as today.

---

## Temporary object cleanup, temporary files cleanup

N/A

---

## Impact on Tools

None.

---

## Impact on Other Components

- Booking pipeline readers of the queue and workspace (mercury-services booking): None — identical `MetaData` and contract JSON.
- Lineage consumers (event-writer, ingestor): None — identical events.
- mercury-services `booking` artifact: None — not modified; version `3.0.0.M` is consumed.

---

## Backwards Compatible

**Yes.** Shared contract C1–C9 applies.

| Question | Answer |
|----------|--------|
| S3 contract JSON / key / `Content-Type` | Identical — verified against fixtures with the mix-in; key `{rootWorkflowId}/{uuid}`; UTF-8, `text/plain` (C2) |
| SQS `MetaData` | Identical — same queue, raw body, no attributes, no delay (C3) |
| SNS events | Identical (C1, C4) |
| Offset row | Identical (C5) |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:cloud-sdk-api` / `cloud-sdk-aws` / `commons` | — | 1.0.38-SNAPSHOT | New | AWS SDK 2.x |
| `com.inttra.mercury:booking` | 2.1.1.M | 3.0.0.M | Upgrade | Model without AWS SDK v1 types |
| `com.inttra.mercury:mercury-shared` | 1.0 | 1.0 | Upgrade | Re-based on commons |
| `com.inttra.mercury:dynamo-client` | 1.0 | removed | Removal | v1 DynamoDB mapper repository |
| `com.amazonaws:aws-java-sdk-*` | 1.12.720 | removed | Removal | No longer direct or via `shared` (may remain transitive via `cloud-sdk-aws` until removed upstream) |

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `BookingContractCompatibilityTest` | The four fixtures through `BookingTransformer` + module mapper equal golden files produced with 2.1.1.M; the three new keys absent; existing `false` booleans present |
| 2 | `BookingWireCompatibilityTest` | Golden `MetaData` and `Event` JSON (incl. `TransformedPayload` token) |
| 3 | `BookingInboundConsumerTest` (extended) | S3 key and `text/plain` via the workspace adapter; SQS body with no attributes; offset updated only after all upserts |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT: swap the v1 build for v2 | Resumes at stored offset + 1. Booking processed downstream as before |

### Existing Test Impact (ext)

JUnit 5 tests are retargeted to cloud-sdk types and fakes. Assertions on outputs are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: the retry count of a poison record is not reset by a reconnect.

---

## Risks

**Key Risks**

- Contract JSON drift from `booking:3.0.0.M` — mitigated by `@JsonIgnoreProperties` on the new properties and fixture goldens from 2.1.1.M.
- `booking:3.0.0.M` availability for CI builds — open issue 4.
- Duplicate bookings on replay (crash, reconnect after a partial change event) — existing behaviour; consumers of the queue are not idempotent on `rootWorkflowId`. Follow-up: idempotent workspace key or offset flush per change event.
- Poison record retried forever (open issue 6) and consumer stall when the `onError` offset write fails — existing; follow-up: keep the retry counter across observers and catch offset-write failures in `onError`.

---

## Dependencies

**Major Dependencies**

- WI01124532 Watermill consumer platform (`consumer-commons`).
- `shared` re-based on commons; `mercury-services-commons` 1.0.38-SNAPSHOT.
- mercury-services `booking:3.0.0.M`.

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
