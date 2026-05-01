# WebBL Module - Design Document

## Overview

The **WebBL** (Web Bill of Lading) module is a Mercury platform service responsible for processing Bill of Lading (BL) PDF documents, archiving BL data, and distributing outbound notifications to subscribers. It integrates with multiple data stores (DynamoDB, Elasticsearch, Oracle, MySQL) and AWS services (S3, SQS, SNS) to provide a complete BL processing pipeline.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    WebBL Module                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              INBOUND PROCESSING                                   │   │
│  │                                                                                   │   │
│  │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐  │   │
│  │   │  SQS Listener   │    │  SQS Listener   │    │   Database Listeners        │  │   │
│  │   │  (PDF Queue)    │    │  (ZIP Queue)    │    │                             │  │   │
│  │   └────────┬────────┘    └────────┬────────┘    │  ┌─────────────────────┐    │  │   │
│  │            │                      │             │  │ InttraDBListener    │    │  │   │
│  │            v                      v             │  │ (Oracle → Archive)  │    │  │   │
│  │   ┌─────────────────┐    ┌─────────────────┐    │  └─────────────────────┘    │  │   │
│  │   │  WebBLPDF       │    │  WebBLZip       │    │                             │  │   │
│  │   │  InboundTask    │    │  InboundTask    │    │  ┌─────────────────────┐    │  │   │
│  │   └────────┬────────┘    └────────┬────────┘    │  │ NetworkDBListener   │    │  │   │
│  │            │                      │             │  │ (MySQL → Retry)     │    │  │   │
│  │            └──────────┬───────────┘             │  └─────────────────────┘    │  │   │
│  │                       │                         │                             │  │   │
│  └───────────────────────┼─────────────────────────┴─────────────────────────────┘   │
│                          │                                                            │
│  ┌───────────────────────┼──────────────────────────────────────────────────────────┐ │
│  │                       │        CORE SERVICES                                      │ │
│  │                       v                                                           │ │
│  │   ┌───────────────────────────────────────────────────────────────────────────┐  │ │
│  │   │                        ElasticSearchService                                │  │ │
│  │   │           (BL lookup by reference, carrier ID filtering)                   │  │ │
│  │   └───────────────────────────────────────────────────────────────────────────┘  │ │
│  │                       │                                                           │ │
│  │                       v                                                           │ │
│  │   ┌───────────────────────────────────────────────────────────────────────────┐  │ │
│  │   │                              BLDao                                          │  │ │
│  │   │              (DynamoDB CRUD - bill_of_lading table)                         │  │ │
│  │   └───────────────────────────────────────────────────────────────────────────┘  │ │
│  │                       │                                                           │ │
│  │                       v                                                           │ │
│  │   ┌───────────────────────────────────────────────────────────────────────────┐  │ │
│  │   │                         OutboundService                                     │  │ │
│  │   │  (Subscription processing, email notifications, S3 archiving)              │  │ │
│  │   └───────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                   │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              REST API LAYER                                       │   │
│  │                                                                                   │   │
│  │   ┌─────────────────────────────────────────────────────────────────────────┐    │   │
│  │   │  WebBLResource                                                           │    │   │
│  │   │  GET /{carrierId}/{blNumber} → Retrieve Bill of Lading                   │    │   │
│  │   └─────────────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                                   │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    v               v               v
            ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
            │  DynamoDB   │ │ Elasticsearch│ │    Oracle/MySQL │
            │ bill_of_    │ │  (BL Index)  │ │   (Legacy DB)   │
            │   lading    │ │              │ │                 │
            └─────────────┘ └─────────────┘ └─────────────────┘
