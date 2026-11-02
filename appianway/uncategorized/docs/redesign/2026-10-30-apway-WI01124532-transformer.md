# WI01124532 transformer — AWS SDK 2.x (cloud-sdk) Upgrade

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

`transformer` consumes the `MetaData` envelope from its SQS pickup queue, reads the document from the workspace bucket, runs structural validation and the Contivo mapping, writes the transformed output (and, where applicable, the structural-validation result and the outbound transformation supplement JSON) to the workspace bucket, and routes the `MetaData` to the context success queue or the distributor-rest queue. When FA is requested, an FA `MetaData` is posted back to the transformer's own pickup queue. Outbound control numbers for EDIFACT (except ZIM), flat-file and XML envelopes are allocated from a DynamoDB sequence table; X12 uses a random 9-digit number and ZIM a time-based hex id (no AWS).

This change moves the module from AWS SDK v1 and the `shared` v1 wrappers to `commons` + `cloud-sdk-api` + `cloud-sdk-aws` **1.0.38-SNAPSHOT** (AWS SDK 2.x), using `shared` re-based on commons: SQS, SNS and workspace S3 go through the `shared` Tier-2 adapters; DynamoDB and SSM use commons / cloud-sdk directly (Tier 1). Contivo maps and `transform.properties` are read from the classpath (no S3 reference data). Queue messages, events, stored objects, encodings, S3 headers and control-number items are unchanged.


---

## Requirements

| | |
|---|---|
| **Epic** | N/A |
| **Story ID** | WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade |
| **Target Release** | TBD |
| **Scope** | `transformer` module only |
| **Fix Version** | TBD |
| **Customer/Client** | Internal — platform remediation |
| **Related Documents** (*If Any*) | WI01124532 AppianWay program design; WI01124532 `shared` design (contract C1–C9) |

### Functional Requirements

1. Read inbound documents as ISO-8859-1 (UTF-8 when the IPF attribute `sanitizeInbound` is true) and outbound documents as UTF-8, exactly as today.
2. Write transformed output through the workspace adapter `putObject(byte[])` (`application/octet-stream`); write the structural-validation result and the supplement JSON through `putObject(String)` (UTF-8, `Content-Type: text/plain`), under the same keys (`{rootWorkflowId}/{uuid}`).
3. Send the same `MetaData` JSON to the context success queue, the distributor-rest queue (projection `DISTRIBUTOR_REST`=true) or, for FA, the transformer pickup queue; error routing per context unchanged.
4. Allocate control numbers from the same DynamoDB table with the same item shape and optimistic-lock semantics (see DynamoDB Changes).
5. Keep event lineage, error codes, annotations and the retry/DLQ path unchanged.

### Non-Functional Requirements

1. No AWS SDK v1 API usage (`com.amazonaws` imports) in module sources.
2. Byte-for-byte compatibility of queue messages, events, stored objects and DynamoDB items (C1–C5).
3. Same listener concurrency (dispatcher threads = `maxNumberOfMessages`, default 10), long-poll wait and batch size as today.

### Acceptance Criteria

