# Ocean Schedules Module — AWS SDK 2.x Upgrade Plan

> **Status**: Planning  
> **Date**: 2026-05-04  
> **Modules**: `oceanschedules/` (Dropwizard API) + `oceanschedules-process/` (Spark/Dropwizard batch pipeline — 8 sub-modules)  
> **Target**: Migrate from AWS SDK v1 (`dynamo-client`, `AmazonS3`, `AmazonSQS`, `AmazonSNS`, `AmazonSSM`) to `cloud-sdk-api` + `cloud-sdk-aws` (AWS SDK 2.x)  
> **Commons Version**: `1.0.23-SNAPSHOT`  
> **Agent Model**: Claude Opus 4.6  
> **Session ID**: `65cf629114ec4ee4` (MCP Context Server — "Visibility + Oceanschedules AWS 2.x Doc Updates")  
> **Current state analysis**: `oceanschedules/docs/DESIGN-PRE-AWS-upgrade.md`  
> **Confluence design doc**: `oceanschedules/docs/CONFLUENCE-os.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Branch & Git Strategy](#2-branch--git-strategy)
3. [Pre-Requisites](#3-pre-requisites)
4. [Upgrade Phases](#4-upgrade-phases)
5. [Phase 1 — POM & Dependency Changes](#5-phase-1--pom--dependency-changes)
6. [Phase 2 — oceanschedules (API Module)](#6-phase-2--oceanschedules-api-module)
7. [Phase 3 — oceanschedules-process/common (Shared Library)](#7-phase-3--oceanschedules-processcommon-shared-library)
8. [Phase 4 — oceanschedules-process Sub-Modules (7)](#8-phase-4--oceanschedules-process-sub-modules)
9. [DynamoDB Model Migration Details](#9-dynamodb-model-migration-details)
10. [SQS Migration Details](#10-sqs-migration-details)
11. [S3 Migration Details](#11-s3-migration-details)
12. [SNS Migration Details](#12-sns-migration-details)
13. [SSM Parameter Store Migration](#13-ssm-parameter-store-migration)
14. [Spark Job AWS Client Migration](#14-spark-job-aws-client-migration)
15. [Unit Test Plan](#15-unit-test-plan)
16. [Integration Test Plan](#16-integration-test-plan)
17. [Verification Strategy](#17-verification-strategy)
18. [Data Format Backward Compatibility](#18-data-format-backward-compatibility)
19. [Risk & Mitigation](#19-risk--mitigation)
20. [Appendix A — File Change Matrix](#appendix-a--file-change-matrix)

---

> **Session Context for Agents**  
> To resume this work, load session `65cf629114ec4ee4` via MCP Context Server:  
> ```
> session_get(session_id="65cf629114ec4ee4")
> ```  
> **Skills**: `java-refactoring`, `session-context`, `git-operations`  
> **Pre-upgrade design**: `oceanschedules/docs/DESIGN-PRE-AWS-upgrade.md`  
> **Business rules**: `oceanschedules/docs/05042026-oceanschedules-business-rules-claude.md`  
> **Architecture**: `oceanschedules/docs/oceanschedules-architecture-design-claude.md`

---

## 1. Executive Summary

The ocean schedules module consists of **two top-level Maven modules** spanning **9 deployable units**:

1. **`oceanschedules/`** — Dropwizard 4.0.16 REST API service (schedule search, carrier management, user preferences)
2. **`oceanschedules-process/`** — Batch processing pipeline with 8 sub-modules:
   - `common` — Shared library (SQS, SNS, S3 clients, models)
   - `collector` — Scheduled API polling service (Dropwizard)
   - `inbound` — EDIFACT/ANSI parser (Spark batch)
   - `staging` — Staging transformer (Spark batch)
   - `aggregator` — Multi-source aggregator (Spark + DynamoDB)
   - `loader` — Elasticsearch indexer (Spark + Jest)
   - `outbound` — Export processor — EDIFACT/ANSI/CSV/XML (Spark)
   - `port-pair-generator` — Port-pair route discovery (Dropwizard)

All modules currently use **AWS SDK v1** via the deprecated `dynamo-client` library and direct AWS SDK v1 client classes.

The upgrade will replace all legacy AWS SDK v1 dependencies with `cloud-sdk-api` (vendor-neutral interfaces) and `cloud-sdk-aws` (AWS SDK v2 implementations) from `mercury-services-commons:1.0.23-SNAPSHOT`.

### Key Metrics

| Metric | oceanschedules | oceanschedules-process | Total |
|--------|---------------|----------------------|-------|
| **Production Java files** | 132 | 426 | 558 |
| **Test files** | 59 | 153 | 212 |
| **DynamoDB entity classes** | 2 | 0 (uses Document API directly) | 2 |
| **DynamoDB DAO / helper classes** | 1 (DynamoSupport) | 1 (DynamoService + DynamoSparkService) | 2 |
| **SQS clients** | 0 | 1 (SQSClient in common) | 1 |
| **SNS clients** | 1 (SNSClient) | 1 (SNSClient in common) | 2 |
| **S3 clients** | 1 (S3Service) | 1 (S3WorkspaceService in common) | 2 |
| **SSM clients** | 0 | 1 (SSMParameterStoreClient in outbound) | 1 |
| **Guice modules** | 1 | 7 | 8 |
| **Current commons version** | `1.R.01.021` | `1.R.01.021` | — |
| **Current AWS SDK version** | via commons | `1.12.558` / `1.12.773` | — |

### Key Differences from Visibility Upgrade

| Aspect | Visibility | Ocean Schedules |
|--------|-----------|----------------|
| DynamoDB usage | DynamoDBMapper with `@DynamoDBTable` entities, 6 DAOs | DynamoDBMapper (2 entities) + **Document API** (port-pair-generator uses raw `PutItemRequest`) |
| Framework | Dropwizard + Lambda | Dropwizard + **Apache Spark** batch jobs |
| SQS extended client | Not used | `amazon-sqs-java-extended-client-lib:1.2.6` for large messages |
| Nested DynamoDB models | ~20 `@DynamoDBDocument` classes | None (simple flat entities with string/number/date attributes) |
| Lambda functions | 4 Lambdas | None (batch triggered by SQS/SNS/CloudWatch) |
| Elasticsearch | Jest 6.3.0 | Jest 6.3.1 (loader) + ES 8.6.2 |
| Booking dependency | Yes (cross-module) | No |

### Reference Modules
1. **webbl** — Single Dropwizard service with DynamoDB, SQS, SNS, S3, SES
2. **booking-bridge** — Single Dropwizard service with DynamoDB, SQS, SNS
3. **booking** — Complex module with 7 DynamoDB tables, Lambdas, SQS/SNS/S3/SES (merged to develop, cloud-sdk `1.0.23-SNAPSHOT`)

---

## 2. Branch & Git Strategy

The ocean schedules module has **no cross-module dependencies** on booking or other in-flight upgrades. Branch directly from `develop`.

```bash
# Create feature branch
git checkout develop
git pull origin develop
git checkout -b feature/oceanschedules-aws-sdk-2x-upgrade
```

Since `oceanschedules/` and `oceanschedules-process/` are separate top-level Maven modules with no shared parent POM (other than `mercury-services`), they can be upgraded independently. However, `oceanschedules-process` sub-modules depend on `os-process-common`, so common must be upgraded first.

### Recommended Upgrade Order

```
Phase 1: POM changes (both modules)
Phase 2: oceanschedules (API — standalone Dropwizard)
Phase 3: oceanschedules-process/common (shared library)
Phase 4: oceanschedules-process sub-modules (7 sub-modules, one at a time)
```

---

## 3. Pre-Requisites

1. **mercury-services-commons `1.0.23-SNAPSHOT`** must be available in the Maven repository (includes `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test`).

2. **DynamoDB Local** must be available for integration testing (provided by `dynamo-integration-test` from mercury-services-commons).

3. **Feature branch**: Create from latest `develop`. No cherry-picking needed.

4. **JDK 17**: Already in use by both modules.

---

## 4. Upgrade Phases

| Phase | Scope | Dependencies | Verification |
|-------|-------|-------------|--------------|
| **Phase 1** | POM & Dependency Changes | All POMs | `mvn compile -pl oceanschedules -am && mvn compile -pl oceanschedules-process/common -am` |
| **Phase 2** | oceanschedules (API module) | DynamoDB entities, SNS, S3, Guice | `mvn test -pl oceanschedules` |
| **Phase 3** | oceanschedules-process/common | SQS, SNS, S3 clients | `mvn test -pl oceanschedules-process/common` |
| **Phase 4** | oceanschedules-process sub-modules (7) | common | `mvn test -pl oceanschedules-process/{submodule}` per module |
| **Final** | Full verification | All | `mvn verify -pl oceanschedules -am && mvn verify -pl oceanschedules-process/common -am` |

### Build Dependency Order

```
oceanschedules (standalone — no dependency on process modules)