```

## Module Structure

### Entry Point

| Component | Class | Description |
|-----------|-------|-------------|
| Application | `WebBLApplication` | Dropwizard application entry point, registers all Guice modules and configures lifecycle |

### Configuration

| Component | Class | Description |
|-----------|-------|-------------|
| Configuration | `WebBLConfig` | Main configuration extending `ApplicationConfiguration` |
| Appian Way Config | `AppianWayConfig` | SQS queue URLs, S3 workspace, database connections |
| ES Config | `ESConfiguration` | Elasticsearch connection settings |
| Retry Config | `RetryConfig` | Retry timing configuration for failed processing |

### Guice Modules

| Module | Class | Responsibility |
|--------|-------|----------------|
| Core Injector | `WebBLInjector` | Elasticsearch via `JestModule` (cloud-sdk-aws: `com.inttra.mercury.cloudsdk.aws.module.JestModule`), Auth, SQS listeners (`@Named("zip")`, `@Named("pdf")`) |
| Storage Module | `WebBLStorageModule` | `StorageClient` via `StorageClientFactory.createDefaultS3Client()` (cloud-sdk-aws) |
| Messaging Module | `WebBLMessagingModule` | `MessagingClient<String>` (SQS), `NotificationService` (SNS), `EventPublisher` via cloud-sdk-aws factories |
| DynamoDB Module | `WebBLDynamoModule` | `DynamoDbClientConfig` from `BaseDynamoDbConfig`, `BLDao` via `DynamoRepositoryFactory` (cloud-sdk-aws) |
| Inbound Module | `InboundServiceModule` | PDF and ZIP processor thread pools |
| Outbound Module | `OutboundServiceModule` | Outbound executor service, `OutboundService` binding |
| Email Module | `WebBLEmailModule` | `EmailService` via `EmailClientFactory.createDefaultSesClient()` (cloud-sdk-aws), `@Named("sourceEmail")` from config |
| MySQL MyBatis | `MyCustomBatisModule` | MySQL database mapper for `RetryRequestMapper` |
| Oracle MyBatis | `MyCustomBatisModule` | Oracle database mapper for `WebBLMapper` |

### CLI Commands

| Command | Class | Description |
|---------|-------|-------------|
| `server` | `WebBLApplication` | Start the Dropwizard server |
| `check` | (built-in) | Validate configuration file |
| `dynamo-create` | `CreateTables` | Create/manage DynamoDB tables (`bill_of_lading`) from entity annotations |

**DynamoDB Table Management:**
```bash
java -jar webbl/target/webbl-1.0.jar dynamo-create webbl/conf/int/config.yaml
```

## Data Flow Diagrams

### 1. PDF Inbound Processing Flow

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────────────┐
│  S3 Bucket  │────▶│  PDF SQS Queue  │────▶│  SQSListener ("pdf")    │
│  (PDF File) │     │  (InPDFQueueUrl)│     │                         │
└─────────────┘     └─────────────────┘     └────────────┬────────────┘
                                                         │
                                                         v
                                            ┌─────────────────────────┐
                                            │ WebBLPDFInboundTask     │
                                            │                         │
                                            │ 1. Parse filename       │
                                            │    - Extract SCAC code  │
                                            │    - Extract BL number  │
                                            └────────────┬────────────┘
                                                         │
                         ┌───────────────────────────────┼───────────────────────────────┐
                         │                               │                               │
                         v                               v                               v
              ┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
              │ NetworkParticipant  │      │ ElasticSearchService│      │      BLDao          │
              │ Service             │      │                     │      │                     │
              │ (SCAC → carrierId)  │      │ (BL lookup by ref)  │      │ (Load BL versions)  │
              └─────────────────────┘      └─────────────────────┘      └─────────────────────┘
                                                         │
                                                         v
                                            ┌─────────────────────────┐
                                            │    OutboundService      │
                                            │                         │
                                            │ - Find subscriptions    │
                                            │ - Create ZIP package    │
                                            │ - Send to subscribers   │
                                            │ - Archive to S3         │
                                            └─────────────────────────┘
```

### 2. Archive Processing Flow (InttraDBListener)

```
┌─────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│   Oracle Database   │────▶│   InttraDBListener      │────▶│   WebBLArchiveTask      │
│   (WebBL Feed)      │     │   (Scheduled polling)   │     │                         │
└─────────────────────┘     └─────────────────────────┘     └────────────┬────────────┘
                                                                         │
                                                                         v
                                                            ┌─────────────────────────┐
                                                            │ 1. Claim process reqs   │
                                                            │ 2. Map to BillOfLading  │
                                                            │ 3. Write JSON to S3     │
                                                            │ 4. Update status in DB  │
                                                            └────────────┬────────────┘
                                                                         │
                                                                         v
                                                            ┌─────────────────────────┐
                                                            │   S3 Archive Bucket     │
                                                            │   (JSON format)         │
                                                            └─────────────────────────┘
```

**Concurrent Claim Mechanism (`WebBLDao.claimAndLoadRequests`):**

The archive flow uses a transactional claim-and-update pattern to allow multiple
application instances to process from the same `WEBBL_FEED` table without overlap:

1. **`SELECT ... FOR UPDATE SKIP LOCKED`** — acquires row-level locks on up to 5000
   `SUBMITTED` rows.  Any rows already locked by a concurrent instance are silently
   skipped, guaranteeing zero overlap.
2. **`UPDATE ... SET PROCESSING_STATUS = 'IN_PROCESSING'`** — marks the locked rows
   within the same transaction.
3. **On commit** — the row locks are released and other instances see the new status.

> **Oracle constraint (ORA-02014):** `FOR UPDATE` cannot be combined with `ORDER BY`,
> `FETCH FIRST`, `DISTINCT`, `GROUP BY`, analytic functions, or inline views containing
> any of these.  Therefore the claim query uses a flat `SELECT` with `ROWNUM <= 5000`
> directly in the `WHERE` clause — no subquery, no `ORDER BY`.  Row selection order is
> non-deterministic, but with `SKIP LOCKED` in a concurrent environment strict FIFO was
> already approximate.  All `SUBMITTED` rows are eventually claimed.

### 3. Retry Processing Flow (NetworkDBListener)

```
┌─────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│   MySQL Database    │────▶│   NetworkDBListener     │────▶│ WebBLPDFInboundTask     │
│   (Retry Requests)  │     │   (Scheduled polling)   │     │   .reprocess()          │
└─────────────────────┘     └─────────────────────────┘     └────────────┬────────────┘
                                                                         │
                                                                         v
                                                            ┌─────────────────────────┐
                                                            │ Load MetaData from S3   │
                                                            │ Re-execute PDF process  │
                                                            │ Delete on success       │
                                                            └─────────────────────────┘
```

### 4. Outbound Subscription Processing

