# watermill-publisher — Design & Architecture Document

> **Original prompt from Arijit Kundu (2026-04-29):**
> "Review the watermill-publisher and all its sub-modules. Explain in detail the design, components, data flow, architecture, integration points, key classes and dependencies of the module and all its sub-modules. Also analyze in detail how each one interacts with booking module and any other module in mercury-services. Also document what are AWS resources it uses and configured for all 4 environments - int, qa, cvt and prod. Create your analysis document in a .md document under watermill-publisher/docs/DESIGN-watermill-publisher.md. Include my prompt in the final analysis document."

---

## Table of Contents

1. [Overview](#1-overview)
2. [Repository Structure](#2-repository-structure)
3. [Technology Stack](#3-technology-stack)
4. [Module: watermill-commons](#4-module-watermill-commons)
5. [Module: watermill-booking](#5-module-watermill-booking)
6. [Module: watermill-booking-aperak](#6-module-watermill-booking-aperak)
7. [Module: watermill-cargo-visibility-subscription](#7-module-watermill-cargo-visibility-subscription)
8. [Cross-Cutting Architecture Patterns](#8-cross-cutting-architecture-patterns)
9. [Data Flow — End-to-End](#9-data-flow--end-to-end)
10. [Integration with the booking Module](#10-integration-with-the-booking-module)
11. [Integration with Other mercury-services Modules](#11-integration-with-other-mercury-services-modules)
12. [AWS Resources by Environment](#12-aws-resources-by-environment)
13. [Key Dependencies](#13-key-dependencies)
14. [Security & Credentials Management](#14-security--credentials-management)
15. [Error Handling & Resilience](#15-error-handling--resilience)

---

## 1. Overview

`watermill-publisher` is a **multi-module Maven parent project** inside `mercury-services`. Its purpose is to act as a **bridge between the INTTRA booking platform and the e2open Watermill event-streaming service**. It consumes booking-related change events from AWS SQS queues, enriches and transforms them into Protobuf messages, and publishes them to Watermill via **bidirectional gRPC streaming**.

There are three independently deployable sub-modules (services):

| Sub-module | Published Event Type | Primary Consumer |
|---|---|---|
| `watermill-booking` | `BookingChangeEvent` + `BookingConfirmationChangeEvent` | Watermill booking stream |
| `watermill-booking-aperak` | APERAK (Application Error And Acknowledgement) booking events | Watermill booking aperak stream |
| `watermill-cargo-visibility-subscription` | `INTTRACWSubscriptionRequestChangeEvent` | Watermill cargo visibility subscription stream |

All three share a common infrastructure library: `watermill-commons`.

---

## 2. Repository Structure

```
watermill-publisher/
├── pom.xml                                         ← parent POM (Java 17, packaging=pom)
│
├── watermill-commons/                              ← shared library (no main class)
│   ├── pom.xml
│   └── src/main/java/.../watermill/commons/
│       ├── config/      ← HealthCheckConfig, S3Config, SQSConfig, WatermillServiceConfig
│       ├── logging/     ← EventLogHandler (SNS event audit)
│       ├── s3/          ← S3WorkspaceService, WorkspaceService interface
│       ├── sqs/         ← SQSListener, SQSListenerClient, SQSClient, DeadLetterService
│       ├── support/     ← Json (Jackson utility)
│       ├── task/        ← Task (FunctionalInterface), TaskFactory, MetaData, MessageKeys
│       └── threaddispatcher/ ← Dispatcher interface, AsyncDispatcher, TaskMessage
│
├── watermill-booking/                              ← deployable JAR (uber-jar via shade)
│   ├── pom.xml
│   ├── lib/             ← local Maven repo: booking-{version}.jar (multiple versions)
│   ├── conf/
│   │   ├── int/config.yaml
│   │   ├── qa/config.yaml
│   │   ├── cvt/config.yaml
│   │   └── prod/config.yaml
│   └── src/main/java/.../watermill/booking/
│       ├── config/      ← WatermillBookingConfig, PublisherInitializer, injector
│       ├── grpc/        ← BookingGrpcClient, BookingConfirmGrpcClient, AuthCredentials
│       ├── model/       ← WatermillBookingDetail, BookingStateModel
│       ├── task/        ← WatermillBKTask (core processing)
│       ├── transformer/ ← BKProtobufTransformer, BKConfirmProtobufTransformer + sub-transformers
│       └── type/        ← 40+ TypeMap classes mapping booking enums to Protobuf enums
│
├── watermill-booking-aperak/                       ← deployable JAR (uber-jar via shade)
│   ├── pom.xml
│   ├── lib/             ← local Maven repo: booking-{version}.jar
│   ├── conf/            ← per-environment config.yaml (same 4 environments)
│   └── src/main/java/.../watermill/bookingaperak/
│       ├── config/      ← WatermillBookingAperakConfig, PublisherInitializer, injector
│       ├── grpc/        ← BookingAperakGrpcClient, AuthCredentials
│       ├── task/        ← WatermillBKAperakTask
│       └── transformer/ ← BKAperakTransformer, BKAperakPartyTransformer
│
└── watermill-cargo-visibility-subscription/        ← deployable JAR (uber-jar via shade)
    ├── pom.xml
    ├── lib/             ← local Maven repo: booking-{version}.jar + dynamo-client
    ├── conf/            ← per-environment config.yaml (same 4 environments)
    ├── README.md
    └── src/main/java/.../cargo/visibility/
        ├── config/      ← CargoVisibilitySubscriptionConfig, PublisherInitializer
        ├── dao/         ← CargoVisibilitySubscriptionDao, BookingDao, DynamoSupport
        ├── grpc/        ← CargoVisibilitySubscriptionGrpcClient, AuthCredentials
        ├── model/       ← CargoVisibilitySubscription, WatermillBookingDetail, 20+ model classes
        ├── networkservices/ ← NetworkParticipantServiceImpl, AuthClient, ParticipantService
        ├── task/        ← CargoVisibilitySubscriptionPublisherTask (core processing)
        └── util/        ← TransformationHelper
```

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Language | Java 17 |
| Application framework | Dropwizard (embedded Jetty) |
| Dependency injection | Google Guice |
| Build | Maven multi-module with `maven-shade-plugin` for uber-JAR |
| Messaging (inbound) | AWS SQS (long polling) |
| Messaging (outbound) | gRPC bidirectional streaming over TLS to e2open Watermill |
| Wire format | Protocol Buffers (proto3) |
| Object storage | AWS S3 (message payload staging area) |
| Secrets management | AWS SSM Parameter Store |
| Event notifications | AWS SNS |
| Database | AWS DynamoDB (cargo-visibility only) |
| Logging | SLF4J + Logback via Dropwizard |
| Code generation | Lombok, Protobuf Maven Plugin 0.6.1 |
| HTTP client | Jersey Client (for auth + network participant calls) |

---

## 4. Module: watermill-commons

### Purpose
A **shared infrastructure library** depended on by all three publisher sub-modules. It contains no `main()` class and is never deployed independently.

### Key Classes

#### `SQSListener` — [watermill-commons/src/main/java/.../sqs/SQSListener.java](../watermill-commons/src/main/java/com/inttra/mercury/watermill/commons/sqs/SQSListener.java)
The polling loop. Runs in its own thread:
- Implements `Listener` interface (`startup()` / `shutdown()`)
- Uses **AWS long polling** (`waitTimeSeconds` 1–20 s) to efficiently receive messages
- Polls in a tight loop until interrupted
- Respects `dispatcher.getIdleThreadCount()` to throttle how many messages to request per poll (prevents fetching more than can be processed)
- Delegates to `Dispatcher.submit(messages, queueUrl)` for processing

```
while (!isStop()) {
    int maxNoOfMessages = dispatcher.getIdleThreadCount();
    if (maxNoOfMessages > 0) {
        pollAndExecute(receiveMessageRequest);
    }
}
```

#### `AsyncDispatcher` — [watermill-commons/src/main/java/.../threaddispatcher/AsyncDispatcher.java](../watermill-commons/src/main/java/com/inttra/mercury/watermill/commons/threaddispatcher/AsyncDispatcher.java)
The dispatcher bridge between `SQSListener` and the concrete `Task` implementation. Holds a fixed `maxNumberOfMsgs` to signal capacity.

#### `Task` — [watermill-commons/src/main/java/.../task/Task.java](../watermill-commons/src/main/java/com/inttra/mercury/watermill/commons/task/Task.java)
A `@FunctionalInterface` with a single method `execute(List<Message> messages, String queueUrl)`. Each sub-module provides one concrete implementation.

#### `S3WorkspaceService` — [watermill-commons/src/main/java/.../s3/S3WorkspaceService.java](../watermill-commons/src/main/java/com/inttra/mercury/watermill/commons/s3/S3WorkspaceService.java)
`@Singleton` — wraps `AmazonS3` to read/write S3 objects. Key operations:
- `getContent(bucket, fileName, charset)` — reads and returns the full S3 object as a `String`
- `putObject(...)` — writes bytes/strings to S3
- `copyObject(...)` / `copyObjectWithMetaDate(...)` — S3-side copies with optional user metadata
- Wraps `SdkClientException` in `RecoverableException` for retry propagation

#### `SQSClient`
Wraps `AmazonSQS` for message deletion (`deleteMessage`) and sending operations. Used by `Task` implementations to acknowledge processed messages.

#### `DeadLetterService`
Moves unprocessable messages to a dead-letter queue when processing fails permanently.

#### `EventLogHandler`
Publishes audit/event log records to the **AWS SNS topic** (`snsEventTopicArn`). Called on both success and failure paths, recording `workflowId`, boolean success flag, and contextual tokens map.

#### `WatermillServiceConfig`
Holds gRPC endpoint configuration:
- `host` — Watermill gRPC host
- `port` — typically 443
- `userIdKey` / `passwordKey` — SSM Parameter Store paths for credentials
- `tenant` — INTTRA tenant identifier (e.g., `INTTRA_INT`, `INTTRA_QA`, `INTTRA`)

---

## 5. Module: watermill-booking

### Purpose
Listens for **booking state change events** (booking confirmations, updates, status changes) from a dedicated SQS queue and publishes two types of Protobuf messages to Watermill:
1. `BookingConfirmationChangeEvent` — backward-compatible confirm path (carrier status only)
2. `BookingChangeEvent` — the primary, general booking event

### Main Class
`com.inttra.mercury.watermill.booking.WatermillBKApplication` — Dropwizard `Application` entry point.

### Key Classes

#### `WatermillBKTask` — [watermill-booking/src/main/java/.../task/WatermillBKTask.java](../watermill-booking/src/main/java/com/inttra/mercury/watermill/booking/task/WatermillBKTask.java)
The central processing unit. For each SQS message batch:

1. Ensures gRPC streams are healthy (`handleStreamTermination()`)
2. Deserializes `MetaData` from the SQS message body (JSON)
3. Retrieves the actual booking payload from **S3** using `workspaceService.getContent(bucket, fileName, ISO_8859_1)`
4. Deserializes the S3 payload as `WatermillBookingDetail`
5. If the booking is a carrier status (`isCarrierStatus()`): calls `transformAndPublishConfirm()` → sends `BookingConfirmationChangeEvent`
6. Always calls `transformAndPublishBooking()` → sends `BookingChangeEvent`
7. On transformation error: deletes the SQS message (to prevent infinite retries) and logs via `EventLogHandler`

#### `BookingConfirmGrpcClient` — [watermill-booking/src/main/java/.../grpc/BookingConfirmGrpcClient.java](../watermill-booking/src/main/java/com/inttra/mercury/watermill/booking/grpc/BookingConfirmGrpcClient.java)
Manages the gRPC bidirectional stream for `BookingConfirmationChangeEvent`:
- Holds `StreamObserver<BookingConfirmationChangeEvent>` (request side) and `ResponseObserver` (response side)
- `invoke()` calls `requestObserver.onNext(event)` — sends over the open stream
- `handleStreamTermination()` — if stream needs reset: calls `onCompleted()`, then pings Watermill via blocking stub (`ping()`) until connectivity is confirmed, then recreates channel and stubs via `PublisherInitializer`, then recreates observers
- Uses gzip compression on the stream
- Stream is the `publishBookingConfirmationMicroBatch` RPC defined in `publisher.proto`

#### `BookingGrpcClient`
Analogous to `BookingConfirmGrpcClient` but for the `BookingChangeEvent` stream. Uses `publishBookingMicroBatch` RPC.

#### `PublisherInitializer`
Singleton that creates and holds the `ManagedChannel` (TLS, port 443) and both `PublisherGrpc.PublisherStub` (async) and `PublisherGrpc.PublisherBlockingStub` (sync for ping). Initialized once at startup.

#### Transformer Layer
Two transformer chains handle domain-to-Protobuf mapping:

- **`BKConfirmProtobufTransformer`** — maps `ConfirmPendingMessage` + notification parties → `BookingConfirmationChangeEvent`
- **`BKProtobufTransformer`** — maps `WatermillBookingDetail` + notification parties + external identifiers → `BookingChangeEvent`

Both delegate to specialized sub-transformers:
- `BKCargoTransformer` — cargo/container goods details
- `BKCarriageTransformer` — transport legs / carriage details
- `BKEquipmentTransformer` — equipment/container details
- `BKLocationTransformer` — place of receipt, port of load, port of discharge, place of delivery
- `BKPartyTransformer` — shipper, consignee, carrier, freight payer etc.

And 40+ `TypeMap` classes for enum conversions (e.g. `BookingStateMap`, `TransportModeTypeMap`, `PackageDangerTypeMap`).

#### `WatermillBookingDetail` — Model
Wraps the booking state machine state (enum `BookingState`) and the raw booking payload (`ConfirmPendingMessage` or similar). Has `getState().isCarrierStatus()` to distinguish confirm-eligible events.

#### `AuthCredentials`
Implements `io.grpc.CallCredentials`. Fetches a bearer token from the auth service and injects it into gRPC call metadata (`Authorization: Bearer <token>`). The token is retrieved by calling INTTRA's auth REST endpoint using the client credentials stored in SSM Parameter Store.

### Proto Files
Located in `src/main/proto/`:
- `api/publisher.proto` — defines the `Publisher` gRPC service with `publishBookingConfirmationMicroBatch`, `publishBookingMicroBatch`, and `ping` RPCs
- `logistics/inttra-booking.proto` — `BookingChangeEvent` message definition
- `logistics/inttra-booking-confirmation.proto` — `BookingConfirmationChangeEvent`
- `logistics/inttra-booking-common.proto` — shared booking proto types
- `logistics/inttra-common.proto` — shared common types
- `audit.proto`, `generic.proto` — audit and generic types

---

## 6. Module: watermill-booking-aperak

### Purpose
Handles **APERAK (Application Error And Acknowledgement) booking events** — a specialized event type used for EDI-style booking acknowledgements. This is a structurally simpler module that follows the same architecture as `watermill-booking` but for APERAK-specific events.

### Main Class
`com.inttra.mercury.watermill.bookingaperak.WatermillBKAperakApplication`

### Key Differences from watermill-booking
- Uses booking module version `2.1.7.M` (one minor version older than the other modules)
- Transformer hierarchy is simpler: `BKAperakTransformer` + `BKAperakPartyTransformer`
- Type maps are a subset: `BRReferenceTypeMap`, `BookingStateMap`, `ChargeTypeMap`, `ContactTypeMap`, `CountryCodeTypeMap`, `PartyTypeMap`, `PaymentTermTypeMap`, `TransactionLocationTypeMap`
- Dedicated SQS queue: `inttra_{env}_sqs_watermill_aperak_bk`
- Publishes APERAK-specific Protobuf messages to Watermill

### Task: `WatermillBKAperakTask`
Follows the same pattern as `WatermillBKTask`: reads `MetaData` from SQS → retrieves payload from S3 → transforms via `BKAperakTransformer` → publishes via `BookingAperakGrpcClient`.

---

## 7. Module: watermill-cargo-visibility-subscription

### Purpose
The most complex of the three publisher sub-modules. It manages **cargo visibility subscriptions** — allowing recipients (customers or INTTRA itself) to subscribe to track cargo movements for a given booking or bill of lading. It:
1. Receives booking state change or customer subscription request events via SQS
2. Creates or updates `CargoVisibilitySubscription` records in **DynamoDB**
3. Publishes `INTTRACWSubscriptionRequestChangeEvent` to Watermill via gRPC
4. Handles subscription lifecycle: SUBMITTED → ACCEPTED/REJECTED → CANCELLED

### Main Class
`com.inttra.mercury.cargo.visibility.WatermillCargoVisibilitySubscriptionPublisherApplication`

### Key Classes

#### `CargoVisibilitySubscriptionPublisherTask` — [watermill-cargo-visibility-subscription/src/main/java/.../task/CargoVisibilitySubscriptionPublisherTask.java](../watermill-cargo-visibility-subscription/src/main/java/com/inttra/mercury/cargo/visibility/task/CargoVisibilitySubscriptionPublisherTask.java)
The most complex task class in the system. Processes two fundamentally different payload types from the same SQS queue:

**A. INTTRA-Initiated Subscriptions** (triggered by booking state changes):
- Detected by presence of `"enrichedAttributes"` in JSON payload
- Parsed as `WatermillBookingDetail`
- Only processes `CONFIRM` state with a booking number and booking parties
- For terminating states (`DECLINE`, `REPLACE`, `CANCEL`): cancels existing subscriptions
- For CONFIRM: filters recipients via `ParticipantService.hasCargoVisibility()`, then creates or updates subscription

**B. Customer-Initiated Subscriptions** (triggered by customer subscription requests):
- Detected by presence of `"carrierBookingNumber"` or `"billOfLadingNumber"` in JSON payload
- Parsed as `CargoVisibilitySubscription` directly
- Requires at least one of `carrierBookingNumber` or `billOfLadingNumber`, plus `requestedRecipients`
- Same eligibility filter and create/update logic

**Subscription Lifecycle Logic:**
```
Incoming event
    │
    ├─► Has existing subscription?
    │       ├─► YES: updateExistingSubscription() → add new recipients → save to DynamoDB → delete SQS message (no gRPC publish)
    │       └─► NO:  buildNewSubscription() → save to DynamoDB → publishSubscriptionEvent() via gRPC
    │
    └─► Terminating state (DECLINE/REPLACE/CANCEL)?
            └─► Find existing subscription → set CANCELLED → save → publishSubscriptionEvent() via gRPC
```

**Subscription expiry:** 400 days from creation (`calculateExpirationDate()`).

#### `CargoVisibilitySubscriptionDao`
DynamoDB DAO for `CargoVisibilitySubscription` records. Uses `DynamoSupport` (from the `dynamo-client` library). Key operations:
- `save(subscription)` — persist/update record
- `findLatestSubscription(bookingNumber, billOfLadingNumber, carrierScac)` — looks up by composite key using one of two GSIs

#### `BookingDao`
Used to supplement booking numbers for terminating-state events that have an INTTRA reference number but no carrier booking number. Queries the booking database (likely via the `booking` module's repository) using `findBookingByInttraReference(inttraReferenceNumber)`.

#### DynamoDB Table: `CargoVisibilitySubscription`

| Attribute | Role |
|---|---|
| `hashKey` (UUID) | Primary partition key |
| `carrierBookingNumber` | Booking number |
| `billOfLadingNumber` | Bill of lading number |
| `carrierScac` | Carrier SCAC code |
| `subscriptionReference` | External reference from Watermill (set after acceptance) |
| `state` | `SUBMITTED` / `CANCELLED` |
| `clientType` | `RESTRICTED` (INTTRA) / `UNRESTRICTED` (Customer) |
| `type` | `INTTRA` / `CUSTOMER` |
| `requestedRecipients` | Set of recipient entity IDs |
| `createdOn`, `modifiedOn`, `expiresOn` | Lifecycle dates |

**Global Secondary Indexes (GSIs):**
- `bookingNumber-carrierScac-index` — hash: `carrierBookingNumber`, sort: `carrierScac`
- `billOfLading-carrierScac-index` — hash: `billOfLadingNumber`, sort: `carrierScac`
- `subscriptionReference-index` — hash: `subscriptionReference` (used for response matching)

#### `NetworkParticipantServiceImpl` / `ParticipantService`
Calls the INTTRA Network Service REST API (`/network/reference/participants`) to determine if a recipient entity has the **cargo visibility** entitlement. Uses OAuth bearer token authentication via `AuthClient`. Results drive the `filterEligibleRecipients()` logic in the task.

#### `TransformationHelper`
Builds `INTTRACWSubscriptionRequestChangeEvent` Protobuf messages from `CargoVisibilitySubscription` domain objects.

#### `CargoVisibilitySubscriptionGrpcClient`
Same pattern as `BookingConfirmGrpcClient`. Manages bidirectional gRPC stream for `INTTRACWSubscriptionRequestChangeEvent`. On receiving a successful response from Watermill, the `ResponseObserver` updates the `subscriptionReference` on the DynamoDB record, marking it as acknowledged.

---

## 8. Cross-Cutting Architecture Patterns

### 8.1 SQS → S3 → gRPC Data Indirection Pattern
All three publishers use a **two-stage message passing** pattern:
```
booking module                watermill-publisher
─────────────────────────     ─────────────────────────────────────────────
Write payload to S3  ──►  S3 bucket (inttra-{env}-workspace)
                                    │
Publish metadata to SQS ──►  SQS queue  ──► SQSListener ──► Task
                                                               │
                                                        Read payload from S3
                                                               │
                                                        Transform to Protobuf
                                                               │
                                                        gRPC → Watermill
```
The SQS message body contains `MetaData` (JSON): `workflowId`, `bucket`, `fileName` — never the full payload. This prevents SQS message size limits from being a constraint.

### 8.2 gRPC Bidirectional Streaming with Stream Recovery
All gRPC clients maintain a **persistent bidirectional stream**:
- Messages are sent via `requestObserver.onNext(event)` without waiting for individual acknowledgements
- The `ResponseObserver` processes acknowledgements asynchronously
- If the stream terminates (network error, server restart): `handleStreamTermination()` is called before each batch
  1. Calls `requestObserver.onCompleted()` to cleanly close the old stream
  2. Pings Watermill in a blocking loop (5-second retry) until `PingAck.ErrorCode.OK`
  3. Reinitializes the `ManagedChannel`, async stub, and blocking stub
  4. Creates new `StreamObserver` pair and opens a new stream

### 8.3 Acknowledgement Flow
```
watermill-publisher                    Watermill (e2open)
────────────────────────────────────   ─────────────────────
send event (onNext) ──────────────────────────────────────►
                    ◄─────────────────── ack/nack (response)
ResponseObserver receives ack
    │
    ├─► success: deleteMessage(SQS) + logEvent(SNS, success=true)
    └─► failure: mark for retry / dead-letter + logEvent(SNS, success=false)
```

### 8.4 Dependency Injection (Google Guice)
Each sub-module has an `ApplicationInjector` (Guice `Module`) that binds:
- Config objects (deserialized from `config.yaml` via Dropwizard)
- AWS clients (SQS, S3, optionally DynamoDB) — bound as singletons
- gRPC clients — singletons
- Task — bound to `Task` interface
- `AsyncDispatcher` with the task and `maxNumberOfMessages`
- `SQSListener` constructed from the above

### 8.5 Singleton Resource Management
Expensive resources (`ManagedChannel`, `AmazonS3`, `AmazonSQS`, `AmazonDynamoDB`) are created once at startup as Guice `@Singleton` instances, preventing connection pool exhaustion.

---

## 9. Data Flow — End-to-End

### watermill-booking Flow

```
1. booking service writes booking state change payload to S3
2. booking service publishes MetaData JSON to SQS: inttra_{env}_sqs_watermill_bk
3. SQSListener (long poll, waitTimeSeconds=20) receives up to 3 messages
4. AsyncDispatcher.submit() → WatermillBKTask.execute()
5. For each message:
   a. Parse MetaData from SQS body
   b. S3WorkspaceService.getContent(bucket, fileName, ISO_8859_1)
   c. Deserialize S3 content as WatermillBookingDetail
   d. If state.isCarrierStatus():
      - BKConfirmProtobufTransformer.transform() → BookingConfirmationChangeEvent
      - BookingConfirmGrpcClient.invoke() → requestObserver.onNext()
   e. BKProtobufTransformer.transform() → BookingChangeEvent
   f. BookingGrpcClient.invoke() → requestObserver.onNext()
6. ResponseObserver receives ack from Watermill
7. SQSClient.deleteMessage() — removes message from queue
8. EventLogHandler.logEvent() → SNS publish (audit)
```

### watermill-cargo-visibility-subscription Flow

```
1. Trigger event (booking CONFIRM or customer subscription request) written to S3
2. SQS: inttra_{env}_sqs_cargo_visibility_subscription_watermill receives MetaData
3. SQSListener → CargoVisibilitySubscriptionPublisherTask.execute()
4. For each message:
   a. Parse MetaData from SQS body
   b. Retrieve file content from S3
   c. Content type detection (JSON field presence check):
      ├─► contains "enrichedAttributes" → parse as WatermillBookingDetail (INTTRA path)
      └─► contains "carrierBookingNumber"/"billOfLadingNumber" → parse as CargoVisibilitySubscription (Customer path)
   d. Filter eligible recipients via ParticipantService.hasCargoVisibility()
   e. DynamoDB lookup: CargoVisibilitySubscriptionDao.findLatestSubscription()
      ├─► exists: updateExistingSubscription() → save to DynamoDB → delete SQS (no gRPC)
      └─► new: buildNewSubscription() → save to DynamoDB → publishSubscriptionEvent() via gRPC
   f. On terminating state: processSubscriptionCancellation() → save CANCELLED → gRPC publish
5. gRPC response (subscription ack): ResponseObserver updates subscriptionReference in DynamoDB
6. SQSClient.deleteMessage() + EventLogHandler.logEvent() → SNS
```

---

## 10. Integration with the booking Module

All three publisher sub-modules depend directly on the `booking` module JAR, stored in local `lib/` directories (not fetched from a remote Maven repository):

```
watermill-booking/lib/
├── booking-1.0.2.M.jar
├── booking-1.0.3.M.jar
├── booking-2.1.2.M.jar
├── booking-2.1.5.M.jar
├── booking-2.1.6.M.jar
├── booking-2.1.7.M.jar
└── booking-2.1.8.M.jar  ← current
```

### What is used from the booking module

| Component | Used By | Booking Class/Package |
|---|---|---|
| `ConfirmPendingMessage` | watermill-booking | `com.inttra.mercury.booking.inbound.confirmation` |
| `BookingState` (enum) | watermill-booking | `com.inttra.mercury.booking.model` |
| `TransactionParty` | watermill-booking | `com.inttra.mercury.booking.model.Common.Artifacts` |
| `MetaData` (booking-specific) | watermill-booking | `com.inttra.mercury.booking.util` |
| `Booking` model | watermill-cargo-visibility | `com.inttra.mercury.booking.model` |
| Booking domain models (cargo, equipment, location, party, carriage, etc.) | all transformers | `com.inttra.mercury.booking.model.*` |

### How booking triggers watermill-publisher

The `booking` module (running as a separate service) is responsible for:
1. Detecting booking state transitions
2. Writing the full booking payload to S3 (under the workspace bucket)
3. Sending a lightweight `MetaData` JSON message to the appropriate SQS queue

The watermill-publisher modules consume these SQS messages and use the `MetaData` to locate and read the S3 payload. There is **no direct HTTP/RPC call** between `booking` and `watermill-publisher` at runtime — the coupling is purely through SQS message contracts and shared domain model JARs.

### Version Coupling Risk
The local `lib/` approach means updating the booking module version requires manually copying the JAR into the `lib/` directory and updating the POM. This creates a manual synchronization step that must be managed carefully.

---

## 11. Integration with Other mercury-services Modules

### `commons` / `dynamo-client` (com.inttra.mercury)
- Both are internal platform libraries consumed at version `1.R.01.021`
- `commons` provides base utilities, JSON support, shared infrastructure
- `dynamo-client` provides DynamoDB table management and ORM capabilities used exclusively by `watermill-cargo-visibility-subscription`

### `emailsender` (com.inttra.mercury:emailsender:1.R.01.021)
- Available in classpath but the actual usage was not observed in task code. Likely available for potential error notification.

### `visibility` module (indirect)
- The cargo visibility subscription publisher acts as the data pipeline that feeds e2open's Watermill, which in turn feeds the `visibility` module's cargo tracking capabilities. There is no direct code coupling.

### `webbl` / `oceanschedules`
- No direct code dependency observed.

### INTTRA Network Services (external REST)
- Used by `watermill-cargo-visibility-subscription` to verify recipient entitlements
- `AuthClient` → `GET /auth` (OAuth client credentials flow)
- `NetworkParticipantServiceImpl` → `GET /network/reference/participants` to check `cargoVisibility` entitlement

---

## 12. AWS Resources by Environment

### AWS Account IDs
| Environment | AWS Account ID |
|---|---|
| INT | `081020446316` |
| QA, CVT, PROD | `642960533737` |

---

### watermill-booking

| Resource | INT | QA | CVT | PROD |
|---|---|---|---|---|
| **SQS Queue URL** | `https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_watermill_bk` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_watermill_bk` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_cv_sqs_watermill_bk` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_pr_sqs_watermill_bk` |
| **SNS Topic ARN** | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event` | `arn:aws:sns:us-east-1:642960533737:inttra2_cv_sns_event` | `arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event` |
| **S3 Bucket** | `inttra-int-workspace` | `inttra2-qa-workspace` | `inttra2-cv-workspace` | `inttra2-pr-workspace` |
| **SSM: gRPC username** | `/inttra/int/appianway/watermill-grpc/se/username` | `/inttra2/qa/appianway/watermill-grpc/se/username` | `/inttra2/cv/appianway/watermill-grpc/se/username` | `/inttra2/pr/appianway/watermill-grpc/se/username` |
| **SSM: gRPC password** | `/inttra/int/appianway/watermill-grpc/se/password` | `/inttra2/qa/appianway/watermill-grpc/se/password` | `/inttra2/cv/appianway/watermill-grpc/se/password` | `/inttra2/pr/appianway/watermill-grpc/se/password` |
| **SSM: auth client secret** | `/inttra/int/mercuryservices/partner-integration/authclientsecret` | `/inttra2/qa/mercuryservices/partner-integration/authclientsecret` | `/inttra2/cv/mercuryservices/partner-integration/authclientsecret` | `/inttra2/pr/mercuryservices/partner-integration/authclientsecret` |
| **Watermill gRPC host** | `watermill.staging.e2open.com:443` | `watermill.staging.e2open.com:443` | `watermill.staging.e2open.com:443` | `watermill.e2open.com:443` |
| **Tenant** | `INTTRA_INT` | `INTTRA_QA` | `INTTRA` | `INTTRA` |
| **Auth URI** | `https://api-alpha.inttra.com/auth` | `https://api-beta.inttra.com/auth` | `https://api-test.inttra.com/auth` | `https://api.inttra.com/auth` |
| **SQS waitTimeSeconds** | 20 | 20 | 20 | 20 |
| **SQS maxNumberOfMessages** | 3 | 3 | 3 | 3 |
| **HTTP port** | 8090 | 8090 | 8090 | 8090 |
| **Admin port** | 8091 | 8091 | 8091 | 8091 |

---

### watermill-booking-aperak

| Resource | INT | QA | CVT | PROD |
|---|---|---|---|---|
| **SQS Queue URL** | `https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_watermill_aperak_bk` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_watermill_aperak_bk` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_cv_sqs_watermill_aperak_bk` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_pr_sqs_watermill_aperak_bk` |
| **SNS Topic ARN** | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` | `arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event` | `arn:aws:sns:us-east-1:642960533737:inttra2_cv_sns_event` | `arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event` |
| **S3 Bucket** | `inttra-int-workspace` | `inttra2-qa-workspace` | `inttra2-cv-workspace` | `inttra2-pr-workspace` |
| **Watermill gRPC host** | `watermill.staging.e2open.com:443` | `watermill.staging.e2open.com:443` | `watermill.staging.e2open.com:443` | `watermill.e2open.com:443` |
| **Auth URI** | `https://api-alpha.inttra.com/auth` | `https://api-beta.inttra.com/auth` | `https://api-test.inttra.com/auth` | `https://api.inttra.com/auth` |

All SSM parameter paths follow the same naming convention as `watermill-booking` with environment prefix substitution.

---

### watermill-cargo-visibility-subscription

| Resource | INT | QA | CVT | PROD |
|---|---|---|---|---|
| **SQS Queue URL** | `https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_cargo_visibility_subscription_watermill` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_cargo_visibility_subscription_watermill` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_cv_sqs_cargo_visibility_subscription_watermill` | `https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_pr_sqs_cargo_visibility_subscription_watermill` |
| **SNS Topic ARN** | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event_ce` | `arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event_ce` | `arn:aws:sns:us-east-1:642960533737:inttra2_cv_sns_event_ce` | `arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event_ce` |
| **S3 Bucket** | `inttra-int-workspace` | `inttra2-qa-workspace` | `inttra2-cv-workspace` | `inttra2-pr-workspace` |
| **DynamoDB environment prefix** | `inttra_int` | `inttra2_qa` | `inttra2_cv` | `inttra2_pr` |
| **DynamoDB table** | `inttra_int_CargoVisibilitySubscription` | `inttra2_qa_CargoVisibilitySubscription` | `inttra2_cv_CargoVisibilitySubscription` | `inttra2_pr_CargoVisibilitySubscription` |
| **DynamoDB read/write throughput** | 5/5 | 5/5 | 5/5 | 5/5 |
| **Watermill gRPC host** | `watermill.staging.e2open.com:443` | `watermill.staging.e2open.com:443` | `watermill.staging.e2open.com:443` | `watermill.e2open.com:443` |
| **Auth URI** | `https://api-alpha.inttra.com/auth` | `https://api-beta.inttra.com/auth` | `https://api-test.inttra.com/auth` | `https://api.inttra.com/auth` |
| **Network Participants URI** | `https://api-alpha.inttra.com/network/reference/participants` | `https://api-beta.inttra.com/network/reference/participants` | `https://api-test.inttra.com/network/reference/participants` | `https://api.inttra.com/network/reference/participants` |
| **Tenant** | `INTTRA_INT` | `INTTRA_QA` | `INTTRA` | `INTTRA` |

#### DynamoDB GSI Configuration (all environments)

| Index Name | Hash Key | Sort Key | Projection |
|---|---|---|---|
| `bookingNumber-carrierScac-index` | `carrierBookingNumber` | `carrierScac` | KEYS_ONLY |
| `billOfLading-carrierScac-index` | `billOfLadingNumber` | `carrierScac` | KEYS_ONLY |
| `subscriptionReference-index` | `subscriptionReference` | — | KEYS_ONLY |

---

## 13. Key Dependencies

### Parent POM (watermill-publisher/pom.xml)

| Dependency | Version | Purpose |
|---|---|---|
| `aws-java-sdk` | 1.12.661 | SQS, S3, SSM clients |
| `grpc-bom` | 1.77.0 | gRPC framework (BOM) |
| `grpc-netty-shaded` | 1.77.0 | gRPC transport (TLS) |
| `grpc-protobuf` | 1.77.0 | Protobuf gRPC integration |
| `grpc-stub` | 1.77.0 | gRPC stub generation |
| `protobuf-java` | 4.33.1 | Protocol Buffers runtime |
| `protobuf-java-format` | 1.4 | JSON format for Protobuf logging |
| `lombok` | — | Boilerplate reduction |
| `jackson-databind` | 2.19.2 | JSON serialization |
| `jakarta.validation-api` | 3.1.0 | Bean validation |
| `junit-jupiter` | 6.1.0-M1 | Unit testing |
| `assertj-core` | 4.0.0-M1 | Fluent assertions |
| `mockito-core` | 5.20.0 | Mocking framework |

### Module-specific

| Module | Dependency | Version |
|---|---|---|
| watermill-booking | `com.inttra.mercury:booking` (local JAR) | 2.1.8.M |
| watermill-booking-aperak | `com.inttra.mercury:booking` (local JAR) | 2.1.7.M |
| watermill-cargo-visibility-subscription | `com.inttra.mercury:booking` (local JAR) | 2.1.8.M |
| watermill-cargo-visibility-subscription | `com.inttra.mercury:dynamo-client` | 1.R.01.021 |
| all | `com.inttra.mercury:commons` | 1.R.01.021 |
| all | `com.inttra.mercury:watermill-commons` | 1.0 (local) |

---

## 14. Security & Credentials Management

All sensitive credentials are stored in **AWS SSM Parameter Store** and injected at startup via Dropwizard's `${awsps:...}` syntax in `config.yaml`:

| Credential | SSM Path Pattern |
|---|---|
| Watermill gRPC username | `/inttra{n}/{env}/appianway/watermill-grpc/se/username` |
| Watermill gRPC password | `/inttra{n}/{env}/appianway/watermill-grpc/se/password` |
| Auth client secret | `/inttra{n}/{env}/mercuryservices/partner-integration/authclientsecret` |

**gRPC Authentication:** The `AuthCredentials` class implements `io.grpc.CallCredentials`. It obtains a bearer token via OAuth 2.0 client credentials flow from INTTRA auth service and injects it into each gRPC call metadata. The token is refreshed as needed.

**TLS Transport:** All gRPC connections use TLS (port 443) via `grpc-netty-shaded`. The `ManagedChannel` is built with TLS by default (no insecure mode is configured).

**SQS/S3 Access:** AWS SDK uses instance role credentials (IAM role attached to the ECS task / EC2 instance). No static AWS credentials are configured in code or config files.

---

## 15. Error Handling & Resilience

### Message Processing Failures
- **Transformation errors:** The SQS message is **deleted immediately** (to prevent infinite re-delivery) and the error is logged to SNS via `EventLogHandler` with `success=false`. This is a poison-pill approach: bad messages are dropped with an audit trail rather than blocking the queue.
- **S3 read failures:** `RecoverableException` is thrown, which propagates up to the `SQSListener`'s catch block. The message remains in the queue (visibility timeout will re-deliver it). The listener loop continues.
- **gRPC send failures:** `resetStream()` is called to flag the stream for recreation on the next `handleStreamTermination()` call. The exception propagates and the SQS message remains in queue.

### gRPC Stream Recovery
The ping-retry loop in `handleStreamTermination()` ensures the publisher waits until Watermill is reachable before sending more messages. Without this, messages would be lost if sent to a dead stream.

### SQS Visibility Timeout
- `waitTimeSeconds: 20` — long polling to reduce empty receives
- `maxNumberOfMessages: 3` — small batches to limit in-flight message exposure
- If a message is not deleted within the queue's visibility timeout, SQS re-delivers it. All task implementations are idempotent for this case (DynamoDB `save()` is an upsert; gRPC publish with the same `messageId` is handled by Watermill deduplication).

### Dead Letter Service
`DeadLetterService` (in `watermill-commons`) provides infrastructure to route unprocessable messages to a dedicated DLQ after N delivery attempts. The DLQ configuration is managed at the SQS queue level in AWS.

---

*Document generated: 2026-04-29 | Author: Claude Sonnet 4.6 | Analysis scope: watermill-publisher parent + all 4 sub-modules (watermill-commons, watermill-booking, watermill-booking-aperak, watermill-cargo-visibility-subscription)*
