# Ocean Schedules Service — Design Document (AWS SDK 2.x Migration)

**Contributors:** Arijit Kundu

---

## Contents

1. [Requirements](#requirements)
2. [Assumptions and Open Issues](#assumptions-and-open-issues)
3. [High Level Design](#high-level-design)
4. [Low Level Design](#low-level-design)
5. [Configuration](#configuration)
6. [Auditing/Logging](#auditinglogging)
7. [Metrics and Statistics](#metrics-and-statistics)
8. [Impact on Current Application](#impact-on-current-application)
9. [Resiliency](#resiliency)
10. [Backwards Compatible](#backwards-compatible)
11. [Unit Test Plan](#unit-test-plan)
12. [Pre-Dev Security](#pre-dev-security)
13. [Documentation Changes](#documentation-changes)
14. [Review](#review)

---

## Requirements

The **Ocean Schedules Service** is a Mercury platform multi-module system responsible for ingesting, processing, and serving ocean carrier sailing schedules. It collects schedule data from multiple carrier APIs and EDIFACT/ANSI feeds, normalizes the data, stages it in DynamoDB, aggregates multi-source schedules, indexes them in Elasticsearch for search, and generates outbound schedule files in EDI/CSV/XML formats.

The system consists of **2 top-level modules** spanning **9 deployable units**:

**`oceanschedules/`** — Dropwizard 4.0.16 REST API service:
- Schedule search (port-to-port, multi-carrier)
- Real-time cache for fast carrier schedule lookups via DynamoDB
- External carrier API integration (Maersk, MSC, CMA, ZIM, Hapag-Lloyd, Evergreen, HMM, etc.)
- Pipeline trigger notifications via SNS
- Schedule file management via S3

**`oceanschedules-process/`** — Batch processing pipeline (8 sub-modules):
- **common** — Shared library (SQS, SNS, S3 clients, models, utilities)
- **collector** — Scheduled API polling service (Dropwizard)
- **inbound** — EDIFACT/ANSI parser (Apache Spark batch)
- **staging** — Staging transformer (Apache Spark batch)
- **aggregator** — Multi-source aggregator (Spark + DynamoDB)
- **loader** — Elasticsearch indexer (Spark + Jest)
- **outbound** — Export processor — EDIFACT/ANSI/CSV/XML (Spark)
- **port-pair-generator** — Port-pair route discovery (Dropwizard)

This document covers the AWS SDK 1.x → 2.x migration via `cloud-sdk-api` and `cloud-sdk-aws` libraries, following the patterns established in `webbl`, `booking-bridge`, `booking`, `network`, `auth`, `registration`, `tx-tracking`, `self-service-reports`, and `db-migration` modules.

### Key Responsibilities
- **Schedule Collection**: Polls carrier APIs (REST) and processes EDIFACT/ANSI feeds
- **Data Staging**: Transforms and stores intermediate schedule data in DynamoDB (`schedules_pro_staging`)
- **Schedule Aggregation**: Aggregates schedules from multiple sources per port-pair
- **Search Indexing**: Loads aggregated schedules into Elasticsearch for REST API search
- **Outbound Generation**: Generates EDI/CSV/XML outbound files uploaded to S3
- **Pipeline Orchestration**: Triggers pipeline stages via SQS/SNS messages
- **Real-Time Cache**: Caches recently-fetched carrier schedules in DynamoDB (`os_realtime_cache`)
- **REST APIs**: Exposes schedule search, carrier management, and user preference endpoints

### Technology Stack
- **Framework**: Dropwizard 4.0.16 (API, collector, port-pair-generator), Apache Spark 3.5.3 (batch jobs)
- **Dependency Injection**: Google Guice
- **AWS SDK**: Version 2 (via cloud-sdk-aws `1.0.23-SNAPSHOT`)
- **Messaging**: SQS (via cloud-sdk-api `MessagingClient`), SNS (via cloud-sdk-api `NotificationService`)
- **Storage**: S3 (via cloud-sdk-api `StorageClient`)
- **Database**: DynamoDB (via cloud-sdk-api `DatabaseRepository`), Elasticsearch (via Jest 6.3.1)
- **Parameter Store**: SSM (outbound module — AWS SDK v2 `SsmClient`)
- **Batch Processing**: Apache Spark 3.5.3 with Hadoop 3.3.4
- **Testing**: JUnit Jupiter 5.10.1, JUnit 4.12 (process modules), Mockito 5.2.0–5.8.0

Detailed design documents for "cloud-sdk-api" and "cloud-sdk-aws" implementations are available at:

1. [AWS Java SDK upgrade - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
2. [High Level Design for AWS S3 Service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
3. [High Level Design for AWS SNS service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
4. [High Level Design for AWS SQS service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
5. [High Level Design for AWS Dynamo DB service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)

---

## Assumptions and Open Issues

### Assumptions
- The `cloud-sdk-api` and `cloud-sdk-aws` libraries (version `1.0.23-SNAPSHOT`) provide full coverage for all AWS service operations required by the ocean schedules modules
- The booking module's AWS 2.x upgrade is **fully merged to `develop`** (final version `1.0.23-SNAPSHOT`). No cross-module dependency between ocean schedules and booking.
- DynamoDB Local (embedded, no Docker) via `dynamo-integration-test` is sufficient for integration testing of both DynamoDB tables (`os_realtime_cache`, `schedules_pro_staging`)
- The ocean schedules DynamoDB entities are **flat** (no nested `@DynamoDBDocument` models) — only primitives, strings, and dates with `DateToEpochSecond` converters. This simplifies the migration compared to booking/visibility.
- **Data format backward compatibility**: `DateEpochSecondAttributeConverter` implementations must handle legacy epoch second values written by SDK v1 `DynamoDBMapper`. This is straightforward since the date ↔ epoch mapping is purely numeric (no format ambiguity like timestamps).
- Apache Spark jobs can use cloud-sdk clients without serialization issues (AWS SDK v2 clients should not be serialized across Spark executors — they should be created per-executor via `@transient` or lazy initialization patterns).
- The `amazon-sqs-java-extended-client-lib:1.2.6` (SDK v1) used for large SQS messages can be replaced with the SDK v2 equivalent or application-level S3 offloading via `StorageClient`.

### Open Issues
- **SQS Extended Client**: The SDK v1 extended client library for large messages needs to be replaced. Options: (a) AWS SDK v2 SQS extended client, (b) cloud-sdk `MessagingClient` if it supports payload offloading, or (c) manual S3 offloading.
- **`StorageClient` coverage**: Verify that the `StorageClient` interface supports paginated listing, batch delete, and copy operations used by `S3Service` and `S3WorkspaceService`.
- **SSM Parameter Store**: Verify if cloud-sdk provides an SSM API or if AWS SDK v2 `SsmClient` should be used directly in the outbound module.
- **Spark + cloud-sdk serialization**: Cloud-sdk AWS clients are not serializable. Spark executor code must create clients lazily, not serialize them.
- **Generic type parameter**: Both entity classes (`RealTimeCache<T>`, `SchedulesProStaging<T>`) declare an unused generic `<T>`. Verify the Enhanced Client handles generic beans; if not, remove `<T>`.

### Branch Strategy

Create a feature branch directly from `develop`:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/oceanschedules-aws-sdk-2x-upgrade
```

No cherry-picking or rebase-drop workflow needed. Ocean schedules has no cross-module dependency on in-flight upgrades.

---

## High Level Design

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      Ocean Schedules Service Suite                                │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                          API SERVICE                                        │ │
│  │                                                                             │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐       │ │
│  │  │  oceanschedules (Dropwizard)                                     │       │ │
│  │  │  - Schedule search REST API                                      │       │ │
│  │  │  - External carrier API integration (12+ carriers)               │       │ │
│  │  │  - Real-time cache (DynamoDB: os_realtime_cache)                 │       │ │
│  │  │  - SNS pipeline triggers                                         │       │ │
│  │  │  - S3 schedule file management                                   │       │ │
│  │  │  - Elasticsearch schedule search                                 │       │ │
│  │  └──────────────────────────────────────────────────────────────────┘       │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                     BATCH PROCESSING PIPELINE                               │ │
│  │                                                                             │ │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │ │
│  │  │collector │──▶│ inbound  │──▶│ staging  │──▶│aggregator│             │ │
│  │  │(DW poll) │    │(Spark    │    │(Spark    │    │(Spark +  │             │ │
│  │  │          │    │ parse)   │    │ transform│    │ DynamoDB)│             │ │
│  │  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘             │ │
│  │                                                       │                    │ │
│  │                                               ┌───────┴───────┐            │ │
│  │                                               ▼               ▼            │ │
│  │                                        ┌──────────┐    ┌──────────┐       │ │
│  │                                        │ loader   │    │ outbound │       │ │
│  │                                        │(Spark +  │    │(Spark    │       │ │
│  │                                        │ ES index)│    │ EDI/CSV) │       │ │
│  │                                        └──────────┘    └──────────┘       │ │
│  │                                                                             │ │
│  │  ┌──────────────────┐                                                      │ │
│  │  │port-pair-        │  (Dropwizard — generates route definitions)          │ │
│  │  │generator         │  (DynamoDB: schedules_pro_staging — raw Document API)│ │
│  │  └──────────────────┘                                                      │ │
│  │                                                                             │ │
│  │  ┌──────────────────┐                                                      │ │
│  │  │ common           │  (Shared: SQSClient, SNSClient, S3WorkspaceService)  │ │
│  │  └──────────────────┘                                                      │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Cloud SDK Integration Architecture

All AWS service interactions are abstracted through the cloud-sdk layer:

```
Ocean Schedules Service
      │
      ├─▶ cloud-sdk-api (Vendor-Neutral Interfaces)
      │     ├─▶ MessagingClient<T>        — SQS operations
      │     ├─▶ QueueMessage<T>           — Immutable message wrapper
      │     ├─▶ ReceiveMessageOptions     — Builder for receive config
      │     ├─▶ NotificationService       — SNS publish
      │     ├─▶ StorageClient             — S3 read/write/list/copy/delete
      │     ├─▶ StorageObject             — S3 object with content stream
      │     ├─▶ DatabaseRepository<T, ID> — DynamoDB CRUD + query
      │     ├─▶ DefaultCompositeKey<P,S>  — Composite key (PK + SK)
      │     ├─▶ DefaultPartitionKey<P>    — Simple partition key
      │     └─▶ DynamoDbClientConfig      — DynamoDB client configuration
      │
      └─▶ cloud-sdk-aws (AWS SDK v2 Implementations)
            ├─▶ SqsMessagingClient            — SQS via SqsClient
            ├─▶ SnsNotificationService        — SNS via SnsClient
            ├─▶ S3StorageClient               — S3 via S3Client
            ├─▶ EnhancedDynamoRepository      — DynamoDB Enhanced Client
            └─▶ Factories: MessagingClientFactory, NotificationClientFactory,
                           StorageClientFactory, DynamoRepositoryFactory
```

### Summary of Changes per Service Area

| Area | Pre-Migration (SDK 1.x) | Post-Migration (SDK 2.x) | Key Changes |
|------|------------------------|--------------------------|-------------|
| **DynamoDB** | `DynamoDBMapper` + `@DynamoDBTable` via `dynamo-client` library; raw Document API (`PutItemRequest`) in port-pair-generator | `DynamoDbEnhancedClient` + `@DynamoDbBean` + `@DynamoDbConvertedBy` via cloud-sdk `DatabaseRepository` | Migrated 2 entity classes (`RealTimeCache`, `SchedulesProStaging`); created `DateEpochSecondAttributeConverter`; removed `DynamoSupport` utility; replaced raw `PutItemRequest` with `DatabaseRepository.save()` |
| **SQS** | AWS SDK 1.x `AmazonSQS` + `Message` + SQS Extended Client (1.2.6) | cloud-sdk `MessagingClient<String>` + `QueueMessage<String>` | Immutable `QueueMessage<String>`, `getPayload()` replaces `getBody()`, extended client replaced |
| **SNS** | Custom `SNSClient` wrappers in both modules (SDK 1.x `AmazonSNS`) | cloud-sdk `NotificationService` | `publish(topicArn, content)` replaces direct SNS client calls; custom retry logic simplified |
| **S3** | AWS SDK 1.x `AmazonS3` in `S3Service` (API) + `S3WorkspaceService` (process) + `TransferManager` multipart | cloud-sdk `StorageClient` | `StorageObject` wrapper; multipart upload evaluated |
| **SSM** | AWS SDK 1.x `AWSSimpleSystemsManagement` (outbound only) | AWS SDK 2.x `SsmClient` directly | Updated client construction in outbound module |

### Data Flow Pipeline (Post-Migration)

```
COLLECTION FLOW                          PROCESSING FLOW
────────────────                         ─────────────────

Carrier APIs ──▶ collector (Dropwizard)    SNS/SQS triggers
                      │                         │
                      ▼                         ▼
              S3 (raw files)             inbound (Spark)
                      │                    │ EDIFACT/ANSI parse
                      ▼                    ▼
              SNS trigger  ──────▶  staging (Spark)
                                     │ Normalize + stage
                                     ▼
                              DynamoDB: schedules_pro_staging
                                     │
                              aggregator (Spark + DynamoDB)
                                     │ Multi-source merge
                              ┌──────┴──────┐
                              ▼              ▼
                        loader (Spark)   outbound (Spark)
                        │ ES index       │ EDI/CSV/XML
                        ▼                ▼
                    Elasticsearch     S3 (outbound files)


SEARCH FLOW
────────────

User ──▶ oceanschedules REST API
              │
              ├─▶ Elasticsearch (indexed schedules)
              └─▶ DynamoDB: os_realtime_cache (cached carrier responses)
```

---

## Low Level Design

### DynamoDB Table Structures

#### Table 1: `os_realtime_cache`

Caches recently-fetched carrier schedule responses for fast lookups.

| Attribute | Type | Role | Converter |
|-----------|------|------|-----------|
| `cacheKey` | String | **Partition Key** | — |
| `carrierConfigName` | String | Attribute | — |
| `writeDateTime` | Date | Attribute | `DateEpochSecondAttributeConverter` |
| `expiresOn` | Date | Attribute (TTL) | `DateEpochSecondAttributeConverter` |
| `inttraSchedules` | String | Attribute (JSON blob) | — |
| `locked` | String | Attribute | — |
| `readWriteError` | boolean | Attribute | — |

**Stream**: KEYS_ONLY (configured at table level, not on entity annotation)

**Entity class migration** (`RealTimeCache.java`):
```java
// Before
@DynamoDBTable(tableName = "os_realtime_cache")
@DynamoDBStream(StreamViewType.KEYS_ONLY)
public class RealTimeCache<T> implements TimeToLive, DynamoHashKey<String> {
    @DynamoDBHashKey(attributeName = "cacheKey")
    private String hashKey;

    @DynamoDBTypeConverted(converter = DateToEpochSecond.class)
    private Date expiresOn;
    // ...
}

// After
@DynamoDbBean
@Table(name = "os_realtime_cache")
@Data @Builder @AllArgsConstructor @NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class RealTimeCache implements Expires {

    @DynamoDbPartitionKey
    @Getter(onMethod_ = @DynamoDbAttribute("cacheKey"))
    private String hashKey;

    private String carrierConfigName;

    @DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)
    private Date writeDateTime;

    @DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)
    @TTL(name = "expiresOn")
    private Date expiresOn;

    private String inttraSchedules;
    private String locked;
    private boolean readWriteError;
}
```

#### Table 2: `schedules_pro_staging`

Stores intermediate staging data for carrier schedules per port-pair.

| Attribute | Type | Role | Converter |
|-----------|------|------|-----------|
| `scac` | String | **Partition Key** | — |
| `portPairIndicator` | String | **Sort Key** | — |
| `scheduleSource` | String | GSI Hash Key (`schedules_pro_source_index`) | — |
| `scheduleJson` | String | Attribute (JSON blob) | — |
| `lastUpdated` | Date | Attribute | `DateEpochSecondAttributeConverter` |
| `expiresOn` | Date | Attribute (TTL) | `DateEpochSecondAttributeConverter` |

**GSI**: `schedules_pro_source_index` (partition key: `scheduleSource`)  
**Stream**: KEYS_ONLY

**Entity class migration** (`SchedulesProStaging.java`):
```java
// Before
@DynamoDBTable(tableName = "schedules_pro_staging")
@DynamoDBStream(StreamViewType.KEYS_ONLY)
public class SchedulesProStaging<T> implements TimeToLive, DynamoHashKey<String> {
    @DynamoDBHashKey(attributeName = "scac")
    private String scac;
    @DynamoDBRangeKey(attributeName = "portPairIndicator")
    private String portPairIndicator;
    @DynamoDBIndexHashKey(globalSecondaryIndexName = "schedules_pro_source_index")
    private String scheduleSource;
    // ...
}

// After
@DynamoDbBean
@Table(name = "schedules_pro_staging")
@Data @Builder @AllArgsConstructor @NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class SchedulesProStaging implements Expires {

    @DynamoDbPartitionKey
    private String scac;

    @DynamoDbSortKey
    private String portPairIndicator;

    @DynamoDbSecondaryPartitionKey(indexNames = {"schedules_pro_source_index"})
    private String scheduleSource;

    private String scheduleJson;

    @DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)
    private Date lastUpdated;

    @DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)
    @TTL(name = "expiresOn")
    private Date expiresOn;
}
```

### Guice Module Architecture

#### Pre-Migration (Single Module)

```
OceanschedulesModule (monolithic)
  ├── AmazonSNS            → AmazonSNSClientBuilder.standard()...build()
  ├── AmazonS3             → AmazonS3ClientBuilder.standard()...build()
  ├── AmazonDynamoDB       → DynamoSupport.newClient(config)
  ├── DynamoDBMapperConfig → DynamoSupport.newDynamoDBMapperConfig(config)
  ├── DynamoDBMapper       → DynamoSupport.newMapper(client, config)
  ├── JestModule           → com.inttra.mercury.module.JestModule
  ├── ServiceDefinition    → named bindings per mercury service
  ├── ExternalServiceDefinition → named bindings per carrier
  └── PortPairRequestBuilder   → Multibinder (12 carrier builders)
```

#### Post-Migration (Split Modules)

```
OceanschedulesModule (orchestrator)
  ├── install(OceanSchedulesDynamoModule)
  │     ├── DynamoDbClientConfig       → from BaseDynamoDbConfig
  │     ├── DynamoRepositoryFactory    → creates Enhanced Client repos
  │     ├── DatabaseRepository<RealTimeCache, ...>
  │     └── DatabaseRepository<SchedulesProStaging, ...>
  │
  ├── install(OceanSchedulesMessagingModule)
  │     └── NotificationService        → NotificationClientFactory.createDefaultClient()
  │
  ├── install(OceanSchedulesStorageModule)
  │     └── StorageClient              → StorageClientFactory.createDefaultS3Client()
  │
  ├── install(new JestModule(esConfig))  → cloud-sdk-aws JestModule
  ├── ServiceDefinition bindings         → unchanged
  ├── ExternalServiceDefinition bindings → unchanged
  └── PortPairRequestBuilder Multibinder → unchanged
```

### Key Component Migrations

#### SNS Client (oceanschedules API)

```java
// Before (com.inttra.mercury.oceanschedules.util.sns.SNSClient)
@Singleton
public class SNSClient implements MessageSender {
    private final AmazonSNS amazonSNS;
    @Inject public SNSClient(AmazonSNS amazonSNS) { this.amazonSNS = amazonSNS; }
    public void sendMessage(String target, String content) {
        PublishRequest req = new PublishRequest();
        req.setTopicArn(target); req.setMessage(content);
        // 3-retry loop with AWSUtil.isRetryable()
        amazonSNS.publish(req);
    }
}

// After
@Singleton
public class SNSClient implements MessageSender {
    private final NotificationService notificationService;
    @Inject public SNSClient(NotificationService notificationService) {
        this.notificationService = notificationService;
    }
    public void sendMessage(String target, String content) {
        notificationService.publish(target, content);
    }
}
```

#### SQS Client (process/common)

```java
// Before (com.inttra.mercury.oceanschedules.process.common.messaging.SQSClient)
@Singleton
public class SQSClient implements MessageSender {
    private final AmazonSQS amazonSQS;
    // sendMessage(), sendMessage(delay), sendMessage(delay, failedAttempts)
    // deleteMessage(), receiveMessage()
}

// After
@Singleton
public class SQSClient implements MessageSender {
    private final MessagingClient<String> messagingClient;
    @Inject public SQSClient(MessagingClient<String> messagingClient) {
        this.messagingClient = messagingClient;
    }
    public void sendMessage(String target, String content) {
        messagingClient.sendMessage(target, content);
    }
    // ... mapped to MessagingClient methods
}
```

#### S3 Service (oceanschedules API)

```java
// Before (com.inttra.mercury.oceanschedules.util.s3.S3Service)
public class S3Service {
    private final AmazonS3 s3Client;
    // listSubFolders(), listFiles(), getObject(), deleteFolder(), deleteObject()
    // with retry logic and AWSUtil.isRetryable()
}

// After
public class S3Service {
    private final StorageClient storageClient;
    @Inject public S3Service(StorageClient storageClient) {
        this.storageClient = storageClient;
    }
    // Operations mapped to StorageClient methods
    // AWS SDK v2 has built-in retry — custom retry logic simplified
}
```

#### DynamoDB Document API (port-pair-generator)

The port-pair-generator uses **raw DynamoDB Document API** (`PutItemRequest`) instead of `DynamoDBMapper`. This is migrated to use the entity class with `DatabaseRepository`:

```java
// Before (DynamoService.java — raw PutItemRequest)
Map<String, AttributeValue> item = new HashMap<>();
item.put("scac", new AttributeValue(scac));
item.put("portPairIndicator", new AttributeValue(portPairIndicator));
item.put("scheduleJson", new AttributeValue(scheduleJson));
item.put("expiresOn", new AttributeValue().withN(String.valueOf(epochSeconds)));
PutItemRequest request = new PutItemRequest().withTableName(tableName).withItem(item);
dynamoClient.putItem(request);

// After — uses SchedulesProStaging entity + DatabaseRepository
SchedulesProStaging entity = SchedulesProStaging.builder()
    .scac(scac)
    .portPairIndicator(portPairIndicator)
    .scheduleJson(scheduleJson)
    .expiresOn(new Date(epochSeconds * 1000))
    .build();
stagingRepository.save(entity);
```

---

## Configuration

### YAML Configuration Changes

**oceanschedules** (`conf/{env}/config.yaml`):

```yaml
# Before
dynamoDbConfig:
  regionEndpoint: "https://dynamodb.us-east-1.amazonaws.com"
  signingRegion: "us-east-1"
  environment: "inttra_int_os"

# After (BaseDynamoDbConfig)
dynamoDbConfig:
  environment: "inttra_int_os"
  region: "us-east-1"
  readCapacityUnits: 5
  writeCapacityUnits: 5
  sseEnabled: true
```

**oceanschedules-process** (`conf/{env}/config.yaml`):

Each sub-module's config YAML is updated similarly if it contains DynamoDB configuration.

### Java Configuration Class Changes

```java
// OceanSchedulesConfig.java — Before
import com.inttra.mercury.dynamo.respository.module.DynamoDbConfig;
@JsonProperty("dynamoDbConfig")
private DynamoDbConfig dynamoDbConfig;

// After
import com.inttra.mercury.cloudsdk.config.BaseDynamoDbConfig;
@JsonProperty("dynamoDbConfig")
private BaseDynamoDbConfig dynamoDbConfig;
```

### POM Dependency Changes

| Module | Remove | Add |
|--------|--------|-----|
| `oceanschedules` | `dynamo-client:1.R.01.021` | `cloud-sdk-api:1.0.23-SNAPSHOT`, `cloud-sdk-aws:1.0.23-SNAPSHOT`, `dynamo-integration-test:1.0.23-SNAPSHOT` (test) |
| `os-process-common` | `aws-java-sdk-sqs:1.12.558` | `cloud-sdk-api:1.0.23-SNAPSHOT`, `cloud-sdk-aws:1.0.23-SNAPSHOT` |
| `outbound` | `aws-java-sdk-sqs:1.12.773`, `aws-java-sdk-sns:1.12.773`, `aws-java-sdk-s3:1.12.773`, `aws-java-sdk-ssm:1.12.773`, `aws-java-sdk-core:1.12.773` | (via common) |
| `port-pair-generator` | `aws-java-sdk-dynamodb:1.12.558` | (via common) |

---

## Auditing/Logging

- **No changes to logging framework**. SLF4J + Logback remains.
- AWS SDK v2 uses its own logging (`software.amazon.awssdk` logger). This may produce additional log output at DEBUG level. Ensure `logback.xml` filters SDK v2 logs to WARN level in production.
- The custom retry logic in `SNSClient` (oceanschedules) and `S3Service` logs retries. After migration, AWS SDK v2 built-in retry logging replaces this.

---

## Metrics and Statistics

- **No new metrics introduced**. Existing Dropwizard metrics remain unchanged.
- The migration does not change the application's monitoring surface.
- AWS SDK v2 provides optional metric publishing via `MetricPublisher` — not enabled by default.

---

## Impact on Current Application

### Behavior Impact
- **No change to business logic**. All schedule processing, search, and outbound generation logic is unchanged.
- **No change to REST API contracts**. All endpoints, request/response formats remain identical.
- **No change to DynamoDB table schemas**. Both tables retain the same attributes, keys, GSIs, and TTL settings.
- **No change to Elasticsearch indices**. Jest client interactions are unchanged.
- **No change to pipeline orchestration**. SQS/SNS message formats remain the same.

### Dependency Impact
- Commons version stays at `1.R.01.021` for base framework classes
- New dependencies: `cloud-sdk-api:1.0.23-SNAPSHOT`, `cloud-sdk-aws:1.0.23-SNAPSHOT`
- Removed dependencies: `dynamo-client`, direct `aws-java-sdk-*` artifacts (v1)
- SQS Extended Client Library (`1.2.6`, SDK v1) replaced

### Performance Impact
- AWS SDK v2 uses non-blocking HTTP (Netty-based) by default. This may improve throughput for high-volume SQS/SNS operations.
- DynamoDB Enhanced Client is comparable in performance to `DynamoDBMapper`.
- No expected degradation.

---

## Resiliency

### Retry Behavior
- **Before**: Custom retry logic in `SNSClient` (3 retries), `S3Service` (3 retries) using `AWSUtil.isRetryable()`.
- **After**: AWS SDK v2 has built-in retry strategies (`RetryPolicy.builder().numRetries(3).build()`). Custom retry logic is simplified or removed.

### Error Handling
- SDK v1 exceptions (`SdkClientException`, `AmazonServiceException`) replaced with SDK v2 exceptions (`SdkException`, `AwsServiceException`).
- The `RecoverableException` pattern in `S3WorkspaceService` is preserved — only the caught exception type changes.
- The `AWSUtil.isRetryable()` utility is updated to handle SDK v2 exception types.

### Circuit Breaker
- No circuit breaker pattern currently implemented. Not added as part of this migration.

---

## Backwards Compatible

### DynamoDB Data Compatibility

Both entity classes use `DateToEpochSecond` converter (Date → Long epoch seconds). The migration to `DateEpochSecondAttributeConverter` maintains the same storage format:

| Data | SDK v1 DynamoDBMapper writes | SDK v2 Enhanced Client reads | Compatibility |
|------|------|------|------|
| `writeDateTime` / `lastUpdated` | `N: "1714567890"` | `N: "1714567890"` → `Date(epoch * 1000)` | ✅ |
| `expiresOn` (TTL) | `N: "1714567890"` | `N: "1714567890"` → `Date(epoch * 1000)` | ✅ |
| `null` dates | Absent attribute | `null` returned | ✅ |
| String fields | `S: "..."` | `S: "..."` | ✅ (no conversion) |

**No backward compatibility risk**: The ocean schedules DynamoDB entities are flat with only String and epoch-second Number attributes. No nested document serialization, no complex type coercion.

### Lessons from Booking Upgrade

The booking module upgrade (PRs #979, #988) revealed data format issues with:
1. **MetaData.timestamp** — `LocalDateTime` T-separator vs space
2. **Boolean/numeric coercion** — SDK v1 `DynamoDBMapper` stored booleans as `N: "0"/"1"`
3. **OffsetDateTime** — zone offset format (`+0000` vs `+00:00`)

**None of these apply to ocean schedules** because:
- No `LocalDateTime` or `OffsetDateTime` fields — only `Date` with epoch seconds
- No boolean attributes stored via converter (the `readWriteError` boolean is stored natively by DynamoDB, not via converter)
- No nested document serialization

### SQS Message Compatibility

SQS message bodies are plain JSON strings. The migration changes only the client library, not the message format. Consumers and producers can be upgraded independently.

### SNS Message Compatibility

SNS `PublishRequest` message format is unchanged. Only the client library changes.

---

## Unit Test Plan

### Existing Test Coverage

| Module | Test Files | JUnit Version |
|--------|-----------|---------------|
| oceanschedules | 59 | JUnit 5 (Jupiter 5.10.1) |
| process/common | ~20 | JUnit 4 (4.12) |
| process/collector | ~10 | JUnit 4 |
| process/inbound | ~15 | JUnit 4 |
| process/staging | ~5 | JUnit 4 |
| process/aggregator | ~10 | JUnit 4 |
| process/loader | ~10 | JUnit 4 |
| process/outbound | ~15 | JUnit 4 |
| process/port-pair-generator | ~15 | JUnit 4 |

### Tests Requiring Migration

| Category | Count (est.) | Change |
|----------|-------------|--------|
| DynamoDB mocks (`DynamoDBMapper`, `AmazonDynamoDB`) | ~10 | Mock `DatabaseRepository` instead |
| SQS mocks (`AmazonSQS`, `Message`) | ~15 | Mock `MessagingClient`, use `QueueMessage<String>` |
| S3 mocks (`AmazonS3`) | ~20 | Mock `StorageClient` |
| SNS mocks (`AmazonSNS`) | ~10 | Mock `NotificationService` |
| SSM mocks (`AWSSimpleSystemsManagement`) | ~3 | Mock `SsmClient` |

### New Tests Required

| Test Class | Module | Description |
|---|---|---|
| `DateEpochSecondAttributeConverterTest` | oceanschedules | Date ↔ epoch second round-trip, null handling, edge cases |
| `OceanSchedulesDynamoModuleTest` | oceanschedules | Guice DynamoDB module bindings verification |
| `OceanSchedulesMessagingModuleTest` | oceanschedules | SNS module bindings |
| `OceanSchedulesStorageModuleTest` | oceanschedules | S3 module bindings |
| `OceanSchedulesDynamoDbAdminCommandTest` | oceanschedules | Table creation CLI command |
| `SQSClientCloudSdkTest` | process/common | SQS operations with mocked `MessagingClient` |
| `SNSClientCloudSdkTest` | process/common | SNS operations with mocked `NotificationService` |
| `S3WorkspaceServiceCloudSdkTest` | process/common | S3 operations with mocked `StorageClient` |

### Verification Commands

```bash
# API module tests
mvn test -pl oceanschedules

# Process common tests
mvn test -pl oceanschedules-process/common

# All process sub-module tests
mvn test -pl oceanschedules-process/collector
mvn test -pl oceanschedules-process/inbound
mvn test -pl oceanschedules-process/staging
mvn test -pl oceanschedules-process/aggregator
mvn test -pl oceanschedules-process/loader
mvn test -pl oceanschedules-process/outbound
mvn test -pl oceanschedules-process/port-pair-generator
```

---

## Pre-Dev Security

### Credential Management
- **No change**: All AWS credentials use IAM roles from the execution environment (EC2 instance profile, ECS task role). No hardcoded credentials before or after migration.
- AWS SDK v2 uses the same credential chain: environment variables → system properties → instance profile → container credentials.

### Dependency Security
- Removing AWS SDK v1 eliminates known CVEs in older SDK versions (e.g., `aws-java-sdk-core:1.12.558`).
- `cloud-sdk-aws:1.0.23-SNAPSHOT` uses AWS SDK v2 latest, which receives regular security patches.

### Input Validation
- No change to input validation logic. REST API input validation remains in resource classes.
- DynamoDB entity validation is unchanged.

### Transport Security
- AWS SDK v2 uses TLS 1.2+ by default for all AWS service communications.
- HTTPS endpoints are used for all AWS interactions.

---

## Documentation Changes

| Document | Change |
|----------|--------|
| `oceanschedules/docs/os-aws2x-plan.md` | **New** — Detailed AWS SDK 2.x upgrade plan |
| `oceanschedules/docs/CONFLUENCE-os.md` | **New** — This design document |
| `oceanschedules/docs/DESIGN-PRE-AWS-upgrade.md` | Existing pre-upgrade architecture reference (no update needed) |
| `oceanschedules/docs/oceanschedules-architecture-design-claude.md` | Existing architecture reference (no update needed) |
| `README.md` (root) | Update module status: oceanschedules → "AWS 2.x upgrade COMPLETED" |

---

## Review

### Review Checklist

- [ ] All DynamoDB entity annotations migrated from SDK v1 to SDK v2 Enhanced Client
- [ ] `DateEpochSecondAttributeConverter` tested with legacy data, null values, edge cases
- [ ] `DynamoSupport` utility class removed; replaced by `DynamoRepositoryFactory`
- [ ] Guice modules split into DynamoDB, Messaging, Storage modules
- [ ] SNS client uses `NotificationService` — custom retry logic simplified
- [ ] S3 service uses `StorageClient` — custom retry logic simplified
- [ ] SQS client uses `MessagingClient<String>` — extended client replaced
- [ ] SSM client uses SDK v2 `SsmClient` (outbound module)
- [ ] DynamoDB Document API (port-pair-generator) replaced with `DatabaseRepository.save()`
- [ ] Spark job AWS client lifecycle handles non-serializable clients correctly
- [ ] All `dynamo-client` and direct `aws-java-sdk-*` v1 dependencies removed from all POMs
- [ ] `cloud-sdk-api:1.0.23-SNAPSHOT` and `cloud-sdk-aws:1.0.23-SNAPSHOT` added
- [ ] All 212 test files updated where needed (mock types, message types)
- [ ] DynamoDB integration tests pass with embedded DynamoDB Local
- [ ] Full `mvn test` passes for both `oceanschedules` and `oceanschedules-process`
- [ ] Full `mvn verify` passes including integration tests
- [ ] YAML config files updated for all environments (int, qa, cvt, prod)
- [ ] No backward-incompatible changes to DynamoDB data format
- [ ] No backward-incompatible changes to SQS/SNS message formats
- [ ] No backward-incompatible changes to REST API contracts

### Reviewers
- Development Team Lead
- DevOps (for deployment config changes)
- QA (for integration test validation)

---

*End of Design Document*
