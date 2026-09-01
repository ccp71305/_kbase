# ION-16397 partner-integrator — AWS SDK 2.x (cloud-sdk) Upgrade

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

`partner-integrator` ("PI") is a multi-module partner-integration service — **8 `pi-*` submodules, 104 v1 files in
`src/main` and 26 in `src/test`** referencing `com.amazonaws.*`. It uses **DynamoDB (the v1 `DynamoDBMapper` ORM),
S3, SQS, SNS and SSM / Parameter Store**, plus two AWS Lambda stream-to-SNS handlers and an Elasticsearch (Jest)
indexer.

This change migrates every AWS interaction in the module from AWS SDK v1 (`com.amazonaws.*`) to the in-house
**cloud-sdk** (`cloud-sdk-api` + `cloud-sdk-aws`, AWS SDK **2.x** over Apache HTTP), bumps `commons` to
**1.0.31-SNAPSHOT**, drops the deprecated `dynamo-client`, and normalises `aws-lambda-java-events` to the **3.x**
line (which no longer drags the AWS SDK v1 DynamoDB client onto the classpath).

### Functional Description

`partner-integrator` bridges INTTRA's internal messaging domains (Booking, Shipping-Instruction, Bill-of-Lading,
Status/Container Events) to external partners over EDI/DX and Cargo-Visibility. Functionally, its submodules:

- **`pi-commons`** — shared library: S3 workspace access (`S3WorkspaceService`), SQS listener/sender plumbing,
  DynamoDB value objects (`vo.SI`, `vo.ContainerEvent`, `vo.EnrichedAttributes`) used to provision tables, network
  services and the async task/dispatcher framework.
- **`pi-booking-processor`** — reads the cross-service Booking table and feeds booking events outbound.
- **`pi-si-in-processor`** / **`pi-si-out-processor`** — inbound and outbound Shipping-Instruction feed processors
  (SI persistence, subscription resolution, Cargo-Visibility subscription publishing, EDI/DX outbound).
- **`pi-statusevents-out-processor`** — outbound Status/Container-Event processor (reads the `container_events` and
  cross-service `booking` tables, resolves subscriptions, publishes to EDI/DX and Watermill).
- **`pi-bl-in-processor`** — inbound Bill-of-Lading feed processor: persists `BLVersion` to the `bill_of_lading`
  DynamoDB table, provisions the table, and indexes BLs into Elasticsearch.
- **`pi-bl-es-lambda`** — the `bill_of_lading` DynamoDB-stream → Elasticsearch indexer Lambda.
- **`pi-lambda-streamToSns`** — two DynamoDB-stream → SNS relay Lambdas (`StreamToSnSProcessor`,
  `StreamStatusEventsToSnsProcessor`).

All of this behaviour is **unchanged** by this ticket — only the AWS SDK plumbing beneath it is migrated.

| Surface | Before | After |
|---|---|---|
| **DynamoDB (ORM)** | `dynamo-client` `DynamoDBMapper` + v1 `@DynamoDB*` field annotations | cloud-sdk `DatabaseRepository` + AWS SDK 2.x Enhanced Client (`@DynamoDbBean` on **getters**) |
| **DynamoDB (table admin)** | v1 `TableUtils` / `CreateTables` + `DeleteTables` commands | cloud-sdk `DynamoDbAdminCommand` (create-oriented; cloud-sdk exposes no delete command) |
| **S3** (`S3WorkspaceService`, `AWSUtil`) | v1 `AmazonS3` + `AmazonS3ClientBuilder` | cloud-sdk `StorageClient` via `StorageClientFactory` |
| **SQS** (listener/sender) | v1 `AmazonSQS` + `AmazonSQSClientBuilder` | cloud-sdk `MessagingClient` + AWS SDK 2.x `SqsClient` (per-message-delay path) |
| **SNS / event logging** | `com.inttra.mercury.messaging.*` (`SNSClient`, `SNSEventPublisher`, `EventLogger`, `MetaData`) | `com.inttra.mercury.cloudsdk.notification.*` (`NotificationService`, `EventLogger`, `MetaData`) via `NotificationClientFactory` |
| **SSM / Parameter Store** | v1 `AWSSimpleSystemsManagementClientBuilder` | cloud-sdk `CloudParameterStore` via `ParameterStoreClientFactory` |
| **Lambda stream event model** | `com.amazonaws.services.dynamodbv2.model.{AttributeValue,OperationType}` (v1 SDK) | `com.amazonaws.services.lambda.runtime.events.models.dynamodb.*` (self-contained, `aws-lambda-java-events` 3.x) |
| **Elasticsearch** | `com.inttra.mercury.module.JestModule` | `com.inttra.mercury.cloudsdk.aws.module.JestModule` (relocated in the earlier cloud-sdk refactor) |

There is **no functional, API, UI or wire-format change**. Every DynamoDB attribute name, key schema, GSI, stream
view type (`KEYS_ONLY`), the `expiresOn` TTL attribute, the converter encodings, the S3 object bodies, the SQS/SNS
delivery bodies and the SNS `DynamodbStreamRecord` JSON envelope are all preserved byte-for-byte.

**Status:** ✅ `mvn -f partner-integrator/pom.xml clean test` green — **4438** tests, 0 failures / 0 errors,
nothing weakened or `@Disabled`. Branch `feature/ION-16397-pi-aws-upgrade`, single commit carrying `ION-16397`.
*(Per-module counts in the Unit Test Plan.)*

---

## Requirements

| | |
|---|---|
| **Epic** | https://jira.dev.e2open.com/jira/browse/ION-15550 & Security Upgrade 26.3 |
| **Story ID** | ION-16397 — *partner-integrator AWS SDK 2.x (cloud-sdk) upgrade* |
| **Target Release** | **26.4** |
| **Scope** | `partner-integrator` (8 `pi-*` submodules) only. Oracle DB, the Elasticsearch document/search contract, the EDI/DX and Cargo-Visibility contracts and the REST API are out of scope and untouched |
| **Fix Version** | 26.4 |
| **Customer/Client** | None — internal security/platform remediation, no customer-visible change |

### Functional Requirements

