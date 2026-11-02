# WI01124532 watermill-publisher — AWS SDK 2.x (cloud-sdk) Upgrade

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

`watermill-publisher` receives `MetaData` from its pickup queue, reads the referenced status-event XML from the workspace bucket (ISO-8859-1), transforms it to the protobuf `ShipmentStatusChangeEvent` and sends it to Watermill on a gRPC client stream (`publishShipmentStatusMicroBatch`, gzip, call credentials). The SQS message is deleted when Watermill returns a `PublisherAck` whose correlation id matches the event's message id, or immediately when the transform fails. A scheduled job moves messages from the pickup queue's DLQ back to the pickup queue.

This change moves the module onto `shared` re-based on `commons` / `cloud-sdk` 1.0.38-SNAPSHOT (AWS SDK 2.x), see the `shared` page. SQS and workspace S3 go through the `shared` Tier 2 adapters, SSM through the `shared` `ParameterSupplier` on `CloudParameterStore`, configuration through the commons config chain. `MetaData`, the gRPC publish, the protobuf payload and Watermill authentication are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `watermill-publisher` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` page |

### Functional Requirements

1. Receive from the pickup queue with the `shared` back-pressure `SQSListener` (v2 listener client over `MessagingClient<String>`): `listenerThreads` listeners, `waitTimeSeconds` long poll, at most `maxNumberOfMessages` per receive (the module's synchronous `AsyncDispatcher` always reports that many idle permits), `messageAttributeNames=[failedAttempts]`, no visibility timeout in the request (C3).
2. Read the payload through the `shared` workspace adapter `getContent(bucket, fileName, ISO_8859_1)`: whole-object bytes decoded as ISO-8859-1, no line joining.
3. Keep the XML → protobuf transform and the gRPC stream publish unchanged.
4. Delete the SQS message on a matching `PublisherAck`, and on transform failure, through the `shared` SQS sender `deleteMessage`.
5. Keep the ack-expiry window equal to the pickup queue's `VisibilityTimeout` attribute, read through the `shared` SQS sender `getVisibilityTimeout`.
6. Keep the DLQ redrive: every 30 min, from `<pickup queue URL>_dlq`, receive up to 10 with a 20 s wait, send the body only (no attributes, no delay) to the pickup queue, delete from the DLQ; stop after 3 empty receives.
7. Load the Watermill username/password from SSM once at startup (one `GetParameters`, `WithDecryption=true`); an unknown name fails startup (C7).

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in `watermill-publisher` sources.
2. Wire compatibility per the `shared` contract: C1 (`MetaData` read with `shared` `Json`), C2 (read only), C3, C7, C8, C9. gRPC payload unchanged.
3. Client profile per the `shared` page: one listener client (socket timeout above the 20 s long poll) and one sender client; one S3 client.

### Acceptance Criteria

1. `mvn -pl watermill-publisher -am clean verify` is green.
2. Unit tests assert the ISO-8859-1 read, delete-on-ack with the stored receipt handle, `VisibilityTimeout` lookup and the body-only DLQ redrive.
3. Config golden test (from the `shared` page) passes for `conf/watermill-publisher.yaml` with every environment's properties.
4. INT: one pickup message is published to Watermill and deleted after the ack, as before.

### Jira Tickets (ext)

| Key | Summary | Type |
|-----|---------|------|
| WI01124532 | AppianWay cloud-sdk 1.0.38 alignment | Work item |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard, Guice, gRPC (versions as managed by commons / root pom) |
| Build | Maven, Java 17 |
| AWS SDK | AWS SDK 2.x via `cloud-sdk-api` / `cloud-sdk-aws` 1.0.38-SNAPSHOT, through `shared` (was AWS SDK v1 1.12.720) |
| Messaging | SQS receive, delete, send (redrive), queue attributes |
| Storage | S3 read (workspace) |
| Parameters | SSM Parameter Store (read, decrypted) |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | `task/Test.java` is a manual load harness in main sources that builds v1 SQS/S3 clients directly; it is not wired into the service | Open Issue | Resolved | Replaced by a v2 load harness in test sources (`WatermillPublisherLoadHarness`, not packaged in the service jar and not picked up by Surefire). It uses the `shared` v2 workspace adapter and SQS sender, and takes the workspace bucket, pickup queue, sample document, thread count, messages per thread and delay as arguments, so no resource names are in code. Run on demand with `exec:java` on the test classpath |
| 3 | `EventPublisher` (SNS) and the SNS client are bound but never used; no events are published | Open Issue | Resolved | No SNS client is bound in v2. `snsEventConfig` stays in YAML because `BaseConfiguration` requires it |
| 4 | `sqsErrorConfig` and `healthCheckConfig` are required by configuration but unused; no health checks are registered | Assumption | Resolved | Keep the keys; no behaviour change |
| 5 | The external-call wrapper (Hystrix) is not used by this module; `NetworkRetryerModule` and a Jersey `Client` are bound but unused | Assumption | Resolved | Unchanged |

---

## High Level Design

### Architectural Overview (ext)

```
 pickup queue (SQS)
        │  shared SQSListener (v2 listener client) x listenerThreads
        ▼
 AsyncDispatcher (module, synchronous) ─▶ WatermillPubTask
   ├─▶ shared workspace adapter getContent(bucket, fileName, ISO_8859_1)
   ├─▶ XMLTransformer ─▶ StatusEventProtobufTransformer ─▶ StatusEventGrpcClient (gRPC stream, unchanged)
   └─▶ transform failure ─▶ shared SQS sender deleteMessage
        │
 ResponseObserver ── PublisherAck ─▶ shared SQS sender deleteMessage
                  └─ ack expiry = getVisibilityTimeout(pickup queue)

 ListenerManager scheduler (30 min): DeadLetterService
   shared listener client receive (DLQ) ─▶ shared SQS sender sendMessage(body) ─▶ deleteMessage (DLQ)

 AuthCredentials ◀─ shared ParameterSupplier ◀─ CloudParameterStore (GetParameters, decrypted)
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Keep the module's ack-based delete and synchronous dispatcher; move the listener, sender, workspace and parameter supplier to the `shared` v2 adapters | No change to delivery semantics; wire parity enforced in `shared` | — | ✅ |
| 2 | Call cloud-sdk `MessagingClient` / `StorageClient` directly from the module | Fewer layers | Breaks the program rule that SQS and workspace-S3 calls go through `shared` (parity enforced in one place); duplicates the exception mapping | ❌ |
| 3 | Use the cloud-sdk `SqsListener` | Less code | Fixed batch, no back-pressure, SDK-typed messages | ❌ |