oceanschedules-process/common          ← FIRST (all process sub-modules depend on this)
  ├── oceanschedules-process/collector
  ├── oceanschedules-process/inbound
  ├── oceanschedules-process/staging
  ├── oceanschedules-process/aggregator
  ├── oceanschedules-process/loader
  ├── oceanschedules-process/outbound
  └── oceanschedules-process/port-pair-generator
```

---

## 5. Phase 1 — POM & Dependency Changes

### 5.1 oceanschedules POM (`oceanschedules/pom.xml`)

**Add properties:**
```xml
<mercury.cloudsdk.version>1.0.23-SNAPSHOT</mercury.cloudsdk.version>
```

**Add dependencies:**
```xml
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-api</artifactId>
    <version>${mercury.cloudsdk.version}</version>
</dependency>
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-aws</artifactId>
    <version>${mercury.cloudsdk.version}</version>
</dependency>
```

**Add test dependency:**
```xml
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>dynamo-integration-test</artifactId>
    <version>${mercury.cloudsdk.version}</version>
    <scope>test</scope>
</dependency>
```

**Remove dependency:**
```xml
<!-- REMOVE dynamo-client -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>dynamo-client</artifactId>
    <version>${mercury.dynamodbclient.version}</version>
</dependency>
```

**Remove property:**
```xml
<!-- REMOVE: <mercury.dynamodbclient.version>1.R.01.021</mercury.dynamodbclient.version> -->
```

### 5.2 oceanschedules-process/common POM

**Update properties:**
```xml
<mercury.commons.version>1.R.01.021</mercury.commons.version>  <!-- Keep for base commons -->
<mercury.cloudsdk.version>1.0.23-SNAPSHOT</mercury.cloudsdk.version>  <!-- ADD -->
```

**Add dependencies:**
```xml
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-api</artifactId>
    <version>${mercury.cloudsdk.version}</version>
</dependency>
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-aws</artifactId>
    <version>${mercury.cloudsdk.version}</version>
</dependency>
```

**Remove/Replace AWS SDK v1 direct dependencies:**
```xml
<!-- REMOVE: direct AWS SDK v1 SQS -->
<dependency>
    <groupId>com.amazonaws</groupId>
    <artifactId>aws-java-sdk-sqs</artifactId>
    <version>${os.aws.java.sdk.version}</version>
</dependency>
```

> **Note on SQS Extended Client**: The `amazon-sqs-java-extended-client-lib:1.2.6` uses AWS SDK v1 and may need to be replaced with `software.amazon.payloadoffloading:payloadoffloading-s3-client:2.x` or an SDK v2 equivalent. If large message support is required, evaluate cloud-sdk's `MessagingClient` capabilities or use the AWS SDK v2 SQS extended client (`software.amazon.awssdk:sqs`).

### 5.3 oceanschedules-process Sub-Module POMs

Each sub-module (`aggregator`, `collector`, `inbound`, `staging`, `loader`, `outbound`, `port-pair-generator`) inherits from `os-process-common` transitively. Update sub-module POMs that have direct AWS SDK v1 dependencies:

**outbound/pom.xml — Remove:**
```xml
<!-- REMOVE all direct AWS SDK v1 dependencies -->
<dependency><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-sqs</artifactId><version>1.12.773</version></dependency>
<dependency><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-sns</artifactId><version>1.12.773</version></dependency>
<dependency><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-s3</artifactId><version>1.12.773</version></dependency>
<dependency><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-ssm</artifactId><version>1.12.773</version></dependency>
<dependency><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-core</artifactId><version>1.12.773</version></dependency>
```

**port-pair-generator/pom.xml — Remove:**
```xml
<!-- REMOVE direct DynamoDB SDK v1 -->
<dependency><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-dynamodb</artifactId><version>1.12.558</version></dependency>
```

---

## 6. Phase 2 — oceanschedules (API Module)

The `oceanschedules` API module is a standalone Dropwizard service. It uses:
- **DynamoDB**: 2 entity classes (`RealTimeCache`, `SchedulesProStaging`) via `DynamoDBMapper`
- **SNS**: `SNSClient` wrapper for pipeline triggering
- **S3**: `S3Service` for schedule file management
- **Elasticsearch**: Jest client via `JestModule`

### 6.1 DynamoDB Entity Migration

#### 6.1.1 RealTimeCache (`os_realtime_cache` table)

| Before (SDK v1) | After (SDK v2) |
|---|---|
| `@DynamoDBTable(tableName = "os_realtime_cache")` | `@DynamoDbBean` + `@Table(name = "os_realtime_cache")` |
| `@DynamoDBHashKey(attributeName = "cacheKey")` | `@DynamoDbPartitionKey` |
| `@DynamoDBAttribute` | Remove (Enhanced Client infers from getter names) |
| `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` on `writeDateTime` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` on `expiresOn` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` + `@TTL(name = "expiresOn")` |
| `implements TimeToLive, DynamoHashKey<String>` | `implements Expires` (from cloud-sdk-api) |
| `@DynamoDBStream(StreamViewType.KEYS_ONLY)` | Remove (streams are configured at table level, not on entity) |

**Fields**: `hashKey` (cacheKey — PK), `carrierConfigName`, `writeDateTime`, `expiresOn` (TTL), `inttraSchedules`, `locked`, `readWriteError`

**No nested `@DynamoDBDocument` classes** — all attributes are primitives/strings/dates. This is simpler than visibility's entities.

#### 6.1.2 SchedulesProStaging (`schedules_pro_staging` table)

| Before (SDK v1) | After (SDK v2) |
|---|---|
| `@DynamoDBTable(tableName = "schedules_pro_staging")` | `@DynamoDbBean` + `@Table(name = "schedules_pro_staging")` |
| `@DynamoDBHashKey(attributeName = "scac")` | `@DynamoDbPartitionKey` |
| `@DynamoDBRangeKey(attributeName = "portPairIndicator")` | `@DynamoDbSortKey` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "schedules_pro_source_index")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"schedules_pro_source_index"})` |
| `@DynamoDBAttribute` | Remove |
| `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` on `lastUpdated` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` on `expiresOn` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` + `@TTL(name = "expiresOn")` |
| `implements TimeToLive, DynamoHashKey<String>` | `implements Expires` |
| `@DynamoDBStream(StreamViewType.KEYS_ONLY)` | Remove |