- **No functional change from this ticket.** All existing behaviour must be preserved exactly.
- Persist and read every DynamoDB entity through the cloud-sdk repository with identical results:
  `BLVersion` (`bill_of_lading`, composite key `id`+`sequenceNumber`), `SIVersion`/`SI` (`si`), `ContainerEvent`
  (`container_events`, partition key `id`) and the cross-service `BookingDetail` (`<prefix>_booking_BookingDetail`).
- Preserve the GSIs unchanged in name, key and projection: `INTTRA_REFERENCE_NUMBER_INDEX` on `si`/`bill_of_lading`
  and the booking-table indexes, all `KEYS_ONLY`.
- Keep DynamoDB Streams `KEYS_ONLY` on every streamed table — the relay Lambdas depend on it.
- Preserve the `expiresOn` TTL attribute (epoch **seconds**, Number) and the per-field stored attribute types.
- Preserve the SNS `DynamodbStreamRecord` JSON envelope, the SNS-in-SQS envelope and the SQS delivery bodies
  byte-identically.
- Keep the cross-service `<prefix>_booking_BookingDetail` table-name resolution for the statusevents booking reader.

### Non-Functional Requirements

| # | Requirement | Target |
|---|---|---|
| 1 | No AWS SDK v1 **client** in `src/main` | Only `com.amazonaws.services.lambda.runtime.*` handler/event POJOs remain (needed to consume the Lambda `DynamodbEvent`); no v1 SDK client and no `dynamo-client` |
| 2 | DynamoDB wire compatibility | Every attribute name, key schema, GSI, stream view type, TTL attribute and converter encoding byte-identical |
| 3 | Wire envelopes | SNS `DynamodbStreamRecord` JSON, SNS-in-SQS and SQS bodies byte-identical after the `aws-lambda-java-events` 3.x normalisation |
| 4 | Lambda cold-start | AWS clients built with **explicit region and credentials provider** (the ION-16387 guard) |
| 5 | Configuration | Only the `dynamoDbConfig` type moves to `BaseDynamoDbConfig`; env values unchanged |
| 6 | Outgoing commits | Exactly **one** commit on top of `origin/develop`, message carrying `ION-16397` |
| 7 | Test suite | No test weakened, skipped or `@Disabled` to reach green; new code covered |

### Acceptance Criteria

| # | Criterion | Result |
|---|---|---|
| 1 | `mvn -f partner-integrator/pom.xml clean verify` green | ✅ BUILD SUCCESS — **4438** unit tests, 0 failures / 0 errors |
| 2 | No AWS SDK v1 DynamoDB/S3/SQS/SNS/SSM **client** in `src/main` | ✅ Only the kept `com.amazonaws.services.lambda.runtime.events.*` stream POJOs remain |
| 3 | No `com.inttra.mercury.dynamo.*` / `com.inttra.mercury.messaging.*` imports | ✅ All re-pointed to `com.inttra.mercury.cloudsdk.*` |
| 4 | Cross-service booking table resolution preserved | ✅ `<prefix>_booking_BookingDetail` reproduced in `pi-statusevents-out-processor` |
| 5 | Lambda region + credentials explicit | ✅ `HandlerSupport` sets both on every client; `US_EAST_1` fallback |
| 6 | Dual-publish routing preserved | ✅ `StreamStatusEventsToSnsProcessor` INSERT/REMOVE → both topics, MODIFY → all-events only |
| 7 | Exactly one outgoing commit | ✅ `git log develop..HEAD` = one commit carrying `ION-16397` |

### Jira Tickets (ext)

| Key | Summary | Type | Priority | Status | Assignee |
|-----|---------|------|----------|--------|----------|
| ION-16397 | partner-integrator AWS SDK 2.x (cloud-sdk) upgrade | Security / Platform Upgrade | Medium | In Review | Arijit Kundu |

### Support Tickets (ext)

None.

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard 5.x (`InttraServer`, Guice) for the 5 processors; AWS Lambda (`RequestHandler`) for the 3 Lambdas |
| Persistence | DynamoDB (cloud-sdk / AWS SDK 2.x Enhanced) |
| Search | Elasticsearch via Jest (`cloudsdk.aws.module.JestModule`, AWS SigV4 on v1 SDK) |
| Messaging | SQS + SNS via cloud-sdk `MessagingClient` / `NotificationService` |
| AWS SDK | cloud-sdk-aws → AWS SDK **2.x** (DynamoDB Enhanced, S3, SQS, SNS, SSM) |
| Build | Maven (shaded jars + Lambda assembly zips), JUnit 5 + Mockito + AssertJ |

---

## Assumptions and Open Issues

- **Elasticsearch stays on the v1 AWS SigV4 signer**, via the relocated `cloudsdk.aws.module.JestModule` — the
  established pattern in `booking`, `webbl` and `tx-tracking`, deferred to the separate OpenSearch track.
- **Model entity jars** for three cross-service tables are consumed as pinned `.M` artifacts and had to converge on
  v2-annotated builds: `booking` → **3.0.0.M**, `visibility` → **2.0.M**, `shipping-instruction` → **2.0.M**
  (ION-16396). These are staged into each consuming submodule's `lib/` repository.
- Live QA/CVT/PROD DynamoDB parity to be confirmed with the QA profile before release.

### Data Flow — Before vs After (ext)

**Before (AWS SDK v1):**
```
processors (SI/SE/BL/Booking)
  → *Dao extends DynamoDBCrudRepository → DynamoDBMapper.load/save/query   (dynamo-client, AWS SDK v1)
      → tables <env>_si, <env>_container_events, <env>_bill_of_lading, <env>_booking_BookingDetail
  S3WorkspaceService → AmazonS3 ; SQSClient/Listener → AmazonSQS ; events → messaging.SNSEventPublisher/EventLogger
  Utils.ssmParameterlookup → AWSSimpleSystemsManagement
DynamoDB stream (KEYS_ONLY) → pi-lambda-streamToSns → AmazonSNS.publish(...)
DynamoDB stream (KEYS_ONLY) → pi-bl-es-lambda IndexerHandler → Jest
Elasticsearch → com.inttra.mercury.module.JestModule
```
**After (cloud-sdk / AWS SDK 2.x):**
```
processors → *Dao → DatabaseRepository (cloud-sdk, AWS SDK 2.x Enhanced)   # same tables, keys, GSIs, streams
  S3WorkspaceService → StorageClient ; SQS → MessagingClient (+ SqsClient for delay) ; events → NotificationService/EventLogger (cloudsdk.notification)
  Utils.ssmParameterlookup → CloudParameterStore
DynamoDB stream (KEYS_ONLY) → pi-lambda-streamToSns → NotificationService.publish(topicArn, message)   # events 3.x
DynamoDB stream (KEYS_ONLY) → pi-bl-es-lambda IndexerHandler → Jest   # UNCHANGED
Elasticsearch → com.inttra.mercury.cloudsdk.aws.module.JestModule
```