### Data Flow — Before vs After (ext)

**Before:** `shared` `SQSListener` on `SQSListenerClient` (v1, `sqs_listener` profile) → `S3WorkspaceService.getContent(..., ISO_8859_1)` (v1) → gRPC publish → `SQSClient.deleteMessage` (v1, `sqs_sender` profile) on ack; `SQSClient.getVisibilityTimeout`; DLQ redrive via `SQSListenerClient` + `SQSClient`; `ParameterStoreModule` with a default v1 SSM client; `shared` `ConfigProcessingServerCommand`.

**After:** the same `shared` classes and method contracts, bound by the `shared` v2 Guice module to cloud-sdk `MessagingClient<String>` (listener and sender roles), `StorageClient` and `CloudParameterStore`. `Message` becomes `QueueMessage<String>` in the module's `Task`, `TaskFactory`, `AsyncDispatcher`, `WatermillPubTask` and `DeadLetterService`. Configuration through the commons config chain. gRPC unchanged.

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `WatermillPubApplication` | `initialize()` registers the commons-based config command instead of the `shared` one and the `shared` v2 S3 configuration source provider; config files unchanged |
| 2 | `ExternalServicesModule` | Replace the inline v1 builders (`AmazonSQS` listener/sender, `AmazonS3`, `AmazonSNS`) and `ParameterStoreModule` with the `shared` v2 Guice module (listener, sender and S3 roles; parameter names `userIdKey`, `passwordKey`). No SNS client (open issue 3). `Clock`, Jersey `Client`, `NetworkRetryerModule` unchanged |
| 3 | `WatermillPubModule` | `WorkspaceService` bound to the `shared` v2 workspace adapter; `SQSListener` list and `DeadLetterService` built from the v2 listener client and sender. gRPC channel and stubs unchanged |
| 4 | `Task`, `TaskFactory`, `AsyncDispatcher` | Typed on `QueueMessage<String>` (implements the SDK-neutral `shared` `Dispatcher`); `getIdleThreadCount()` still returns `maxNumberOfMessages`; `submit` still runs the task synchronously on the listener thread |
| 5 | `WatermillPubTask` | `message.getBody()` / `getReceiptHandle()` from `QueueMessage`; `MetaData` parsed with `shared` `Json`; ISO-8859-1 read and delete-on-transform-failure unchanged |
| 6 | `ResponseObserver`, `StatusEventGrpcClient` | Use the `shared` SQS sender adapter (`deleteMessage`, `getVisibilityTimeout`, the latter on `MessagingClient.getQueueAttributes`). gRPC logic unchanged |
| 7 | `DeadLetterService` | Receive through the v2 listener client (10 messages, 20 s, `failedAttempts` requested as today); send through `sendMessage(target, body)` (no attributes, no delay); delete from the DLQ |
| 8 | `AuthCredentials`, transformers, `MessageKeys` | Unchanged |
| 9 | `task/Test.java` | Removed from main sources; replaced by the v2 test-source harness `WatermillPublisherLoadHarness` (open issue 2) |