```
┌─────────────────────┐
│    BLVersion        │
│    (from DynamoDB)  │
└─────────┬───────────┘
          │
          v
┌─────────────────────────────────────────────────────────────────────┐
│                      OutboundServiceImpl                             │
│                                                                      │
│  1. Get coded parties from BL (consignee, notify, shipper, etc.)    │
│  2. Query subscriptions for each party                               │
│  3. Filter subscriptions by direction (OUTBOUND)                     │
└─────────┬───────────────────────────────────────────────────────────┘
          │
          v
┌─────────────────────────────────────────────────────────────────────┐
│                    For Each Subscription:                            │
│                                                                      │
│  1. Download PDF from S3                                             │
│  2. Generate XML (BlCrossReferenceType)                             │
│  3. Create ZIP (PDF + XML)                                          │
│  4. Upload ZIP to S3                                                │
│  5. Process subscription actions:                                    │
│     - EMAIL → OutboundEmailSender                                   │
│     - FTP/SFTP → Send to configured endpoint                        │
│     - ERROR_EMAIL → Send error notifications                        │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Stores

### DynamoDB

| Table | Description | Partition Key | Sort Key | GSI |
|-------|-------------|---------------|----------|-----|
| `bill_of_lading` | Stores BL versions with message payload | `id` (String) | `sequenceNumber` (auto-generated) | `INTTRA_REFERENCE_NUMBER_INDEX` (blInttraReferenceNumber) |

**BLVersion Model Attributes:**
- `id` - Partition key (BL identifier)
- `sequenceNumber` - Sort key (format: `m_{timestamp}_{state}_{inttraRef}`)
- `blInttraReferenceNumber` - GSI hash key
- `carrierId` - Carrier identifier
- `requestorId` - Requestor identifier
- `shipperId` - Shipper identifier
- `bookingNumber` - Associated booking number
- `blNumber` - Bill of Lading number
- `message` - Full BL JSON payload
- `expiresOn` - TTL attribute (epoch seconds)

### Elasticsearch

| Index | Type | Description |
|-------|------|-------------|
| `_all` | `bl` | Bill of Lading search index |

**Search Attributes:**
- `BillOfLadingNumber` - BL reference number
- `BookingNumber` - Booking reference
- `carrierId` - Carrier identifier
- `lastModifiedDateUtc` - Last modified timestamp

### Oracle Database (MyBatis - WebBLMapper)

| Entity | Description |
|--------|-------------|
| `WebBLProcessRequest` | BL feed records pending archive processing |
| `BlCrossReferenceType` | XML schema type for BL cross-reference data |

**WebBL Feed Query Methods:**

| Method | Purpose | Row Limit | Locking |
|--------|---------|-----------|---------|
| `getWebBLProcessRequests` | Read-only load for retry flow (`NetworkDBListener`) | `FETCH FIRST 5000 ROWS ONLY` | None |
| `selectForClaimWebBLProcessRequests` | Concurrent claim for archive flow (`InttraDBListener`) | `ROWNUM <= 5000` | `FOR UPDATE SKIP LOCKED` |

> The claim query cannot use `ORDER BY` or `FETCH FIRST` because Oracle raises
> **ORA-02014** when `FOR UPDATE` is combined with those clauses (or inline views
> containing them).  See [Archive Processing Flow](#2-archive-processing-flow-inttradblistener)
> for the full claim mechanism.

### MySQL Database (MyBatis - RetryRequestMapper)

| Entity | Description |
|--------|-------------|
| `RetryRequest` | Failed PDF processing requests pending retry |

**RetryRequest Fields:**
- `workspaceFilePath` - S3 path to MetaData JSON
- `retryCount` - Number of retry attempts
- `nextRetryDate` - Scheduled next retry time
- `status` - Processing status

## AWS Components (via cloud-sdk)

All AWS service access is abstracted through `cloud-sdk-api` interfaces with `cloud-sdk-aws` providing the implementations. No direct `com.amazonaws` SDK 1.x imports remain.

### Service Integration Summary

| AWS Service | cloud-sdk Interface | cloud-sdk Factory | Guice Module |
|-------------|---------------------|--------------------|--------------|
| S3 | `StorageClient` | `StorageClientFactory.createDefaultS3Client()` | `WebBLStorageModule` |
| SQS | `MessagingClient<String>` | `MessagingClientFactory.createDefaultStringClient()` | `WebBLMessagingModule` |
| SNS | `NotificationService` | `NotificationClientFactory.createDefaultClient(topicArn)` | `WebBLMessagingModule` |
| DynamoDB | `DatabaseRepository<BLVersion, DefaultCompositeKey<String, String>>` | `DynamoRepositoryFactory.createEnhancedRepository()` | `WebBLDynamoModule` |
| SES | `EmailService` | `EmailClientFactory.createDefaultSesClient(templateFiles)` | `WebBLEmailModule` |

### S3

| Bucket | Purpose |
|--------|---------|
| `appianWayConfig.s3WorkSpaceLocation` | Working storage for MetaData, PDF processing |
| `s3ArchiveBucket` | Long-term archive storage for BL JSON documents |

### SQS

| Queue | Config Key | Purpose |
|-------|------------|---------|
| PDF Queue | `appianWayConfig.inPDFQueueUrl` | Incoming PDF file notifications |
| ZIP Queue | `appianWayConfig.inZIPQueueUrl` | Incoming ZIP file notifications |

**SQS Listener Configuration:**
- `waitTimeSeconds` - Long polling wait time (1-20 seconds)
- `maxNumberOfMessages` - Batch size (max 10)

### SNS

| Topic | Config Key | Purpose |
|-------|------------|---------|
| Event Topic | `snsEventTopicArn` | Event logging and notifications |

### Event Workflow (via cloud-sdk-api)

All event/workflow classes are sourced from `com.inttra.mercury.cloudsdk.notification.workflow.*` (cloud-sdk-api).
No legacy `com.inttra.mercury.messaging.*` (messaging-helper) imports remain.

| Class | Package | Purpose |
|-------|---------|---------|
| `MetaData` | `cloudsdk.notification.workflow` | Workflow context: `messageId`, `workflowId`, `bucket`, `fileName`, `component`, `exitStatus`, `projections` |
| `Event` | `cloudsdk.notification.workflow` | SNS event payload with `SubType` (`START_WORKFLOW`, `CLOSE_WORKFLOW`) |
| `EventLogger` | `cloudsdk.notification.workflow` | Logs close-run events via `EventPublisher` + `EventGenerator` |
| `EventGenerator` | `cloudsdk.notification.workflow` | Generates `Event` objects from `MetaData` with standard tokens |
| `EventPublisher` | `cloudsdk.notification.workflow` | `@FunctionalInterface` — `publishEvent(List<Event>)` — implemented via `SNSClient` lambda in `WebBLMessagingModule` |
| `RandomGenerator` | `cloudsdk.notification.util` | `@Singleton` — UUID, event ID, and random numeric generation |

### DynamoDB

| Table | Partition Key | Sort Key | GSI | TTL |
|-------|--------------|----------|-----|-----|
| `{prefix}_bill_of_lading` | `id` (String) | `sequenceNumber` (String) | `INTTRA_REFERENCE_NUMBER_INDEX` (`blInttraReferenceNumber`) | `expiresOn` (epoch seconds) |

**DynamoDB Annotations (SDK 2.x Enhanced Client):**
- `@DynamoDbBean` - Entity marker and nested document marker
- `@DynamoDbPartitionKey` - Partition key (`id`)
- `@DynamoDbSortKey` - Sort key (`sequenceNumber`)
- `@DynamoDbSecondaryPartitionKey` - GSI partition key (`blInttraReferenceNumber`)
- `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` - Date → epoch seconds conversion (`expiresOn`)
- `@Table(name = "bill_of_lading")` - cloud-sdk table name annotation

## Key Components Detail

### WebBLPDFInboundProcessorTask

**Responsibilities:**
1. Extract BL number and SCAC code from PDF filename (format: `{SCAC}_{BLNumber}.pdf`)
2. Resolve carrier ID from SCAC code via `CacheNetworkParticipantService`
3. Search Elasticsearch for BL by reference and carrier
4. Load BL versions from DynamoDB
5. Select most relevant version (FinalTransmission or latest)
6. Trigger outbound processing

**Error Handling:**
- `BillOfLadingNotFound` - BL not in Elasticsearch
- `BLNumberNotFound` - Cannot parse BL from filename
- `CarrierNotFound` - SCAC code not resolved
- Failed requests → MySQL retry table with exponential backoff

**Retry Schedule (configurable):**
- 1st retry: `firstRetryGapInMinutes`
- 2nd retry: `secondRetryGapInMinutes`
- 3rd retry: `thirdRetryGapInMinutes`
- 4th retry: `fourthRetryGapInMinutes`
- 5th retry: `lastRetryGapInDays`
- Max attempts: 5

### OutboundServiceImpl

**Responsibilities:**
1. Extract coded parties from BL (consignee, notify party, shipper, etc.)
2. Query subscription service for each party
3. Filter subscriptions by direction and BL attributes
4. For each subscription:
   - Download PDF from S3
   - Generate XML cross-reference document
   - Create ZIP package (PDF + XML)
   - Upload ZIP to S3
   - Execute subscription actions (email, FTP, etc.)
5. Archive BL to S3

**Thread Pool:**
- `outbound` executor: 32 threads
- Work queue: 60 capacity
- Shutdown time: 30 seconds

### ElasticSearchService

**Responsibilities:**
1. Search BL by reference (BillOfLadingNumber, BookingNumber)
2. Filter by carrier ID
3. Date range filtering (last 365 days)
4. Return most recently modified match

**Jest Client Usage:**
- Long polling with scroll API
- Result size: 10,000 max
- Source field filtering for efficiency

### WebBLArchiveTask

**Responsibilities:**
1. Process WebBLProcessRequest batches from Oracle
2. Map legacy BL data to `BillOfLading` JSON model
3. Write JSON to S3 archive bucket
4. Update processing status in Oracle

**Processing Flow:**
1. Load BlCrossReferenceType from Oracle
2. Populate control, comments, document, references, parties, equipment, sailing
3. Serialize to JSON
4. Upload to S3 with timestamped key
5. Log events via EventLogger

## Listener Management

### ListenerManager

Manages lifecycle of all listeners:
- PDF SQS Listener
- ZIP SQS Listener
- InttraDBListener (Oracle polling)
- NetworkDBListener (MySQL retry polling)

**Configuration:**
- `appianWayConfig.listenerEnabled` - Master switch for all listeners
- `appianWayConfig.outboundEnabled` - Enable/disable outbound processing

## REST API

### Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/{carrierId}/{blNumber}` | Retrieve BL by carrier and BL number | Required (companyId = 1000 only) |