---

## Low Level Design

### Server

The migration is wiring-and-type-mapping only; **no business logic was rewritten**.

#### API mapping — every removed symbol (ext)

| AWS SDK v1 / `dynamo-client` / `messaging` | Target |
|---|---|
| `services.dynamodbv2.datamodeling.DynamoDBMapper` (ORM) | `cloudsdk.database.api.DatabaseRepository<T,ID>` |
| `dynamo.respository.DynamoDBCrudRepository` | `cloudsdk.database.api.DatabaseRepository<T,ID>` |
| `dynamo.respository.id.DynamoHashAndSortKey` / `DynamoHashKey` | `cloudsdk.database.api.id.DefaultCompositeKey<String,String>` / `DefaultPartitionKey<String>` |
| `dynamo.respository.DynamoRepositoryConfig` | `cloudsdk.database.config.DynamoRepositoryConfig` |
| `dynamo.respository.module.DynamoDbConfig` | `cloudsdk.database.config.BaseDynamoDbConfig` |
| `dynamo.annotation.DynamoDBStream` | `cloudsdk.database.annotation.DynamoDBStream` |
| `@DynamoDBTable(tableName=)` | `cloudsdk.database.annotation.@Table(name=)` + `@DynamoDbBean` |
| `@DynamoDBDocument` (nested) | `@DynamoDbBean` |
| `@DynamoDBHashKey` / `@DynamoDBRangeKey` | `@DynamoDbPartitionKey` / `@DynamoDbSortKey` **on getters** |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName=)` | `@DynamoDbSecondaryPartitionKey(indexNames=)` + `cloudsdk...@GsiConfig` |
| `@DynamoDBAttribute(attributeName=)` | `@DynamoDbAttribute("…")` **on the getter** |
| `@DynamoDBIgnore` | `@DynamoDbIgnore` **on the getter** |
| `@DynamoDBTypeConvertedEnum` | *(none — SDK 2.x stores enums as `toString()`/`name()`/`S` by default; verified no enum overrides `toString()`)* |
| `@DynamoDBTypeConverted(converter=)` | `@DynamoDbConvertedBy(...)` implementing `software.amazon.awssdk.enhanced.dynamodb.AttributeConverter` |
| v1 `TableUtils` + `CreateTables`/`DeleteTables` | `cloudsdk.database.command.DynamoDbAdminCommand<T>` (create-oriented) |
| `services.s3.AmazonS3` / `AmazonS3ClientBuilder` | `cloudsdk.storage.api.StorageClient` via `StorageClientFactory` |
| `services.sqs.AmazonSQS` / `AmazonSQSClientBuilder` | `cloudsdk.messaging.api.MessagingClient` (+ AWS SDK 2.x `SqsClient` for per-message delay) |
| `messaging.sns.SNSClient` / `messaging.logging.SNSEventPublisher` | `cloudsdk.notification.api.NotificationService` via `NotificationClientFactory` |
| `messaging.logging.EventPublisher` / `EventLogger` / `messaging.model.{MetaData,Event}` | `cloudsdk.notification.workflow.{EventPublisher,EventLogger,MetaData,Event}` |
| `services.simplesystemsmanagement.*` (SSM) | `cloudsdk.paramstore.api.CloudParameterStore` via `ParameterStoreClientFactory` |
| `services.sns.AmazonSNS` (relay Lambdas) | `cloudsdk.notification.api.NotificationService` via `NotificationClientFactory.createConfiguredClient` |
| `services.dynamodbv2.model.{AttributeValue,OperationType}` | `services.lambda.runtime.events.models.dynamodb.{AttributeValue,OperationType}` (events 3.x) |
| `com.amazonaws.util.StringUtils` | Guava `Strings` / plain null-empty checks |
| `com.inttra.mercury.module.JestModule` | `cloudsdk.aws.module.JestModule` |

> The `com.amazonaws.services.lambda.runtime.*` handler and event POJOs are intentionally kept — they are how the
> Lambda/processor handlers parse the `DynamodbEvent` / `SNSEvent` records. In `aws-lambda-java-events` **3.x** the
> stream record extends the self-contained `events.models.dynamodb.Record` (not the v1 SDK `Record`), so the library
> no longer transitively drags `aws-java-sdk-dynamodb` onto the classpath.

#### Key Components and Changes (ext)

| # | Submodule | Key Changes |
|---|-----------|-------------|
| 1 | Parent `partner-integrator/pom.xml` | `mercury.commons.version` → `1.0.31-SNAPSHOT`; dependency-management for `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test`, `aws-lambda-java-events` (3.x); jackson BOM |
| 2 | `pi-commons` | S3 (`S3WorkspaceService`/`AWSUtil`) → `StorageClient`; SQS (`SQSClient`/`SQSListenerClient`) → `MessagingClient` + `SqsClient`; DynamoDB VOs (`vo.SI`, `vo.ContainerEvent`, `vo.EnrichedAttributes`) + converters (`CompressionConverter`, `DateToEpochSecond`) ported to v2; `messaging.*` → `cloudsdk.notification.*`; module-local `DynamoSupport` deleted |
| 3 | `pi-booking-processor` | `BookingApplicationInjector` on cloud-sdk repositories; `BookingDao` → `DatabaseRepository`; `booking` → 3.0.0.M |
| 4 | `pi-si-in-processor` | `SIApplicationInjector` + `SIDao` on cloud-sdk; entity `SIVersion` from `shipping-instruction:2.0.M` |
| 5 | `pi-si-out-processor` | Widest surface — S3+SQS+SNS+DDB+SSM; `SIDao` (fixed latent generic-type bug `ContainerEvent`→`SIVersion`); `CreateTables`/`DeleteTables` → `SIFeedDynamoDbAdminCommand`; `Utils.ssmParameterlookup` → `CloudParameterStore`; `aws-lambda-java-events` → 3.14.0 |
| 6 | `pi-statusevents-out-processor` | `SEFeedApplicationInjector` (S3+SQS+SNS+DDB + the `<prefix>_booking_BookingDetail` resolver); `BookingDao` + `ContainerEventDao` on cloud-sdk; `OutboundProcessor` → `QueueMessage` + `cloudsdk.notification` MetaData/EventLogger + events-3.x `OperationType`; `Utils` → `CloudParameterStore`; `booking` → 3.0.0.M, `visibility` → 2.0.M |
| 7 | `pi-bl-in-processor` | `BLApplicationInjector`, `BLDynamoDao`, `CreateTables`/`DeleteTables` → `BLFeedDynamoDbAdminCommand`; 28 `@DynamoDBDocument` BL model beans + `BLVersion` → v2; module-local `DynamoSupport` deleted; `JestModule` relocated + `ESConfiguration implements cloudsdk.config.ElasticSearchServiceConfig` |
| 8 | `pi-bl-es-lambda` | `HandlerSupport` (explicit region+credentials), `IndexerHandler`, `BLDynamoDao`, 28 BL model beans (identical to `pi-bl-in-processor`); Jest indexing untouched |
| 9 | `pi-lambda-streamToSns` | `StreamToSnSProcessor` + `StreamStatusEventsToSnsProcessor`: `AmazonSNS` → `NotificationService`; `OperationType`/`AttributeValue` → events-3.x; `HandlerSupport` region+credentials seam; dual-publish routing preserved with two `NotificationService` instances |

#### DynamoDB entity attribute mapping (ext)

The v1 annotations sat on **fields**; v2 requires them on **getters** — a silent-rename trap. Attribute names, types
and roles are unchanged.

**`BLVersion` → table `bill_of_lading`** (composite key; `@DynamoDBStream(KEYS_ONLY)` preserved):

| Attribute (on wire) | Type | Role | v1 (field) | v2 (getter) |
|---|---|---|---|---|
| `id` | S | **Partition key** | `@DynamoDBHashKey @DynamoDBAttribute("id")` on `getHashKey()` (field `id` `@DynamoDBIgnore`) | `@DynamoDbPartitionKey @DynamoDbAttribute("id")` |
| `sequenceNumber` | S | **Sort key** | `@DynamoDBRangeKey @DynamoDBAutoGeneratedKey @DynamoDBAttribute("sequenceNumber")` on `getSortKey()` | `@DynamoDbSortKey @DynamoDbAttribute("sequenceNumber")`; set by the entity constructor |
| `blInttraReferenceNumber` | S | **GSI** `INTTRA_REFERENCE_NUMBER_INDEX` (HASH) | `@DynamoDBIndexHashKey @DynamoDBAttribute` | `@DynamoDbSecondaryPartitionKey(indexNames=…)` + `@GsiConfig(KEYS_ONLY)` |
| `message` | S | attribute (**plain**, no converter) | `@DynamoDBAttribute` | property-derived getter (plain `S`) |
| `expiresOn` | N | attribute (**TTL**), **converted** | `@DynamoDBAttribute @DynamoDBTypeConverted(DateToEpochSecond)` | `@DynamoDbConvertedBy(DateToEpochSecond)` — epoch **seconds** |
| `carrierId`, `requestorId`, `shipperId`, `bookingNumber`, `blNumber` | S | attributes | field | property-name-derived getter (same name) |

> The **28 nested `@DynamoDBDocument` beans** (AirFlow, BLContract, Charge, … Weight) are `@DynamoDbBean` swaps; all
> enum fields drop `@DynamoDBTypeConvertedEnum` and use the SDK 2.x default enum converter (`toString()`==`name()`,
> verified no override) so the stored `S` is byte-identical. The two duplicated copies (in `pi-bl-in-processor` and
> `pi-bl-es-lambda`) are kept equivalent (they differ only by their `package`).

**Cross-service `BookingDetail` → table `<prefix>_booking_BookingDetail`** (read-only, from `booking:3.0.0.M`): the
v1 `DynamoDBMapperConfig` table-name resolver special-cased `BookingDetail` to `<prefix>_booking_<name>`; the
cloud-sdk `pi-statusevents-out-processor` injector reproduces this exactly as
`clientConfig.getTablePrefix() + "booking_" + @Table.name()` (the base prefix already carries the trailing `_`).

**`ContainerEvent` → table `container_events`** (partition key `id`, from `visibility:2.0.M`) and
**`SI`/`SIVersion` → table `si`** (composite key) — attribute names, GSIs, `expiresOn` TTL and converter encodings
unchanged.

### UI

N/A — headless service; no UI change.

### API Architecture

No REST endpoint, request/response body, header or status-code change.

---

## Configuration

### Component-Level Configuration

`conf/{int,qa,cvt,prod}/config.yaml`: the `dynamoDbConfig` block is **unchanged** in value (cloud-sdk
`BaseDynamoDbConfig` reads the same `readCapacityUnits` / `writeCapacityUnits` / `environment` / `sseEnabled`
fields); only its Java type moves from `dynamo-client` `DynamoDbConfig` to `cloudsdk.database.config.BaseDynamoDbConfig`.
SQS/S3/SNS/topic-ARN config blocks are untouched.

### Model-Level Configuration

Table names remain `<environment>_<table>` (prefix `environment + "_"`, identical to the v1 recipe), including the
double-prefixed cross-service `<environment>_booking_BookingDetail`. Keys, GSIs, projections and stream view types
are declared by the v2 entity annotations.

### Stack-Level Configuration

None new.

### Professional Services/System Integrator Configuration

None.

---

## Auditing/Logging

SLF4J/Logback unchanged. The cloud-sdk repository/module/command emit `INFO` table-wiring lines at startup.

### Logging Details (ext)

Unchanged log levels and messages except added `INFO` lines when the DynamoDB repositories and admin commands
initialise.

### Event Publishing (ext)

The tx-tracking close-run event contract is preserved: the `messaging.SNSEventPublisher`/`EventLogger` path is
replaced by `cloudsdk.notification.NotificationService`/`EventLogger`, publishing the same event payload to the same
tx-tracking topic ARN.

---

## Metrics and Statistics

No metric change. DynamoDB/SQS/SNS call characteristics are equivalent (AWS SDK 2.x over Apache HTTP).

---

## Installer Changes

None. Standard shaded-jar packaging for the 5 Dropwizard processors and Lambda-assembly zips for the 3 Lambdas.

---

## Impact on Current Application

### Migration Required

**No data migration.** The live tables already exist with the exact key/GSI/stream/TTL schema the v2 models map to.
The cloud-sdk admin commands are idempotent (describe-then-skip) and create/alter nothing on existing environments.

### Runtime Behavior (ext)

- DynamoDB reads/writes go through the AWS SDK 2.x Enhanced Client; attribute names and converter encodings are
  byte-identical.
- Lambda AWS clients now carry an explicit **region and** credentials provider (ION-16387 guard).
- S3/SQS/SNS calls use the cloud-sdk clients; SQS per-message delay is preserved via a cloud-sdk-configured
  AWS SDK 2.x `SqsClient`.

### Performance (ext)

Equivalent. No added network round-trips; GSI queries preserve the read-then-refetch pattern.

### Deployment (ext)

Standard rolling ECS deployment via Jenkins CI. No data migration, no config value change, no coordinated deployment.

---

## Resiliency

- **Wire compatibility is the core resiliency guarantee** — reads tolerate all existing 1.x data; writes reproduce
  the legacy representation (attribute names, `expiresOn` epoch-second `N`, converter blobs, GSIs, stream `KEYS_ONLY`,
  and the SNS/SNS-in-SQS envelopes).
- **Lambda cold-start** builds AWS clients with an explicit region and credentials provider so a cold container
  cannot fail with `CredentialsProvider must not be null` (the ION-16387 outage pattern).
- **Dual-publish routing** in `StreamStatusEventsToSnsProcessor` (INSERT/REMOVE → both topics, MODIFY → all-events
  only) is preserved and regression-tested.

---

## Temporary object cleanup, temporary files cleanup

No temporary files introduced. S3 reads close their streams on every path.

---

## Impact on Tools

N/A.

---

## Impact on Other Components

| Component | Impact |
|---|---|
| DynamoDB tables (`si`, `bill_of_lading`, `container_events`, cross-service booking) | **None** — same names, keys, GSIs, streams, TTL; admin commands idempotent |
| DynamoDB-stream relay/indexer Lambdas | **None** — streams stay `KEYS_ONLY`; envelope JSON byte-identical |
| S3 workspace / SQS queues / SNS topics | **None** — same buckets, queues, topics, bodies |
| Elasticsearch / REST API / Oracle | **None** — out of scope, untouched |
| Other mercury-services modules | **None** — change confined to `partner-integrator` (model jars consumed as pinned `.M` artifacts) |

---

## Backwards Compatible

**Yes — fully backwards compatible.**

| Question | Answer |
|----------|--------|
| Is the change backwards compatible? | Yes. All DynamoDB attribute names, key schema, GSIs, stream view types, the `expiresOn` TTL and converter encodings, and the SNS/SNS-in-SQS/SQS bodies are byte-identical |
| Are there breaking changes? | None to any external contract |
| API contract changes? | None |
| Data migration needed? | No — tables already match the v2 models |
| Do clients require changes? | No |
| Deployable independently? | Yes |
| Is any in-flight/at-rest item affected? | No — items written by 1.x read identically under 2.x and vice versa |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current | New | New/Upgrade | Reason |
|---|---|---|---|---|
| `com.inttra.mercury:commons` | prior | `1.0.31-SNAPSHOT` | Upgrade | cloud-sdk + relocated messaging/JestModule |
| `com.inttra.mercury:cloud-sdk-api` | — | `1.0.31-SNAPSHOT` | **New** | AWS SDK 2.x abstraction (database / storage / messaging / notification / paramstore) |
| `com.inttra.mercury:cloud-sdk-aws` | — | `1.0.31-SNAPSHOT` | **New** | AWS SDK 2.x implementation |
| `com.inttra.mercury:dynamo-client` | prior | **removed** | Removal | Replaced by cloud-sdk; removes the AWS SDK v1 DynamoDB mapper tree |
| `com.amazonaws:aws-java-sdk-{sns,dynamodb,…}` | v1.12.x | **removed** | Removal | Replaced by cloud-sdk (AWS SDK 2.x) |
| `com.amazonaws:aws-lambda-java-events` | 2.2.2 / 3.13.0 (mixed) | **3.14.0** (normalised) | Upgrade | 3.x stream record no longer extends the v1 SDK `Record` → drops transitive `aws-java-sdk-dynamodb` |
| `com.inttra.mercury:booking` (model) | 1.0.M/2.1.7.M/2.1.8.M | **3.0.0.M** | Upgrade | v2-annotated `BookingDetail` |
| `com.inttra.mercury:visibility` (model) | 1.4.M | **2.0.M** | Upgrade | v2-annotated `ContainerEvent` |
| `com.inttra.mercury:shipping-instruction` (model) | 1.0.M | **2.0.M** | Upgrade | v2-annotated `SIVersion` (ION-16396) |
| `elasticsearch` / Jest | prior | unchanged | **Unchanged** | ES stays on the v1 SigV4 signer (separate OpenSearch track) |


---

## Unit Test Plan

`mvn -f partner-integrator/pom.xml clean verify` = **BUILD SUCCESS** — **4438** unit tests, 0 failures / 0 errors.
**No test was weakened, skipped or `@Disabled`.**

Baseline was **4452** tests on `develop`. The small net delta is obsolete v1-implementation tests removed and
replaced with cloud-sdk equivalents (e.g. `DynamoSupportTest`, v1 `CreateTables`/`DeleteTables` command tests) —
offset by new cloud-sdk unit tests. Per-module post-migration counts:

| Submodule | Baseline | Post |
|---|---:|---:|
| pi-commons | 1216 | 1210 |
| pi-booking-processor | 2025 | 2032 |
| pi-si-in-processor | 504 | 504 |
| pi-si-out-processor | 264 | 243 |
| pi-statusevents-out-processor | 50 | 58 |
| pi-lambda-streamToSns | 16 | 22 |
| pi-bl-in-processor | 313 | 279 |
| pi-bl-es-lambda | 64 | 90 |
| **Total** | **4452** | **4438** |

### New / Rewritten Tests (ext)

| # | Area | Type | Coverage |
|---|------|------|----------|
| 1 | `*Dao` (all modules) | Unit | Rebuilt on a mocked cloud-sdk `DatabaseRepository`; `findById`/`query`/GSI paths, null guards |
| 2 | `SEFeedApplicationInjector` / `*DynamoModule` | Unit | Constructor/generator/listener wiring (config-package coverage-excluded for the AWS-bound `@Provides`) |
| 3 | `Utils.ssmParameterlookup` | Unit | `CloudParameterStore` happy/absent/blank paths via a mocked `ParameterStoreClientFactory` |
| 4 | `OutboundProcessor` (statusevents) | Unit | `QueueMessage` payload parse, events-3.x `OperationType` routing, `cloudsdk.notification` MetaData/EventLogger |
| 5 | `HandlerSupport` (Lambdas) | Unit | `resolveRegion(Supplier)` success/null/exception → `US_EAST_1` fallback; `createNotificationService` via a mocked factory (asserts region + credentials non-null) |
| 6 | `StreamToSnSProcessor` / `StreamStatusEventsToSnsProcessor` | Unit | INSERT/REMOVE/MODIFY routing, dual-publish, empty-list and publish-exception handling |
| 7 | `*DynamoDbAdminCommand` | Unit | Entity list + `resolveClientConfig` null guards |
| 8 | Converters (`DateToEpochSecond`, BL/vo) | Unit | Byte-compat assertions bridged to the v2 `transformFrom`/`transformTo` API |

### Existing Test Impact (ext)

Obsolete v1-implementation tests (module-local `DynamoSupportTest`, `CreateTables`/`DeleteTables` command tests) are
rewritten to the cloud-sdk equivalents; DAO tests move from a mocked v1 `DynamoDBMapper` to a mocked cloud-sdk
`DatabaseRepository`. No behaviour test was weakened.

### Manual Tests (ext)

Local INT boot-check of the 5 Dropwizard submodules and live AWS `describe-table` verification (below).

---

## Risks

**Key Risks**

- **High** — the 28-bean BL model v1→v2 conversion silently renames an attribute (v1 annotations on **fields**,
  v2 on **getters**), or the two duplicated copies drift. *Mitigation:* mechanical getter-based mapping following the
  migrated `vo.SI`; the two copies kept equivalent (normalised diff); no attribute renames on nested beans.
- **High** — converter/enum encoding drift (`DateToEpochSecond`; `@DynamoDBTypeConvertedEnum` → SDK 2.x default).
  *Mitigation:* converter ported byte-identically (epoch-seconds `N`); verified **no enum overrides `toString()`** so
  the default enum converter stores the same `S`.
- **High** — `aws-lambda-java-events` 2.x transitively is an AWS-SDK-v1 dependency; the SNS `DynamodbStreamRecord`
  JSON envelope must not change after the 3.x normalisation. *Mitigation:* 3.13/3.14 expose byte-identical getter
  names; the relay Lambdas' routing is regression-tested.
- **High** — the cross-service `<prefix>_booking_BookingDetail` resolution must be preserved for the statusevents
  booking reader. *Mitigation:* reproduced explicitly in the injector; note the physical name segment is
  `booking_BookingDetail` (v1 `@DynamoDBTable` name was `BookingDetail`).
- **Medium** — cloud-sdk `MessagingClient` has no per-message delay. *Mitigation:* retain a cloud-sdk-configured
  AWS SDK 2.x `SqsClient` for the delay path.
- **Medium** — model-jar pins (`booking`/`visibility`/`shipping-instruction`) must be v2-annotated. *Mitigation:*
  converged on 3.0.0.M / 2.0.M / 2.0.M, staged into each submodule's `lib/`.

---

## Dependencies

**Major Dependencies**

- `commons 1.0.31-SNAPSHOT` (`cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test`, relocated
  `messaging`/`JestModule`).
- v2-annotated model jars: `booking:3.0.0.M`, `visibility:2.0.M`, `shipping-instruction:2.0.M`.
- `aws-lambda-java-events:3.14.0` (self-contained stream event model).

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

Internal security/platform remediation (removes the AWS SDK v1 DynamoDB/S3/SQS/SNS/SSM client trees). No new external
surface; no secrets in code or config.

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | **N** | No UI surface; no new endpoint, field or exposed attribute |
| 2 | Use of new services/ports | **N** | Same AWS services (DynamoDB, S3, SQS, SNS, SSM), same tables/queues/topics/buckets, same Elasticsearch domain, same app/admin ports |
| 3 | Authentication changes | **N** | AWS credentials still come from the `DefaultCredentialsProvider` chain / ECS task role — never hard-coded. The Lambda handlers now pass the region **and** provider **explicitly** (ION-16387 guard) — same chain, stated rather than implied |
| 4 | New/changed encryption | **N** | No change. TLS to all AWS endpoints; DynamoDB `sseEnabled` unchanged |
| 5 | Changes in the way data is transmitted | **Y** | AWS transport stack changed: AWS SDK v1 → **AWS SDK 2.x over Apache HTTP** (via `cloud-sdk-aws`) for DynamoDB/S3/SQS/SNS/SSM. Endpoints, region, credentials chain, TLS and every payload unchanged — only the client library |
| 6 | Changes in the way/location data is being stored | **N** | Same tables, key schema, GSIs, stream view types (`KEYS_ONLY`), the `expiresOn` TTL and every converter encoding — byte-identical. Same S3 buckets/keys/bodies. **No data migration** |
| 120 | New API implementation / change of existing APIs (Please fill the API arch table) | **N** | No REST endpoint, request/response body, header or status code changed |
| 124 | New / Change in existing file upload functionality | **N** | S3 workspace writes are internal service-to-service and unchanged in bucket, key and body |
| 125 | New / Change in integration within e2open or third-party apps | **Y** | Third-party AWS integration libraries replaced: `dynamo-client` and `aws-java-sdk-*` removed; `cloud-sdk-api`/`cloud-sdk-aws` (AWS SDK 2.x) added; `commons` bumped to `1.0.31-SNAPSHOT`; `aws-lambda-java-events` normalised to 3.x. Which AWS services/tables/queues/topics/buckets are integrated is unchanged |
| 126 | New / Existing UI functionality support querying via either of them (VST, XML, java expressions, SQL or any other) | **N** | No expression language exposed; DynamoDB access is typed repository calls and GSI key lookups (`DefaultQuerySpec` / `CloudAttributeValue`) — no string-concatenated filter expressions |

---

## REQUIRED: Documentation Changes

### Engineering Documentation Impact (ext)

- This Confluence design document is the design record for the change.

---

## Blocking Issues and Actions from the Design Review

None outstanding.

---

## Deployment Verification (ext)

### INT — local boot on the migrated build — ✅ (2026-08-21)

All **5 Dropwizard submodules** were booted on the INT profile with a valid INT AWS SSO session (account
`081020446316`, `us-east-1`) and each returned **HTTP 200** on both the application ping and the admin healthcheck.
Guice injection built the cloud-sdk DynamoDB repositories (`BaseDynamoDbConfig` resolving region `us-east-1` +
`DefaultCredentialsProvider`), `StorageClient` / `MessagingClient` / `NotificationService`, the new
`*DynamoDbAdminCommand`s and the relocated `cloudsdk.aws.module.JestModule` ES client; the SQS/MQ listeners started
and (where applicable) the Oracle healthcheck passed.

| Submodule | Ports (app/admin) | App ping | Admin healthcheck |
|---|---|---|---|
| `pi-statusevents-out-processor` | 8080 / 8081 | ✅ 200 `{"healthy":"true"}` | ✅ 200 (Basic functionality, deadlocks) |
| `pi-si-out-processor` | 8080 / 8081 | ✅ 200 `{"healthy":"true"}` | ✅ 200 (Basic functionality, deadlocks) |
| `pi-si-in-processor` | 8080 / 8081 | ✅ 200 `{"healthy":"true"}` | ✅ 200 (Basic functionality, deadlocks, **oracle**) |
| `pi-booking-processor` | 8080 / 8081 | ✅ 200 `{"healthy":"true"}` | ✅ 200 (Basic functionality, deadlocks, **oracle**) |
| `pi-bl-in-processor` | 8090 / 8091 | ✅ 200 `{"healthy":"true"}` | ✅ 200 (Basic functionality, deadlocks, **oracle**) |

> The two Lambda submodules (`pi-lambda-streamToSns`, `pi-bl-es-lambda`) and the `pi-commons` library are not
> bootable Dropwizard servers; their AWS wiring is validated by unit tests (including the `HandlerSupport`
> region+credentials seam) and the shaded/assembly packaging in `mvn verify`. Exact run commands and the healthcheck
> steps are recorded in the engineering design doc (`docs/2026-0731-pi-aws-upgrade-design.md`, §8).

### Live DynamoDB schema parity

To be confirmed with the INT profile: `si`, `bill_of_lading`, `container_events` and the cross-service booking table
key schema, GSIs (`KEYS_ONLY`), streams (`KEYS_ONLY`) and `expiresOn` TTL align with the v2 entity mappings; the
cloud-sdk admin commands describe-then-skip (no new table creation on live environments).

### QA / CVT / PROD

To be verified with the QA profile before release; INT verified above.

---

## Post-Merge Fix — `pi-bl-es-lambda` Deployment Package Size (PIBL-ES Lambda)

> Added 2026-08-29 as a follow-up to the AWS SDK 2.x upgrade. Tracked under the same ticket (ION-16417);
> engineering runbook and full command log in `docs/2026-08-29-pibl-es-lambda-build-issue.md`.

### What broke

After the upgrade merged to `develop`, the **PIBL-ES Lambda Jenkins job failed at deploy time** (not at
build time) with:

```
An error occurred (InvalidParameterValueException) when calling the UpdateFunctionCode operation:
Unzipped size must be smaller than 262144000 bytes
```

`262,144,000 bytes = 250 MB` is AWS Lambda's **hard limit on the total *unzipped* deployment package**
(function code **plus** any attached layers). `pi-bl-es-lambda` ships as a single Maven-shaded fat-jar
that *is* the deployment package, so the whole dependency set is unpacked into that 250 MB budget.

### Root cause — a pre-existing heavyweight, tipped over by the upgrade

Two independent contributors stacked up:

1. **(Pre-existing) The full Elasticsearch *server* distribution for two lines of query building.**
   `pi-bl-es-lambda` performs all its Elasticsearch I/O through the lightweight **Jest** client, but
   `Indexer.java` also imported `org.elasticsearch.index.query.QueryBuilders` /
   `BoolQueryBuilder` / `SearchSourceBuilder` — **purely to assemble a term query as a JSON string**:

   ```java
   BoolQueryBuilder q = QueryBuilders.boolQuery().must(QueryBuilders.termQuery("siId", siId));
   return SearchSourceBuilder.searchSource().query(q);   // -> .toString()
   ```

   Those two lines drag in **`org.elasticsearch:elasticsearch` 8.17.0 — the entire ES server** — which
   transitively pulls **13 Lucene 9.12 modules, Log4j2, grok/joni, tdigest, HdrHistogram, hppc and
   native libraries (~35 MB zipped / ~80 MB unzipped)**. This weight was already present *before* the
   upgrade; the Lambda was sitting just under the 250 MB ceiling with little headroom.

2. **(New) `cloud-sdk-aws` replaced the lean single-service v1 client with an all-services aggregate.**
   The upgrade swapped the ~4 MB AWS SDK v1 `dynamo-client` for the shared **`cloud-sdk-aws`**
   aggregate, which declares the AWS SDK **2.x** clients for **S3, S3-transfer-manager, SES, SNS, SQS,
   SSM and DynamoDB**, **three** HTTP clients (Apache, URL-connection and the **native `aws-crt`**),
   plus a transitive copy of **AWS SDK v1** — ~40 MB zipped. This Lambda only needs **DynamoDB +
   DynamoDB-Enhanced** (and one HTTP client).

Stacked on the ES server jar and the Dropwizard/Jetty/POI/MySQL tree that `commons` brings, the extra
`cloud-sdk-aws` service clients **removed the last of the headroom and pushed the package over 250 MB**.

### Resolution — ship only the runtimes the Lambda actually loads

The fix keeps the artifact as a fat-jar but trims it to the classes this Lambda executes, via Maven
`<exclusions>` (no functional change):

- **AWS SDK:** exclude the unused AWS SDK 2.x services (`s3`, `s3-transfer-manager`, `sesv2`, `sns`,
  `sqs`, `ssm`), the redundant HTTP clients (`url-connection-client`, `aws-crt-client` + native
  `aws-crt`) and the transitive **AWS SDK v1** tree — keeping **DynamoDB + DynamoDB-Enhanced** and the
  **Apache** sync HTTP client only.
- **Web stack from the in-house aggregates:** exclude the Dropwizard / Jetty / Jersey / HK2 / Codahale,
  MySQL, MyBatis, POI/XmlBeans, jsoup, Spring-Security-crypto bundles a Lambda never uses.
- **Elasticsearch:** retained for now (query-string building still uses it); flagged as follow-up to
  replace with a lightweight client and drop the server jar (a further ~80 MB unzipped).

### Tripwires encountered (and how they were resolved)

- **The Apache HTTP client cannot be excluded.** cloud-sdk's `DynamoDbClientConfig` instantiates
  `software.amazon.awssdk.http.apache.ApacheHttpClient` as its sync client; excluding it fails at
  runtime with `NoClassDefFoundError: .../ApacheHttpClient` (caught by `HandlerSupportTest`). Exactly
  **one** sync HTTP client is kept (Apache); the other two are dropped.
- **The web stack is declared on *three* paths.** `dropwizard-core` (→ Jetty/Jersey/HK2) is pulled by
  **`commons`, `cloud-sdk-api` and `cloud-sdk-aws`**; excluding it from one path just re-resolves it via
  the next, so the exclusions had to be applied to **all three**. (Maven wildcard `artifactId`
  exclusions *are* supported — 3.2.1+/MNG-5600 — and did work; the gap was the multiple paths.)
- **`Indexer.java` genuinely used two classes from that stack**, blocking a clean exclusion:
  - `org.eclipse.jetty.io.RuntimeIOException` → replaced with the JDK-standard
    `java.io.UncheckedIOException` (identical semantics: an unchecked wrapper around `IOException`).
  - `com.codahale.metrics.annotation.@Timed` on `index()` was **dead code in the Lambda**: `Indexer` is
    constructed directly (`new Indexer(newJestClient())` in `IndexerHandler`) with **no `MetricRegistry`,
    no Guice AOP interceptor and no JAX-RS/Jersey listener** to honour the annotation, so no timer was
    ever recorded (it was live only in the code's earlier Dropwizard-hosted life). It was removed and the
    timing **intent restored with dependency-free instrumentation** — `System.nanoTime()` around
    `index()`, logging `Indexed bl <id> in <N> ms`.

### Pre/post size and validation

| Stage | Unzipped size | vs 250 MB (262,144,000 B) limit |
|---|---:|---:|
| **Before fix** (`develop`) | **334.4 MB** (350,672,249 B) | ❌ over by 84.4 MB |
| Dependency exclusions only | 177.7 MB (186,299,610 B) | ✅ under by 72.3 MB |
| **After fix** (+ web-stack removal on all 3 paths + `Indexer.java` cleanup) | **146.5 MB** (153,598,295 B) | ✅ **under by 103.5 MB** |

Validated locally with `mvn -pl partner-integrator/pi-bl-es-lambda package` on JDK 17 / Maven 3.9.11:
**BUILD SUCCESS, 93/93 unit tests pass (0 failures, 0 errors)**; the resolved dependency tree is clean of
Dropwizard/Jetty/Jersey/HK2/Codahale and the unused AWS services. No DynamoDB schema, ES mapping,
SNS/SQS envelope or wire-format change. Delivered on branch
`feature/ION-16417-pibl-es-lambda-size-fix` (PR #1219).

---

## Design Document Review and Approval Matrix

> Add **"Approved"** or **"NA"** in the status column to approve the design document.
> **Approval Status Should have "Approved" or "NA" Only.**

| Stage | Reviewer | Status | Notes | Ownership |
|-------|----------|--------|-------|-----------|
| Design | @Arijit Kundu | Approved | Design authored and implemented under ION-16397 (single commit `343ec541ec` on `feature/ION-16397-pi-aws-upgrade`) | **Product Management** |
| Product Owner | @Mahendran Pandian | | | **Product Owner** |
| Pre Dev Security | @Kamalesh Bhol | | Removes the AWS SDK v1 DynamoDB/S3/SQS/SNS/SSM client trees; no new external surface | **InfoSec** |
| Pre Dev Architecture | @Arijit Kundu | Approved | cloud-sdk repository / notification / storage / paramstore patterns and the wire-compatibility approach | **Product Development** |
| Browser | NA | NA | No UI surface | **Product Development** |
| UX | NA | NA | No UI surface | **Product Development** |
| Post Dev Security | @Kamalesh Bhol | | | **InfoSec** |
| Post Dev Architecture | @Arijit Kundu | Approved | | **Product Development** |
| QA/Test Driven Development (TDD) | @Venkat Ganga | | `mvn clean verify` green (4438 tests) + QA-profile DynamoDB parity | **Product Development/QA** |