#### Guice Module Loading Order (ext)

`shared` v2 module (clients, adapters, parameter supplier) → `ExternalServicesModule` remainder → `WatermillPubModule`. The `shared` v1 bindings are not installed.

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive (pickup, DLQ), delete, send (redrive), `GetQueueAttributes` (`VisibilityTimeout`) | AWS SDK 2.x via `shared` adapters |
| S3 | `GetObject` of the workspace payload | AWS SDK 2.x via `shared` workspace adapter |
| SSM Parameter Store | `GetParameters` with decryption (Watermill username/password) | AWS SDK 2.x via `shared` `ParameterSupplier` |

`getQueueAttributes` on cloud-sdk requests `All` attributes (v1 requested `VisibilityTimeout` only); only `VisibilityTimeout` is read. Same IAM action.

#### DynamoDB Changes (ext)

None.

### UI

N/A

### API Architecture

N/A — no API added or changed. The outbound gRPC publish to Watermill is unchanged.

---

## Configuration

### Component-Level Configuration

No change. `conf/watermill-publisher.yaml` keys and the environment `.properties` files are unchanged.

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change. Same SSM parameter names, same ECS task definitions and start command.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to log messages or levels. `watermill-publisher.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3 calls at INFO, and `com.inttra.mercury` is at DEBUG in this file), as the shared design requires.

### Event Publishing (ext)

None — no events are published today or after the change.

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

No observable change: same gRPC payloads, same delete-on-ack, same DLQ redrive. Exceptions from SQS/S3 change type inside the adapters only (C9); `SQSListener` and `WatermillPubTask` catch generically, so handling is unchanged.

### Performance (ext)

No material change expected. One listener and one sender client (50 connections each) as today. Each stream reset calls `GetQueueAttributes` once (unchanged).

### Deployment (ext)

Rolling restart as part of the single AppianWay release. No data migration. A single service can be rolled back to its previous build alone, because formats are unchanged.

---

## Resiliency

Unchanged, and recorded here because the upgrade must not hide it:

- Delivery is at-least-once. A stream error or completion (`ResponseObserver.reset`) clears the pending-ack map; those messages are not deleted, reappear after the visibility timeout and are published again. Watermill must tolerate duplicates by message id.
- A missing ack (expiry = queue visibility timeout) leaves the message to be redelivered; repeated failures reach the DLQ via the queue redrive policy, and `DeadLetterService` puts them back every 30 min with no attempt counter, so a message that never acks or never deletes cycles indefinitely.
- While Watermill is unreachable, `handleStreamTermination` pings every 5 s on the listener thread holding the received batch; those messages become visible again and can be published twice once the stream recovers.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files.

---

## Impact on Tools

None.

---

## Impact on Other Components

- Watermill: None — protobuf payload, stream and authentication unchanged.
- Upstream producers of the pickup queue: None — input contract unchanged.

---

## Backwards Compatible

**Yes.**

| Question | Answer |
|----------|--------|
| C1 JSON | `MetaData` read with `shared` `Json`, unchanged |
| C2 S3 | Read only; byte-exact ISO-8859-1 decode, same as v1 `getContent(..., charset)` |
| C3 SQS | Same queues; receive requests `failedAttempts`, no visibility timeout; redrive sends the body only, no attributes, no delay (as today) |
| C7 SSM | Same names, `WithDecryption=true`, unknown name fails startup |
| C8 Config | YAML and `.properties` unchanged; golden test |
| C9 Exceptions | Adapter mapping as `shared`; module handling unchanged |
| gRPC payload | Identical — same transform, compression and credentials |
| API contract changes? | None |
| Data migration needed? | No |
| Deployable independently? | Released with all AppianWay modules in one release; a single service can still be rolled back alone because formats are unchanged |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:mercury-shared` | 1.0 | 1.0 | Upgrade | Re-based on commons; brings `commons`, `cloud-sdk-api`, `cloud-sdk-aws` 1.0.38-SNAPSHOT |
| `com.amazonaws:aws-java-sdk-sqs` | 1.12.720 | removed | Removal | Direct dependency dropped (still transitive via `cloud-sdk-aws` until upstream removal) |