**Fields**: `scac` (PK), `portPairIndicator` (SK), `scheduleSource` (GSI hash key), `scheduleJson`, `lastUpdated`, `expiresOn` (TTL)

**GSI**: `schedules_pro_source_index` (hash key: `scheduleSource`)

### 6.2 AttributeConverter Implementations

Create new `AttributeConverter<T>` implementations for the date fields. Since both entities use only `DateToEpochSecond`, only **one** converter is needed:

| Converter Class | Target Type | Pattern |
|---|---|---|
| `DateEpochSecondAttributeConverter` | `Date` | Date ↔ Long (epoch seconds) — for both `writeDateTime`/`lastUpdated` and TTL fields |

**Reference implementation** (from booking/visibility modules):
```java
public class DateEpochSecondAttributeConverter implements AttributeConverter<Date> {

    @Override
    public AttributeValue transformFrom(Date input) {
        if (input == null) return AttributeValue.builder().nul(true).build();
        return AttributeValue.builder().n(String.valueOf(input.getTime() / 1000)).build();
    }

    @Override
    public Date transformTo(AttributeValue input) {
        if (input == null || input.n() == null) return null;
        return new Date(Long.parseLong(input.n()) * 1000);
    }

    @Override
    public EnhancedType<Date> type() {
        return EnhancedType.of(Date.class);
    }

    @Override
    public AttributeValueType attributeValueType() {
        return AttributeValueType.N;
    }
}
```

### 6.3 DynamoSupport Removal

The `DynamoSupport` utility class provides factory methods for `AmazonDynamoDB`, `DynamoDBMapper`, and `DynamoDBMapperConfig`. It is replaced by cloud-sdk factories:

| Before (`DynamoSupport`) | After (cloud-sdk) |
|---|---|
| `DynamoSupport.newClient(dynamoDbConfig)` | `DynamoRepositoryFactory` via Guice |
| `DynamoSupport.newMapper(client, config)` | `DynamoRepositoryFactory.createEnhancedRepository()` |
| `DynamoSupport.newDynamoDBMapperConfig(config)` | Table name prefix configured via `DynamoDbClientConfig` |

**Action**: Remove `DynamoSupport.java` entirely. Replace all usages with `DynamoRepositoryFactory` in the Guice module.

### 6.4 Guice Module Migration (`OceanschedulesModule`)

**Current bindings to replace:**
```java
// REMOVE these lines:
AmazonDynamoDB client = DynamoSupport.newClient(configuration.getDynamoDbConfig());
bind(AmazonDynamoDB.class).toInstance(client);
DynamoDBMapperConfig dynamoDBMapperConfig = DynamoSupport.newDynamoDBMapperConfig(configuration.getDynamoDbConfig());
bind(DynamoDBMapperConfig.class).toInstance(dynamoDBMapperConfig);
DynamoDBMapper mapper = DynamoSupport.newMapper(client, configuration.getDynamoDbConfig(), dynamoDBMapperConfig);
bind(DynamoDBMapper.class).toInstance(mapper);

bind(AmazonSNS.class).toInstance(AmazonSNSClientBuilder.standard()...build());
bind(AmazonS3.class).toInstance(AmazonS3ClientBuilder.standard()...build());
```

**New module structure** — split into dedicated modules (following webbl/booking pattern):

1. **`OceanSchedulesDynamoModule`** — Provides `DynamoDbClientConfig` from `BaseDynamoDbConfig`, creates `DatabaseRepository` instances via `DynamoRepositoryFactory`, provides DAO bindings.

2. **`OceanSchedulesMessagingModule`** — Provides `NotificationService` via `NotificationClientFactory.createDefaultClient(topicArn)`.

3. **`OceanSchedulesStorageModule`** — Provides `StorageClient` via `StorageClientFactory.createDefaultS3Client()`.

4. **Updated `OceanschedulesModule`** — Installs the above three modules, keeps carrier/service bindings.

```java
// OceanSchedulesDynamoModule.java
public class OceanSchedulesDynamoModule extends AbstractModule {
    private final BaseDynamoDbConfig dynamoDbConfig;

    public OceanSchedulesDynamoModule(BaseDynamoDbConfig dynamoDbConfig) {
        this.dynamoDbConfig = dynamoDbConfig;
    }

    @Override
    protected void configure() {
        DynamoDbClientConfig clientConfig = dynamoDbConfig.toClientConfigBuilder().build();
        bind(DynamoDbClientConfig.class).toInstance(clientConfig);

        DynamoRepositoryFactory factory = new DynamoRepositoryFactory(clientConfig);
        bind(DynamoRepositoryFactory.class).toInstance(factory);

        // RealTimeCache repository (partition key only)
        DatabaseRepository<RealTimeCache, DefaultPartitionKey<String>> cacheRepo =
            factory.createEnhancedRepository(RealTimeCache.class);
        bind(new TypeLiteral<DatabaseRepository<RealTimeCache, DefaultPartitionKey<String>>>() {})
            .toInstance(cacheRepo);

        // SchedulesProStaging repository (composite key: scac + portPairIndicator)
        DatabaseRepository<SchedulesProStaging, DefaultCompositeKey<String, String>> stagingRepo =
            factory.createEnhancedRepository(SchedulesProStaging.class);
        bind(new TypeLiteral<DatabaseRepository<SchedulesProStaging, DefaultCompositeKey<String, String>>>() {})
            .toInstance(stagingRepo);
    }
}
```

