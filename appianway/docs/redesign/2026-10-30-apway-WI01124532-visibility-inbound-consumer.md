# WI01124532 watermill visibility-inbound-consumer — AWS SDK 2.x (cloud-sdk) Upgrade

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

`visibility-inbound-consumer` runs three Watermill gRPC stream consumers in one process, each with its own offset row, `OffsetUtil` and `OffsetUpdateScheduler`:

| Consumer | Offset row key (config) | Workspace payload | Queue (config) | `messageType` projection |
|---|---|---|---|---|
| `VisibilityInboundConsumer` | `topicName` | `ContainerEventSubmission` (visibility model) | `shippeoInboundQueueUrl` | `ShippeoContainerEvent` |
| `CargoVisibilitySubscriptionConsumer` | `subscriptionTopicName` | module-local `CargoVisibilitySubscription` | `cargoVisibilitySubscriptionQueueUrl` | `CargoVisibilitySubscription` |
| `CargoVisibilityEventConsumer` | `eventTopicName` | module-local `model.ContainerEvent` | `cargoVisibilityEventQueueUrl` | `CargoVisibilityEvent` |

For each upsert a consumer writes the payload JSON to `{rootWorkflowId}/{workflowId}`, sends `MetaData` to its queue, always writes the raw protobuf JSON to `{rootWorkflowId}/{workflowId}_proto` and publishes one `CLOSE_WORKFLOW` lineage event. When a change event with more than one upsert fails at batch level, it also writes `{rootWorkflowId}/{rootWorkflowId}_proto` and a batch event. The offset is updated in memory after the whole change event.