**Response:**
- 200 OK: Returns `BLContract` JSON
- 403 Forbidden: Non-authorized company
- 404 Not Found: BL not found

## Dependencies

### Maven Dependencies

```xml
<!-- AWS SDK 2.x (via cloud-sdk) -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-api</artifactId>
    <version>1.0.22-SNAPSHOT</version>
</dependency>
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-aws</artifactId>
    <version>1.0.22-SNAPSHOT</version>
</dependency>

<!-- DynamoDB Integration Tests -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>dynamo-integration-test</artifactId>
    <version>1.0.22-SNAPSHOT</version>
    <scope>test</scope>
</dependency>

<!-- Elasticsearch -->
<dependency>
    <groupId>io.searchbox</groupId>
    <artifactId>jest</artifactId>
    <version>6.3.1</version>
</dependency>


```

### Internal Library Dependencies

| Library | Purpose |
|---------|---------|
| `cloud-sdk-api` | AWS service abstractions: `StorageClient`, `MessagingClient`, `NotificationService`, `DatabaseRepository`, `EmailService`, event workflow classes |
| `cloud-sdk-aws` | AWS SDK 2.x implementations: `StorageClientFactory`, `MessagingClientFactory`, `NotificationClientFactory`, `DynamoRepositoryFactory`, `EmailClientFactory`, `JestModule`, `BaseDynamoDbConfig`, `DynamoDbAdminCommand` |
| `dynamo-integration-test` | DynamoDB integration test support: `BaseDynamoDbIT`, `DynamoDbExtension`, `DynamoDbTestConfig` (embedded DynamoDB Local) |
| `mercury-commons` | Core utilities |
| Network Services | Subscription, geography, network participant caching |