### 6.5 SNS Migration

Replace `com.inttra.mercury.oceanschedules.util.sns.SNSClient` with cloud-sdk `NotificationService`:

**Before:**
```java
@Singleton
public class SNSClient implements MessageSender {
    private final AmazonSNS amazonSNS;
    // retry logic with AWSUtil.isRetryable()
    public void sendMessage(String target, String content) { ... }
}
```

**After:**
```java
@Singleton
public class SNSClient implements MessageSender {
    private final NotificationService notificationService;

    @Inject
    public SNSClient(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    public void sendMessage(String target, String content) {
        notificationService.publish(target, content);
    }
}
```

> **Note**: The existing retry logic (`RETRY_LIMIT = 3` with `AWSUtil.isRetryable()`) can be simplified since the cloud-sdk/AWS SDK v2 has built-in retry policies. Evaluate whether custom retry logic is still needed.

### 6.6 S3 Migration

Replace `com.inttra.mercury.oceanschedules.util.s3.S3Service` with cloud-sdk `StorageClient`:

The `S3Service` class has extensive operations (listing, get, put, delete, copy, paginated listing with retry). These need to be mapped to `StorageClient` methods:

| S3Service Method | StorageClient Equivalent |
|---|---|
| `listSubFolders(bucket, folder)` | `storageClient.listObjects(bucket, prefix)` + filter common prefixes |
| `listFiles(bucket, folder)` | `storageClient.listObjects(bucket, prefix)` |
| `getObject(bucket, key)` | `storageClient.getObject(bucket, key)` → `StorageObject` |
| `deleteFolder(bucket, folder)` | Iterate `listObjects()` + `deleteObject()` per key |
| `deleteObject(bucket, key)` | `storageClient.deleteObject(bucket, key)` |

> **Note**: The `StorageClient` interface may not support all operations (e.g., paginated listing, `deleteObjects` batch, `copyObject`). Check `cloud-sdk-api` for available methods. For missing operations, either extend `StorageClient` in cloud-sdk-api or use AWS SDK v2 `S3Client` directly for those operations.

### 6.7 Configuration Changes

**Add `BaseDynamoDbConfig` to `OceanSchedulesConfig`:**
```java
@JsonProperty("dynamoDbConfig")
private BaseDynamoDbConfig dynamoDbConfig;
```

This replaces the existing `DynamoDbConfig` from `com.inttra.mercury.dynamo.respository.module.DynamoDbConfig` (dynamo-client).

**Update YAML configs** (`conf/{env}/config.yaml`):
```yaml
dynamoDbConfig:
  environment: "inttra_{env}_os"
  region: "us-east-1"
  readCapacityUnits: 5
  writeCapacityUnits: 5
  sseEnabled: true
```

### 6.8 Elasticsearch / JestModule

The `JestModule` import needs to change from `com.inttra.mercury.module.JestModule` (old commons) to `com.inttra.mercury.cloudsdk.aws.module.JestModule` (cloud-sdk-aws):

```java
// Before
import com.inttra.mercury.module.JestModule;

// After
import com.inttra.mercury.cloudsdk.aws.module.JestModule;
```

Similarly, `ElasticSearchServiceConfig` import changes:
```java
// Before
import com.inttra.mercury.config.ElasticSearchServiceConfig;

// After
import com.inttra.mercury.cloudsdk.config.ElasticSearchServiceConfig;
```

### 6.9 DynamoDB Table Management Command

Create `OceanSchedulesDynamoDbAdminCommand` (Dropwizard CLI command) following the webbl/booking pattern:

```java
public class OceanSchedulesDynamoDbAdminCommand extends ConfiguredCommand<OceanSchedulesConfig> {
    private static final List<Class<?>> ENTITY_CLASSES = List.of(
        RealTimeCache.class,
        SchedulesProStaging.class
    );
    // Uses DynamoRepositoryFactory to create/describe tables
}
```

---

## 7. Phase 3 — oceanschedules-process/common (Shared Library)

All 7 process sub-modules depend on `os-process-common`. This module contains the SQS, SNS, and S3 clients used across the pipeline.

### 7.1 SQS Client Migration

Replace `com.inttra.mercury.oceanschedules.process.common.messaging.SQSClient` with cloud-sdk `MessagingClient<String>`:

**Current SQSClient** (100 lines):
- `sendMessage(target, content)` — basic send
- `sendMessage(target, content, delay)` — send with delay
- `sendMessage(target, content, delay, failedAttempts)` — send with delay + message attributes (`failedAttempts`)
- `deleteMessage(queueUrl, receiptHandle)` — delete
- `receiveMessage(ReceiveMessageRequest)` — raw receive
- `receiveMessage(target, maxMessages, waitInSeconds)` — polling receive

**After:**
```java
@Singleton
public class SQSClient implements MessageSender {
    private final MessagingClient<String> messagingClient;

    @Inject
    public SQSClient(MessagingClient<String> messagingClient) {
        this.messagingClient = messagingClient;
    }

    public void sendMessage(String target, String content) {
        messagingClient.sendMessage(target, content);
    }

    public void sendMessage(String target, String content, int delay) {
        messagingClient.sendMessage(target, content, delay);
    }

    public void deleteMessage(String queueUrl, String receiptHandle) {
        messagingClient.deleteMessage(queueUrl, receiptHandle);
    }

    public List<QueueMessage<String>> receiveMessage(String target, int maxMessages, int waitInSeconds) {
        ReceiveMessageOptions options = ReceiveMessageOptions.builder()
            .maxNumberOfMessages(maxMessages)
            .waitTimeSeconds(waitInSeconds)
            .build();
        return messagingClient.receiveMessages(target, options);
    }
}
```

> **Important**: The `failedAttempts` message attribute pattern needs evaluation. Check if `MessagingClient.sendMessage()` supports message attributes. If not, this may require extending the cloud-sdk API or using the AWS SDK v2 SQS client directly for this specific use case.

> **SQS Extended Client**: The `amazon-sqs-java-extended-client-lib:1.2.6` (SDK v1) is used for large message payloads (>256KB). This must be replaced with `software.amazon.awssdk:sqs` + `software.amazon.payloadoffloading:payloadoffloading-s3-client` (SDK v2 equivalent), or the cloud-sdk `MessagingClient` if it supports large message handling. Verify with the cloud-sdk-api documentation.