This change replaces the module's AWS SDK v1 clients (S3, SQS, SNS, SSM, DynamoDB) with `cloud-sdk` 1.0.38-SNAPSHOT through the `shared` Tier-2 adapters and the Tier-1 parameter store, and moves the visibility model from `visibility:1.0.M` to `visibility:2.0.M`. Offset persistence and the S3 upload come from the migrated `consumer-commons` (Watermill platform page). Outputs are unchanged (shared contract C1–C9).


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `watermill/visibility-inbound-consumer` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` page; WI01124532 watermill consumer platform |

### Functional Requirements

1. Same three topics, three offset rows and three offset schedulers.
2. Same S3 objects (keys, bodies, `Content-Type`), SQS `MetaData` messages and lineage events as today.
3. Keep the gRPC `maxInboundMessageSize` of 50 MiB (`50 * 1024 * 1024`, `ConsumerInitUtil`).

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in module sources and no `dynamo-client`.
2. The visibility model moves to `visibility:2.0.M` (AWS SDK 2.x model built from mercury-services `visibility-commons`, Java 17 class files, POM with no dependencies).
3. Wire compatibility per shared contract C1–C9; the container-event JSON stays byte-identical apart from set ordering that is already unstable today (open issue 4).
4. Keep the existing mixed test stack (JUnit 4 and JUnit 5 classes as they are today).

### Acceptance Criteria

1. `mvn -pl watermill/visibility-inbound-consumer -am clean verify` is green.
2. Golden-fixture tests: `ContainerEventTransformer` output for `shippeo_proto.json` and `shippeo_proto_1.json`, serialised by the consumer mapper with `visibility:2.0.M`, equals the 1.0.M output (`references` compared as a set); subscription and event payloads, `MetaData` and `Event` JSON identical.
3. Each of the three offset rows is read and updated independently. Parity is covered by the platform IT.
4. No `com.amazonaws` imports in module sources and no `dynamo-client` in `mvn dependency:tree`.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |
| ION-15497 | gRPC max inbound message size 50 MiB | Story (prior, preserved) |

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
| 2 | `visibility:1.0.M` carries `dynamo-client` / v1 types (`ContainerEvent`, `ContainerEventOutbound` implement `DynamoHashKey` / `DynamoHashAndSortKey`; v1 `DateToEpochSecond`). `visibility:2.0.M` removes them. Verified: all 14 model classes the module imports exist in 2.0.M; among them only `TransportationDetail` (new field) and `ReferenceType` (new constants) differ; `ContainerEventSubmission` is unchanged | Decision | Resolved | Move to `visibility:2.0.M` |
| 3 | `TransportationDetail` gains the primitive `transportationDetailsPresent`. Verified by running `ContainerEventTransformer` on the test fixtures with both jars and the consumer mapper (value inclusion `NON_NULL`, content `NON_EMPTY`, so primitives are written): 2.0.M adds `"transportationDetailsPresent":false` inside `transportationDetails`; nothing else changes. Only `VisibilityInboundConsumer` serialises a visibility-model type; the subscription and event consumers serialise module-local classes and are unaffected | Open Issue | Resolved | Mix-in `@JsonIgnoreProperties("transportationDetailsPresent")` on `TransportationDetail`, registered on the `VisibilityInboundConsumer` mapper only. Not "omit `false`": `Reference.ignoreForOutbound:false` is in today's output. Ignoring is identical in every case because 1.0.M has no such property and the transformer never sets it (built via the Lombok builder) |
| 4 | `ContainerEventSubmission.references` is a `HashSet<Reference>`; Lombok `hashCode` includes the `ReferenceType` enum, whose hash is the JVM identity hash. The array order in today's JSON therefore depends on the JVM run, not on the data (observed: same input, different order between two classpaths) | Finding | Resolved | Not a regression. Golden tests compare `references` as a set; downstream already receives varying order |
| 5 | `visibility:2.0.M` is available only from mercury-services module `lib/` file repositories, not from the corporate Maven repository; 1.0.M is vendored today in this module's `lib/` repository | Open Issue | Resolved | Vendor 2.0.M into this module's `lib/` file repository, as 1.0.M is today |
| 6 | Today's S3 client is the v1 default (connect 10 s, socket 50 s, 3 retries). The `shared` S3 profile would change this to connect 1 s, socket 5 s. Payloads can approach the 50 MiB gRPC limit | Decision | Resolved | Keep the current values: the module passes a `shared` client-profile override for S3 (connect 10 s, socket 50 s, 3 retries, no API-call timeout), with a code comment naming the v1 default it reproduces |

---

## High Level Design

### Architectural Overview (ext)

```
 main topic         ──▶ VisibilityInboundConsumer           ─┐  S3 payload + _proto: consumer-commons S3PublishService
 subscription topic ──▶ CargoVisibilitySubscriptionConsumer ─┼─▶   -> shared WorkspaceService putObject(String), text/plain
 event topic        ──▶ CargoVisibilityEventConsumer        ─┘  SQS MetaData: shared SQS sender (raw, no attributes)
                                                                SNS CLOSE_WORKFLOW: shared EventLogger -> SNS EventPublisher
   each consumer ──▶ ConsumerManager (reconnect) ; own OffsetUtil + OffsetUpdateScheduler ──▶ WatermillOffsetRepository
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Keep `visibility:1.0.M` | No model change | v1 / `dynamo-client` types on the path | ❌ |
| 2 | `visibility:2.0.M` + `@JsonIgnoreProperties` mix-in on the main consumer mapper | No v1 types; aligned with upgraded visibility; JSON identical (verified) | Mix-in to maintain | ✅ |
| 3 | `visibility:2.0.M` + mapper-wide "omit false booleans" | Generic | Drops `ignoreForOutbound:false` present today — wire change | ❌ |

### Data Flow — Before vs After (ext)

**Before:** v1 `AmazonS3` (defaults), `AmazonSQS` (`sqs_sender`), `AmazonSNS` (`sns_publish`), SSM default client and v1 DynamoDB client/mapper in `ExternalServicesModule` / `WatermillConsumerModule`. `shared` `SQSClient`, `SNSEventPublisher`, `EventLogger`, `ParameterSupplier`.