No module-local versions for libraries managed by commons (rule C6).

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `WatermillPubTaskTest` (retargeted) | `QueueMessage` parse; ISO-8859-1 charset argument; transform failure → delete, no publish |
| 2 | `ResponseObserverTest` (retargeted) | Delete on ack with the stored receipt handle; expiry from `VisibilityTimeout` |
| 3 | `DeadLetterServiceTest` (retargeted) | DLQ receive (10, 20 s) → `sendMessage(target, body)` with no attributes/delay → delete from DLQ; stops after 3 empty receives |
| 4 | `WatermillPubModuleTest` (retargeted) | Injector builds with the `shared` v2 module and cloud-sdk fakes |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Task | `WatermillPubTaskTest` | Unit, mocked `shared` adapters |
| gRPC ack | `ResponseObserverTest` | Unit |
| DLQ | `DeadLetterServiceTest` | Unit, mocked `shared` adapters |
| Transform | `StatusEventProtobufTransformerTest` | Unchanged |
| Wiring | `WatermillPubModuleTest` | Guice injector, `functional-testing` cloud-sdk fakes |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT boot; post one pickup message | Published to Watermill; deleted after ack |
| 2 | Message in the DLQ | Back on the pickup queue after the next 30-min run, body unchanged |

### Existing Test Impact (ext)

Existing tests (JUnit 4 runner) are retargeted from v1 types to `QueueMessage` and the `shared` adapters; assertions on content are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: DLQ redrive continues after one failed run; a reconnect does not leave a running `CleanerThread`; a poison message stops cycling between the DLQ and the pickup queue.

---

## Risks

**Key Risks**

- Charset drift on the payload read — mitigated by the workspace adapter's charset overload and a test on the charset argument.
- Receipt-handle or visibility-timeout drift breaks delete-on-ack — mitigated by `ResponseObserverTest`.
- Redrive adding attributes or delay — mitigated by `DeadLetterServiceTest`.
- Existing, unchanged by this design:
  - `DeadLetterService` runs under `scheduleAtFixedRate`; any exception (for example an SQS error) ends all later runs until restart (`ListenerManager.java:31`, `DeadLetterService.java:29-46`).
  - Every stream reset creates a new `ResponseObserver`, which starts a new non-daemon `CleanerThread` that never stops and calls `GetQueueAttributes` (`StatusEventGrpcClient.java:91-99`, `ResponseObserver.java:29-31,67-69`); repeated reconnects leak threads.
  - `deleteMessage` in `ResponseObserver.onNext` is not guarded; an SQS failure there throws on the gRPC callback thread, which cancels the stream and clears all pending acks (duplicates on redelivery) (`ResponseObserver.java:40`).
  - `StatusEventGrpcClient.resetStream` is a non-volatile flag written by the gRPC thread and read by the listener thread (`StatusEventGrpcClient.java:28`).
  - `ListenerManager.stop()` does not stop the executors or the gRPC channel.

---

## Dependencies

**Major Dependencies**

- `shared` re-base: v2 Guice module, back-pressure listener client, SQS sender (incl. `getVisibilityTimeout`), workspace adapter, `ParameterSupplier` on `CloudParameterStore`, commons config command.
- `mercury-services-commons` 1.0.38-SNAPSHOT.
- `functional-testing` cloud-sdk fakes.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | N | No UI |
| 2 | Use of new services/ports | N | Same AWS services and resources; same Watermill endpoint; same ports |
| 3 | Authentication changes | N | AWS credentials from the default provider chain / task role, as today; Watermill authentication unchanged |
| 4 | New/changed encryption | N | No change; TLS to AWS and Watermill endpoints; SSM decryption as today |
| 5 | Changes in the way data is transmitted | Y | AWS client library changes from SDK v1 to SDK 2.x. Endpoints, credentials and payloads unchanged; gRPC unchanged |
| 6 | Changes in the way/location data is being stored | N | No data stored |
| 120 | New API implementation / change of existing APIs (Please fill the API arch table) | N | None |
| 124 | New / Change in existing file upload functionality | N | None |
| 125 | New / Change in integration within e2open or third-party apps | N | Watermill integration unchanged |
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