### 7.2 SNS Client Migration

Replace `com.inttra.mercury.oceanschedules.process.common.messaging.SNSClient`:

**After:**
```java
@Singleton
public class SNSClient implements MessageSender {
    private final NotificationService notificationService;

    @Inject
    public SNSClient(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    public void sendMessage(String target, String content) {
        notificationService.publish(target, content);
    }
}
```

### 7.3 S3 Workspace Service Migration

Replace `com.inttra.mercury.oceanschedules.process.common.s3.S3WorkspaceService` with cloud-sdk `StorageClient`:

**Current S3WorkspaceService** (extensive — copyObject, putObject, putObjectWithMetadata, deleteObject, listObjects, getObject, multipart upload via TransferManager):

```java
@Singleton
public class S3WorkspaceService implements WorkspaceService {
    private final StorageClient storageClient;

    @Inject
    public S3WorkspaceService(StorageClient storageClient) {
        this.storageClient = storageClient;
    }

    @Override
    public void copyObject(String srcBucket, String srcKey, String dstBucket, String dstKey) {
        storageClient.copyObject(srcBucket, srcKey, dstBucket, dstKey);
    }

    @Override
    public PutObjectResult putObject(String bucket, String key, String content) {
        storageClient.putObject(bucket, key, content);
        return null; // Or return a wrapper if needed
    }

    // ... etc.
}
```

> **Note**: The existing `TransferManager` usage for multipart uploads needs evaluation. Check if `StorageClient.putObject()` handles large files automatically or if AWS SDK v2 `S3AsyncClient` with multipart upload is needed.

### 7.4 SQS Listener Migration

The `SQSListener` and `SqsThreadPoolListener` classes in common use `com.amazonaws.services.sqs.model.Message`. These need to use `QueueMessage<String>`:

```java
// Before
public class SQSListener implements Runnable {
    void processMessage(Message message) {
        String body = message.getBody();
        // ...
    }
}

// After
public class SQSListener implements Runnable {
    void processMessage(QueueMessage<String> message) {
        String body = message.getPayload();
        // ...
    }
}
```

---

## 8. Phase 4 — oceanschedules-process Sub-Modules

### 8.1 collector

**Entry point**: `OceanSchedulesCollectorApplication.java` (Dropwizard)  
**AWS usage**: SNS (via common `SNSClient`), S3 (via common `S3WorkspaceService`)  
**Changes**:
- Update `OceanSchedulesCollectorModule` to install cloud-sdk Guice modules
- Migrate any direct AWS client references to cloud-sdk abstractions

### 8.2 inbound

**Entry point**: `OceanSchedulesInboundProcessorApplication.java` (Spark)  
**AWS usage**: SQS (via common `SQSClient`), S3 (via common `S3WorkspaceService`), SNS (via common `SNSClient`)  
**Changes**:
- Update `OceanSchedulesInboundProcessInjector` to install cloud-sdk modules
- Update `ScheduleProcessorTask` for `QueueMessage<String>` if applicable

### 8.3 staging

**Entry point**: `OceanSchedulesStagingProcessor.java` (Spark)  
**AWS usage**: SQS, S3, SNS (all via common)  
**Changes**:
- Update `OceanSchedulesStagingProcessorModule`
- Update `StagedPortPairProcessor` and `OceanScheduleStagingProcessorTask`

### 8.4 aggregator

**Entry point**: `OSAggregatorApplication.java` (Spark)  
**AWS usage**: SQS, S3, SNS (via common) + **DynamoDB** (via `DynamoSparkService` — direct `AmazonDynamoDBClientBuilder`)  
**Changes**:
- Update `SchedulesAggregatorModule`
- **Migrate `DynamoSparkService`** — uses `AmazonDynamoDBClientBuilder.standard().withRegion(region).build()` directly. Replace with `DynamoRepositoryFactory` or `DynamoDbEnhancedClient` via cloud-sdk.
- This is the most complex sub-module due to Spark + DynamoDB integration

### 8.5 loader

**Entry point**: `OceanSchedulesLoader.java` (Spark)  
**AWS usage**: SQS, S3, SNS (via common)  
**ES usage**: Jest 6.3.1 + ES 8.6.2  
**Changes**:
- Update `OceanSchedulesLoaderModule` and `JestModule`
- Update Jest module import path to cloud-sdk-aws

### 8.6 outbound

**Entry point**: `OceanSchedulesOutboundProcessorApplication.java` (Spark)  
**AWS usage**: SQS, SNS, S3 (direct SDK v1 — `1.12.773`), **SSM** (`AWSSimpleSystemsManagement`)  
**Changes**:
- Update `OceanSchedulesOutboundProcessModule`
- **Remove all direct AWS SDK v1 dependencies** from pom.xml (already listed in Phase 1)
- **Migrate `SSMParameterStoreClient`** — replace `AWSSimpleSystemsManagement` with `SsmClient` (SDK v2) or cloud-sdk paramstore API
- Migrate outbound-specific S3/SQS/SNS clients that bypass common

### 8.7 port-pair-generator

**Entry point**: `OceanSchedulesPortPairGeneratorApplication.java` (Dropwizard)  
**AWS usage**: DynamoDB (direct `AmazonDynamoDB` + Document API), S3 (via `S3MergeService`), ES (via `PrefetchElasticService`)  
**Changes**:
- Update `OceanSchedulesPortPairGeneratorModule`
- **Migrate `DynamoService`** — currently uses raw `PutItemRequest` with `AmazonDynamoDB.putItem()`. Replace with `DatabaseRepository<SchedulesProStaging, DefaultCompositeKey<String, String>>` and use `repository.save()` instead of raw `PutItemRequest`.

This is the sub-module that writes directly to the `schedules_pro_staging` DynamoDB table using the low-level Document API instead of DynamoDBMapper. The migration approach is:

```java
// Before (DynamoService.java — raw PutItemRequest)
Map<String, AttributeValue> dynamoValuesMap = new HashMap<>();
dynamoValuesMap.put("scac", new AttributeValue(scac));
dynamoValuesMap.put("portPairIndicator", new AttributeValue(portPairIndicator));
dynamoValuesMap.put("scheduleJson", new AttributeValue(scheduleJson));
dynamoValuesMap.put("expiresOn", new AttributeValue().withN(String.valueOf(epochSeconds)));
PutItemRequest request = new PutItemRequest().withTableName(tableName).withItem(dynamoValuesMap);
dynamoClient.putItem(request);

// After (DynamoService.java — using entity class + DatabaseRepository)
SchedulesProStaging entity = SchedulesProStaging.builder()
    .scac(scac)
    .portPairIndicator(portPairIndicator)
    .scheduleJson(scheduleJson)
    .expiresOn(new Date(epochSeconds * 1000))
    .build();
stagingRepository.save(entity);
```