## Configuration Reference

### WebBLConfig Properties

| Property | Type | Description |
|----------|------|-------------|
| `dynamoDbConfig` | `BaseDynamoDbConfig` | DynamoDB connection settings (cloud-sdk-aws) |
| `appianWayConfig` | `AppianWayConfig` | SQS/S3/DB settings |
| `blElasticSearchConfig` | `ESConfiguration` | Elasticsearch settings |
| `emailSenderConfig` | `EmailSenderConfig` | Email service settings |
| `snsEventTopicArn` | String | SNS topic for events |
| `retryConfig` | `RetryConfig` | Retry timing settings |
| `s3ArchiveBucket` | String | S3 bucket for archives |

### AppianWayConfig Properties

| Property | Description |
|----------|-------------|
| `inPDFQueueUrl` | SQS URL for PDF queue |
| `inZIPQueueUrl` | SQS URL for ZIP queue |
| `s3WorkSpaceLocation` | S3 bucket for workspace |
| `waitTimeSeconds` | SQS long polling wait |
| `maxNumberOfMessages` | SQS batch size |
| `listenerEnabled` | Enable/disable listeners |
| `outboundEnabled` | Enable/disable outbound |
| `networkDataBase` | MySQL DataSourceFactory |
| `inttraDatabase` | Oracle DataSourceFactory |

## Error Handling Strategy

### PDF Processing Errors

1. **BLNumberNotFound** - Cannot extract BL from filename
   - Log error
   - Save to retry table (if enabled)
   - Send error notification to FTP ID subscriptions

2. **CarrierNotFound** - SCAC code not in network participant
   - Log error
   - Save to retry table
   - Continue processing other messages

3. **BillOfLadingNotFound** - BL not in Elasticsearch
   - Log error
   - Save to retry table with backoff schedule
   - Max 5 retries over configurable time periods

4. **General Exceptions**
   - Log error with stack trace
   - Message acknowledged (deleted from queue)
   - EventLogger logs close workflow event with failure status

### Outbound Processing Errors

1. **Subscription Processing Error**
   - Log error per subscription
   - Continue with remaining subscriptions
   - Archive still attempted

2. **S3 Upload Error**
   - Retry via SDK client exception handling
   - Non-retryable errors throw `UnrecoverableAWSException`

## Monitoring and Logging

### Event Logging

Uses `EventLogger` for workflow tracking:
- `START_WORKFLOW` - Processing begins
- `CLOSE_WORKFLOW` - Processing completes (success/failure)

**Token Metadata:**
- `blNumber` - Bill of Lading number
- `bookingNumber` - Associated booking
- `blId` - DynamoDB ID
- `attemptCount` - Retry attempt number
- `nextRetryDate` - Scheduled retry time

### Metrics

Dropwizard metrics via `@Timed` annotations:
- PDF processing execution time
- Message batch processing time
- API endpoint response times

## Thread Pool Configuration

| Pool | Name | Min Threads | Max Threads | Queue Type | Queue Size |
|------|------|-------------|-------------|------------|------------|
| PDF Processor | `pdfProcessor` | 8 | 8 | SynchronousQueue | 0 |
| ZIP Processor | `zipProcessor` | 8 | 8 | SynchronousQueue | 0 |
| Outbound | `outbound` | 32 | 32 | ArrayBlockingQueue | 60 |

All pools use `CallerRunsPolicy` for rejected executions and 30-second shutdown timeout.