**After:** the `shared` v2 Guice module supplies the cloud-sdk clients (one per role, C3 profile, `ManagedCloudResource`) behind the Tier-2 adapters; SSM via `CloudParameterStore`; offsets via the platform `WatermillOffsetRepository`. Module mappers, protobuf mappers, `ConsumerManager` and `ConsumerInitUtil` channel settings are unchanged.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `VisibilityInboundConsumerApplication` | `initialize()` registers the commons-based config command instead of the shared one; S3 configuration source provider is the shared v2 one. Config files unchanged. The three `OffsetUpdateScheduler` registrations are unchanged |
| 2 | `ExternalServicesModule` | Remove the v1 `AmazonSNS`/`AmazonS3`/`AmazonSQS` bindings and the v1 `ParameterStoreModule`; install the shared v2 module. `ParameterSupplier` backed by `CloudParameterStore.getParameters(userIdKey, passwordKey)` (one call, decrypted, unknown name fails startup — C7) |
| 3 | `WatermillConsumerModule` | Drop the v1 DynamoDB client, mapper and table-name resolver; bind `WatermillOffsetRepository` on `environment + "_watermill_offset"`. Shared v2 SNS `EventPublisher` on the same topic. The three named `ConsumptionRequest` and `OffsetUtil` providers are unchanged |
| 4 | `VisibilityInboundConsumerConfiguration` | `DynamoDbConfig` → `WatermillDynamoDbConfig`. YAML unchanged |
| 5 | Three consumers | `SQSClient` → shared SQS sender adapter `sendMessage(queueUrl, metaData.toJsonString())`; S3 via `S3PublishService` → shared workspace adapter `putObject(String)` (UTF-8, `text/plain`). `VisibilityInboundConsumer` mapper registers the mix-in (open issue 3); other mappers unchanged |
| 6 | `grpc/AuthCredentials`, `grpc/ConsumerManager` | No change |
| 7 | `util/ConsumerInitUtil` | No change: TLS channel, keep-alive 30 s / 20 s, idle 30 min, `maxInboundMessageSize(50 * 1024 * 1024)` |
| 8 | `pom.xml` | Remove `dynamo-client`; `visibility` 1.0.M → 2.0.M (open issue 5); library versions from commons (C6) |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| S3 | `PutObject` payload, `_proto` and batch `_proto` JSON (`text/plain`) | AWS SDK 2.x via cloud-sdk |
| SQS | `SendMessage` `MetaData` to three queues | AWS SDK 2.x via cloud-sdk |
| SNS | `Publish` lineage events | AWS SDK 2.x via cloud-sdk |
| SSM Parameter Store | `GetParameters` Watermill credentials, decrypted, at startup | AWS SDK 2.x via cloud-sdk |
| DynamoDB | Three offset rows: `GetItem` / `PutItem` (initialise) / `UpdateItem` | AWS SDK 2.x via cloud-sdk |

#### DynamoDB Changes (ext)

| Table | Partition Key | Sort Key | GSIs | Annotation Class |
|-------|--------------|----------|------|-----------------|
| `${environment}_watermill_offset` — **No change** (three rows, one per topic) | `topicName` (S) — No change | None | None | `consumer-commons` `WatermillOffset` |

Attributes unchanged: `offset` (N), `readDateTime` (N, epoch seconds). The v2 bean must map the key getter to `topicName` (platform page).

### UI

N/A

### API Architecture

N/A — no API added or changed.

---

## Configuration

### Component-Level Configuration