---

## 9. DynamoDB Model Migration Details

### 9.1 Annotation Mapping Reference

| SDK v1 Annotation | SDK v2 / cloud-sdk Annotation |
|---|---|
| `@DynamoDBTable(tableName = "...")` | `@DynamoDbBean` + `@Table(name = "...")` |
| `@DynamoDBHashKey` | `@DynamoDbPartitionKey` |
| `@DynamoDBRangeKey` | `@DynamoDbSortKey` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "...")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"..."})` |
| `@DynamoDBAttribute` | Remove (Enhanced Client infers from getter names) |
| `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` |
| `@DynamoDBStream(StreamViewType.KEYS_ONLY)` | Remove (not part of entity annotation in SDK v2) |
| `implements TimeToLive` (dynamo-client) | `implements Expires` (cloud-sdk-api) |
| `implements DynamoHashKey<String>` (dynamo-client) | Remove (not needed with cloud-sdk) |

### 9.2 TTL Configuration

Both entities use `expiresOn` as the TTL attribute:
- Add `implements Expires` interface (from cloud-sdk-api)
- Use `@TTL(name = "expiresOn")` annotation
- Use `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` on the TTL field

### 9.3 Table Name Prefix

The current `DynamoSupport` uses `DynamoDBMapperConfig.TableNameOverride.withTableNamePrefix()` to add environment prefixes (e.g., `inttra_int_os_`). In cloud-sdk, this is handled by `DynamoDbClientConfig`:

```java
DynamoDbClientConfig clientConfig = dynamoDbConfig.toClientConfigBuilder()
    .tableNamePrefix("inttra_int_os_")
    .build();
```

The `BaseDynamoDbConfig` from cloud-sdk-api handles this via the `environment` property.

### 9.4 Generic Type Parameter

Both entity classes use `<T>` generic type parameter (`RealTimeCache<T>`, `SchedulesProStaging<T>`). The DynamoDB Enhanced Client works with concrete types. If the generic parameter is not used for DynamoDB serialization (it appears unused based on the source), the classes should work as-is with `@DynamoDbBean`. If the Enhanced Client has issues with generic type parameters, consider removing the unused `<T>` parameter.

---

## 10. SQS Migration Details

### 10.1 Message Type Change

All SQS message consumers change from:
```java
com.amazonaws.services.sqs.model.Message message
→ message.getBody()
→ message.getReceiptHandle()
→ message.getMessageAttributes().get("failedAttempts")
```

to:
```java
QueueMessage<String> message
→ message.getPayload()
→ message.getReceiptHandle()
→ message.getAttributes().get("failedAttempts")  // Verify cloud-sdk API
```

### 10.2 SQS Extended Client

The `amazon-sqs-java-extended-client-lib:1.2.6` is used for large message payloads that exceed the SQS 256KB limit. The library stores large payloads in S3 and sends a pointer via SQS.

**Migration options:**
1. **AWS SDK v2 SQS Extended Client** (`software.amazon.awssdk:sqs` + `software.amazon.payloadoffloading:payloadoffloading-s3-client:2.x`) — direct SDK v2 replacement
2. **cloud-sdk `MessagingClient`** — check if it supports payload offloading
3. **Application-level S3 offloading** — manually store large payloads in S3 and send S3 key via SQS (if cloud-sdk doesn't support it natively)

**Recommendation**: Use option 1 (SDK v2 extended client) unless cloud-sdk already provides this functionality.

### 10.3 SQS Client Construction

**Before** (in Guice modules):
```java
AmazonSQSClientBuilder.standard().build();
// or via extended client lib:
new AmazonSQSExtendedClient(AmazonSQSClientBuilder.standard().build(), extendedClientConfig);
```

**After:**
```java
MessagingClient<String> sqs = MessagingClientFactory.createDefaultStringClient();
```

---

## 11. S3 Migration Details

### 11.1 Operations Mapping

| Current (S3Service / S3WorkspaceService) | cloud-sdk StorageClient |
|---|---|
| `s3Client.putObject(bucket, key, content)` | `storageClient.putObject(bucket, key, content)` |
| `s3Client.getObject(bucket, key)` → `S3Object` | `storageClient.getObject(bucket, key)` → `StorageObject` |
| `s3Client.deleteObject(bucket, key)` | `storageClient.deleteObject(bucket, key)` |
| `s3Client.copyObject(src, srcKey, dst, dstKey)` | `storageClient.copyObject(src, srcKey, dst, dstKey)` |
| `s3Client.listObjects(ListObjectsRequest)` → paginated | `storageClient.listObjects(bucket, prefix)` — verify pagination support |
| `s3Client.listNextBatchOfObjects(listing)` | May need SDK v2 `S3Client.listObjectsV2Paginator()` |
| `TransferManager` multipart upload | `storageClient.putObject()` or SDK v2 `S3AsyncClient` |

### 11.2 S3 Paginated Listing

Both `S3Service` (oceanschedules) and `S3WorkspaceService` (process common) implement paginated S3 listing with retry logic. Verify that `StorageClient.listObjects()` supports pagination. If not, use AWS SDK v2 `S3Client.listObjectsV2Paginator()` directly.

### 11.3 S3 Client Construction

**Before:**
```java
AmazonS3ClientBuilder.standard().withClientConfiguration(AWSClientConfiguration.s3_read_put_copy).build();
```

**After:**
```java
StorageClient storageClient = StorageClientFactory.createDefaultS3Client();
```

---

## 12. SNS Migration Details

### 12.1 SNS Publishing

**Before:**
```java
PublishRequest publishRequest = new PublishRequest();
publishRequest.setTopicArn(target);
publishRequest.setMessage(content);
amazonSNS.publish(publishRequest);
```

**After:**
```java
notificationService.publish(topicArn, message);
```

### 12.2 SNS Client Construction

**Before:**
```java
AmazonSNSClientBuilder.standard().withClientConfiguration(AWSClientConfiguration.sns_publish).build();
```

**After:**
```java
NotificationService notificationService = NotificationClientFactory.createDefaultClient(topicArn);
```

> **Note**: The `AWSClientConfiguration.sns_publish` custom configuration may set timeouts or retry policies. Verify that the cloud-sdk default configuration provides equivalent settings.

---

## 13. SSM Parameter Store Migration

The `outbound` module uses `AWSSimpleSystemsManagement` (SDK v1) for reading configuration from SSM Parameter Store.

**Before:**
```java
AWSSimpleSystemsManagement ssmClient = AWSSimpleSystemsManagementClientBuilder.standard().build();
GetParameterRequest request = new GetParameterRequest().withName(paramName).withWithDecryption(true);
String value = ssmClient.getParameter(request).getParameter().getValue();
```

**After — Option 1 (cloud-sdk paramstore API):**
Check `com.inttra.mercury.cloudsdk.paramstore.api` for available interfaces.

**After — Option 2 (AWS SDK v2 directly):**
```java
SsmClient ssmClient = SsmClient.create();
GetParameterResponse response = ssmClient.getParameter(r -> r.name(paramName).withDecryption(true));
String value = response.parameter().value();
```

---

## 14. Spark Job AWS Client Migration

Several sub-modules run as Apache Spark jobs (`inbound`, `staging`, `aggregator`, `loader`, `outbound`). These create AWS clients differently from Dropwizard services:

### 14.1 Spark + DynamoDB (aggregator)

The `DynamoSparkService` creates `AmazonDynamoDB` directly:
```java
AmazonDynamoDB client = AmazonDynamoDBClientBuilder.standard().withRegion(region).build();
```

**Migration approach**: Use `DynamoRepositoryFactory` with `DynamoDbClientConfig` configured for the region:
```java
DynamoDbClientConfig config = DynamoDbClientConfig.builder()
    .region(region)
    .environment(environment)
    .build();