1. `mvn -pl transformer -am clean verify` is green.
2. Golden-fixture tests prove routed `MetaData`, FA `MetaData`, `Event`, structural-validation result and supplement JSON are byte-identical to the v1 build.
3. Content-type assertions: `text/plain` for string writes, `application/octet-stream` for byte writes.
4. DynamoDB-Local parity test: an item written by the v1 mapper is read and advanced by the v2 repository and vice versa; first write has `version` = 1; a stale `version` fails the condition and is retried.
5. INT boot and an end-to-end transformation produce the same objects, messages and control-number continuation as before.

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
| Storage | S3 workspace (get/put) via `shared` adapter; DynamoDB (control-number sequence) via cloud-sdk `DatabaseRepository` |
| Parameters | SSM Parameter Store (Network Services credentials) via `CloudParameterStore` |
| Mapping | Contivo runtime (classpath maps), unchanged |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | `shared` re-based on commons ships in the same release | Assumption | Resolved | Single release |
| 2 | `DatabaseRepository` has no consistent scan (`findAll()` is non-consistent and returns empty unless `isFindAllUnpaginatedScanEnabled`). Today the DAO does a consistent scan and fails if more than one item exists | Open Issue | Resolved | Interface only: read the single item with `DatabaseRepository.findById(DefaultPartitionKey("SequenceId"), true)`, a strongly consistent GetItem of the same item the scan returns today (the provider only ever writes key `SequenceId`; confirm the stored key in each environment before cut-over). The "more than one item" error is not raised until U6 (consistent-read flag on the repository scan) restores the scan. A direct SDK enhanced-client scan is not allowed (AWS SDK boundary, `shared` open issue 14) |
| 3 | v1 `AwsSdkMetrics.enableDefaultMetrics()` (namespace `AWSSDK_{environment}_{componentName}`) is JVM-wide; SDK 2.x has no global equivalent | Open Issue | Resolved | Kept: transformer passes the namespace `AWSSDK_{environment}_{componentName}` to the `shared` v2 module, which attaches one SDK 2.x `CloudWatchMetricPublisher` to its SQS, S3, SNS and DynamoDB clients (`shared` open issue 13). The SDK 2.x metric names and dimensions differ from v1, so dashboards or alarms on v1 metric names must be checked before cut-over |
| 4 | Control-number table is provisioned outside the application | Assumption | Resolved | `create-table` command kept with the identical schema (hash key `keyId` S, 10/10 provisioned) |
| 5 | Network Services clients stay in `shared` (Tier 3) | Assumption | Resolved | Unchanged |
| 6 | An SDK 2.x API-call timeout would bound the whole download (`getContent` buffers the body inside the timed call); v1's client-execution timeout did not cover reading the streamed body | Open Issue | Resolved | `shared` client profile sets no S3 API-call timeout; stalls are bounded by the 5 s socket timeout. Verify with the largest INT document |
| 7 | cloud-sdk rejects zero-length S3 writes; v1 wrote empty objects. A Contivo map that returns an empty target would hit this | Open Issue | Resolved | The `shared` workspace adapter writes zero-length objects through the interface-only fallback (`shared` open issue 3, U2): same key, metadata and content type |

---

## High Level Design

### Architectural Overview (ext)