No change. `conf/visibility-inbound-consumer.yaml` keys are unchanged (HTTP port `server.connector.port`, default 8085).

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to log messages or levels. `visibility-inbound-consumer.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3 calls at INFO, and `com.inttra.mercury` is at DEBUG in this file), as the shared design requires.

### Event Publishing (ext)

Same `CLOSE_WORKFLOW` events on the same topic: raw JSON array, no subject, no attributes (C1, C4). On AWS failures the error tokens and annotations carry the exception stack trace, so their text changes with the SDK (error path only).

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
| Database schema | No | Offset rows unchanged |
| Property migration | No | Config keys unchanged |
| Other file migration | No | Outputs unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change on the success path. S3 timeouts keep today's v1 default values through a client-profile override (open issue 6).

### Performance (ext)

Unchanged: per upsert two S3 puts, one SQS send and one SNS publish, synchronously on the gRPC callback thread of that consumer; the three consumers run concurrently. The 50 MiB inbound limit is kept.

### Deployment (ext)

Restarted with the platform modules as part of the single AppianWay release. All three rows are flushed on shutdown. Rollback is safe.

---

## Resiliency

Behaviour is unchanged by this design; documented so that tests preserve it:

- Per-upsert S3 or SQS failure is caught: a failed `CLOSE_WORKFLOW` event and the `_proto` object are written and the offset still advances, so that upsert is not retried.
- A failure in the `finally` path (the `_proto` upload) escapes `onNext`; `ConsumerManager` flushes the offset, waits `retryDelay` s and reconnects from stored offset + 1. The change event is reprocessed, so earlier upserts are sent again with new workflow ids. No code throws `NonRetryableException`, so reconnects are unlimited (`resetRetryCount` is never called).
- If the offset write or the reconnect itself fails (for example a DynamoDB error), `ConsumerManager` only logs it; no stream remains and that consumer stops consuming while the process stays up (no health check covers the streams).
- The first reconnect does not close the channel created by the task (separate `ConsumerInitUtil` instance); later reconnects close their predecessor.
- Crash or kill replays up to `offsetUpdateDelay` minutes per topic.
- cloud-sdk failures are wrapped in `RecoverableException` by the adapters (C9); all are caught as `Exception` here, as today.

---

## Temporary object cleanup, temporary files cleanup

N/A

---

## Impact on Tools

None.

---

## Impact on Other Components

- Visibility readers of the queues and workspace (mercury-services visibility): None — identical `MetaData` and payload JSON.
- Lineage consumers: None.
- mercury-services `visibility` artifact: None — not modified; version `2.0.M` is consumed.

---

## Backwards Compatible

**Yes.** Shared contract C1–C9 applies.

| Question | Answer |
|----------|--------|
| S3 payloads / keys / `Content-Type` | Identical (verified for the container event with the mix-in; `references` order is unstable today, open issue 4). UTF-8, `text/plain` (C2) |
| SQS `MetaData` / SNS events | Identical (C1, C3, C4) |
| Offset rows | Identical (three rows, C5) |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:cloud-sdk-api` / `cloud-sdk-aws` / `commons` | — | 1.0.38-SNAPSHOT | New | AWS SDK 2.x |
| `com.inttra.mercury:visibility` | 1.0.M | 2.0.M | Upgrade | Model without v1 / `dynamo-client` types |
| `com.inttra.mercury:mercury-shared` | 1.0 | 1.0 | Upgrade | Re-based on commons |
| `com.inttra.mercury:dynamo-client` | 1.0 | removed | Removal | v1 DynamoDB mapper repository |
| `com.amazonaws:aws-java-sdk-*` | 1.12.720 | removed | Removal | No longer direct or via `shared` (may remain transitive via `cloud-sdk-aws` until removed upstream) |

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `VisibilityWireCompatibilityTest` | Golden fixtures for the three consumers' S3 payloads (container event `references` as a set; `transportationDetailsPresent` absent), `MetaData` and `Event` JSON |
| 2 | `WatermillConsumerModuleTest` (extended) | Three distinct offset keys resolved and initialised |
| 3 | `ConsumerInitUtilTest` (existing) | 50 MiB inbound limit still set |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT: swap the v1 build for v2 | All three consumers resume at stored offset + 1. Outputs unchanged |

### Existing Test Impact (ext)

JUnit 4 and JUnit 5 tests are retargeted from v1 mocks to cloud-sdk types and fakes. Assertions are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: a per-message S3 or SQS failure does not advance the offset, so the message is retried.

---

## Risks

**Key Risks**

- Container event JSON drift from `visibility:2.0.M` — mitigated by `@JsonIgnoreProperties` on the new properties and fixture goldens from 1.0.M.
- `visibility:2.0.M` availability for CI builds — open issue 5.
- A row mix-up between the three topics — mitigated by the module test on offset keys.
- Existing reliability gaps (not introduced here): upserts dropped after an S3/SQS failure, duplicates on change-event replay, silent consumer stall when the offset write or reconnect fails. Follow-up: retry per upsert before advancing the offset and reschedule a failed reconnect.

---

## Dependencies

**Major Dependencies**

- WI01124532 Watermill consumer platform (`consumer-commons`).
- `shared` re-based on commons; `mercury-services-commons` 1.0.38-SNAPSHOT.
- mercury-services `visibility:2.0.M`.

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
| 6 | Changes in the way/location data is being stored | N | Same buckets, keys, bodies and offset rows |
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