DynamoRepositoryFactory factory = new DynamoRepositoryFactory(config);
DatabaseRepository<SchedulesProStaging, DefaultCompositeKey<String, String>> repo =
    factory.createEnhancedRepository(SchedulesProStaging.class);
```

### 14.2 Spark + S3

Spark jobs use `AmazonS3` for reading/writing schedule files in S3 workspace. Replace with `StorageClient` from cloud-sdk.

### 14.3 Spark + SQS

Spark jobs receive trigger messages via SQS. Replace with `MessagingClient<String>` from cloud-sdk.

### 14.4 Guice in Spark Context

Spark jobs use Guice for dependency injection (each sub-module has its own `AbstractModule`). The cloud-sdk Guice modules (`DynamoModule`, `MessagingModule`, `StorageModule`) should be installed in each sub-module's injector.

---

## 15. Unit Test Plan

### 15.1 Existing Test Inventory (212 files)

| Module | Test Files | Focus Areas |
|---|---|---|
| oceanschedules | 59 | Resources, services, clients, persistence, SNS, S3, DynamoDB |
| oceanschedules-process/common | ~20 | SQS, SNS, S3 clients, utilities |
| oceanschedules-process/collector | ~10 | Collector tasks, configuration |
| oceanschedules-process/inbound | ~15 | EDIFACT/ANSI parsers, generators |
| oceanschedules-process/staging | ~5 | Staging processor tasks |
| oceanschedules-process/aggregator | ~10 | Aggregation logic, DynamoDB |
| oceanschedules-process/loader | ~10 | ES loader tasks, Jest client |
| oceanschedules-process/outbound | ~15 | Outbound format generators, SSM |
| oceanschedules-process/port-pair-generator | ~15 | DynamoService, S3MergeService, scheduler |

### 15.2 Tests Requiring Migration

| Category | Approximate Count | Migration Action |
|---|---|---|
| DynamoDB mocks | ~10 tests | Replace `DynamoDBMapper` / `AmazonDynamoDB` mocks with `DatabaseRepository` mocks |
| SQS mocks | ~15 tests | Replace `AmazonSQS` / `Message` mocks with `MessagingClient` / `QueueMessage<String>` mocks |
| S3 mocks | ~20 tests | Replace `AmazonS3` mocks with `StorageClient` mocks |
| SNS mocks | ~10 tests | Replace `AmazonSNS` mocks with `NotificationService` mocks |
| SSM mocks | ~3 tests | Replace `AWSSimpleSystemsManagement` mocks with `SsmClient` mocks |

### 15.3 New Tests Required

| Test Class | Module | Description |
|---|---|---|
| `DateEpochSecondAttributeConverterTest` | oceanschedules | Test Date ↔ epoch second round-trip |
| `OceanSchedulesDynamoModuleTest` | oceanschedules | Test Guice DynamoDB module configuration |
| `OceanSchedulesMessagingModuleTest` | oceanschedules | Test SNS module configuration |
| `OceanSchedulesStorageModuleTest` | oceanschedules | Test S3 module configuration |
| `OceanSchedulesDynamoDbAdminCommandTest` | oceanschedules | Test table creation command |
| `SQSClientCloudSdkTest` | process/common | Test SQSClient with mocked MessagingClient |
| `SNSClientCloudSdkTest` | process/common | Test SNSClient with mocked NotificationService |
| `S3WorkspaceServiceCloudSdkTest` | process/common | Test S3 operations with mocked StorageClient |

---

## 16. Integration Test Plan

### 16.1 DynamoDB Integration Tests

Use `BaseDynamoDbIT` from `dynamo-integration-test` (mercury-services-commons) with embedded DynamoDB Local.

| Test Class | Module | Tables Tested | Test Count (estimate) |
|---|---|---|---|
| `RealTimeCacheDaoIT` | oceanschedules | `os_realtime_cache` | 4-6 tests (CRUD, TTL, partition key query) |
| `SchedulesProStagingDaoIT` | oceanschedules | `schedules_pro_staging` | 6-8 tests (composite key CRUD, GSI query, TTL) |
| `OceanSchedulesDynamoDbAdminCommandIT` | oceanschedules | Both tables | 4-6 tests (table creation, PK/SK validation, GSI validation) |

### 16.2 Integration Test Pattern

```java
@Category(IntegrationTests.class)
public class RealTimeCacheDaoIT extends BaseDynamoDbIT {

    private DatabaseRepository<RealTimeCache, DefaultPartitionKey<String>> repository;

    @Override
    protected List<Class<?>> entityClasses() {
        return List.of(RealTimeCache.class);
    }

    @BeforeEach
    void setUp() {
        repository = createPartitionKeyRepository(RealTimeCache.class);
    }