```
 transformer pickup queue (SQS)
           │  shared back-pressure SQSListener (idle permits, wait 20 s, attrs=[failedAttempts])
           ▼
 AsyncDispatcher (maxNumberOfMessages threads) ─▶ TransformerTask
      │  ─▶ shared workspace adapter getContent (ISO-8859-1 / UTF-8)
      │  ─▶ StructuralValidationFAProcessor ─▶ putObject(String) result (text/plain)
      │                                     └▶ shared SQS sender: FA MetaData ─▶ pickup queue
      │  ─▶ OutboundTransformation ─▶ putObject(String) supplement (text/plain)
      │            └▶ ControlNumberSequenceProvider ─▶ DatabaseRepository       ─▶ DynamoDB
      │  ─▶ Contivo ─▶ putObject(byte[]) output (application/octet-stream)
      │  ─▶ shared SQS sender ─▶ success / distributor-rest queue
      └──▶ EventLogger ─▶ shared SNS event publisher (shared Json, raw JSON array)
           │
 failure ─▶ TransformerErrorHandler ─▶ retry (failedAttempts + DelaySeconds) / (pickup)_dlq / context errors queue
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | cloud-sdk `EnhancedDynamoRepository` (built by the `shared` client-profile helper so its client carries the metric publisher; Open Issue 3); `findById(.., consistentRead=true)` + `save()` with the enhanced client's default `VersionedRecordExtension` | Tier 1 (commons); table name passed in from `dynamoDbSequenceTable`; same item and lock semantics | No consistent scan, so the read becomes a consistent key lookup and the "more than one item" error waits for U6 (Open Issue 2) | ✅ |
| 2 | DAO on a `DynamoDbEnhancedClient` over the cloud-sdk-built `DynamoDbClient` (`createDynamoDbClient(config)`), consistent scan + versioned put | Keeps the scan and the guard exactly | Uses SDK client and table types directly, which the AWS SDK boundary forbids | ❌ |
| 3 | Call cloud-sdk `StorageClient` / `MessagingClient` / `NotificationService` directly | Fewer layers | Breaks C1 (wire parity enforced in `shared`): `putObject(String)` uses `text/plain; charset=UTF-8` and rejects blank content | ❌ |

### Data Flow — Before vs After (ext)

**Before:** v1 `AmazonSQS` receive → `shared S3WorkspaceService` (v1 `AmazonS3`) → v1 `DynamoDBMapper` (consistent scan, versioned save) → `shared SQSClient` / `SNSEventPublisher` (v1) → `shared Json`.

**After:** `shared` back-pressure listener over `MessagingClient<String>` → `shared` workspace adapter over `StorageClient` → cloud-sdk `DatabaseRepository` (`EnhancedDynamoRepository`: consistent GetItem, versioned PutItem) → `shared` SQS sender / SNS event publisher → `shared Json` (unchanged).

---

## Low Level Design

### Server

#### Key Components and Changes (ext)

| # | Component | Key Changes |
|---|-----------|-------------|
| 1 | `ExternalServicesModule` | Drops the v1 SQS/S3/SNS/DynamoDB builders and the unused `DynamoDBMapperConfig` binding. Installs the `shared` v2 module (one client per role from the C3 profile, `ManagedCloudResource` lifecycle). Binds `DatabaseRepository<ControlNumberSequence, DefaultPartitionKey<String>>` built by the `shared` client-profile helper as `EnhancedDynamoRepository` (table `dynamoDbSequenceTable`) over one DynamoDB client with the SDK standard retry and the CloudWatch metric publisher (Open Issue 3). `ParameterStoreModule` (shared) backed by `CloudParameterStore` |
| 2 | `TransformerApplication` | `initialize()` registers the commons-based config command instead of the shared one; config files unchanged. S3 config source via the `shared` bootstrap provider. Health checks (`InboundSqs`, `HttpGet`, `ErrorThreshold`, `SnsPublish`, `S3Write`, `OutboundSqs` per routing success/error queue) reuse the injected clients; the inbound SQS probe uses `getQueueAttributes` (`shared` open issue 11). `AwsSdkMetrics` removed (Open Issue 3) |
| 3 | `TransformerConfiguration` | Unchanged; YAML keys unchanged |
| 4 | `TransformerTask`, `StructuralValidationFAProcessor`, `TransformerErrorHandler` | SQS message type → SDK-neutral queue message from `shared`; same charsets, keys, content types and routing |
| 5 | `ControlNumberSequence` | v2 bean annotations: `@DynamoDbBean`; `getHashKey()` → `@DynamoDbPartitionKey @DynamoDbAttribute("keyId")`; explicit `getKeyId()` with `@DynamoDbIgnore` (Lombok getter would otherwise map a second `keyId`); `getId()` → `@DynamoDbAttribute("id")`; `getVersion()` → `@DynamoDbVersionAttribute` |
| 6 | `ControlNumberSequenceDao` | Wraps the repository: `find()` = `findById(new DefaultPartitionKey<>("SequenceId"), true)`; `save()` = repository `save()` (PutItem with the default `VersionedRecordExtension`: first write `attribute_not_exists`, then `version = :old`) |
| 7 | `ControlNumberSequenceProvider` | Catches `software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException` (propagated unwrapped by `EnhancedDynamoRepository.save`; one of the allowed SDK types, as in mercury-services, until U10); same seed, range, key and 10-attempt retry |
| 8 | `DynamoTableCommand` | Extends the commons-based config command; v2 `createTable` + waiter with identical key schema and throughput |
| 9 | `X12ControlCharacterPreprocessor` | `com.amazonaws.util.StringUtils.isNullOrEmpty` → commons-lang3 `StringUtils.isEmpty` |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| SQS | Long-poll receive (`failedAttempts` attribute), send to success / distributor-rest / pickup (FA) / context errors / retry / `_dlq` queues, delete | AWS SDK 2.x via `shared` adapters |
| S3 | Workspace get document; put output (bytes), validation result, supplement, error annotations (strings) | AWS SDK 2.x via `shared` workspace adapter |
| SNS | Publish close-run events | AWS SDK 2.x via `shared` event publisher |
| DynamoDB | Consistent GetItem and versioned conditional PutItem on the control-number sequence | AWS SDK 2.x via cloud-sdk `DatabaseRepository` |
| SSM | Read Network Services client credentials (with decryption) | AWS SDK 2.x via `CloudParameterStore` |

#### DynamoDB Changes (ext)

No schema or data change. Table name from `dynamoDbSequenceTable` (passed to the repository; no prefix logic). One item: `keyId` (S, hash key) = `SequenceId`, `id` (N, Long), `version` (N).

| Aspect | v1 today | v2 |
|--------|----------|----|
| Read | `DynamoDBMapper.scan` with `ConsistentReads.CONSISTENT`; error if more than one item | `findById(SequenceId, consistentRead=true)`; "more than one item" error after U6 (Open Issue 2) |
| Write | `DynamoDBMapper.save` (UpdateItem, SaveBehavior UPDATE) with `@DynamoDBVersionAttribute` | `save()` = PutItem with `VersionedRecordExtension` (default extension of the enhanced client inside `EnhancedDynamoRepository`). Item has only these three attributes, so PutItem and UpdateItem store the same item |
| First write | `version` = 1, expected `version` not exists | `version` = 1, `attribute_not_exists(version)` |
| Update | expected `version` = current, writes current + 1 | `version = :current`, writes current + 1 (SDK 2.30.24 parses it as `int`; one increment per 1000-number block, so no overflow risk) |
| Conflict | v1 `ConditionalCheckFailedException`, 10 retries in the provider, no backoff | v2 `ConditionalCheckFailedException`, same retry |
| Failure classification | Not `RecoverableException` → context errors queue | Unchanged: DynamoDB exceptions are not mapped to `RecoverableException` (v1 never wrapped them) |

DynamoDB client: built from `DynamoDbClientConfig` with the SDK default retry mode (throttling / 5xx only). It must not use `AwsRetryCondition`, which retries every failure and would resend a stale conditional write. v1 used the default DynamoDB client (`AmazonDynamoDBClientBuilder.standard()`, up to 10 retries).

Mixed fleet during rolling deploy is safe: both versions use the same attribute names and version condition.

### UI

N/A

### API Architecture

N/A — no API added or changed. Only the existing Dropwizard health/admin endpoints, unchanged.

---

## Configuration

### Component-Level Configuration

Application `initialize()` registers the commons-based config command instead of the shared one; config files unchanged. `conf/transformer.yaml` keys (including `dynamoDbSequenceTable`, `routing`, `envelopeCodeRules`, `formatConfig`) and `.properties` overrides are unchanged.

### Model-Level Configuration

N/A

### Stack-Level Configuration

No change. Same queues, topic, buckets, table and SSM parameter names.

### Professional Services/System Integrator Configuration

N/A

---

## Auditing/Logging

No change to application log messages or levels. `transformer.yaml` adds `com.inttra.mercury.cloudsdk: WARN` under `logging.loggers` (cloud-sdk logs individual S3/SNS calls at INFO), as the shared design requires.

### Event Publishing (ext)

Unchanged: close-run events with the same sub-types, workflow ids and tokens (`pickupQueue`, `dropOffQueue`, `transformationSupplement`, `timeTakenForStructuralValidation`, `timeTakenForTransformation`) and `success` flag, published as a raw JSON array to the same topic.

---

## Metrics and Statistics

Application metrics unchanged. AWS SDK CloudWatch metrics are kept under the same namespace through the SDK 2.x `CloudWatchMetricPublisher`, attached per client by the `shared` client-profile helper; the SDK 2.x metric names differ from v1 (Open Issue 3).

---

## Installer Changes

None. Same shaded jar, same start command.

---

## Impact on Current Application

### Migration Required

| Area | Needed? | Details |
|------|---------|---------|
| Database schema | No | Same table, key and attributes |
| Property migration | No | Config keys unchanged |
| Other file migration | No | Objects and messages unchanged |
| UI / look & feel | No | No UI |

### Runtime Behavior (ext)

No observable change: same queues, routing, objects, encodings, headers, events and control-number continuation. Each instance still reserves a block of 1000 numbers at first use and on every block rollover (numbers left in a block at shutdown are skipped, as today).

### Performance (ext)

- DynamoDB read becomes a single strongly consistent GetItem instead of a consistent full-table scan.
- S3 reads still buffer the whole object in memory (as v1 `IOUtils.toByteArray` does). The S3 client sets no API-call timeout, so the full download is not capped (Open Issue 6).
- Dispatcher threads (default 10) are well below the 50-connection pool per client.

### Deployment (ext)

Rolling restart as part of the single AppianWay release. v1 and v2 instances can run side by side against the same sequence table, so a single service can be rolled back alone. No data migration.

---

## Resiliency

- Unchanged error model: `RecoverableException` (all S3/SQS/SNS client failures, mapped by type in the `shared` adapters per C9) re-queues to the pickup queue with `failedAttempts` and `DelaySeconds`, then to `(pickup)_dlq`; other exceptions write annotations to the workspace bucket and post the `MetaData` to the context errors queue; then the message is deleted.
- Control-number contention: up to 10 immediate retries per block reservation. Existing behaviour kept: the provider's `retry` counter is only reset on success (`ControlNumberSequenceProvider.java:149`), so after one exhausted episode the next conflict fails at once.
- Existing behaviour kept: the non-recoverable path calls `TransformerErrorHandler.getErrorQueue` → `paramsProvider.get()` (`TransformerErrorHandler.java:46`), which reads the source document from S3 again and, for outbound, writes another supplement object and reserves another control number. If parameter resolution itself fails, `getErrorQueue` throws an NPE (`:50`), the message is not deleted, and SQS redelivers it until the queue redrive policy moves it.
- Hystrix (`externalwrapper`) is not used by this module.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files.

---

## Impact on Tools

None.

---

## Impact on Other Components

- `distributor`, `distributor-rest`, validator/booking/schedule consumers of the routed queues: None — `MetaData` JSON and stored objects unchanged.
- Event consumers (`event-writer`, `ingestor`): None — events unchanged.
- Partners: None — control numbers continue from the same sequence.

---

## Backwards Compatible

**Yes.** The only behaviour difference is that the "more than one item" error is not raised until U6 (Open Issue 2).

| Question | Answer |
|----------|--------|
| Routed / FA / error `MetaData` JSON | Identical — `shared` `Json` (C1) |
| Transformed output | Identical key and bytes; `Content-Type` `application/octet-stream` |
| Validation result / supplement JSON | Identical key and body; UTF-8, `Content-Type` `text/plain` |
| Events | Identical — same sub-types, tokens and lineage ids |
| Control-number item | Identical table, attribute names/types and `version` semantics |
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
| `com.inttra.mercury:cloud-sdk-aws` (brings `cloud-sdk-api`, AWS SDK 2.x `dynamodb-enhanced`) | — | 1.0.38-SNAPSHOT (via `shared`) | New | AWS SDK 2.x, DynamoDB repository |
| `com.amazonaws:aws-java-sdk-sqs`, `aws-java-sdk-dynamodb`, `aws-java-sdk-cloudwatchmetrics` | 1.12.720 | removed as direct dependencies | Removal | Replaced by AWS SDK 2.x |
| `software.amazon.awssdk:cloudwatch-metric-publisher` | — | AWS SDK 2.x version managed by commons; declared by `shared` | New (transitive) | Keeps the SDK CloudWatch metrics (Open Issue 3) |

---

## Unit Test Plan

### New Tests (ext)

| # | Test Class | Coverage |
|---|-----------|----------|
| 1 | `TransformerWireCompatibilityTest` | Golden fixtures: routed and FA `MetaData`, `Event`, validation result and supplement JSON byte-identical to v1 output |
| 2 | `ControlNumberSequenceParityTest` | DynamoDB Local: v1-written item read/advanced by v2 and vice versa; first write `version` = 1; stale `version` → `ConditionalCheckFailedException` |
| 3 | `ControlNumberSequenceProviderTest` (updated) | Retry on v2 `ConditionalCheckFailedException`; seed and range; give-up after 10 |
| 4 | `ControlNumberSequenceTest` (updated) | Bean schema: attribute names `keyId`/`id`/`version`, partition key, version attribute, `keyId` property not mapped twice |
| 5 | `TransformerTaskTest` (extended) | Charsets and content types of every write; routing to success / distributor-rest / FA queues |

### Test Layer Coverage (ext)

| Layer | Test Class | Faithfulness |
|-------|------------|-------------|
| Repository | `ControlNumberSequenceParityTest` | DynamoDB Local, real wire format |
| Task | `TransformerTaskTest`, `StructuralValidationFAProcessorTest` | Unit, mocked `shared` adapters |
| End-to-end | `*TransformationFuncTest` | `functional-testing` cloud-sdk fakes |

### Manual Tests (ext)

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | INT boot; transform one inbound and one outbound document | Same objects and routed envelopes as the v1 build |
| 2 | INT; outbound EDIFACT with control numbers | Numbers continue the existing sequence; item `version` incremented |
| 3 | INT; largest available workspace document | Read and write complete within the S3 client timeouts (Open Issue 6) |

### Existing Test Impact (ext)

Existing tests (JUnit 5; the functional tests are JUnit 4) are retargeted from v1 types and fakes to cloud-sdk / `shared` v2 types; assertions on messages, events, stored content and control numbers are kept.

Existing defects are not fixed in this program. Each one below gets a test that asserts the correct behaviour, committed disabled (JUnit 5 `@Disabled` with the defect reference) so the build stays green and the fix only has to enable it: the retry counter resets on each new message; the non-recoverable path does not write a second supplement or reserve a second control number.

---

## Risks

**Key Risks**

- Control-number duplication or reset if table name, key value, attribute mapping or version semantics differ — mitigated by the bean-schema test and the DynamoDB-Local parity test; key value checked per environment (Open Issue 2).
- Retrying conditional writes at SDK level if the DynamoDB client is given `AwsRetryCondition` — mitigated by the SDK default retry mode for DynamoDB.
- Large documents and S3 read timeouts — mitigated by the `shared` client profile (no S3 API-call timeout), Open Issue 6.
- Empty transform output rejected by cloud-sdk where v1 wrote an empty object — mitigated by the `shared` zero-length fallback (Open Issue 7).
- Dashboards or alarms built on v1 SDK metric names stop matching, because SDK 2.x publishes different metric names under the same namespace — Open Issue 3; check before cut-over.
- JSON or content-type drift if code bypasses the `shared` adapters — mitigated by C1 and golden tests.

---

## Dependencies

**Major Dependencies**

- `shared` re-based on commons, including the client profile (C3), the metrics helper (`shared` open issue 13) and empty-object writes (`shared` open issue 3).
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
| 6 | Changes in the way/location data is being stored | N | Same buckets, keys, bodies, headers and DynamoDB item |
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