    @Test
    void shouldSaveAndRetrieve() {
        RealTimeCache cache = RealTimeCache.builder()
            .hashKey("test-key")
            .carrierConfigName("MAEU")
            .inttraSchedules("{...}")
            .build();
        repository.save(cache);

        Optional<RealTimeCache> result = repository.findById(new DefaultPartitionKey<>("test-key"), true);
        assertThat(result).isPresent();
        assertThat(result.get().getCarrierConfigName()).isEqualTo("MAEU");
    }
}
```

---

## 17. Verification Strategy

### 17.1 Per-Phase Verification

| Phase | Command | Expected Outcome |
|---|---|---|
| Phase 1 | `mvn compile -pl oceanschedules -am` | API module compiles |
| Phase 1 | `mvn compile -pl oceanschedules-process/common -am` | Common library compiles |
| Phase 2 | `mvn test -pl oceanschedules` | All API unit tests pass |
| Phase 3 | `mvn test -pl oceanschedules-process/common` | All common unit tests pass |
| Phase 4 (each) | `mvn test -pl oceanschedules-process/{submodule}` | Sub-module tests pass |
| Final | `mvn verify -pl oceanschedules -am` | All tests including integration pass |

### 17.2 Smoke Test (Local)

```bash
# Build and run oceanschedules API
mvn package -pl oceanschedules -am -DskipTests
java -jar oceanschedules/target/ocean-schedules-1.0.jar server oceanschedules/conf/int/config.yaml
```

---

## 18. Data Format Backward Compatibility

> Lessons learned from booking upgrade (PRs #979, #988, #990, #991).

### 18.1 Date Field Compatibility

Both DynamoDB entities store dates as epoch seconds (via `DateToEpochSecond` converter). The `DateEpochSecondAttributeConverter` must handle:

1. **Normal case**: DynamoDB `N` type → `Long` → `Date`
2. **Null/missing**: Return `null` gracefully
3. **String representation**: Some legacy records may store epoch as a string in `N` type — `Long.parseLong()` handles this
4. **Zero epoch**: `0` → `new Date(0)` (1970-01-01) — valid

### 18.2 String Field Compatibility

The `inttraSchedules` and `scheduleJson` fields store JSON strings. These are read/written as-is (no converter needed). No backward compatibility issues expected.

### 18.3 Testing Strategy

- Pre-populate DynamoDB Local with records representing legacy SDK v1 data
- Read via new SDK v2 entity classes and verify no exceptions
- Write new data via SDK v2, read back, and verify round-trip consistency
- Verify TTL field (`expiresOn`) is correctly stored as epoch seconds

---

## 19. Risk & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| SQS Extended Client incompatibility | Large messages fail to send/receive | Test with AWS SDK v2 SQS extended client; verify payload offloading works with `StorageClient` for S3 |
| Spark job AWS client lifecycle | Client creation/disposal in Spark executors | Test cloud-sdk client creation in Spark executor context; verify thread safety |
| `StorageClient` missing operations | S3 paginated listing, batch delete, copy not supported | Use AWS SDK v2 `S3Client` directly for unsupported operations; document gaps for cloud-sdk-api enhancement |
| Generic type parameter on entity classes | `RealTimeCache<T>` / `SchedulesProStaging<T>` may not work with Enhanced Client | Test with generic parameter; remove `<T>` if Enhanced Client requires concrete types |
| DynamoDB Document API in port-pair-generator | Different migration path from DynamoDBMapper entities | Replace raw `PutItemRequest` with `DatabaseRepository.save()` using entity class |
| `AWSClientConfiguration` custom settings | Timeout/retry settings lost in migration | Document current custom settings; configure equivalent in cloud-sdk or SDK v2 client builder |
| JUnit 4 tests in process/common | JUnit 4 → JUnit 5 migration may be needed | Keep JUnit 4 for now (cloud-sdk supports both); migrate to JUnit 5 separately |
| 212 test files to update | Large surface area | Migrate tests alongside production code per phase |
| SSM Parameter Store | cloud-sdk may not have paramstore API | Use AWS SDK v2 `SsmClient` directly |

---

## Appendix A — File Change Matrix

### oceanschedules (API Module)

| File | Change Type | Description |
|---|---|---|
| `pom.xml` | Modify | Add cloud-sdk deps, remove dynamo-client |
| `RealTimeCache.java` | Modify | SDK v2 annotations, remove `DynamoHashKey<String>`, `TimeToLive` |
| `SchedulesProStaging.java` | Modify | SDK v2 annotations, add `@DynamoDbSortKey`, `@DynamoDbSecondaryPartitionKey` |
| `DynamoSupport.java` | **Delete** | Replaced by cloud-sdk `DynamoRepositoryFactory` |
| `OceanschedulesModule.java` | Modify | Remove DynamoDB/SNS/S3 direct bindings, install new modules |
| `OceanSchedulesConfig.java` | Modify | Replace `DynamoDbConfig` with `BaseDynamoDbConfig` |
| `SNSClient.java` (util/sns) | Modify | Use `NotificationService` instead of `AmazonSNS` |
| `S3Service.java` (util/s3) | Modify/Rewrite | Use `StorageClient` instead of `AmazonS3` |
| `AWSUtil.java` | Modify | Update exception types for SDK v2 |
| Config YAML files (4 envs) | Modify | Update `dynamoDbConfig` section |
| New: `DateEpochSecondAttributeConverter.java` | Create | Date ↔ epoch seconds converter |
| New: `OceanSchedulesDynamoModule.java` | Create | DynamoDB Guice module |
| New: `OceanSchedulesMessagingModule.java` | Create | SNS Guice module |
| New: `OceanSchedulesStorageModule.java` | Create | S3 Guice module |
| New: `OceanSchedulesDynamoDbAdminCommand.java` | Create | Table creation CLI command |

### oceanschedules-process/common

| File | Change Type | Description |
|---|---|---|
| `pom.xml` | Modify | Add cloud-sdk deps, remove AWS SDK v1 SQS dep |
| `SQSClient.java` | Rewrite | Use `MessagingClient<String>` |
| `SNSClient.java` | Rewrite | Use `NotificationService` |
| `S3WorkspaceService.java` | Rewrite | Use `StorageClient` |
| `SQSListener.java` | Modify | Use `QueueMessage<String>` |
| `SqsThreadPoolListener.java` | Modify | Use `QueueMessage<String>` |
| `MessageSender.java` | Keep | Interface unchanged |

### oceanschedules-process Sub-Modules (7)

| Sub-Module | Files Changed | Key Changes |
|---|---|---|
| collector | `pom.xml`, `*Module.java` | Install cloud-sdk modules |
| inbound | `pom.xml`, `*Module.java`, task classes | Install cloud-sdk modules, update message types |
| staging | `pom.xml`, `*Module.java`, task classes | Install cloud-sdk modules |
| aggregator | `pom.xml`, `*Module.java`, `DynamoSparkService.java` | Replace direct `AmazonDynamoDB` with cloud-sdk, install modules |
| loader | `pom.xml`, `*Module.java`, `JestModule.java` | Update Jest module import, install cloud-sdk modules |
| outbound | `pom.xml`, `*Module.java`, `SSMParameterStoreClient.java` | Remove 5 direct AWS SDK v1 deps, migrate SSM, install modules |
| port-pair-generator | `pom.xml`, `*Module.java`, `DynamoService.java`, `S3MergeService.java` | Replace raw DynamoDB Document API with `DatabaseRepository`, update S3 |

---

*End of Plan Document*
